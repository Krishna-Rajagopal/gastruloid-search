"""extract_fulltext_grn.py — GRN observation extraction from full-text PMC sections.

Reads data/fulltext/{pmid}.json (results + discussion) and sends each to Claude to
extract GRN edges.  Output: data/observations_fulltext.csv

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 extract_fulltext_grn.py

After running, review data/observations_fulltext.csv in the Curate tab, then merge:
    python3 extract_fulltext_grn.py --merge
This deduplicates against existing abstract-level observations and appends new rows to
data/observations.csv.
"""

import argparse
import json
import os
import time
import ast

import anthropic
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL        = "claude-haiku-4-5-20251001"   # fast + cheap; switch to sonnet-4-6 for quality
MAX_CHARS    = 7000                            # truncation per paper (results + discussion)
RESULTS_CAP  = 4000                            # chars taken from results section
DISCUSS_CAP  = 3000                            # chars taken from discussion section
DELAY_S      = 0.4                             # rate limit gap between API calls
DRY_RUN      = False                           # set True to process first 5 papers only

FULLTEXT_DIR = os.path.join("data", "fulltext")
PAPERS_CSV   = os.path.join("data", "papers.csv")
OBS_CSV      = os.path.join("data", "observations.csv")
OUT_CSV      = os.path.join("data", "observations_fulltext.csv")

SCHEMA_KEYS  = [
    "observation_type",      # grn_edge | spatial_pattern | perturbation | expression_timing
    "entity_a",              # acting entity (canonical name)
    "relationship",          # activates | inhibits | high_in | low_in | ...
    "entity_b_or_context",   # target entity or spatial context
    "confidence",            # high | medium | low
    "supporting_quote",      # verbatim ≤20-word phrase from the text
    "needs_full_text",       # always False here (we already have full text)
    "evidence_type",         # direct | cited | review
    "figure_ref",            # e.g. "Fig. 3B" or "" if not mentioned
]

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a developmental biology expert extracting structured observations
from the Results and Discussion sections of gastruloid research papers.

Extract ONLY observations that are:
1. GRN edges: one molecule/pathway activates or inhibits another
2. Spatial patterns: a signal or gene is high/low/graded in a specific compartment
3. Perturbation outcomes: blocking/activating a pathway changes a phenotype (this paper's experiments)
4. Expression timing: when a gene turns on/off relative to gastruloid stages

CRITICAL rules:
- Only extract claims DIRECTLY demonstrated by experiments in THIS paper.
- If a claim cites another paper (e.g. "as shown by Smith et al."), set evidence_type="cited".
- If a claim is a hypothesis or interpretation with no data, set evidence_type="review".
- Set evidence_type="direct" ONLY when this paper's own figures/experiments support it.
- Include figure_ref (e.g. "Fig. 3B") when mentioned near the claim.

Focus entities: Wnt, Nodal, BMP, FGF, Retinoic acid, TBXT, Brachyury, SOX2, SOX17,
FOXA2, GATA6, E-cadherin, β-catenin, YAP1, ERK, SMAD2/3, CDX2, OTX2, TBX6, Snail.
Include other signaling molecules if clearly relevant to gastruloid biology.

IMPORTANT — use EXACTLY these JSON keys (no others):
{
  "observation_type":    "grn_edge" | "spatial_pattern" | "perturbation" | "expression_timing",
  "entity_a":            "the acting entity, e.g. Wnt",
  "relationship":        "activates" | "inhibits" | "high_in" | "low_in" | "gradient_in" |
                         "enhances" | "reduces" | "abolishes" | "required_for" |
                         "correlates_with" | "anticorrelates_with" | "modulates",
  "entity_b_or_context": "target entity or spatial context, e.g. Nodal or posterior",
  "confidence":          "high" | "medium" | "low",
  "supporting_quote":    "verbatim ≤20-word phrase from the text",
  "needs_full_text":     false,
  "evidence_type":       "direct" | "cited" | "review",
  "figure_ref":          "Fig. 3B or empty string"
}

Return a JSON array of such objects, or [] if nothing extractable.
NEVER use other key names. NEVER invent observations not in the text."""

USER_PROMPT_TEMPLATE = """Title: {title}
Species: {species}

--- RESULTS ---
{results}

--- DISCUSSION ---
{discussion}

Extract all relevant GRN observations as a JSON array."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def truncate_section(text: str, cap: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:cap] + ("…" if len(text) > cap else "")


def extract_observations(client: anthropic.Anthropic, paper: dict,
                         results_text: str, discussion_text: str) -> list[dict]:
    results_trunc    = truncate_section(results_text, RESULTS_CAP)
    discussion_trunc = truncate_section(discussion_text, DISCUSS_CAP)

    if len(results_trunc) + len(discussion_trunc) < 200:
        return []

    user_msg = USER_PROMPT_TEMPLATE.format(
        title=paper.get("title", ""),
        species=paper.get("species", "unspecified"),
        results=results_trunc or "(not available)",
        discussion=discussion_trunc or "(not available)",
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        import re as _re
        raw = response.content[0].text.strip()
        raw = _re.sub(r"^```(?:json)?\n?", "", raw)
        raw = _re.sub(r"\n?```.*$", "", raw, flags=_re.DOTALL)
        raw = raw.strip()
        # Extract JSON array if wrapped in extra text
        m = _re.search(r"\[.*\]", raw, _re.DOTALL)
        raw = m.group(0) if m else raw
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IndexError, anthropic.APIError) as e:
        print(f"  ⚠ Error for PMID {paper.get('pmid')}: {e}")
        return []


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------
def merge_into_obs(new_df: pd.DataFrame) -> None:
    """Append observations not already in observations.csv (deduplicate by key)."""
    existing = pd.read_csv(OBS_CSV)
    # Key: (pmid, entity_a, relationship, entity_b_or_context)
    existing_keys = set(
        zip(existing["pmid"].astype(str), existing["entity_a"],
            existing["relationship"], existing["entity_b_or_context"])
    )
    to_add = []
    for _, row in new_df.iterrows():
        key = (str(row["pmid"]), row["entity_a"],
               row["relationship"], row["entity_b_or_context"])
        if key not in existing_keys:
            to_add.append(row)
            existing_keys.add(key)

    if not to_add:
        print("No new observations to merge (all already present).")
        return

    merged = pd.concat([existing, pd.DataFrame(to_add)], ignore_index=True)
    merged.to_csv(OBS_CSV, index=False)
    print(f"Merged {len(to_add)} new observations into {OBS_CSV}. Total: {len(merged)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--merge", action="store_true",
                        help="Merge observations_fulltext.csv into observations.csv")
    parser.add_argument("--model", default=MODEL,
                        help=f"Claude model to use (default: {MODEL})")
    args = parser.parse_args()

    if args.merge:
        if not os.path.exists(OUT_CSV):
            print(f"No {OUT_CSV} found. Run extraction first.")
            return
        ft_df = pd.read_csv(OUT_CSV)
        merge_into_obs(ft_df)
        return

    client = anthropic.Anthropic()

    papers = pd.read_csv(PAPERS_CSV)
    paper_map = {str(r["pmid"]): r for _, r in papers.iterrows()}

    ft_files = sorted([f for f in os.listdir(FULLTEXT_DIR) if f.endswith(".json")])
    if DRY_RUN:
        ft_files = ft_files[:5]

    all_rows = []
    for i, fname in enumerate(ft_files):
        pmid_str = fname.replace(".json", "")
        try:
            with open(os.path.join(FULLTEXT_DIR, fname)) as fh:
                ft = json.load(fh)
        except Exception:
            continue

        results_text    = ft.get("results", "") or ""
        discussion_text = ft.get("discussion", "") or ""

        if len(results_text) + len(discussion_text) < 200:
            print(f"[{i+1}/{len(ft_files)}] PMID {pmid_str}: no fulltext, skipping")
            continue

        paper = paper_map.get(pmid_str, {"pmid": pmid_str, "title": "", "species": ""})
        print(f"[{i+1}/{len(ft_files)}] PMID {pmid_str}: "
              f"{len(results_text)+len(discussion_text):,} chars … ", end="", flush=True)

        obs = extract_observations(client, paper, results_text, discussion_text)
        print(f"{len(obs)} observations")

        for o in obs:
            row = {
                "pmid":               int(pmid_str) if pmid_str.isdigit() else pmid_str,
                "year":               paper.get("year"),
                "title":              paper.get("title", ""),
                "species":            paper.get("species", ""),
                "observation_type":   o.get("observation_type", ""),
                "entity_a":           o.get("entity_a", ""),
                "relationship":       o.get("relationship", ""),
                "entity_b_or_context": o.get("entity_b_or_context", ""),
                "confidence":         o.get("confidence", "medium"),
                "supporting_quote":   o.get("supporting_quote", ""),
                "needs_full_text":    False,
                "reviewed":           False,
                "devSim_param":       "unmapped",
                "entity_a_raw":       o.get("entity_a", ""),
                "entity_b_raw":       o.get("entity_b_or_context", ""),
                "source":             "fulltext",
                "evidence_type":      o.get("evidence_type", ""),
                "figure_ref":         o.get("figure_ref", ""),
            }
            all_rows.append(row)

        time.sleep(DELAY_S)

    if not all_rows:
        print("No observations extracted.")
        return

    df = pd.DataFrame(all_rows)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {len(df)} observations to {OUT_CSV}")
    print(f"Unique PMIDs: {df['pmid'].nunique()}")
    print(f"\nobservation_type breakdown:\n{df['observation_type'].value_counts()}")
    print(f"\nevidence_type breakdown:\n{df['evidence_type'].value_counts()}")
    print(f"\nRun with --merge to integrate into observations.csv after review.")


if __name__ == "__main__":
    main()
