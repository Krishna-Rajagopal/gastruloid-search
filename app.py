"""
app.py
------
Streamlit web interface for exploring the gastruloid literature database.

Run from the terminal (from the project directory):
    python3 -m streamlit run app.py

Tabs:
  1. Papers          — full corpus with filters
  2. Observations    — AI-extracted GRN phenomenon list
  3. GRN Summary     — edge-ranked signaling network
  4. Culture Conditions — uniform protocol/morphology extraction + manual editing
"""

import os
import pandas as pd
import streamlit as st

try:
    import networkx as nx
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    _GRAPH_AVAILABLE = True
except ImportError:
    _GRAPH_AVAILABLE = False

PAPERS_CSV       = os.path.join("data", "papers.csv")
OBSERVATIONS_CSV = os.path.join("data", "observations.csv")
EXTRACTION_CSV   = os.path.join("data", "extraction_table.csv")
SCRNA_CSV        = os.path.join("data", "scrna_summary.csv")

_CORE_ENTITIES = {
    "Wnt", "Nodal", "BMP", "BMP4", "FGF", "FGF8", "TBXT", "SOX2", "SOX17",
    "E-cadherin", "N-cadherin", "Retinoic acid", "ROCK signaling",
    "YAP1", "OTX2", "CDX2", "TBX6", "TGF-β", "β-catenin/Wnt",
    "ERK", "NOGGIN", "SMAD2/3", "Snail",
}
_ACT_RELS = {"activates", "enhances", "required_for", "rescues", "restores"}
_INH_RELS = {"inhibits", "abolishes", "reduces"}
_DISPUTED_EDGES = {
    ("BMP", "Nodal"): "Not observed by Dias lab (Nodal persists in -BMP gastruloids)",
}

st.set_page_config(
    page_title="Gastruloid Literature Explorer",
    page_icon="🧫",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_papers():
    df = pd.read_csv(PAPERS_CSV)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    for col in ["gene_pathways", "phenotypes", "species", "genes_found", "authors"]:
        df[col] = df[col].fillna("")
    if "dataset" not in df.columns:
        df["dataset"] = "gastruloid"
    return df


@st.cache_data
def load_extraction():
    df = pd.read_csv(EXTRACTION_CSV)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    str_cols = [
        "cell_line", "n_cells_per_aggregate", "chir_uM", "chir_onset_h",
        "chir_offset_h", "base_media", "harvest_timepoints_h",
        "imaging_modalities", "fluorescent_reporters",
        "morphology_quantified", "morphology_metric", "morphology_n",
        "morphology_timepoint_h", "elongation_pct", "shape_distribution_figure",
        "variability_addressed", "key_perturbation", "key_finding",
        "full_text_source", "pmcid", "first_last_authors", "species", "journal",
    ]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].fillna("not reported").astype(str)
    if "manually_edited" not in df.columns:
        df["manually_edited"] = False
    if "manual_note" not in df.columns:
        df["manual_note"] = ""
    if "extraction_reviewed" not in df.columns:
        df["extraction_reviewed"] = False
    else:
        df["extraction_reviewed"] = df["extraction_reviewed"].map(
            lambda x: True if str(x).lower() in ("true", "1", "yes") else False
        )
    return df


@st.cache_data
def load_observations():
    df = pd.read_csv(OBSERVATIONS_CSV)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["needs_full_text"] = df["needs_full_text"].fillna(False).astype(bool)
    df["reviewed"] = df["reviewed"].fillna(False).astype(bool)
    for col in ["entity_a", "relationship", "entity_b_or_context",
                "confidence", "observation_type", "species", "devSim_param",
                "supporting_quote"]:
        df[col] = df[col].fillna("").astype(str)
    if "timepoint_h" not in df.columns:
        df["timepoint_h"] = "not_specified"
    else:
        df["timepoint_h"] = df["timepoint_h"].fillna("not_specified").astype(str)
    if "perturbation_type" not in df.columns:
        df["perturbation_type"] = "none"
    else:
        df["perturbation_type"] = df["perturbation_type"].fillna("none").astype(str)
    return df


def unique_tags(series: pd.Series) -> list:
    tags = set()
    for cell in series.dropna():
        for tag in str(cell).split(";"):
            t = tag.strip()
            if t:
                tags.add(t)
    return sorted(tags)


# ---------------------------------------------------------------------------
# GRN network visualization helpers
# ---------------------------------------------------------------------------

def _blend_color(inh_frac: float) -> str:
    """Interpolate green→red based on fraction of inhibitory papers (0=all-act, 1=all-inh)."""
    # green #2ca02c = (44, 160, 44)   red #d62728 = (214, 39, 40)
    r = int(44  + (214 - 44)  * inh_frac)
    g = int(160 + (39  - 160) * inh_frac)
    b = int(44  + (40  - 44)  * inh_frac)
    return f"#{r:02x}{g:02x}{b:02x}"


def _build_lit_grn(obs_df, species_filter="All", obs_type_filter="All", min_papers=1,
                   timepoint_filter="All", tier="All"):
    """Return (DiGraph, species_coverage_dict) for molecular-to-molecular edges.

    Edge attributes:
      n_act, n_inh, n_other  — unique-paper counts per direction
      papers                  — total unique papers for this (A,B) pair
      color                   — blended green→red based on inh_frac
      label                   — e.g. '3+/2−' when there is conflict
    """
    df = obs_df.copy()
    if species_filter != "All":
        df = df[df["species"] == species_filter]
    if obs_type_filter != "All":
        df = df[df["observation_type"] == obs_type_filter]

    # Tier filter based on perturbation_type
    if tier == "Tier 1 — Genetic":
        if "perturbation_type" in df.columns:
            df = df[df["perturbation_type"].isin(["genetic_KO", "genetic_OE"])]
        else:
            df = df[df["observation_type"] == "perturbation"]
    elif tier == "Tier 2 — All perturbation":
        df = df[df["observation_type"] == "perturbation"]

    # Timepoint filter — parse numeric values for flexible binning
    if timepoint_filter != "All" and "timepoint_h" in df.columns:
        def _tp_h(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        tp_num = df["timepoint_h"].map(_tp_h)
        if timepoint_filter == "≤48h":
            mask = (tp_num <= 48) | df["timepoint_h"].isin(["early"])
            df = df[mask.fillna(False)]
        elif timepoint_filter == "48–72h":
            mask = ((tp_num >= 48) & (tp_num <= 72))
            df = df[mask.fillna(False)]
        elif timepoint_filter == "72–96h":
            mask = ((tp_num >= 72) & (tp_num <= 96))
            df = df[mask.fillna(False)]
        elif timepoint_filter == "≥96h":
            mask = (tp_num >= 96) | df["timepoint_h"].isin(["late"])
            df = df[mask.fillna(False)]
        elif timepoint_filter == "not specified":
            df = df[df["timepoint_h"] == "not_specified"]

    df = df[
        df["entity_a"].isin(_CORE_ENTITIES) &
        df["entity_b_or_context"].isin(_CORE_ENTITIES) &
        (df["entity_a"] != df["entity_b_or_context"])
    ]

    if df.empty:
        return nx.DiGraph() if _GRAPH_AVAILABLE else None, {}

    # Species coverage per node (from full unfiltered obs)
    all_nodes = set(df["entity_a"]) | set(df["entity_b_or_context"])
    sp_cov = {}
    for n in all_nodes:
        spp = set(obs_df[
            (obs_df["entity_a"] == n) | (obs_df["entity_b_or_context"] == n)
        ]["species"].str.lower())
        has_mouse = any("mouse" in s for s in spp)
        has_human = any("human" in s for s in spp)
        sp_cov[n] = "both" if (has_mouse and has_human) else (
            "mouse" if has_mouse else ("human" if has_human else "other"))

    # Accumulate per-direction paper sets for each (src, tgt) pair
    edge_pmids: dict = {}
    for _, row in df.iterrows():
        src, tgt = row["entity_a"], row["entity_b_or_context"]
        rel, pmid = row["relationship"], row["pmid"]
        if (src, tgt) not in edge_pmids:
            edge_pmids[(src, tgt)] = {"act": set(), "inh": set(), "other": set()}
        bucket = "act" if rel in _ACT_RELS else ("inh" if rel in _INH_RELS else "other")
        edge_pmids[(src, tgt)][bucket].add(pmid)

    G = nx.DiGraph()
    for (src, tgt), buckets in edge_pmids.items():
        n_act   = len(buckets["act"])
        n_inh   = len(buckets["inh"])
        n_other = len(buckets["other"])
        total   = len(buckets["act"] | buckets["inh"] | buckets["other"])
        if total < min_papers:
            continue

        n_dir = n_act + n_inh
        if n_dir == 0:
            color = "#7f7f7f"
        else:
            color = _blend_color(n_inh / n_dir)

        # Only label edges where evidence conflicts (both activating and inhibitory papers exist)
        label = f"{n_act}+/{n_inh}−" if (n_act > 0 and n_inh > 0) else ""

        G.add_edge(src, tgt, papers=total, n_act=n_act, n_inh=n_inh,
                   n_other=n_other, color=color, label=label)

    return G, sp_cov


def _plot_lit_grn(G, sp_cov, title="Literature GRN"):
    """Matplotlib figure of the literature-derived molecular GRN.

    Edge color encodes evidence consensus: green (all activating) → amber (mixed) → red (all inhibitory).
    Edge width encodes total unique-paper count.
    Conflict label 'N+/M−' shown when both directions have support.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    if len(G.nodes()) == 0:
        ax.text(0.5, 0.5,
                "No molecular-to-molecular edges found with current filters.\n"
                "Most observations describe phenotypic outcomes, not molecular targets.\n"
                "Try 'All types' or lower the minimum-papers threshold.",
                ha="center", va="center", fontsize=9, color="#777",
                transform=ax.transAxes, wrap=True)
        ax.axis("off")
        ax.set_title(title, fontsize=10, fontweight="bold")
        plt.tight_layout()
        return fig

    pos = nx.spring_layout(G, seed=42, k=2.2, iterations=120)

    # Wrap long node names so they fit inside circles
    _WRAP = {
        "E-cadherin":    "E-cad-\nherin",
        "N-cadherin":    "N-cad-\nherin",
        "Retinoic acid": "Retinoic\nacid",
        "ROCK signaling":"ROCK\nsig.",
        "β-catenin/Wnt": "β-cat/\nWnt",
        "SMAD2/3":       "SMAD\n2/3",
    }
    node_labels = {n: _WRAP.get(n, n) for n in G.nodes()}

    sp_colors = {"mouse": "#4C72B0", "human": "#DD8452", "both": "#55A868", "other": "#9E9E9E"}
    n_colors = [sp_colors.get(sp_cov.get(n, "other"), "#9E9E9E") for n in G.nodes()]
    n_sizes  = [max(700, 280 * (G.in_degree(n) + G.out_degree(n) + 1)) for n in G.nodes()]

    e_colors = [G[u][v]["color"] for u, v in G.edges()]
    e_widths = [0.8 + G[u][v]["papers"] * 0.9 for u, v in G.edges()]

    nx.draw_networkx_nodes(G, pos, node_color=n_colors, node_size=n_sizes, alpha=0.9, ax=ax)
    nx.draw_networkx_labels(G, pos, node_labels, font_size=7, font_weight="bold",
                            font_color="white", ax=ax)
    nx.draw_networkx_edges(G, pos, edge_color=e_colors, width=e_widths,
                           arrows=True, arrowsize=18,
                           connectionstyle="arc3,rad=0.15",
                           ax=ax, alpha=0.85)

    # Highlight disputed edges with dashed overlay
    disputed_present = [(u, v) for u, v in G.edges() if (u, v) in _DISPUTED_EDGES]
    if disputed_present:
        nx.draw_networkx_edges(
            G, pos,
            edgelist=disputed_present,
            edge_color="white",
            style="dashed",
            width=1.5,
            alpha=0.7,
            arrows=False,
            ax=ax,
        )

    # Only label conflict edges (N+/M−); pure-direction edges rely on color + width
    edge_labels = {(u, v): G[u][v]["label"]
                   for u, v in G.edges() if G[u][v].get("label")}
    if edge_labels:
        nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=6, ax=ax, alpha=0.8)

    # Legend — node species colors + gradient description
    node_patches = [
        mpatches.Patch(color="#4C72B0", label="Mouse evidence"),
        mpatches.Patch(color="#DD8452", label="Human evidence"),
        mpatches.Patch(color="#55A868", label="Both species"),
        mpatches.Patch(color="#9E9E9E", label="Species unspecified"),
    ]
    # Edge gradient swatch: green → amber → red
    edge_patches = [
        mpatches.Patch(color="#2ca02c", label="Edge: all activating"),
        mpatches.Patch(color=_blend_color(0.5), label="Edge: mixed (conflict)"),
        mpatches.Patch(color="#d62728", label="Edge: all inhibitory"),
        mpatches.Patch(color="#7f7f7f", label="Edge: other/unclear"),
    ]
    legend_handles = node_patches + edge_patches
    if disputed_present:
        legend_handles.append(
            mpatches.Patch(facecolor="none", edgecolor="white", linestyle="dashed",
                           label="Edge: disputed (expert disagreement)")
        )
    ax.legend(handles=legend_handles, loc="lower left",
              fontsize=6, framealpha=0.85, ncol=2, columnspacing=0.6, handlelength=1.1)
    ax.set_title(title, fontsize=10, fontweight="bold", pad=8)
    ax.axis("off")
    plt.tight_layout()
    return fig


def _plot_devsim_grn():
    """Hardcoded DevSim GRN from Guan et al. 2025, Fig. 5B.

    Force equations (Fig. 5B):
      α_{m,n} = 0.95 - K_α × (1-G1_m)(1-G1_n) × (1-(G2_m+G2_n)/2)
      β_{m,n} = K_β × (1-G1_n) × G2_n
    → Both G1 and G2 modulate both α (short-range) and β (long-range).
    """
    G = nx.DiGraph()
    # Gene-gene interactions (green = activation, red = inhibition)
    # G2/G3 mutual inhibition → bistability (winner-take-all inner/outer sorting)
    edges_spec = [
        ("G1\n(Timer)",       "G2\n(Wnt/Outer)",      "#2ca02c", 2.2, "activates\n(extracellular)"),
        ("G2\n(Wnt/Outer)",   "G3\n(Nodal/Inner)",    "#d62728", 2.2, "inhibits"),
        ("G3\n(Nodal/Inner)", "G2\n(Wnt/Outer)",      "#d62728", 2.2, "inhibits"),
        # Mechanical force outputs — both G1 and G2 modulate both forces (Fig. 5B equations)
        ("G1\n(Timer)",       "Short-range\nforce (α)", "#444444", 1.4, "modulates"),
        ("G2\n(Wnt/Outer)",   "Short-range\nforce (α)", "#444444", 1.8, "modulates"),
        ("G1\n(Timer)",       "Long-range\nforce (β)",  "#444444", 1.4, "suppresses\n(when high)"),
        ("G2\n(Wnt/Outer)",   "Long-range\nforce (β)",  "#444444", 1.8, "drives"),
    ]
    for src, tgt, col, w, lbl in edges_spec:
        G.add_edge(src, tgt, color=col, weight=w, label=lbl)

    pos = {
        "G1\n(Timer)":           ( 0.0,  1.0),
        "G2\n(Wnt/Outer)":       (-0.85, 0.05),
        "G3\n(Nodal/Inner)":     ( 0.85, 0.05),
        "Short-range\nforce (α)":(-1.35,-0.85),
        "Long-range\nforce (β)": ( 0.15,-0.85),
    }
    n_colors_map = {
        "G1\n(Timer)":            "#e6ac00",
        "G2\n(Wnt/Outer)":        "#F3722C",
        "G3\n(Nodal/Inner)":      "#4895EF",
        "Short-range\nforce (α)": "#57BA47",
        "Long-range\nforce (β)":  "#43AA8B",
    }
    fig, ax = plt.subplots(figsize=(6, 5))
    fig.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    nc = [n_colors_map.get(n, "gray") for n in G.nodes()]
    ec = [G[u][v]["color"] for u, v in G.edges()]
    ew = [G[u][v]["weight"] for u, v in G.edges()]

    nx.draw_networkx_nodes(G, pos, node_color=nc, node_size=1600, alpha=0.92, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=7, font_weight="bold", font_color="white", ax=ax)
    nx.draw_networkx_edges(G, pos, edge_color=ec, width=ew,
                           arrows=True, arrowsize=20,
                           connectionstyle="arc3,rad=0.18",
                           ax=ax, alpha=0.9)
    nx.draw_networkx_edge_labels(G, pos, {(u, v): G[u][v]["label"] for u, v in G.edges()},
                                  font_size=5.5, ax=ax, label_pos=0.38, alpha=0.85)

    ax.text(0.02, 0.02,
            "G1 = early Wnt/CHIR timer (degrades over time)\n"
            "G2 = Wnt-high / outer cells  |  G3 = Nodal-high / inner cells\n"
            "G2 ⊣ G3 and G3 ⊣ G2: mutual inhibition → bistable sorting\n"
            "G2 also self-activates (locker circuit, not shown)\n"
            "α = 0.95 − K_α(1−G1)(1−G1)(1−G2)  |  β = K_β(1−G1)·G2",
            transform=ax.transAxes, fontsize=6, color="#444", va="bottom", style="italic",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    ax.set_title("DevSim GRN — Guan et al. 2025 (Fig. 5B)", fontsize=9.5, fontweight="bold", pad=8)
    ax.set_xlim(-1.9, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.axis("off")
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Extraction table session state
# ---------------------------------------------------------------------------
def save_extraction(df: pd.DataFrame):
    """Write to CSV, clear cache, keep updated df in session state."""
    df.to_csv(EXTRACTION_CSV, index=False)
    load_extraction.clear()
    st.session_state["_ext_df"] = df


def get_ext_df() -> pd.DataFrame:
    if "_ext_df" not in st.session_state:
        st.session_state["_ext_df"] = load_extraction().copy()
    return st.session_state["_ext_df"]


def set_ext_df(df: pd.DataFrame):
    st.session_state["_ext_df"] = df


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------
if not os.path.exists(PAPERS_CSV):
    st.error("No data found. Run `python3 run.py` first, then refresh.")
    st.stop()

papers_df     = load_papers()
obs_available = os.path.exists(OBSERVATIONS_CSV)
obs_df        = load_observations() if obs_available else None
ext_available = os.path.exists(EXTRACTION_CSV)

# ---------------------------------------------------------------------------
# Header + tabs
# ---------------------------------------------------------------------------
_GASTRULOID_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 52" width="90" height="46">
  <defs>
    <linearGradient id="ap" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="#2E6DB4"/>
      <stop offset="38%"  stop-color="#5BA85A"/>
      <stop offset="100%" stop-color="#C0392B"/>
    </linearGradient>
    <radialGradient id="gl" cx="30%" cy="35%">
      <stop offset="0%"   stop-color="rgba(255,255,255,0.22)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
  </defs>
  <ellipse cx="45" cy="26" rx="37" ry="21" fill="url(#ap)"/>
  <ellipse cx="80" cy="27" rx="15" ry="12" fill="#C0392B"/>
  <ellipse cx="45" cy="26" rx="37" ry="21" fill="url(#gl)"/>
  <circle cx="20" cy="23" r="6"  fill="none" stroke="rgba(255,255,255,0.38)" stroke-width="1.2"/>
  <circle cx="35" cy="32" r="6"  fill="none" stroke="rgba(255,255,255,0.38)" stroke-width="1.2"/>
  <circle cx="50" cy="19" r="6"  fill="none" stroke="rgba(255,255,255,0.38)" stroke-width="1.2"/>
  <circle cx="63" cy="30" r="6"  fill="none" stroke="rgba(255,255,255,0.33)" stroke-width="1.2"/>
  <circle cx="75" cy="23" r="5"  fill="none" stroke="rgba(255,255,255,0.28)" stroke-width="1.2"/>
  <text x="5"  y="48" font-size="5.5" fill="rgba(255,255,255,0.7)" font-family="sans-serif" font-weight="bold">ANT</text>
  <text x="70" y="48" font-size="5.5" fill="rgba(255,255,255,0.7)" font-family="sans-serif" font-weight="bold">POST</text>
</svg>
"""

_hcol, _tcol = st.columns([1, 9])
with _hcol:
    st.markdown(_GASTRULOID_SVG, unsafe_allow_html=True)
with _tcol:
    st.title("Gastruloid Literature Explorer")
    st.caption("Human & murine gastruloid papers on PubMed, 2014–2025.")

tab_papers, tab_grn, tab_obs, tab_ext, tab_curate, tab_scrna = st.tabs(
    ["Papers", "GRN Summary", "Observations", "Culture Conditions", "Curate", "scRNA"]
)


# ============================================================
# TAB 1 — PAPERS
# ============================================================
with tab_papers:
    df = papers_df
    all_pathways   = unique_tags(df["gene_pathways"])
    all_phenotypes = unique_tags(df["phenotypes"])

    with st.sidebar:
        st.title("Filters (Papers tab)")
        year_min, year_max = int(df["year"].min()), int(df["year"].max())
        year_range = st.slider("Year range", year_min, year_max, (year_min, year_max), key="papers_year_range")
        species_options = ["All", "human", "mouse", "both", "mammalian", "unspecified"]
        selected_species = st.selectbox("Species", species_options, key="papers_species")
        dataset_options = ["All", "gastruloid", "mouse_embryo"]
        selected_dataset = st.selectbox("Dataset", dataset_options, key="papers_dataset")
        selected_pathways = st.multiselect("Gene / signaling pathway (any match)", options=all_pathways, key="papers_pathways")
        selected_phenotypes = st.multiselect("Phenotype / experimental outcome (any match)", options=all_phenotypes, key="papers_phenotypes")
        keyword_search = st.text_input("Free-text search (title & abstract)",
                                       placeholder="e.g. symmetry breaking adhesion",
                                       key="papers_keyword")

    filtered = df.copy()
    filtered = filtered[(filtered["year"] >= year_range[0]) & (filtered["year"] <= year_range[1])]
    if selected_species != "All":
        filtered = filtered[filtered["species"] == selected_species]
    if selected_dataset != "All":
        filtered = filtered[filtered["dataset"] == selected_dataset]
    for pathway in selected_pathways:
        filtered = filtered[filtered["gene_pathways"].str.contains(pathway, case=False, na=False)]
    for phenotype in selected_phenotypes:
        filtered = filtered[filtered["phenotypes"].str.contains(phenotype, case=False, na=False)]
    if keyword_search.strip():
        for term in keyword_search.strip().lower().split():
            mask = (
                filtered["title"].str.lower().str.contains(term, na=False) |
                filtered["abstract"].str.lower().str.contains(term, na=False)
            )
            filtered = filtered[mask]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Papers shown",  len(filtered))
    col2.metric("Total in DB",   len(df))
    col3.metric("Human papers",  len(df[df["species"].isin(["human", "both"])]))
    col4.metric("Mouse papers",  len(df[df["species"].isin(["mouse", "both"])]))

    st.divider()
    st.subheader(f"{len(filtered)} papers match your filters")

    if filtered.empty:
        st.info("No papers match the current filters.")
    else:
        display_cols = ["year", "title", "authors", "journal", "species",
                        "gene_pathways", "phenotypes"]
        st.dataframe(filtered[display_cols].reset_index(drop=True),
                     use_container_width=True, height=400)

        st.subheader("Paper details")
        st.caption("Enter a row number (0-indexed) from the table above.")
        paper_index = st.number_input("Row number", min_value=0,
                                      max_value=max(len(filtered) - 1, 0),
                                      value=0, step=1, key="papers_row")
        row = filtered.iloc[int(paper_index)]
        with st.container(border=True):
            st.markdown(f"### {row['title']}")
            st.markdown(f"**Authors:** {row.get('authors', 'N/A')}")
            st.markdown(f"**Journal:** {row.get('journal', 'N/A')} &nbsp;|&nbsp; **Year:** {row.get('year', 'N/A')}")
            st.markdown(f"**Species:** {row.get('species', 'N/A')}")
            st.markdown(f"**Pathways:** {row.get('gene_pathways', '—')}")
            st.markdown(f"**Phenotypes:** {row.get('phenotypes', '—')}")
            st.markdown(f"**Genes/terms found:** {row.get('genes_found', '—')}")
            if row.get("doi"):
                st.markdown(f"**DOI:** [{row['doi']}](https://doi.org/{row['doi']})")
            st.markdown("**Abstract:**")
            st.markdown(row.get("abstract", "_No abstract available._"))

        st.divider()
        csv_bytes = filtered.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download filtered results as CSV", data=csv_bytes,
                           file_name="gastruloid_filtered.csv", mime="text/csv")

    st.divider()
    st.subheader("Pathway frequency across all papers")
    pathway_counts = {}
    for cell in df["gene_pathways"].dropna():
        for tag in str(cell).split(";"):
            t = tag.strip()
            if t:
                pathway_counts[t] = pathway_counts.get(t, 0) + 1
    if pathway_counts:
        chart_df = pd.DataFrame.from_dict(pathway_counts, orient="index",
                                           columns=["count"]).sort_values("count", ascending=False)
        st.bar_chart(chart_df)

    st.divider()
    with st.expander("Field definitions"):
        st.markdown("""
| Field | Description |
|---|---|
| `year` | Publication year |
| `title` | Full paper title |
| `authors` | Author list (surname, forename) |
| `journal` | Journal of publication |
| `species` | Organism detected from abstract keywords: human / mouse / both / mammalian / unspecified |
| `gene_pathways` | Signaling pathways mentioned: Wnt · Nodal · BMP · FGF · Retinoic acid |
| `phenotypes` | Developmental outcomes: elongation · AP axis · primitive streak · self-organization · inside-outside patterning · variability |
| `genes_found` | Specific gene or compound names detected in title + abstract |
| `doi` | Digital Object Identifier (links to publisher) |
| `pmid` | PubMed unique identifier |
""")


# ============================================================
# TAB 2 — OBSERVATIONS
# ============================================================
with tab_obs:
    if not obs_available:
        st.info("Run `python3 extract.py` first, then refresh.")
    else:
        odf = obs_df.copy()

        with st.expander("Filters", expanded=True):
            fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns(5)
            sel_entity  = fcol1.selectbox("Entity (A)", ["All"] + sorted(odf["entity_a"].dropna().unique()), key="obs_entity")
            sel_rel     = fcol2.selectbox("Relationship", ["All"] + sorted(odf["relationship"].dropna().unique()), key="obs_rel")
            sel_type    = fcol3.selectbox("Obs type",   ["All"] + sorted(odf["observation_type"].dropna().unique()), key="obs_type")
            sel_species = fcol4.selectbox("Species",    ["All"] + sorted(odf["species"].dropna().unique()), key="obs_species")
            sel_conf    = fcol5.selectbox("Confidence", ["All"] + sorted(odf["confidence"].dropna().unique()), key="obs_conf")
            _chk1, _chk2 = st.columns(2)
            needs_ft   = _chk1.checkbox("Needs full text only",    value=False, key="obs_needs_ft")
            unreviewed = _chk2.checkbox("Unreviewed only",         value=False, key="obs_unreviewed")

        filt = odf.copy()
        if sel_entity  != "All": filt = filt[filt["entity_a"] == sel_entity]
        if sel_rel     != "All": filt = filt[filt["relationship"] == sel_rel]
        if sel_type    != "All": filt = filt[filt["observation_type"] == sel_type]
        if sel_species != "All": filt = filt[filt["species"] == sel_species]
        if sel_conf    != "All": filt = filt[filt["confidence"] == sel_conf]
        if needs_ft:   filt = filt[filt["needs_full_text"] == True]
        if unreviewed: filt = filt[filt["reviewed"] == False]

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Observations shown", len(filt))
        mc2.metric("Total extracted",    len(odf))
        mc3.metric("Need full text",     int(odf["needs_full_text"].sum()))
        mc4.metric("Reviewed",           int(odf["reviewed"].sum()))

        st.divider()
        display_obs_cols = ["year", "species", "entity_a", "relationship", "entity_b_or_context",
                            "observation_type", "confidence", "supporting_quote", "devSim_param",
                            "needs_full_text", "pmid"]
        st.dataframe(filt[display_obs_cols].reset_index(drop=True),
                     use_container_width=True, height=450)

        if not filt.empty:
            st.subheader("Observation detail")
            obs_index = st.number_input("Row number", min_value=0,
                                        max_value=max(len(filt) - 1, 0),
                                        value=0, step=1, key="obs_row")
            obs_row = filt.iloc[int(obs_index)]
            with st.container(border=True):
                st.markdown(f"**{obs_row['entity_a']}** `{obs_row['relationship']}` **{obs_row['entity_b_or_context']}**")
                st.markdown(f"Type: `{obs_row['observation_type']}` &nbsp;|&nbsp; Confidence: `{obs_row['confidence']}`")
                st.markdown(f"DevSim param: _{obs_row['devSim_param']}_")
                st.markdown(f"Supporting quote: _{obs_row['supporting_quote']}_")
                st.markdown(f"Needs full text: `{obs_row['needs_full_text']}` &nbsp;|&nbsp; Reviewed: `{obs_row['reviewed']}`")
                st.markdown("---")
                paper_match = papers_df[papers_df["pmid"].astype(str) == str(obs_row["pmid"])]
                if not paper_match.empty:
                    p = paper_match.iloc[0]
                    st.markdown(f"**Paper:** {p['title']}")
                    st.markdown(f"_{p.get('authors','')}_ | {p.get('journal','')} | {p.get('year','')}")
                    if p.get("doi"):
                        st.markdown(f"[DOI link](https://doi.org/{p['doi']})")
                    with st.expander("Abstract"):
                        st.markdown(p.get("abstract", "_No abstract._"))

        st.divider()
        obs_csv = filt.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download filtered observations as CSV", data=obs_csv,
                           file_name="gastruloid_observations_filtered.csv", mime="text/csv")

        st.divider()
        with st.expander("Field definitions"):
            st.markdown("""
| Field | Description |
|---|---|
| `observation_type` | **grn_edge** — regulatory claim (A activates/inhibits B, typically from Discussion) · **spatial_pattern** — where a molecule is high/low · **perturbation** — experimental manipulation (pharmacological inhibitor, genetic KO, or signaling titration) paired with a measured outcome; causal strength depends on design (genetic KO with controls > inhibitor with controls > dose titration without defined baseline) · **expression_timing** — when a gene turns on/off |
| `entity_a` | Acting molecule or experimental manipulation (Wnt, Nodal, BMP, CHIR99021, TBXT, SOX2, …) |
| `relationship` | Direction: activates · inhibits · high_in · low_in · gradient_in · enhances · reduces · abolishes · required_for · correlates_with · anticorrelates_with |
| `entity_b_or_context` | Target molecule, or spatial context: inner cells · outer cells · anterior · posterior · core · peripheral |
| `confidence` | **high** — directly stated · **medium** — implied · **low** — speculative or indirect |
| `supporting_quote` | Verbatim phrase (≤20 words) from the abstract |
| `needs_full_text` | True when quantitative data likely exists in figures but not in the abstract |
| `reviewed` | False by default; set True after manual verification against the original paper |
| `devSim_param` | Mapped DevSim parameter (α/β/GRN); **unmapped** = candidate extension beyond current model |
""")


# ============================================================
# TAB 3 — GRN SUMMARY
# ============================================================
with tab_grn:
    if not obs_available:
        st.info("Run `python3 extract.py` first, then refresh.")
    else:
        odf = obs_df.copy()

        # ── Compact filter row ────────────────────────────────────────────────
        _fc1, _fc2, _fc3, _fc4, _fc5 = st.columns([2, 2, 2, 2, 2])
        grn_species  = _fc1.selectbox("Species",
                                       ["All", "human", "mouse", "both", "mammalian"],
                                       key="grn_species")
        grn_obs_type = _fc2.selectbox("Obs type",
                                       ["All", "perturbation", "grn_edge",
                                        "spatial_pattern", "expression_timing"],
                                       key="grn_obs_type")
        grn_tier = _fc3.selectbox(
            "Evidence tier",
            ["All", "Tier 2 — All perturbation", "Tier 1 — Genetic"],
            key="grn_tier",
        )
        grn_timepoint = _fc4.selectbox(
            "Timepoint",
            ["All", "≤48h", "48–72h", "72–96h", "≥96h", "not specified"],
            key="grn_timepoint",
        )
        net_min_papers = _fc5.slider("Min papers/edge", 1, 4, 1, key="net_min_papers")

        grn_df = odf.copy()
        if grn_species  != "All": grn_df = grn_df[grn_df["species"] == grn_species]
        if grn_obs_type != "All": grn_df = grn_df[grn_df["observation_type"] == grn_obs_type]

        pert_df = odf.copy()
        if grn_species != "All":
            pert_df = pert_df[pert_df["species"] == grn_species]
        pert_df = pert_df[pert_df["observation_type"] == "perturbation"]

        entity_summary = (
            pert_df.groupby("entity_a")
            .agg(
                perturbation_papers=("pmid", "nunique"),
                high_conf_obs=("confidence", lambda x: (x == "high").sum()),
                total_obs=("pmid", "count"),
                devSim_param=("devSim_param", "first"),
            )
            .reset_index()
            .sort_values("perturbation_papers", ascending=False)
            .rename(columns={
                "entity_a": "Entity",
                "perturbation_papers": "Papers (manipulation)",
                "high_conf_obs": "High-conf observations",
                "total_obs": "Total manipulation obs",
                "devSim_param": "DevSim parameter",
            })
        )

        # ── Network visualization (front and centre) ─────────────────────────
        if not _GRAPH_AVAILABLE:
            st.info("Install dependencies to enable: `pip install networkx matplotlib`")
        else:
            G_lit, sp_cov = _build_lit_grn(
                odf,
                species_filter=grn_species,
                obs_type_filter=grn_obs_type,
                min_papers=net_min_papers,
                timepoint_filter=grn_timepoint,
                tier=grn_tier,
            )
            net_col1, net_col2 = st.columns([3, 2], gap="large")
            with net_col1:
                fig_lit = _plot_lit_grn(
                    G_lit, sp_cov,
                    title=f"Literature GRN — {len(G_lit.nodes())} entities, {len(G_lit.edges())} edges",
                )
                st.pyplot(fig_lit, use_container_width=True)
                plt.close(fig_lit)
            with net_col2:
                st.markdown("**DevSim reference circuit**")
                st.caption("Guan et al. 2025, Fig. 5B.")
                fig_dev = _plot_devsim_grn()
                st.pyplot(fig_dev, use_container_width=True)
                plt.close(fig_dev)

            st.caption(
                "**Edge color:** 🟢 all activating · 🔴 all inhibitory · 🟤 amber = conflicting papers "
                "(label N+/M−: N activating, M inhibitory). **Edge width** ∝ paper count. "
                "**Node color:** blue=mouse · orange=human · green=both. "
                "Tier 1 shows only perturbation-type edges; All tiers adds grn_edge, "
                "spatial_pattern, expression_timing."
            )

        st.divider()

        # ── Data tables (collapsed by default) ───────────────────────────────
        with st.expander("Evidence by entity — manipulation paper counts"):
            st.caption(
                "How many independent papers have experimental manipulation evidence per entity. "
                "Genetic KO with controls > pharmacological inhibitor > dose titration."
            )
            st.dataframe(entity_summary, use_container_width=True, height=280)

        edge_cols = ["entity_a", "relationship", "entity_b_or_context"]
        edge_summary = (
            grn_df.groupby(edge_cols)
            .agg(
                papers=("pmid", "nunique"),
                high_conf=("confidence", lambda x: (x == "high").sum()),
                needs_ft=("needs_full_text", "sum"),
                devSim_param=("devSim_param", "first"),
            )
            .reset_index()
            .sort_values("papers", ascending=False)
        )

        with st.expander("Full observation triplets (A · relationship · B)"):
            st.caption(
                "Each row is a unique (A, relationship, B) triplet. Low counts are expected — "
                "each paper uses its own wording. Use the entity table for aggregate claims."
            )
            if edge_summary.empty:
                st.info("No observations match this filter.")
            else:
                st.dataframe(
                    edge_summary.rename(columns={
                        "entity_a": "Entity A", "relationship": "Relationship",
                        "entity_b_or_context": "Entity B / Context",
                        "papers": "# Papers", "high_conf": "High confidence",
                        "needs_ft": "Need full text", "devSim_param": "DevSim parameter",
                    }),
                    use_container_width=True, height=380,
                )
                unmapped = edge_summary[edge_summary["devSim_param"] == "unmapped"]
                if not unmapped.empty:
                    st.markdown("**Unmapped — DevSim extension candidates**")
                    st.dataframe(
                        unmapped[edge_cols + ["papers", "high_conf"]].rename(columns={
                            "entity_a": "Entity A", "relationship": "Relationship",
                            "entity_b_or_context": "Entity B / Context",
                            "papers": "# Papers", "high_conf": "High confidence",
                        }),
                        use_container_width=True,
                    )

        ft_papers = (
            odf[odf["needs_full_text"] == True]
            .groupby(["pmid", "title", "species", "year"])
            .size()
            .reset_index(name="flagged_obs")
            .sort_values("flagged_obs", ascending=False)
        )
        if not ft_papers.empty:
            with st.expander(f"Papers flagged for full-text review ({len(ft_papers)})"):
                st.dataframe(
                    ft_papers.rename(columns={
                        "pmid": "PMID", "title": "Title", "species": "Species",
                        "year": "Year", "flagged_obs": "# Obs needing full text",
                    }),
                    use_container_width=True,
                )

        with st.expander("Protocol diversity for manipulation evidence"):
            st.caption(
                "CHIR concentrations and cell lines across papers supporting each entity. "
                "Evidence spanning diverse protocols is more robust. "
                "⚠️ Descriptive only — culture conditions have not been used for statistical inference."
            )
            if ext_available:
                _ext_ref = get_ext_df()[["pmid", "chir_uM", "cell_line"]].copy()
                _ext_ref["pmid"] = _ext_ref["pmid"].astype(str)
                _pert_ctx = pert_df.copy()
                _pert_ctx["pmid"] = _pert_ctx["pmid"].astype(str)
                _merged = _pert_ctx.merge(_ext_ref, on="pmid", how="left", suffixes=("", "_ext"))
                _ctx_rows = []
                for entity, grp in _merged.groupby("entity_a"):
                    chir_vals = sorted({v for v in grp["chir_uM"].dropna()
                                        if v and str(v) != "not reported"})
                    lines     = sorted({v for v in grp["cell_line"].dropna()
                                        if v and str(v) != "not reported"})
                    spp_vals  = sorted({v for v in grp["species"].dropna() if v})
                    _ctx_rows.append({
                        "Entity":              entity,
                        "Manipulation papers": grp["pmid"].nunique(),
                        "CHIR concentrations": "; ".join(chir_vals[:6]) or "not reported",
                        "Cell lines":          "; ".join(lines[:4]) or "not reported",
                        "Species":             "; ".join(spp_vals[:4]) or "not reported",
                    })
                st.dataframe(
                    pd.DataFrame(_ctx_rows).sort_values("Manipulation papers", ascending=False),
                    use_container_width=True,
                )
            else:
                st.info("Run `python3 extract_uniform.py` first.")

        with st.expander("Data provenance — entity normalization"):
            st.markdown(
                "Entity names canonicalized by `normalize_entities.py`. "
                "Synonyms collapsed — e.g. `WNT`, `Wnt signaling`, `Wnt activation` → `Wnt`. "
                "Original AI values preserved in `entity_a_raw` / `entity_b_raw` columns.  \n"
                "**Paper counts = distinct PMIDs**, not independent replications."
            )

        with st.expander("Field definitions"):
            st.markdown("""
| Field | Description |
|---|---|
| `Entity` / `Entity A` | Canonical signaling molecule or experimental manipulation. Post-hoc normalized from raw AI extraction — see provenance note above. Raw values in `entity_a_raw` column of `data/observations.csv`. |
| `Entity B / Context` | Canonical target molecule or spatial/phenotypic context. Raw value preserved in `entity_b_raw` column of `data/observations.csv`. |
| `Relationship` | Directional verb linking A → B: `activates` · `inhibits` · `high_in` · `low_in` · `gradient_in` · `enhances` · `reduces` · `abolishes` · `required_for` · `correlates_with` · `anticorrelates_with`. Near-synonyms (`drives`, `triggers`, `causes` → `activates`; `impairs` → `inhibits`) were collapsed by normalization. |
| `Papers (manipulation)` | Distinct PMIDs with at least one `perturbation`-type observation for this entity (experimental manipulation → measured outcome). Not a replication count — same lab in two papers = 2. Causal strength varies by design (see Evidence tier caption in GRN Network). |
| `# Papers` (triplet view) | Distinct PMIDs asserting this specific (A, relationship, B) triplet. Typically low (1–2) because each paper describes effects in its own words; use the entity-level table for aggregate claims. |
| `High-conf observations` | Count of observations rated `high` confidence (effect directly stated in abstract, not inferred). |
| `Total manipulation obs` | Total `perturbation`-type observations for this entity across all papers. One paper may contribute multiple observations. |
| `Need full text` | Observations where quantitative data likely exists in figures but was not extractable from the abstract alone. |
| `DevSim parameter` | Mapped DevSim α/β/GRN parameter, or **unmapped** (candidate model extension). Mapping was done at extraction time by the AI; not manually verified. |
| `entity_a_raw` / `entity_b_raw` | Original AI-extracted entity names before normalization. Available in `data/observations.csv`; not shown in this view. Pre-normalization snapshot: `data/observations_prenorm.csv`. |
""")


# ============================================================
# TAB 4 — CULTURE CONDITIONS
# ============================================================
with tab_ext:
    if not ext_available:
        st.info(
            "Uniform extraction not yet run.  \n"
            "1. `python3 fetch_fulltext.py`  \n"
            "2. `python3 extract_uniform.py`  \n"
            "Then refresh this page."
        )
        st.stop()

    edf = get_ext_df()

    # ── Metrics ──────────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total papers",           len(edf))
    m2.metric("PMC full text",          int((edf["full_text_source"] == "PMC").sum()))
    m3.metric("Morphology quantified",  int((edf["morphology_quantified"] == "Y").sum()))
    m4.metric("Shape distribution fig", int((edf["shape_distribution_figure"] == "Y").sum()))
    m5.metric("Manually edited",        int(edf["manually_edited"].sum()))

    st.divider()

    # ── Filters ──────────────────────────────────────────────────────────────
    st.subheader("Filters")
    fc1, fc2, fc3, fc4 = st.columns(4)
    sel_species  = fc1.selectbox("Species",               ["All"] + sorted(edf["species"].dropna().unique()), key="ext_species")
    sel_source   = fc2.selectbox("Full text source",      ["All", "PMC", "abstract only"], key="ext_source")
    sel_morph    = fc3.selectbox("Morphology quantified", ["All", "Y", "N", "unclear"],    key="ext_morph")
    sel_var      = fc4.selectbox("Variability addressed", ["All", "Y", "N"],               key="ext_var")
    show_distrib  = st.checkbox("Shape distribution figure = Y only", value=False, key="ext_show_distrib")
    show_edited   = st.checkbox("Show manually edited rows only",      value=False, key="ext_show_edited")
    show_reviewed = st.checkbox("Show reviewed rows only",             value=False, key="ext_show_reviewed")

    filt = edf.copy()
    if sel_species != "All":  filt = filt[filt["species"] == sel_species]
    if sel_source  != "All":  filt = filt[filt["full_text_source"] == sel_source]
    if sel_morph   != "All":  filt = filt[filt["morphology_quantified"] == sel_morph]
    if sel_var     != "All":  filt = filt[filt["variability_addressed"] == sel_var]
    if show_distrib:   filt = filt[filt["shape_distribution_figure"] == "Y"]
    if show_edited:    filt = filt[filt["manually_edited"] == True]
    if show_reviewed:  filt = filt[filt["extraction_reviewed"] == True]

    st.caption(f"{len(filt)} papers match current filters.")

    view_cols = [
        "year", "first_last_authors", "journal", "species",
        "cell_line", "n_cells_per_aggregate", "chir_uM", "chir_onset_h",
        "chir_offset_h", "base_media", "harvest_timepoints_h",
        "imaging_modalities", "morphology_quantified", "morphology_metric",
        "morphology_n", "elongation_pct", "shape_distribution_figure",
        "variability_addressed", "full_text_source", "extraction_reviewed",
        "manually_edited",
    ]
    view_cols = [c for c in view_cols if c in filt.columns]
    st.dataframe(filt[view_cols].reset_index(drop=True),
                 use_container_width=True, height=400)

    st.divider()

    # ── Edit row ─────────────────────────────────────────────────────────────
    st.subheader("Edit a row")
    st.caption(
        "Select a row by its 0-indexed position in the filtered table above. "
        "Changes are written immediately to `data/extraction_table.csv`. "
        "Identification columns (PMID, title, provenance) are read-only."
    )

    if not filt.empty:
        edit_idx = st.number_input(
            "Row to edit (0-indexed from filtered table above)",
            min_value=0, max_value=max(len(filt) - 1, 0),
            value=0, step=1, key="edit_idx"
        )
        target_row  = filt.iloc[int(edit_idx)]
        target_pmid = str(target_row["pmid"])

        st.markdown(
            f"**Editing:** {target_row.get('title', '—')}  \n"
            f"PMID: `{target_pmid}` | Source: `{target_row.get('full_text_source','—')}`"
        )

        with st.form("edit_row_form", clear_on_submit=False):
            st.markdown("**Protocol**")
            c1, c2, c3 = st.columns(3)
            f_cell_line  = c1.text_input("cell_line",             value=str(target_row.get("cell_line", "")))
            f_n_cells    = c2.text_input("n_cells_per_aggregate", value=str(target_row.get("n_cells_per_aggregate", "")))
            f_base_media = c3.text_input("base_media",            value=str(target_row.get("base_media", "")))

            c4, c5, c6, c7 = st.columns(4)
            f_chir_uM    = c4.text_input("chir_uM",             value=str(target_row.get("chir_uM", "")))
            f_chir_onset = c5.text_input("chir_onset_h",        value=str(target_row.get("chir_onset_h", "")))
            f_chir_offset= c6.text_input("chir_offset_h",       value=str(target_row.get("chir_offset_h", "")))
            f_timepoints = c7.text_input("harvest_timepoints_h",value=str(target_row.get("harvest_timepoints_h", "")))

            st.markdown("**Imaging**")
            ci1, ci2 = st.columns(2)
            f_modalities = ci1.text_input("imaging_modalities",   value=str(target_row.get("imaging_modalities", "")))
            f_reporters  = ci2.text_input("fluorescent_reporters",value=str(target_row.get("fluorescent_reporters", "")))

            st.markdown("**Morphology / variability**")
            cm1, cm2, cm3 = st.columns(3)

            _mq_opts = ["Y", "N", "unclear", "not reported"]
            _mq_val  = str(target_row.get("morphology_quantified", "not reported"))
            f_morph_q = cm1.selectbox("morphology_quantified", _mq_opts,
                                       index=_mq_opts.index(_mq_val) if _mq_val in _mq_opts else 3)
            f_morph_metric = cm2.text_input("morphology_metric", value=str(target_row.get("morphology_metric", "")))
            f_morph_n      = cm3.text_input("morphology_n",      value=str(target_row.get("morphology_n", "")))

            cm4, cm5, cm6, cm7 = st.columns(4)
            f_morph_tp  = cm4.text_input("morphology_timepoint_h", value=str(target_row.get("morphology_timepoint_h", "")))
            f_elong_pct = cm5.text_input("elongation_pct",         value=str(target_row.get("elongation_pct", "")))

            _sd_opts = ["Y", "N", "unclear", "not reported"]
            _sd_val  = str(target_row.get("shape_distribution_figure", "not reported"))
            f_distrib = cm6.selectbox("shape_distribution_figure", _sd_opts,
                                       index=_sd_opts.index(_sd_val) if _sd_val in _sd_opts else 3)

            _va_opts = ["Y", "N", "not reported"]
            _va_val  = str(target_row.get("variability_addressed", "not reported"))
            f_var = cm7.selectbox("variability_addressed", _va_opts,
                                   index=_va_opts.index(_va_val) if _va_val in _va_opts else 2)

            st.markdown("**Mechanistic**")
            f_perturbation = st.text_input("key_perturbation", value=str(target_row.get("key_perturbation", "")))
            f_finding      = st.text_area("key_finding",       value=str(target_row.get("key_finding", "")), height=80)

            st.markdown("**Review status**")
            cr1, cr2 = st.columns(2)
            f_reviewed = cr1.checkbox("Mark as reviewed (extraction_reviewed)",
                                       value=bool(target_row.get("extraction_reviewed", False)),
                                       key="form_reviewed")
            f_note = cr2.text_input("manual_note (source / figure reference)",
                                     value=str(target_row.get("manual_note", "")))

            submitted = st.form_submit_button("💾 Save changes to this row")

        if submitted:
            working_df = get_ext_df()
            mask = working_df["pmid"].astype(str) == target_pmid
            if mask.sum() == 0:
                st.error(f"PMID {target_pmid} not found in extraction table.")
            else:
                working_df.loc[mask, "cell_line"]                = f_cell_line
                working_df.loc[mask, "n_cells_per_aggregate"]    = f_n_cells
                working_df.loc[mask, "base_media"]               = f_base_media
                working_df.loc[mask, "chir_uM"]                  = f_chir_uM
                working_df.loc[mask, "chir_onset_h"]             = f_chir_onset
                working_df.loc[mask, "chir_offset_h"]            = f_chir_offset
                working_df.loc[mask, "harvest_timepoints_h"]     = f_timepoints
                working_df.loc[mask, "imaging_modalities"]       = f_modalities
                working_df.loc[mask, "fluorescent_reporters"]    = f_reporters
                working_df.loc[mask, "morphology_quantified"]    = f_morph_q
                working_df.loc[mask, "morphology_metric"]        = f_morph_metric
                working_df.loc[mask, "morphology_n"]             = f_morph_n
                working_df.loc[mask, "morphology_timepoint_h"]   = f_morph_tp
                working_df.loc[mask, "elongation_pct"]           = f_elong_pct
                working_df.loc[mask, "shape_distribution_figure"]= f_distrib
                working_df.loc[mask, "variability_addressed"]    = f_var
                working_df.loc[mask, "key_perturbation"]         = f_perturbation
                working_df.loc[mask, "key_finding"]              = f_finding
                working_df.loc[mask, "extraction_reviewed"]      = f_reviewed
                working_df.loc[mask, "manual_note"]              = f_note
                working_df.loc[mask, "manually_edited"]          = True
                set_ext_df(working_df)
                save_extraction(working_df)
                st.success(
                    f"Saved — PMID {target_pmid}."
                    + (" Marked as reviewed." if f_reviewed else "")
                )
                # No st.rerun() — form submission already triggers a rerun

    st.divider()

    # ── Detail view ──────────────────────────────────────────────────────────
    st.subheader("Row detail view")
    if not filt.empty:
        det_idx = st.number_input("Row (0-indexed)", min_value=0,
                                   max_value=max(len(filt) - 1, 0),
                                   value=0, step=1, key="ext_det_row")
        er = filt.iloc[int(det_idx)]
        with st.container(border=True):
            st.markdown(f"### {er.get('title', '—')}")
            st.markdown(
                f"**Authors:** {er.get('first_last_authors','—')} | "
                f"**Journal:** {er.get('journal','—')} | "
                f"**Year:** {er.get('year','—')} | "
                f"**Species:** {er.get('species','—')}"
            )
            st.markdown("---")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Protocol**")
                st.markdown(f"Cell line: `{er.get('cell_line','—')}`")
                st.markdown(f"Cells/aggregate: `{er.get('n_cells_per_aggregate','—')}`")
                st.markdown(f"CHIR: `{er.get('chir_uM','—')} µM` | onset `{er.get('chir_onset_h','—')} h` | offset `{er.get('chir_offset_h','—')} h`")
                st.markdown(f"Base media: `{er.get('base_media','—')}`")
                st.markdown(f"Harvest: `{er.get('harvest_timepoints_h','—')} h`")
            with col_b:
                st.markdown("**Morphology / variability**")
                st.markdown(f"Quantified: `{er.get('morphology_quantified','—')}` | Metric: `{er.get('morphology_metric','—')}`")
                st.markdown(f"N: `{er.get('morphology_n','—')}` | Time point: `{er.get('morphology_timepoint_h','—')} h`")
                st.markdown(f"% elongated: `{er.get('elongation_pct','—')}` | Distribution fig: `{er.get('shape_distribution_figure','—')}`")
                st.markdown(f"Variability addressed: `{er.get('variability_addressed','—')}`")
            st.markdown("---")
            st.markdown(f"**Imaging:** {er.get('imaging_modalities','—')} | **Reporters:** {er.get('fluorescent_reporters','—')}")
            st.markdown(f"**Key perturbation:** {er.get('key_perturbation','—')}")
            st.markdown(f"**Key finding:** _{er.get('key_finding','—')}_")
            st.markdown(
                f"**Source:** {er.get('full_text_source','—')} | PMCID: {er.get('pmcid','—')} | "
                f"Reviewed: `{er.get('extraction_reviewed','—')}` | "
                f"Manually edited: `{er.get('manually_edited','—')}` | "
                f"Note: _{er.get('manual_note','—')}_"
            )
            paper_match = papers_df[papers_df["pmid"].astype(str) == str(er.get("pmid",""))]
            if not paper_match.empty:
                with st.expander("Abstract"):
                    st.markdown(paper_match.iloc[0].get("abstract", "_No abstract._"))

    st.divider()

    # ── QC sample ────────────────────────────────────────────────────────────
    with st.expander("QC random sample (15 papers, seed=42)"):
        st.caption(
            "Verify these rows against their source papers. "
            "Target ≥80% correct on Protocol + key_finding. "
            "Use Edit Row above to correct errors and set extraction_reviewed=True."
        )
        qc_cols = ["pmid", "title", "species", "full_text_source",
                   "cell_line", "chir_uM", "morphology_quantified",
                   "morphology_metric", "extraction_reviewed", "manually_edited"]
        qc_cols = [c for c in qc_cols if c in edf.columns]
        st.dataframe(edf.sample(15, random_state=42)[qc_cols].reset_index(drop=True),
                     use_container_width=True)

    st.divider()
    dl_csv = filt.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download filtered extraction table as CSV",
                        data=dl_csv, file_name="gastruloid_extraction_filtered.csv",
                        mime="text/csv")

    st.divider()
    with st.expander("Field definitions"):
        st.markdown("""
| Field | Description |
|---|---|
| `cell_line` | Specific ESC/iPSC line (e.g. v6.5, E14, H9, RUES2); 'mESC unspecified' or 'hESC unspecified' if not named |
| `n_cells_per_aggregate` | Number of cells seeded per well/aggregate at start of protocol |
| `chir_uM` | Concentration of CHIR99021 (GSK3β inhibitor / Wnt activator) in µM |
| `chir_onset_h` | Hours post-aggregation when CHIR99021 was added |
| `chir_offset_h` | Hours post-aggregation when CHIR99021 was removed; 'continuous' if maintained throughout |
| `base_media` | Base culture medium (e.g. N2B27 for mouse ESC; mTeSR1 for human ESC) |
| `harvest_timepoints_h` | Hours post-aggregation at which gastruloids were imaged or collected |
| `imaging_modalities` | Methods used: brightfield · widefield-fluorescence · confocal · light-sheet · live-imaging |
| `fluorescent_reporters` | Reporter lines or antibody targets (e.g. TBXT-GFP, SOX2-mCherry); 'none' if brightfield only |
| `morphology_quantified` | Y — a shape metric was numerically reported · N — no quantification · unclear |
| `morphology_metric` | Shape descriptor used (e.g. aspect ratio, elongation ratio, % elongated, circularity) |
| `morphology_n` | Number of individual gastruloids measured |
| `morphology_timepoint_h` | Hour at which morphology was measured |
| `elongation_pct` | Percentage described as elongated or polarized, if explicitly stated |
| `shape_distribution_figure` | Y — histogram/violin/scatter of shape data appears in a figure · N · unclear |
| `variability_addressed` | Y — paper explicitly discusses batch variability, stochasticity, or reproducibility · N |
| `key_perturbation` | Main experimental manipulation (e.g. CHIR dose titration, SB431542 Nodal inhibition, none) |
| `key_finding` | One-sentence central conclusion |
| `full_text_source` | PMC — Methods/Results/Discussion text fetched · abstract only — only abstract available |
| `pmcid` | PubMed Central ID; empty if not in PMC open-access archive |
| `extraction_reviewed` | Set True after manual verification against the original paper |
| `manually_edited` | Auto-set True when any field is edited via the Edit Row form |
| `manual_note` | Free-text provenance note (e.g. 'CHIR 3µM stated in Methods p. 2') |
""")


# ============================================================
# TAB 5 — CURATE
# ============================================================
with tab_curate:
    st.header("Curate Observations")
    st.caption(
        "Review and correct AI-extracted observations, add manual observations from papers "
        "the AI could not fully process, and verify key edges before presentation. "
        "Changes are saved directly to `data/observations.csv`."
    )

    odf_cur = load_observations()

    # ── Section 1: Review existing observations for a paper ─────────────────
    st.subheader("Review / edit observations for a paper")

    # Build paper list: show title for known papers
    papers_df_c = pd.read_csv(PAPERS_CSV)
    pmid_to_title = dict(zip(papers_df_c["pmid"].astype(str),
                              papers_df_c["title"].str[:70]))
    obs_pmids = sorted(odf_cur["pmid"].unique(), reverse=True)
    pmid_labels = {p: f"{p} — {pmid_to_title.get(str(p), '(unknown)')}" for p in obs_pmids}

    sel_pmid = st.selectbox(
        "Select paper",
        options=obs_pmids,
        format_func=lambda p: pmid_labels.get(p, str(p)),
        key="curate_sel_pmid",
    )

    if sel_pmid:
        paper_obs = odf_cur[odf_cur["pmid"] == sel_pmid].reset_index(drop=True)

        st.caption(
            f"**{len(paper_obs)} observations** — "
            f"source: {paper_obs['source'].value_counts().to_dict() if 'source' in paper_obs.columns else 'unknown'}  |  "
            f"verified: {int(paper_obs['reviewed'].sum())} / {len(paper_obs)}"
        )

        _edit_cols = [
            "observation_type", "entity_a", "relationship", "entity_b_or_context",
            "confidence", "supporting_quote", "reviewed", "source",
        ]
        _edit_cols = [c for c in _edit_cols if c in paper_obs.columns]

        edited = st.data_editor(
            paper_obs[_edit_cols],
            key=f"curate_editor_{sel_pmid}",
            num_rows="dynamic",
            column_config={
                "observation_type": st.column_config.SelectboxColumn(
                    "Type", options=["perturbation", "grn_edge", "spatial_pattern", "expression_timing"], width="medium"),
                "relationship": st.column_config.SelectboxColumn(
                    "Relationship",
                    options=["activates", "inhibits", "high_in", "low_in", "gradient_in",
                             "enhances", "reduces", "abolishes", "required_for",
                             "correlates_with", "anticorrelates_with", "modulates"],
                    width="medium"),
                "confidence": st.column_config.SelectboxColumn(
                    "Confidence", options=["high", "medium", "low"], width="small"),
                "reviewed": st.column_config.CheckboxColumn("Verified", width="small"),
                "source": st.column_config.SelectboxColumn(
                    "Source", options=["abstract", "fulltext", "manual"], width="small"),
                "entity_a": st.column_config.TextColumn("Entity A", width="medium"),
                "entity_b_or_context": st.column_config.TextColumn("Entity B / Context", width="medium"),
                "supporting_quote": st.column_config.TextColumn("Quote", width="large"),
            },
            use_container_width=True,
        )

        save_col, msg_col = st.columns([1, 3])
        if save_col.button("💾 Save changes", key="curate_save_btn"):
            full_obs = pd.read_csv(OBSERVATIONS_CSV)
            # Drop old rows for this paper and replace with edited rows
            full_obs = full_obs[full_obs["pmid"] != sel_pmid]
            # Re-attach non-edited columns from original
            kept_orig = paper_obs.drop(columns=[c for c in _edit_cols if c in paper_obs.columns])
            merged_back = edited.copy()
            for col in kept_orig.columns:
                if col not in merged_back.columns:
                    merged_back[col] = kept_orig[col].values[:len(merged_back)]
            merged_back["pmid"] = sel_pmid
            if "year" not in merged_back.columns:
                yr = papers_df_c.loc[papers_df_c["pmid"] == sel_pmid, "year"]
                merged_back["year"] = yr.iloc[0] if len(yr) else None
            full_obs = pd.concat([full_obs, merged_back], ignore_index=True)
            full_obs.to_csv(OBSERVATIONS_CSV, index=False)
            load_observations.clear()
            msg_col.success(f"Saved {len(merged_back)} observations for PMID {sel_pmid}")

    st.divider()

    # ── Section 2: Add a new observation ────────────────────────────────────
    st.subheader("Add new observation")

    with st.form("curate_add_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 2])
        new_entity_a = c1.text_input("Entity A", placeholder="e.g. Nodal")
        new_rel = c2.selectbox("Relationship",
            ["inhibits", "activates", "required_for", "reduces", "enhances",
             "abolishes", "high_in", "low_in", "gradient_in", "correlates_with",
             "anticorrelates_with", "modulates"])
        new_entity_b = c3.text_input("Entity B / Context", placeholder="e.g. Wnt  or  posterior")

        c4, c5, c6 = st.columns([2, 2, 2])
        new_obs_type = c4.selectbox("Observation type",
            ["perturbation", "grn_edge", "spatial_pattern", "expression_timing"])
        new_conf = c5.selectbox("Confidence", ["high", "medium", "low"])
        new_source = c6.selectbox("Source", ["manual", "abstract", "fulltext"])

        new_quote = st.text_input("Supporting quote (verbatim ≤20 words from paper)",
                                  placeholder="e.g. Nodal signalling inversely affects Wnt activity")

        all_pmids = sorted(papers_df_c["pmid"].tolist(), reverse=True)
        new_pmid = st.selectbox("Paper (PMID)",
                                options=all_pmids,
                                format_func=lambda p: pmid_labels.get(p, str(p)),
                                key="curate_add_pmid")

        submitted = st.form_submit_button("Add observation")
        if submitted:
            if not new_entity_a.strip() or not new_entity_b.strip():
                st.error("Entity A and Entity B are required.")
            else:
                paper_row = papers_df_c[papers_df_c["pmid"] == new_pmid]
                new_row = {
                    "pmid": new_pmid,
                    "year": paper_row["year"].iloc[0] if len(paper_row) else None,
                    "title": paper_row["title"].iloc[0] if len(paper_row) else "",
                    "species": paper_row["species"].iloc[0] if len(paper_row) else "",
                    "observation_type": new_obs_type,
                    "entity_a": new_entity_a.strip(),
                    "relationship": new_rel,
                    "entity_b_or_context": new_entity_b.strip(),
                    "confidence": new_conf,
                    "supporting_quote": new_quote.strip(),
                    "needs_full_text": False,
                    "reviewed": True,
                    "devSim_param": "unmapped",
                    "entity_a_raw": new_entity_a.strip(),
                    "entity_b_raw": new_entity_b.strip(),
                    "source": new_source,
                }
                full_obs = pd.read_csv(OBSERVATIONS_CSV)
                full_obs = pd.concat([full_obs, pd.DataFrame([new_row])], ignore_index=True)
                full_obs.to_csv(OBSERVATIONS_CSV, index=False)
                load_observations.clear()
                st.success(
                    f"Added: **{new_entity_a.strip()} {new_rel} {new_entity_b.strip()}** "
                    f"({new_obs_type}, {new_conf}) from PMID {new_pmid}"
                )

    st.divider()

    # ── Section 3: Unverified AI observations ────────────────────────────────
    with st.expander("All unverified AI observations (reviewed=False)"):
        unverified = odf_cur[odf_cur["reviewed"] == False]
        st.caption(
            f"{len(unverified)} observations have not been manually verified. "
            "Use the paper selector above to review them in context."
        )
        st.dataframe(
            unverified[["pmid", "observation_type", "entity_a", "relationship",
                         "entity_b_or_context", "confidence", "source"]].sort_values("pmid"),
            use_container_width=True,
            height=400,
        )


# ============================================================
# TAB 6 — scRNA VERIFICATION
# ============================================================
with tab_scrna:
    st.header("scRNA Verification")
    st.caption(
        "Gene expression across developmental timepoints from single-cell RNA-seq. "
        "When loaded, use this to cross-validate GRN edges inferred from the literature."
    )

    if not os.path.exists(SCRNA_CSV):
        st.info(
            "No scRNA data loaded yet. Place a gene × timepoint expression matrix at "
            f"`{SCRNA_CSV}` to enable this tab.\n\n"
            "Expected format: CSV with a `gene` column and one column per timepoint "
            "(e.g. `48h`, `72h`, `96h`, `120h`). Values should be normalised expression "
            "(log-normalised counts or z-scores)."
        )
    else:
        scrna_df = pd.read_csv(SCRNA_CSV, index_col="gene")

        # Filter to GRN genes present in the data
        grn_genes = [g for g in sorted(_CORE_ENTITIES) if g in scrna_df.index]
        other_genes = [g for g in scrna_df.index if g not in _CORE_ENTITIES]

        gene_options = grn_genes + other_genes
        selected_genes = st.multiselect(
            "Genes to display",
            options=gene_options,
            default=grn_genes[:15] if len(grn_genes) >= 15 else grn_genes,
        )

        if selected_genes and _GRAPH_AVAILABLE:
            import numpy as np
            fig, ax = plt.subplots(figsize=(max(6, len(scrna_df.columns) * 1.2),
                                            max(4, len(selected_genes) * 0.35)))
            data = scrna_df.loc[selected_genes]
            # z-score rows for display
            row_mean = data.mean(axis=1)
            row_std  = data.std(axis=1).replace(0, 1)
            data_z   = data.sub(row_mean, axis=0).div(row_std, axis=0)

            im = ax.imshow(data_z.values, aspect="auto", cmap="RdBu_r", vmin=-2, vmax=2)
            ax.set_xticks(range(len(data_z.columns)))
            ax.set_xticklabels(data_z.columns, fontsize=8)
            ax.set_yticks(range(len(selected_genes)))
            ax.set_yticklabels(selected_genes, fontsize=7)
            plt.colorbar(im, ax=ax, label="z-score", shrink=0.6)
            ax.set_title("GRN gene expression by timepoint (z-scored)", fontsize=10)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

            with st.expander("Raw expression table"):
                st.dataframe(scrna_df.loc[selected_genes], use_container_width=True)
        elif not _GRAPH_AVAILABLE:
            st.warning("Install matplotlib to enable heatmap: `pip install matplotlib`")
