"""
fetch_fulltext.py
-----------------
Fetches full-text XML from PubMed Central (PMC) for each paper in papers.csv.

For each PMID that has a PMC record, downloads the article XML and extracts
the Methods, Results, and Discussion/Conclusion section text.

Outputs:
  data/fulltext/{pmid}.json   one file per paper (PMC text or empty if not in PMC)
  data/papers.csv             updated with 'pmcid' column

Run from the project directory:
    python3 fetch_fulltext.py

Rate limits:
  Default (no key):  3 requests/second → 0.34s delay enforced
  With NCBI API key: 10 requests/second → set NCBI_API_KEY env var to enable
"""

import os
import json
import time
import xml.etree.ElementTree as ET
import pandas as pd
from Bio import Entrez

from config import ENTREZ_EMAIL

Entrez.email = ENTREZ_EMAIL

# Use NCBI API key if set — raises rate limit to 10 req/sec
_ncbi_key = os.environ.get("NCBI_API_KEY", "")
if _ncbi_key:
    Entrez.api_key = _ncbi_key
    DELAY = 0.11
else:
    DELAY = 0.34

PAPERS_CSV   = os.path.join("data", "papers.csv")
FULLTEXT_DIR = os.path.join("data", "fulltext")

# Section title keywords (lowercase) mapped to output key
SECTION_MAP = {
    "methods":    ["methods", "materials and methods", "experimental procedures",
                   "materials & methods", "experimental methods", "method"],
    "results":    ["results", "results and discussion"],
    "discussion": ["discussion", "conclusion", "conclusions",
                   "discussion and conclusion", "summary and conclusion"],
}


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _collect_text(element) -> str:
    """Recursively collect all text within an XML element."""
    parts = []
    if element.text:
        parts.append(element.text.strip())
    for child in element:
        parts.append(_collect_text(child))
        if child.tail:
            parts.append(child.tail.strip())
    return " ".join(p for p in parts if p)


def extract_sections(xml_bytes: bytes) -> dict[str, str]:
    """Parse PMC JATS XML and return dict of section texts."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"    [WARN] XML parse error: {e}")
        return {}

    buckets: dict[str, list[str]] = {k: [] for k in SECTION_MAP}

    for sec in root.iter("sec"):
        title_el = sec.find("title")
        if title_el is None:
            continue
        title = (title_el.text or "").lower().strip()
        for key, variants in SECTION_MAP.items():
            if any(title.startswith(v) for v in variants):
                buckets[key].append(_collect_text(sec))
                break  # one section → one bucket

    return {k: " ".join(v) for k, v in buckets.items() if v}


# ---------------------------------------------------------------------------
# NCBI API calls
# ---------------------------------------------------------------------------

def get_pmcid(pmid: str):
    """Return PMCID for a PMID via elink, or None if not in PMC."""
    try:
        handle = Entrez.elink(dbfrom="pubmed", db="pmc", id=pmid)
        record = Entrez.read(handle)
        handle.close()
        for ls in record[0].get("LinkSetDb", []):
            if ls.get("LinkName") == "pubmed_pmc":
                links = ls.get("Link", [])
                if links:
                    return str(links[0]["Id"])
    except Exception as e:
        print(f"    [WARN] elink failed for PMID {pmid}: {e}")
    return None


def fetch_pmc_xml(pmcid: str):
    """Fetch raw PMC XML for a PMCID."""
    try:
        handle = Entrez.efetch(db="pmc", id=pmcid, rettype="xml", retmode="xml")
        data = handle.read()
        handle.close()
        return data if isinstance(data, bytes) else data.encode("utf-8")
    except Exception as e:
        print(f"    [WARN] efetch failed for PMCID {pmcid}: {e}")
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(FULLTEXT_DIR, exist_ok=True)

    papers_df = pd.read_csv(PAPERS_CSV)
    print(f"Loaded {len(papers_df)} papers from {PAPERS_CSV}")

    if "pmcid" not in papers_df.columns:
        papers_df["pmcid"] = ""

    already_fetched = {
        f.replace(".json", "")
        for f in os.listdir(FULLTEXT_DIR)
        if f.endswith(".json")
    }
    print(f"Cached already:   {len(already_fetched)} papers")

    n_fetched = n_no_pmc = n_skipped = 0

    for i, row in papers_df.iterrows():
        pmid = str(row.get("pmid", "")).strip()
        if not pmid:
            continue
        if pmid in already_fetched:
            n_skipped += 1
            continue

        title_short = str(row.get("title", ""))[:58]
        print(f"  [{i+1}/{len(papers_df)}] PMID {pmid}: {title_short}...")

        # Step 1: resolve PMCID
        pmcid = get_pmcid(pmid)
        time.sleep(DELAY)

        record: dict = {"pmid": pmid, "pmcid": pmcid or "",
                        "methods": "", "results": "", "discussion": ""}

        if not pmcid:
            n_no_pmc += 1
            print(f"    → not in PMC")
        else:
            papers_df.at[i, "pmcid"] = pmcid

            # Step 2: fetch full text
            xml_data = fetch_pmc_xml(pmcid)
            time.sleep(DELAY)

            if xml_data:
                sections = extract_sections(xml_data)
                record.update(sections)
                found = [k for k in ("methods", "results", "discussion") if record[k]]
                print(f"    → PMC{pmcid}  sections: {', '.join(found) if found else 'body not parsed'}")
                n_fetched += 1
            else:
                n_no_pmc += 1
                print(f"    → PMC{pmcid} (fetch failed)")

        with open(os.path.join(FULLTEXT_DIR, f"{pmid}.json"), "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)

    papers_df.to_csv(PAPERS_CSV, index=False)

    print(f"\n{'='*60}")
    print(f"PMC text retrieved:  {n_fetched}")
    print(f"Not in PMC / failed: {n_no_pmc}")
    print(f"Skipped (cached):    {n_skipped}")
    print(f"papers.csv updated with pmcid column.")
    print(f"\nNext step: python3 extract_uniform.py")


if __name__ == "__main__":
    main()
