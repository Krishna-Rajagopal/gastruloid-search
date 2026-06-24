# Gastruloid Literature Search Tool

**Hormoz Lab — Harvard Medical School / Dana-Farber Cancer Institute**

A computational tool for surveying and structuring the experimental literature on human and mouse gastruloid development, in support of the DevSim agent-based model of anterior-posterior axis formation.

---

## Background

Gastruloids are self-organizing 3D aggregates of embryonic stem cells that spontaneously break symmetry, elongate, and establish an anterior-posterior (A-P) axis — recapitulating key features of early mammalian gastrulation without extraembryonic tissues. The DevSim model (Hormoz Lab) reproduces this behavior using two cell populations (outer/peripheral and inner/core) coupled by short-range adhesion (α parameters), long-range chemotaxis-like forces (β parameters), and a gene regulatory network with a timer gene (G1) feeding a bistable Wnt/Nodal circuit (G2/G3).

This tool systematically compiles, classifies, and extracts knowledge from the gastruloid literature to:
- Identify what GRN wiring is experimentally supported across human and mouse systems
- Map experimental observations to DevSim parameters (α, β, G1/G2/G3)
- Flag gaps — experiments that no current DevSim configuration can reproduce, pointing to candidate new feedback loops

---

## Phase 1 — Literature Search and Classification

Pulls all gastruloid papers from PubMed (2014–2025) and classifies them by signaling pathway and developmental phenotype.

**Output:** `data/papers.csv` — 156 curated papers.

**Run:**
```
python3 run.py
```

**Explore interactively:**
```
python3 -m streamlit run app.py
```

### Classification scheme

| Pathways | Wnt, Nodal, BMP, FGF, Retinoic acid |
|---|---|
| Phenotypes | AP axis / symmetry breaking, Elongation, Primitive streak / mesoderm induction, Germ layer specification, Inside-outside / radial patterning, Self-organization, Experimental variability / robustness |
| Species | human, mouse, both, mammalian |

---

## Phase 2 — Abstract-Level Observation Extraction

Uses the Claude API (Haiku model) to read each abstract and extract structured biological observations: GRN edges, spatial expression patterns, perturbation outcomes, and expression timing. Each observation is mapped to a DevSim parameter where possible.

**Output:** `data/observations.csv` (abstract-level rows, `source = "abstract"`).

**Prerequisites:**
- Anthropic API key: `export ANTHROPIC_API_KEY="sk-ant-..."`
- Install dependency: `pip3 install anthropic`

**Run:**
```
python3 extract.py
```

---

## Phase 2.5 — Full-Text Extraction

Fetches open-access full text from PubMed Central (PMC) and re-extracts observations from Results and Discussion sections, yielding higher-confidence GRN edges with figure references and evidence-type labels.

### Step 1 — Fetch PMC full text

```
python3 fetch_fulltext.py
```

Downloads XML from PMC for each paper that has an open-access version. Saves Results and Discussion text as `data/fulltext/{pmid}.json`. Coverage: ~73 of 156 papers (open-access only; paywalled papers such as Beccari 2018 and Veenvliet 2020 are not accessible this way).

### Step 2 — Extract GRN observations from full text

```
python3 extract_fulltext_grn.py
```

Sends Results + Discussion sections to Claude and extracts observations with two additional fields:

| Field | Description |
|---|---|
| `evidence_type` | `direct` (this paper's experiments) · `cited` (references another paper) · `review` (interpretive claim, no new data) |
| `figure_ref` | Figure panel cited near the claim, e.g. `Fig. 3B` |

Output saved to `data/observations_fulltext.csv` (537 rows from 73 papers).

### Step 3 — Normalize entity names and merge

```
python3 normalize_entities.py        # canonicalize WNT → Wnt, etc.
python3 extract_fulltext_grn.py --merge   # deduplicate and append to observations.csv
```

Deduplication uses source-rank priority: manual > fulltext > abstract. Current `observations.csv`: **982 rows** (439 abstract · 532 fulltext · 11 manual).

### Step 4 — Extract culture condition metadata

```
python3 extract_uniform.py
```

Extracts protocol metadata per paper (CHIR concentration, cell line, aggregate size, imaging modality, variability metrics) into `data/extraction_table.csv`. Displayed in the **Culture Conditions** tab.

---

## Observation schema

| Field | Description |
|---|---|
| `observation_type` | `grn_edge` · `spatial_pattern` · `perturbation` · `expression_timing` |
| `entity_a` | Acting signal: Wnt, Nodal, BMP, FGF, RA, TBXT, SOX2, SOX17, … |
| `relationship` | `activates` · `inhibits` · `high_in` · `low_in` · `enhances` · `abolishes` · `required_for` · … |
| `entity_b_or_context` | Target gene or spatial context: `inner cells` · `outer cells` · `anterior` · `posterior` |
| `confidence` | `high` · `medium` · `low` |
| `supporting_quote` | Verbatim phrase from text |
| `needs_full_text` | Flagged when quantitative data likely exists in figures |
| `devSim_param` | Mapped DevSim parameter, or `unmapped` (extension candidate) |
| `source` | `abstract` · `fulltext` · `manual` |
| `evidence_type` | `direct` · `cited` · `review` (fulltext rows only) |
| `figure_ref` | Figure panel, e.g. `Fig. 3B` (fulltext rows only) |

---

## Web interface

```
python3 -m streamlit run app.py
```

Five tabs:

| Tab | Contents |
|---|---|
| **Papers** | Filterable table of all 156 papers; sidebar filters by year, species, pathway, phenotype |
| **GRN Summary** | Network diagram with gradient edge coloring (green = activating, red = inhibitory, amber = conflicting evidence, width ∝ paper count); entity manipulation counts; observation triplets |
| **Observations** | Full observations table with filters |
| **Culture Conditions** | Protocol metadata per paper: CHIR dose, cell line, aggregate size, imaging modality |
| **Curate** | Manual review and correction of observations; add new rows directly |

---

## Project structure

```
gastruloid-search/
├── config.py                 # Keyword lists, pathway/phenotype categories, DevSim mapping
├── fetch_papers.py           # PubMed query via NCBI Entrez (Biopython)
├── classify.py               # Relevance filter + per-paper pathway/phenotype tagging
├── run.py                    # Phase 1 entry point: fetch → classify → save CSV
├── extract.py                # Phase 2: abstract-level observation extraction
├── fetch_fulltext.py         # Phase 2.5: PMC full-text fetching
├── extract_fulltext_grn.py   # Phase 2.5: full-text GRN extraction (+ --merge flag)
├── extract_uniform.py        # Phase 2.5: culture condition metadata extraction
├── normalize_entities.py     # Entity name canonicalization
├── app.py                    # Streamlit web interface
├── requirements.txt          # Python dependencies
└── data/
    ├── papers.csv                # 156 curated papers
    ├── dropped.csv               # Filtered-out papers (audit trail)
    ├── observations.csv          # 982 structured observations (abstract + fulltext + manual)
    ├── observations_fulltext.csv # Raw full-text extraction output (pre-merge)
    ├── extraction_table.csv      # Culture condition metadata per paper
    └── fulltext/                 # PMC full-text JSON files ({pmid}.json), 155 files
```

---

## Dependencies

```
biopython    # PubMed API via NCBI Entrez
pandas       # Data manipulation
streamlit    # Web interface
anthropic    # Claude API (Phases 2 and 2.5)
networkx     # GRN network graph
matplotlib   # GRN visualization
```

Install: `pip3 install -r requirements.txt`
