"""
classify.py
-----------
Tags each paper with species, signaling pathways, and phenotype categories.
Also applies a relevance filter so only papers genuinely about gastruloid
development pass through to the CSV.

A paper is considered relevant if:
  - "gastruloid" appears in its title  (primary subject, high confidence)
  - OR "gastruloid" is in the abstract AND at least one RELEVANCE_TERM is too
    (abstract mentions it in a developmental biology context)

Papers where species cannot be identified as human or mouse are dropped,
because the DevSim comparison requires knowing which system is being studied.
"""

from config import (
    GENE_CATEGORIES,
    PHENOTYPE_CATEGORIES,
    SPECIES_KEYWORDS,
    RELEVANCE_TERMS,
)


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _matching_categories(text: str, category_dict: dict) -> list[str]:
    """Return category names whose keyword list has at least one hit in text."""
    return [
        cat for cat, keywords in category_dict.items()
        if _contains_any(text, [kw.lower() for kw in keywords])
    ]


# ── Relevance filter ────────────────────────────────────────────────────────

def is_relevant(paper: dict) -> bool:
    """
    Return True if this paper is primarily about gastruloid development
    and has an identifiable species (human or mouse).
    """
    title    = paper.get("title",    "").lower()
    abstract = paper.get("abstract", "").lower()

    # 1. Must mention gastruloid somewhere
    if "gastruloid" not in title and "gastruloid" not in abstract:
        return False

    # 2. Must discuss actual gastruloid biology, not just cite a study in passing.
    #    If "gastruloid" is in the title we trust the paper is on-topic.
    #    If it's only in the abstract, require at least one relevance term.
    if "gastruloid" not in title:
        if not _contains_any(abstract, RELEVANCE_TERMS):
            return False

    # 3. Species must be identifiable, OR the paper has "gastruloid" in its
    #    title (which is strong enough evidence on its own — some high-value
    #    papers say "mammalian stem cells" rather than naming the species).
    species = _detect_species(title + " " + abstract)
    if species == "unspecified" and "gastruloid" not in title:
        return False

    return True


# ── Species detection ────────────────────────────────────────────────────────

def _detect_species(text: str) -> str:
    text = text.lower()
    found_human    = _contains_any(text, [k.lower() for k in SPECIES_KEYWORDS["human"]])
    found_mouse    = _contains_any(text, [k.lower() for k in SPECIES_KEYWORDS["mouse"]])
    found_mammal   = _contains_any(text, [k.lower() for k in SPECIES_KEYWORDS.get("mammalian", [])])
    if found_human and found_mouse:
        return "both"
    if found_human:
        return "human"
    if found_mouse:
        return "mouse"
    if found_mammal:
        return "mammalian"   # species not pinned but clearly a stem-cell/gastruloid paper
    return "unspecified"


# ── Per-paper classification ─────────────────────────────────────────────────

def classify_paper(paper: dict) -> dict:
    """Add species, gene_pathways, phenotypes, genes_found columns."""
    searchable = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()

    paper["species"]       = _detect_species(searchable)
    paper["gene_pathways"] = "; ".join(_matching_categories(searchable, GENE_CATEGORIES))
    paper["phenotypes"]    = "; ".join(_matching_categories(searchable, PHENOTYPE_CATEGORIES))

    # Flat list of specific keyword hits — handy for quick scanning
    hits = []
    for keywords in GENE_CATEGORIES.values():
        hits += [kw for kw in keywords if kw.lower() in searchable]
    paper["genes_found"] = "; ".join(sorted(set(hits)))

    return paper


# ── Batch entry point ────────────────────────────────────────────────────────

def classify_all(papers: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Classify and filter all papers.
    Returns (relevant_papers, dropped_papers) as separate lists.
    """
    print("Classifying and filtering papers...")

    relevant = []
    dropped  = []

    for paper in papers:
        classify_paper(paper)
        if is_relevant(paper):
            relevant.append(paper)
        else:
            dropped.append(paper)

    species_counts = {}
    for p in relevant:
        s = p["species"]
        species_counts[s] = species_counts.get(s, 0) + 1

    print(f"  Kept {len(relevant)} relevant papers  |  Dropped {len(dropped)} off-topic")
    print(f"  Species breakdown: {species_counts}")
    print(f"  Papers with pathway tag:  {sum(1 for p in relevant if p['gene_pathways'])}")
    print(f"  Papers with phenotype tag: {sum(1 for p in relevant if p['phenotypes'])}")
    return relevant, dropped
