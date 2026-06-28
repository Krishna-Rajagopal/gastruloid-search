"""
extract.py
----------
Uses Claude Haiku to extract structured biological observations from each
paper abstract in data/papers.csv.

Output: data/observations.csv — one row per observation.

Run from the project directory:
    python3 extract.py

Prerequisites:
    export ANTHROPIC_API_KEY="sk-ant-..."   (or add to ~/.zshrc)
    pip3 install anthropic

Options (edit the constants below):
    SKIP_EXISTING  — if True, re-running skips PMIDs already in observations.csv
    DRY_RUN        — if True, processes only the first 5 papers (for testing)
"""

import os
import json
import time
import pandas as pd
import anthropic

from config import DEVSIM_MAPPING

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
PAPERS_CSV      = os.path.join("data", "papers.csv")
OBSERVATIONS_CSV = os.path.join("data", "observations.csv")

SKIP_EXISTING = True   # set to False to re-extract everything from scratch
DRY_RUN       = False  # set to True to test on just the first 5 papers

MODEL         = "claude-haiku-4-5-20251001"
DELAY_SECONDS = 0.15   # pause between API calls to stay under rate limits

# ---------------------------------------------------------------------------
# Observation schema columns (in final CSV order)
# ---------------------------------------------------------------------------
OBS_COLUMNS = [
    "pmid", "year", "title", "species",
    "observation_type",        # grn_edge | spatial_pattern | perturbation | expression_timing
    "entity_a",                # Wnt, Nodal, BMP, FGF, RA, TBXT, SOX2, SOX17, FOXA2, …
    "relationship",            # activates | inhibits | high_in | low_in | gradient_in |
                               # enhances | reduces | abolishes | required_for |
                               # correlates_with | anticorrelates_with
    "entity_b_or_context",     # target gene, or: inner cells | outer cells | anterior | posterior
    "confidence",              # high | medium | low
    "supporting_quote",        # verbatim ≤20-word phrase from abstract
    "needs_full_text",         # True if quantitative backing likely in figures
    "reviewed",                # False by default; flip manually after verification
    "devSim_param",            # filled by map_devsim_param()
    "timepoint_h",             # developmental timepoint: 48 | 72 | 96 | 120 | early | late | not_specified
    "perturbation_type",       # genetic_KO | genetic_OE | pharmacological | morpholino | reporter | none
]

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a developmental biology expert extracting structured observations
from gastruloid research abstracts. Your output will be used to constrain a mathematical
model of anterior-posterior axis formation (DevSim).

Extract ONLY observations that are:
1. GRN edges: one molecule/pathway activates or inhibits another
2. Spatial patterns: a signal or gene is high/low/graded in a specific compartment
3. Perturbation outcomes: blocking/activating a pathway enhances/reduces/abolishes a phenotype
4. Expression timing: when a gene turns on/off relative to gastruloid development stages

Focus entities: Wnt, Nodal, BMP, FGF, Retinoic acid (RA), TBXT/Brachyury, SOX2, SOX17,
FOXA2, GATA6, E-cadherin/CDH1. Include other signaling molecules if clearly relevant.

For each observation, return a JSON object with these exact keys:
  observation_type: "grn_edge" | "spatial_pattern" | "perturbation" | "expression_timing"
  entity_a: the acting/measured entity (use standard names: Wnt, Nodal, BMP, FGF, RA, TBXT, ...)
  relationship: one of: activates, inhibits, high_in, low_in, gradient_in, enhances, reduces,
                abolishes, required_for, correlates_with, anticorrelates_with
  entity_b_or_context: the target gene/pathway, or spatial context (inner cells, outer cells,
                       anterior, posterior, uniform, peripheral, core)
  confidence: "high" (directly stated), "medium" (implied), "low" (speculative/indirect)
  supporting_quote: verbatim phrase from the abstract, ≤20 words
  needs_full_text: true if quantitative data (concentrations, timing, fractions) likely exists
                   in figures but is not in the abstract
  timepoint_h: the developmental hour at which the observation was made — use "48", "72", "96",
               "120", "early" (before 48h), "late" (after 120h), or "not_specified" if unclear
  perturbation_type: for perturbation observations only — "genetic_KO" (CRISPR/RNAi/knockout),
                     "genetic_OE" (overexpression/knock-in), "pharmacological" (drug/small molecule
                     e.g. CHIR, inhibitor), "morpholino", "reporter" (reporter line only, no perturbation),
                     or "none" for non-perturbation observations

Return a JSON array. Return [] if the abstract contains no extractable observations.
NEVER invent observations not directly supported by the text."""

USER_PROMPT_TEMPLATE = """Title: {title}
Species: {species}
Abstract: {abstract}

Extract all relevant observations as a JSON array."""


# ---------------------------------------------------------------------------
# DevSim parameter mapping
# ---------------------------------------------------------------------------
def map_devsim_param(entity_a: str, relationship: str, entity_b: str) -> str:
    """Look up the DevSim parameter for this observation triplet."""
    key = (entity_a.lower().strip(), relationship.lower().strip(), entity_b.lower().strip())
    return DEVSIM_MAPPING.get(key, "unmapped")


# ---------------------------------------------------------------------------
# Claude API call
# ---------------------------------------------------------------------------
def extract_observations(client: anthropic.Anthropic, paper: dict) -> list[dict]:
    """Call Claude Haiku and return a list of observation dicts for one paper."""
    abstract = str(paper.get("abstract", "")).strip()
    if not abstract or abstract == "nan":
        return []

    user_msg = USER_PROMPT_TEMPLATE.format(
        title=paper.get("title", ""),
        species=paper.get("species", "unspecified"),
        abstract=abstract,
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()

        # Claude sometimes wraps JSON in markdown code fences — strip them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        observations = json.loads(raw)
        if not isinstance(observations, list):
            return []

        # Attach paper metadata and DevSim mapping to each row
        rows = []
        for obs in observations:
            if not isinstance(obs, dict):
                continue
            entity_a = str(obs.get("entity_a", "")).strip()
            relationship = str(obs.get("relationship", "")).strip()
            entity_b = str(obs.get("entity_b_or_context", "")).strip()
            rows.append({
                "pmid":                 paper.get("pmid", ""),
                "year":                 paper.get("year", ""),
                "title":                paper.get("title", ""),
                "species":              paper.get("species", ""),
                "observation_type":     obs.get("observation_type", ""),
                "entity_a":             entity_a,
                "relationship":         relationship,
                "entity_b_or_context":  entity_b,
                "confidence":           obs.get("confidence", ""),
                "supporting_quote":     obs.get("supporting_quote", ""),
                "needs_full_text":      obs.get("needs_full_text", False),
                "reviewed":             False,
                "devSim_param":         map_devsim_param(entity_a, relationship, entity_b),
            })
        return rows

    except (json.JSONDecodeError, IndexError, anthropic.APIError) as e:
        print(f"    [WARN] PMID {paper.get('pmid', '?')}: {type(e).__name__}: {e}")
        return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.")
        print("  Run: export ANTHROPIC_API_KEY=\"sk-ant-...\"")
        print("  Then re-run this script.")
        return

    # Load papers
    if not os.path.exists(PAPERS_CSV):
        print(f"ERROR: {PAPERS_CSV} not found. Run python3 run.py first.")
        return

    papers_df = pd.read_csv(PAPERS_CSV)
    print(f"Loaded {len(papers_df)} papers from {PAPERS_CSV}")

    # Optionally skip already-extracted PMIDs
    already_done = set()
    if SKIP_EXISTING and os.path.exists(OBSERVATIONS_CSV):
        existing = pd.read_csv(OBSERVATIONS_CSV)
        already_done = set(str(p) for p in existing["pmid"].dropna().unique())
        print(f"Skipping {len(already_done)} already-extracted PMIDs (SKIP_EXISTING=True)")

    papers_to_process = [
        row for _, row in papers_df.iterrows()
        if str(row.get("pmid", "")) not in already_done
    ]

    if DRY_RUN:
        papers_to_process = papers_to_process[:5]
        print("DRY_RUN=True — processing first 5 papers only")

    print(f"Extracting observations from {len(papers_to_process)} papers...\n")

    client = anthropic.Anthropic()
    all_observations = []
    failed_pmids = []

    for i, paper in enumerate(papers_to_process):
        pmid = paper.get("pmid", "?")
        title_short = str(paper.get("title", ""))[:60]
        print(f"  [{i+1}/{len(papers_to_process)}] PMID {pmid}: {title_short}...")

        obs = extract_observations(client, paper)
        if obs:
            all_observations.extend(obs)
            print(f"    → {len(obs)} observations")
        else:
            print(f"    → 0 (no extractable observations or empty abstract)")

        time.sleep(DELAY_SECONDS)

    # Merge with any previously saved observations
    if SKIP_EXISTING and os.path.exists(OBSERVATIONS_CSV):
        prev = pd.read_csv(OBSERVATIONS_CSV)
        new_df = pd.DataFrame(all_observations, columns=OBS_COLUMNS)
        combined = pd.concat([prev, new_df], ignore_index=True)
    else:
        combined = pd.DataFrame(all_observations, columns=OBS_COLUMNS)

    os.makedirs("data", exist_ok=True)
    combined.to_csv(OBSERVATIONS_CSV, index=False)

    # Summary
    print(f"\n{'='*60}")
    print(f"Saved {len(combined)} total observations → {OBSERVATIONS_CSV}")
    if not combined.empty:
        print(f"\nBy observation type:")
        for otype, count in combined["observation_type"].value_counts().items():
            print(f"  {otype:<25} {count}")
        print(f"\nTop entities (entity_a):")
        for entity, count in combined["entity_a"].value_counts().head(10).items():
            print(f"  {entity:<25} {count}")
        print(f"\nNeeds full-text review: {combined['needs_full_text'].sum()} observations")
    if failed_pmids:
        print(f"\nFailed PMIDs (API errors): {failed_pmids}")
    print(f"\nNext step: python3 -m streamlit run app.py")


if __name__ == "__main__":
    main()
