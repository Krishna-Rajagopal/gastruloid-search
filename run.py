"""
run.py
------
Main entry point. Run from the terminal:

    python3 run.py

Produces:
  data/papers.csv        — relevant gastruloid development papers
  data/dropped.csv       — papers filtered out (for auditing if needed)
"""

import os
import pandas as pd
from fetch_papers import fetch_all_papers
from classify import classify_all

RELEVANT_PATH = os.path.join("data", "papers.csv")
DROPPED_PATH  = os.path.join("data", "dropped.csv")

COLUMN_ORDER = [
    "year", "title", "authors", "journal",
    "species", "gene_pathways", "phenotypes", "genes_found",
    "abstract", "doi", "pmid", "mesh",
]


def main():
    papers = fetch_all_papers()
    relevant, dropped = classify_all(papers)

    os.makedirs("data", exist_ok=True)

    def save(records, path):
        df = pd.DataFrame(records)
        df = df[[c for c in COLUMN_ORDER if c in df.columns]]
        df = df.sort_values("year", ascending=False).reset_index(drop=True)
        df.to_csv(path, index=False)
        return df

    df = save(relevant, RELEVANT_PATH)
    save(dropped, DROPPED_PATH)

    print(f"\nSaved {len(df)} relevant papers → {RELEVANT_PATH}")
    print(f"Saved {len(dropped)} dropped papers → {DROPPED_PATH}  (audit if needed)")
    print("\nNext step:  streamlit run app.py")


if __name__ == "__main__":
    main()
