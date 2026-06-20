"""
app.py
------
Streamlit web interface for exploring the gastruloid literature database.

Run from the terminal (from the project directory):
    python3 -m streamlit run app.py

Opens automatically in your browser at http://localhost:8501

The CSV must already exist (run `python3 run.py` first).
For the Observations and GRN Summary tabs, also run `python3 extract.py`.
"""

import os
import pandas as pd
import streamlit as st

PAPERS_CSV       = os.path.join("data", "papers.csv")
OBSERVATIONS_CSV = os.path.join("data", "observations.csv")

st.set_page_config(
    page_title="Gastruloid Literature Explorer",
    page_icon="🧬",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
@st.cache_data
def load_papers():
    df = pd.read_csv(PAPERS_CSV)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    for col in ["gene_pathways", "phenotypes", "species", "genes_found", "authors"]:
        df[col] = df[col].fillna("")
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
    return df


def unique_tags(series: pd.Series) -> list[str]:
    tags = set()
    for cell in series.dropna():
        for tag in str(cell).split(";"):
            t = tag.strip()
            if t:
                tags.add(t)
    return sorted(tags)


# ---------------------------------------------------------------------------
# Guard: papers.csv must exist
# ---------------------------------------------------------------------------
if not os.path.exists(PAPERS_CSV):
    st.error(
        "No data file found. Please run `python3 run.py` in the terminal first, "
        "then refresh this page."
    )
    st.stop()

papers_df = load_papers()
obs_available = os.path.exists(OBSERVATIONS_CSV)
obs_df = load_observations() if obs_available else None

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("🧬 Gastruloid Literature Explorer")
st.caption("Human & murine gastruloid papers on PubMed, 2015–2025.")

# ---------------------------------------------------------------------------
# Three tabs
# ---------------------------------------------------------------------------
tab_papers, tab_obs, tab_grn = st.tabs(["Papers", "Observations", "GRN Summary"])


# ============================================================
# TAB 1 — PAPERS (original view, unchanged)
# ============================================================
with tab_papers:
    df = papers_df
    all_pathways   = unique_tags(df["gene_pathways"])
    all_phenotypes = unique_tags(df["phenotypes"])

    # Sidebar filters
    with st.sidebar:
        st.title("Filters (Papers tab)")

        year_min, year_max = int(df["year"].min()), int(df["year"].max())
        year_range = st.slider("Year range", year_min, year_max, (year_min, year_max))

        species_options = ["All", "human", "mouse", "both", "mammalian", "unspecified"]
        selected_species = st.selectbox("Species", species_options)

        selected_pathways = st.multiselect(
            "Gene / signaling pathway (any match)",
            options=all_pathways,
        )
        selected_phenotypes = st.multiselect(
            "Phenotype / experimental outcome (any match)",
            options=all_phenotypes,
        )
        keyword_search = st.text_input(
            "Free-text search (title & abstract)",
            placeholder="e.g. symmetry breaking adhesion",
        )

    # Apply filters
    filtered = df.copy()
    filtered = filtered[
        (filtered["year"] >= year_range[0]) & (filtered["year"] <= year_range[1])
    ]
    if selected_species != "All":
        filtered = filtered[filtered["species"] == selected_species]
    for pathway in selected_pathways:
        filtered = filtered[filtered["gene_pathways"].str.contains(pathway, case=False, na=False)]
    for phenotype in selected_phenotypes:
        filtered = filtered[filtered["phenotypes"].str.contains(phenotype, case=False, na=False)]
    if keyword_search.strip():
        terms = keyword_search.strip().lower().split()
        for term in terms:
            mask = (
                filtered["title"].str.lower().str.contains(term, na=False) |
                filtered["abstract"].str.lower().str.contains(term, na=False)
            )
            filtered = filtered[mask]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Papers shown",  len(filtered))
    col2.metric("Total in DB",   len(df))
    col3.metric("Human papers",  len(df[df["species"].isin(["human", "both"])]))
    col4.metric("Mouse papers",  len(df[df["species"].isin(["mouse", "both"])]))

    st.divider()
    st.subheader(f"{len(filtered)} papers match your filters")

    if filtered.empty:
        st.info("No papers match the current filters. Try broadening your selection.")
    else:
        display_cols = ["year", "title", "authors", "journal", "species",
                        "gene_pathways", "phenotypes"]
        st.dataframe(
            filtered[display_cols].reset_index(drop=True),
            use_container_width=True,
            height=400,
        )

        st.subheader("Paper details")
        st.caption("Enter a row number (0-indexed) from the table above.")
        paper_index = st.number_input(
            "Row number", min_value=0, max_value=max(len(filtered) - 1, 0), value=0, step=1
        )
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
        st.download_button(
            label="⬇️ Download filtered results as CSV",
            data=csv_bytes,
            file_name="gastruloid_filtered.csv",
            mime="text/csv",
        )

    st.divider()
    st.subheader("Pathway frequency across all papers")
    pathway_counts = {}
    for cell in df["gene_pathways"].dropna():
        for tag in str(cell).split(";"):
            t = tag.strip()
            if t:
                pathway_counts[t] = pathway_counts.get(t, 0) + 1
    if pathway_counts:
        chart_df = (
            pd.DataFrame.from_dict(pathway_counts, orient="index", columns=["count"])
            .sort_values("count", ascending=False)
        )
        st.bar_chart(chart_df)


# ============================================================
# TAB 2 — OBSERVATIONS
# ============================================================
with tab_obs:
    if not obs_available:
        st.info(
            "Observations not yet extracted.  \n"
            "Run `python3 extract.py` in your terminal (requires Anthropic API key), "
            "then refresh this page."
        )
    else:
        odf = obs_df.copy()

        # Filters
        st.subheader("Filter observations")
        fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns(5)

        all_entities = sorted(odf["entity_a"].dropna().unique())
        sel_entity = fcol1.selectbox("Entity (entity_a)", ["All"] + all_entities)

        all_relationships = sorted(odf["relationship"].dropna().unique())
        sel_rel = fcol2.selectbox("Relationship", ["All"] + all_relationships)

        all_obs_types = sorted(odf["observation_type"].dropna().unique())
        sel_type = fcol3.selectbox("Observation type", ["All"] + all_obs_types)

        all_species = sorted(odf["species"].dropna().unique())
        sel_species = fcol4.selectbox("Species", ["All"] + all_species)

        all_conf = sorted(odf["confidence"].dropna().unique())
        sel_conf = fcol5.selectbox("Confidence", ["All"] + all_conf)

        needs_ft = st.checkbox("Show only 'needs full text' observations", value=False)
        unreviewed = st.checkbox("Show only unreviewed observations", value=False)

        # Apply
        filt = odf.copy()
        if sel_entity != "All":
            filt = filt[filt["entity_a"] == sel_entity]
        if sel_rel != "All":
            filt = filt[filt["relationship"] == sel_rel]
        if sel_type != "All":
            filt = filt[filt["observation_type"] == sel_type]
        if sel_species != "All":
            filt = filt[filt["species"] == sel_species]
        if sel_conf != "All":
            filt = filt[filt["confidence"] == sel_conf]
        if needs_ft:
            filt = filt[filt["needs_full_text"] == True]
        if unreviewed:
            filt = filt[filt["reviewed"] == False]

        # Metrics
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Observations shown",  len(filt))
        mc2.metric("Total extracted",     len(odf))
        mc3.metric("Need full text",      int(odf["needs_full_text"].sum()))
        mc4.metric("Reviewed",            int(odf["reviewed"].sum()))

        st.divider()

        display_obs_cols = [
            "year", "species", "entity_a", "relationship", "entity_b_or_context",
            "observation_type", "confidence", "supporting_quote", "devSim_param",
            "needs_full_text", "pmid",
        ]
        st.dataframe(
            filt[display_obs_cols].reset_index(drop=True),
            use_container_width=True,
            height=450,
        )

        # Detail expander
        if not filt.empty:
            st.subheader("Observation detail")
            obs_index = st.number_input(
                "Row number", min_value=0, max_value=max(len(filt) - 1, 0),
                value=0, step=1, key="obs_row"
            )
            obs_row = filt.iloc[int(obs_index)]

            with st.container(border=True):
                st.markdown(f"**{obs_row['entity_a']}** `{obs_row['relationship']}` **{obs_row['entity_b_or_context']}**")
                st.markdown(f"Type: `{obs_row['observation_type']}` &nbsp;|&nbsp; Confidence: `{obs_row['confidence']}`")
                st.markdown(f"DevSim param: _{obs_row['devSim_param']}_")
                st.markdown(f"Supporting quote: _{obs_row['supporting_quote']}_")
                st.markdown(f"Needs full text: `{obs_row['needs_full_text']}` &nbsp;|&nbsp; Reviewed: `{obs_row['reviewed']}`")
                st.markdown("---")
                # Show corresponding paper
                paper_match = papers_df[papers_df["pmid"].astype(str) == str(obs_row["pmid"])]
                if not paper_match.empty:
                    p = paper_match.iloc[0]
                    st.markdown(f"**Paper:** {p['title']}")
                    st.markdown(f"_{p.get('authors','')}_  |  {p.get('journal','')}  |  {p.get('year','')}")
                    if p.get("doi"):
                        st.markdown(f"[DOI link](https://doi.org/{p['doi']})")
                    with st.expander("Abstract"):
                        st.markdown(p.get("abstract", "_No abstract._"))

        st.divider()
        obs_csv = filt.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download filtered observations as CSV",
            data=obs_csv,
            file_name="gastruloid_observations_filtered.csv",
            mime="text/csv",
        )


# ============================================================
# TAB 3 — GRN SUMMARY
# ============================================================
with tab_grn:
    if not obs_available:
        st.info(
            "Run `python3 extract.py` first to generate observations, "
            "then refresh this page."
        )
    else:
        odf = obs_df.copy()

        st.subheader("GRN edge support — ranked by number of papers")
        st.caption(
            "Each row is a unique (entity_a, relationship, entity_b_or_context) triplet. "
            "Count = number of distinct papers asserting this edge."
        )

        # Species filter for GRN summary
        grn_species = st.selectbox(
            "Filter by species", ["All", "human", "mouse", "both", "mammalian"],
            key="grn_species"
        )
        if grn_species != "All":
            grn_df = odf[odf["species"] == grn_species].copy()
        else:
            grn_df = odf.copy()

        # Count unique papers per edge
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

        if edge_summary.empty:
            st.info("No observations match this filter.")
        else:
            # Display as a formatted table
            st.dataframe(
                edge_summary.rename(columns={
                    "entity_a": "Entity A",
                    "relationship": "Relationship",
                    "entity_b_or_context": "Entity B / Context",
                    "papers": "# Papers",
                    "high_conf": "High confidence",
                    "needs_ft": "Need full text",
                    "devSim_param": "DevSim parameter",
                }),
                use_container_width=True,
                height=500,
            )

            st.divider()

            # Highlight unmapped observations (GRN extension candidates)
            unmapped = edge_summary[edge_summary["devSim_param"] == "unmapped"]
            if not unmapped.empty:
                st.subheader("Unmapped observations — DevSim extension candidates")
                st.caption(
                    "These edges are supported by the literature but have no current DevSim "
                    "parameter. They are candidates for adding new feedback loops or ODEs."
                )
                st.dataframe(
                    unmapped[edge_cols + ["papers", "high_conf"]].rename(columns={
                        "entity_a": "Entity A",
                        "relationship": "Relationship",
                        "entity_b_or_context": "Entity B / Context",
                        "papers": "# Papers",
                        "high_conf": "High confidence",
                    }),
                    use_container_width=True,
                )

            st.divider()

            # Papers flagged for full-text deep read
            ft_papers = (
                odf[odf["needs_full_text"] == True]
                .groupby(["pmid", "title", "species", "year"])
                .size()
                .reset_index(name="flagged_obs")
                .sort_values("flagged_obs", ascending=False)
            )
            if not ft_papers.empty:
                st.subheader(f"Papers flagged for full-text deep read ({len(ft_papers)} papers)")
                st.caption(
                    "These papers contain observations where quantitative data (concentrations, "
                    "timing, fractions) likely exists in the figures but not the abstract."
                )
                st.dataframe(
                    ft_papers.rename(columns={
                        "pmid": "PMID",
                        "title": "Title",
                        "species": "Species",
                        "year": "Year",
                        "flagged_obs": "# Observations needing full text",
                    }),
                    use_container_width=True,
                )
