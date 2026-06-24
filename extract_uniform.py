"""
extract_uniform.py
------------------
Applies the uniform extraction schema (see REVIEW_PROTOCOL.md) to all 152 papers.
Uses PMC full text (methods + results + discussion) where available, abstract otherwise.
Every field is extracted identically for every paper; missing values are "not reported".

Output: data/extraction_table.csv  (152 rows × uniform schema)

Run: python3 extract_uniform.py

After running, generate the QC sample with:
    python3 -c "
    import pandas as pd, random
    df = pd.read_csv('data/extraction_table.csv')
    df.sample(15, random_state=42)[['pmid','title','full_text_source']].to_csv('data/qc_sample.csv', index=False)
    print('QC sample saved to data/qc_sample.csv')
    "
"""

import os
import json
import time
import pandas as pd
import anthropic

PAPERS_CSV      = os.path.join("data", "papers.csv")
FULLTEXT_DIR    = os.path.join("data", "fulltext")
EXTRACTION_CSV  = os.path.join("data", "extraction_table.csv")

SKIP_EXISTING    = True   # set False to re-extract everything
DRY_RUN          = False  # set True to test on first 5 papers only
MODEL            = "claude-haiku-4-5-20251001"
DELAY_SECONDS    = 0.15
MAX_SECTION_CHARS = 5000  # per section, to stay within token budget

# ---------------------------------------------------------------------------
# Output schema — all 152 papers get the same columns
# ---------------------------------------------------------------------------
COLUMNS = [
    # Block 1 — pre-populated from papers.csv
    "pmid", "year", "title", "first_last_authors", "journal", "species",
    # Block 2 — protocol / culture conditions
    "cell_line",
    "n_cells_per_aggregate",
    "chir_uM",
    "chir_onset_h",
    "chir_offset_h",
    "base_media",
    "harvest_timepoints_h",
    # Block 3 — imaging
    "imaging_modalities",
    "fluorescent_reporters",
    # Block 4 — morphology / variability
    "morphology_quantified",       # Y / N / unclear
    "morphology_metric",
    "morphology_n",
    "morphology_timepoint_h",
    "elongation_pct",
    "shape_distribution_figure",   # Y / N / unclear
    "variability_addressed",       # Y / N
    # Block 5 — GRN / mechanistic
    "key_perturbation",
    "key_finding",
    # Block 6 — provenance
    "full_text_source",            # PMC / abstract only
    "pmcid",
    "extraction_reviewed",         # False by default
]

EXTRACTED_FIELDS = [
    "cell_line", "n_cells_per_aggregate", "chir_uM", "chir_onset_h",
    "chir_offset_h", "base_media", "harvest_timepoints_h",
    "imaging_modalities", "fluorescent_reporters",
    "morphology_quantified", "morphology_metric", "morphology_n",
    "morphology_timepoint_h", "elongation_pct", "shape_distribution_figure",
    "variability_addressed", "key_perturbation", "key_finding",
]

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a research assistant performing structured data extraction from
gastruloid research papers for a scoping review. Extract ONLY values explicitly stated in the
provided text. If a field is not present, return the string "not reported". Never infer values
from context or general knowledge. Return a single JSON object with exactly these keys:

  cell_line               : specific ESC/iPSC line (e.g. "v6.5", "E14", "H9", "RUES2"), or
                            "mESC unspecified" / "hESC unspecified" / "not reported"
  n_cells_per_aggregate   : cells seeded per aggregate (e.g. "300"), or "not reported"
  chir_uM                 : CHIR99021 concentration in µM (e.g. "3"), or "not reported"
  chir_onset_h            : hours post-aggregation when CHIR was added (e.g. "0"), or "not reported"
  chir_offset_h           : hours post-aggregation when CHIR was removed (e.g. "24"),
                            or "continuous" if not removed, or "not reported"
  base_media              : base culture medium (e.g. "N2B27", "mTeSR1"), or "not reported"
  harvest_timepoints_h    : comma-separated hours when gastruloids were collected/imaged
                            (e.g. "96, 120"), or "not reported"
  imaging_modalities      : comma-separated from: brightfield, widefield-fluorescence, confocal,
                            light-sheet, live-imaging — or "not reported"
  fluorescent_reporters   : reporter lines or antibody targets used (e.g. "TBXT-GFP, SOX2-mCherry"),
                            or "none" if brightfield only, or "not reported"
  morphology_quantified   : "Y" if any shape metric is reported numerically; "N" if not; "unclear"
  morphology_metric       : name of shape metric (e.g. "aspect ratio", "elongation ratio",
                            "% elongated", "circularity"), or "not reported"
  morphology_n            : number of individual gastruloids measured (e.g. "87"), or "not reported"
  morphology_timepoint_h  : hour at which morphology was measured (e.g. "120"), or "not reported"
  elongation_pct          : percentage of gastruloids described as elongated or polarized
                            (e.g. "65"), or "not reported"
  shape_distribution_figure: "Y" if a histogram, violin, or scatter of shape data appears in a
                              figure; "N"; "unclear"
  variability_addressed   : "Y" if paper explicitly discusses batch variability, stochasticity,
                            or reproducibility of morphological outcomes; "N" otherwise
  key_perturbation        : main experimental manipulation (e.g. "CHIR dose titration",
                            "SB431542 Nodal inhibition", "none / descriptive study")
  key_finding             : one sentence — central conclusion, verbatim or minimally paraphrased

All values must be strings. Return only the JSON object, no commentary."""

USER_PROMPT_TEMPLATE = """{source_label}

Title: {title}
Authors: {authors}
Journal: {journal}
Year: {year}
Species: {species}

{text_block}

Extract all fields per the schema."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_last(authors_str: str) -> str:
    """Return 'FirstSurname … LastSurname' from a comma-separated author list."""
    names = [a.strip() for a in str(authors_str or "").split(",") if a.strip()]
    if not names:
        return "not reported"
    first_surname = names[0].split()[-1] if names[0].split() else names[0]
    if len(names) == 1:
        return first_surname
    last_surname = names[-1].split()[-1] if names[-1].split() else names[-1]
    return f"{first_surname} … {last_surname}"


def _build_text_block(paper_row: dict, fulltext: dict) -> tuple[str, str]:
    """Return (source_label, text_block) — full text if available, else abstract."""
    methods    = (fulltext.get("methods", "") or "")[:MAX_SECTION_CHARS]
    results    = (fulltext.get("results", "") or "")[:MAX_SECTION_CHARS]
    discussion = (fulltext.get("discussion", "") or "")[:MAX_SECTION_CHARS]

    if any([methods, results, discussion]):
        parts = []
        if methods:
            parts.append(f"[METHODS]\n{methods}")
        if results:
            parts.append(f"[RESULTS]\n{results}")
        if discussion:
            parts.append(f"[DISCUSSION/CONCLUSION]\n{discussion}")
        return "SOURCE: PMC full text", "\n\n".join(parts)

    abstract = str(paper_row.get("abstract", "") or "").strip()
    return "SOURCE: abstract only", f"[ABSTRACT]\n{abstract}"


# ---------------------------------------------------------------------------
# Claude extraction
# ---------------------------------------------------------------------------

def extract_paper(client: anthropic.Anthropic, paper_row: dict, fulltext: dict) -> dict:
    """Call Claude and return extracted field dict for one paper."""
    source_label, text_block = _build_text_block(paper_row, fulltext)

    user_msg = USER_PROMPT_TEMPLATE.format(
        source_label=source_label,
        title=paper_row.get("title", ""),
        authors=paper_row.get("authors", ""),
        journal=paper_row.get("journal", ""),
        year=paper_row.get("year", ""),
        species=paper_row.get("species", ""),
        text_block=text_block,
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except Exception as e:
        print(f"    [WARN] extraction failed: {type(e).__name__}: {e}")
        return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("  Run: export ANTHROPIC_API_KEY=\"sk-ant-...\"")
        return

    papers_df = pd.read_csv(PAPERS_CSV)
    print(f"Loaded {len(papers_df)} papers from {PAPERS_CSV}")

    already_done: set[str] = set()
    if SKIP_EXISTING and os.path.exists(EXTRACTION_CSV):
        prev = pd.read_csv(EXTRACTION_CSV)
        already_done = set(str(p) for p in prev["pmid"].dropna().unique())
        print(f"Skipping {len(already_done)} already-extracted PMIDs (SKIP_EXISTING=True)")

    to_process = [
        row for _, row in papers_df.iterrows()
        if str(row.get("pmid", "")) not in already_done
    ]
    if DRY_RUN:
        to_process = to_process[:5]
        print("DRY_RUN=True — processing 5 papers only")

    print(f"Extracting {len(to_process)} papers...\n")

    client = anthropic.Anthropic()
    rows: list[dict] = []

    for i, paper in enumerate(to_process):
        pmid = str(paper.get("pmid", "?"))
        title_short = str(paper.get("title", ""))[:58]
        print(f"  [{i+1}/{len(to_process)}] PMID {pmid}: {title_short}...")

        ft_path = os.path.join(FULLTEXT_DIR, f"{pmid}.json")
        fulltext: dict = {}
        if os.path.exists(ft_path):
            with open(ft_path, encoding="utf-8") as fh:
                fulltext = json.load(fh)

        has_full = any(fulltext.get(k, "") for k in ("methods", "results", "discussion"))
        source   = "PMC" if has_full else "abstract only"

        extracted = extract_paper(client, paper, fulltext)

        row = {
            # Block 1 — pre-populated
            "pmid":               pmid,
            "year":               paper.get("year", ""),
            "title":              paper.get("title", ""),
            "first_last_authors": _first_last(str(paper.get("authors", ""))),
            "journal":            paper.get("journal", ""),
            "species":            paper.get("species", ""),
            # Blocks 2–5 — from Claude (default "not reported" for missing keys)
            **{k: str(extracted.get(k, "not reported")) for k in EXTRACTED_FIELDS},
            # Block 6 — provenance
            "full_text_source":   source,
            "pmcid":              fulltext.get("pmcid", "") or paper.get("pmcid", ""),
            "extraction_reviewed": "False",
        }
        rows.append(row)

        morph = extracted.get("morphology_quantified", "?")
        var   = extracted.get("variability_addressed", "?")
        print(f"    → {source} | morphology: {morph} | variability: {var}")

        time.sleep(DELAY_SECONDS)

    # Merge with any previously saved rows
    new_df = pd.DataFrame(rows, columns=COLUMNS)
    if SKIP_EXISTING and os.path.exists(EXTRACTION_CSV):
        prev = pd.read_csv(EXTRACTION_CSV)
        combined = pd.concat([prev, new_df], ignore_index=True)
    else:
        combined = new_df

    os.makedirs("data", exist_ok=True)
    combined.to_csv(EXTRACTION_CSV, index=False)

    # Summary
    print(f"\n{'='*60}")
    print(f"Saved {len(combined)} rows → {EXTRACTION_CSV}")
    if not combined.empty:
        pmc_n    = (combined["full_text_source"] == "PMC").sum()
        morph_y  = (combined["morphology_quantified"] == "Y").sum()
        var_y    = (combined["variability_addressed"] == "Y").sum()
        distrib  = (combined["shape_distribution_figure"] == "Y").sum()
        print(f"\nPMC full text used:          {pmc_n} / {len(combined)}")
        print(f"Morphology quantified (Y):   {morph_y}")
        print(f"Variability addressed (Y):   {var_y}")
        print(f"Shape distribution figure:   {distrib}")

    print(f"""
Next steps:
  1. Generate QC sample (15 random papers for manual verification):
       python3 -c "
       import pandas as pd
       df = pd.read_csv('data/extraction_table.csv')
       df.sample(15, random_state=42)[['pmid','title','full_text_source']].to_csv('data/qc_sample.csv', index=False)
       print('Saved data/qc_sample.csv')
       "
  2. Open the app:
       python3 -m streamlit run app.py
""")


if __name__ == "__main__":
    main()
