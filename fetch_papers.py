"""
fetch_papers.py
---------------
Queries PubMed for gastruloid-related papers and returns a list of dicts,
one per paper, with fields: pmid, title, authors, journal, year, abstract, doi.

Uses Biopython's Entrez module, which wraps NCBI's free E-utilities API.
No API key is required — just an email address (set in config.py).
"""

import time
from Bio import Entrez
from config import ENTREZ_EMAIL, SEARCH_QUERIES, YEAR_START, YEAR_END

Entrez.email = ENTREZ_EMAIL

# How many results to fetch per query (PubMed has ~400 gastruloid papers total)
MAX_RESULTS_PER_QUERY = 500


def search_pubmed(query: str) -> list[str]:
    """Return a list of PMIDs matching a query, filtered by year range."""
    full_query = f"({query}) AND ({YEAR_START}[PDAT]:{YEAR_END}[PDAT])"
    handle = Entrez.esearch(db="pubmed", term=full_query, retmax=MAX_RESULTS_PER_QUERY)
    record = Entrez.read(handle)
    handle.close()
    return record["IdList"]


def fetch_details(pmid_list: list[str]) -> list[dict]:
    """
    Fetch full metadata for a list of PMIDs in batches of 100.
    Returns a list of paper dicts.
    """
    papers = []
    batch_size = 100

    for start in range(0, len(pmid_list), batch_size):
        batch = pmid_list[start : start + batch_size]
        ids = ",".join(batch)

        handle = Entrez.efetch(db="pubmed", id=ids, rettype="xml", retmode="xml")
        records = Entrez.read(handle)
        handle.close()

        for article in records["PubmedArticle"]:
            papers.append(_parse_article(article))

        # Be polite to NCBI servers — max 3 requests/second without an API key
        time.sleep(0.4)

    return papers


def _parse_article(article: dict) -> dict:
    """Extract the fields we care about from a raw PubMed XML record."""
    medline = article["MedlineCitation"]
    art     = medline["Article"]

    # Title
    title = str(art.get("ArticleTitle", ""))

    # Abstract — may be structured (list of sections) or plain text
    abstract = ""
    abstract_data = art.get("Abstract", {}).get("AbstractText", "")
    if isinstance(abstract_data, list):
        abstract = " ".join(str(s) for s in abstract_data)
    else:
        abstract = str(abstract_data)

    # Authors — Last FM format joined by ", "
    author_list = art.get("AuthorList", [])
    authors = []
    for a in author_list:
        last  = a.get("LastName", "")
        fore  = a.get("ForeName", "")
        authors.append(f"{last} {fore}".strip())
    authors_str = ", ".join(authors)

    # Journal and year
    journal = str(art.get("Journal", {}).get("Title", ""))
    pub_date = art.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
    year = str(pub_date.get("Year", pub_date.get("MedlineDate", "")[:4]))

    # PMID and DOI
    pmid = str(medline["PMID"])
    doi  = ""
    for loc in article.get("PubmedData", {}).get("ArticleIdList", []):
        if str(loc.attributes.get("IdType", "")) == "doi":
            doi = str(loc)
            break

    # MeSH terms (useful for cross-checking our keyword classification)
    mesh_list = medline.get("MeshHeadingList", [])
    mesh_terms = [str(m["DescriptorName"]) for m in mesh_list]

    return {
        "pmid":     pmid,
        "title":    title,
        "authors":  authors_str,
        "journal":  journal,
        "year":     year,
        "abstract": abstract,
        "doi":      doi,
        "mesh":     "; ".join(mesh_terms),
    }


def fetch_all_papers() -> list[dict]:
    """
    Run all search queries from config.py, collect PMIDs, deduplicate,
    then fetch full metadata. Returns a list of paper dicts.
    """
    print("Searching PubMed...")
    all_pmids = set()

    for query in SEARCH_QUERIES:
        pmids = search_pubmed(query)
        print(f"  '{query}' → {len(pmids)} results")
        all_pmids.update(pmids)
        time.sleep(0.4)

    print(f"\n{len(all_pmids)} unique papers found. Fetching metadata...\n")
    papers = fetch_details(list(all_pmids))
    print(f"Done. {len(papers)} papers retrieved.")
    return papers
