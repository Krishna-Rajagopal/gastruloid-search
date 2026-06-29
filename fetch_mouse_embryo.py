"""
fetch_mouse_embryo.py
---------------------
Fetches mouse embryo GRN papers from PubMed using MOUSE_EMBRYO_QUERY,
skips PMIDs already in papers.csv, and appends new papers tagged
dataset='mouse_embryo'.

Run from the project directory:
    python3 fetch_mouse_embryo.py

After reviewing the results in the Papers tab (dataset filter → mouse_embryo),
optionally run full-text extraction:
    python3 fetch_fulltext.py    # fetches Methods/Results/Discussion
    python3 extract_fulltext_grn.py
"""

import time
import pandas as pd
from Bio import Entrez

from config import ENTREZ_EMAIL, MOUSE_EMBRYO_QUERY
from fetch_papers import fetch_details

Entrez.email = ENTREZ_EMAIL

PAPERS_CSV   = "data/papers.csv"
MAX_RESULTS  = 500

# Relevance filter for mouse embryo papers — must mention GRN-relevant signaling
# in title or abstract.  Less strict than gastruloid filter since the query
# already pre-selects well.
RELEVANCE_TERMS = [
    "nodal", "wnt", "bmp", "fgf", "gata", "sox", "tbxt", "brachyury",
    "smad", "β-catenin", "gene regulatory", "transcription factor",
    "cell fate", "germ layer", "epiblast", "mesoderm", "endoderm",
    "anterior", "posterior", "axis", "patterning", "signaling",
    "single.cell", "scrna", "rna.seq",
]

import re as _re

def _is_relevant(paper: dict) -> bool:
    text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
    return any(_re.search(t, text) for t in RELEVANCE_TERMS)


def main():
    existing = pd.read_csv(PAPERS_CSV)
    existing_pmids = set(existing["pmid"].astype(str))
    print(f"Existing corpus: {len(existing_pmids)} PMIDs")

    print("Searching PubMed with MOUSE_EMBRYO_QUERY...")
    handle = Entrez.esearch(db="pubmed", term=MOUSE_EMBRYO_QUERY, retmax=MAX_RESULTS)
    record = Entrez.read(handle)
    handle.close()
    all_pmids = record["IdList"]
    print(f"  {len(all_pmids)} results from PubMed")

    new_pmids = [p for p in all_pmids if p not in existing_pmids]
    print(f"  {len(new_pmids)} not already in corpus — fetching metadata...")

    if not new_pmids:
        print("Nothing new to add.")
        return

    time.sleep(0.4)
    papers = fetch_details(new_pmids)

    relevant = [p for p in papers if _is_relevant(p)]
    print(f"  {len(relevant)} passed relevance filter ({len(papers)-len(relevant)} dropped)")

    if not relevant:
        print("No relevant new papers found.")
        return

    new_df = pd.DataFrame(relevant)
    new_df["dataset"] = "mouse_embryo"
    new_df["species"] = new_df.get("species", "mouse")
    # species col may be absent from fetch_details — default to mouse
    if "species" not in new_df.columns:
        new_df["species"] = "mouse"

    # Align columns with existing papers.csv
    for col in existing.columns:
        if col not in new_df.columns:
            new_df[col] = ""
    new_df = new_df[[c for c in existing.columns if c in new_df.columns]]

    combined = pd.concat([existing, new_df], ignore_index=True)
    combined.to_csv(PAPERS_CSV, index=False)

    print(f"\nAdded {len(new_df)} mouse embryo papers → {PAPERS_CSV}")
    print(f"Total corpus: {len(combined)} papers")
    print("\nSample titles:")
    for _, r in new_df.head(5).iterrows():
        print(f"  [{r.get('year','')}] {r.get('title','')[:80]}")
    print("\nNext: review in app (Papers tab → dataset: mouse_embryo)")
    print("      then run: python3 fetch_fulltext.py && python3 extract_fulltext_grn.py")


if __name__ == "__main__":
    main()
