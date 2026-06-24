# Gastruloid Literature Review Protocol

**Project:** DevSim parameterization — preliminary GRN inference and protocol landscape  
**Scope:** 152 PubMed papers (2015–2025); search documented in `config.py`  
**Deadline:** Wednesday presentation to Guoye Guan and Andre Dias

---

## Scientific objective

The goal is not to compile a list of what papers claim. It is to produce a preliminary
inference of the regulatory network governing gastruloid patterning — one that is grounded in
experimental evidence, distinguishes causal from correlational support, and is honest about
uncertainty.

**Why culture conditions matter for this:** A regulatory edge supported across diverse protocols
(different CHIR concentrations, cell lines, species, labs) is more likely to reflect genuine
biology than one observed only in a narrow regime. The extraction_table.csv is not metadata —
it is the covariate data that lets us assess whether each inferred edge is robust or
protocol-contingent.

**What "preliminary" means here:** The inference is coarse-grained and AI-assisted, not a
full Bayesian network estimation. But it is structured to be upgradeable: the observation
schema and evidence weighting can be refined as manual verification proceeds.

---

## Inferential framework for regulatory edges

For each candidate edge (entity_a → relationship → entity_b), evidence is stratified by
causal strength:

| Tier | Observation type | Causal strength | Example |
|---|---|---|---|
| 1 | Perturbation | Strongest — intervention changes outcome | "SB431542 (Nodal inhibitor) abolishes symmetry breaking" |
| 2 | Reporter dynamics / live imaging | Consistent with causality; not sufficient alone | "Wnt and Nodal reporters are spatially anticorrelated" |
| 3 | Correlation or GRN edge claimed in discussion | Weakest — may be circular or indirect | "Authors propose Wnt activates Nodal downstream" |

An edge is **causally well-supported** when:
- It has ≥1 Tier 1 observations (perturbation), AND
- The effect is consistent in direction across those experiments, AND
- It holds in ≥2 independent labs or across species

An edge is **provisionally supported** when it has only Tier 2–3 evidence.

The GRN Summary tab (observations.csv) already separates these: filter
`observation_type = perturbation` to see Tier 1 evidence only. Paper count alone is not a
sufficient criterion.

**Culture conditions as confound check:** For edges where all Tier 1 support comes from one
CHIR concentration, one cell line, or one species, the edge should be flagged as
protocol-contingent pending cross-condition replication. This check is done by cross-referencing
the supporting PMIDs against extraction_table.csv.

---

## Corpus completeness check (do first, ~30 min)

Verify these papers are in papers.csv. If absent, manually append a row with pmid, title,
authors, journal, year, abstract, species, gene_pathways:

| Paper | Status to verify |
|---|---|
| van den Brink et al. 2014, *Development* | Founding gastruloid paper |
| Beccari et al. 2018, *Nature* | Quantitative elongation distributions |
| Moris et al. 2020, *Nature* | Symmetry breaking, anterior identity |
| Veenvliet et al. 2020, *Science* | 3D morphology data |
| Dias et al. 2025, doi:10.1101/2025.01.11.632562 | Ground truth: Wnt↔Nodal mutual inhibition, Fig. 6 |
| Guan et al. 2025 (DevSim paper) | Model being parameterized |
| Chhabra et al. 2019, *PNAS*, doi:10.1073/pnas.1815363116 | Wnt/BMP/Nodal topology — missed by keyword, known absent |

---

## Automated extraction pipeline

**Run in order:**

```bash
python3 fetch_fulltext.py     # fetch PMC XML for all 152 PMIDs → data/fulltext/
python3 extract.py            # phenomenon list (GRN observations) → data/observations.csv
python3 extract_uniform.py    # uniform schema across all papers → data/extraction_table.csv
```

`fetch_fulltext.py` is already running. `extract.py` was run previously and produced
observations.csv. `extract_uniform.py` runs after fetch_fulltext.py finishes.

### What extract_uniform.py extracts (same fields for all 152 papers)

**Protocol:** cell_line · n_cells_per_aggregate · chir_uM · chir_onset_h · chir_offset_h ·
base_media · harvest_timepoints_h

**Imaging:** imaging_modalities · fluorescent_reporters

**Morphology:** morphology_quantified (Y/N/unclear) · morphology_metric · morphology_n ·
morphology_timepoint_h · elongation_pct · shape_distribution_figure (Y/N) ·
variability_addressed (Y/N)

**Mechanistic:** key_perturbation · key_finding (one sentence)

All absent fields are "not reported" — never inferred.

---

## Validation of AI extraction accuracy (~1h manual)

**Primary test — ground truth interaction:**  
Open Dias et al. 2025 (doi:10.1101/2025.01.11.632562), Figure 6. This paper directly
demonstrates Wnt activation inhibits Nodal and vice versa. In the GRN Summary tab, verify:
- (Wnt, inhibits, Nodal) appears with ≥3 papers, at least one classified as `perturbation`
- (Nodal, inhibits, Wnt) appears similarly

If both edges appear with perturbation-type support, the AI is correctly classifying
causal evidence. If they appear only as grn_edge (discussion claim), the observation_type
classification needs manual correction for these entries.

**Random QC sample (15 papers):**
```bash
python3 -c "
import pandas as pd
df = pd.read_csv('data/extraction_table.csv')
df.sample(15, random_state=42)[['pmid','title','full_text_source','cell_line','chir_uM','morphology_quantified','key_finding']].to_csv('data/qc_sample.csv', index=False)
print('Saved data/qc_sample.csv')
"
```
For each: open paper, check protocol fields and key_finding against source. Target: ≥80%
correct. If below threshold, revise the extraction prompt and re-run.

---

## Two-day schedule

### Day 1 — Extraction + network construction

1. Wait for `fetch_fulltext.py` to finish; run `extract_uniform.py`
2. Corpus completeness check (Step above) — add missing papers; re-run extractions for new PMIDs
3. Open app → GRN Summary tab:
   - Filter `observation_type = perturbation` — this is the causally defensible edge list
   - Note which edges have only Tier 2–3 support (candidates for manual upgrading)
4. For the top 10 edges by perturbation count: cross-reference PMIDs in extraction_table.csv —
   do they span multiple species? Multiple CHIR conditions? Multiple cell lines?
   Record: edge / N_perturbation / N_species / N_cell_lines / protocol_range

### Day 2 — Verification + synthesis

1. QC sample: verify 15 random papers against originals
2. For the 3–5 highest-priority edges (Wnt↔Nodal mutual inhibition, Wnt→elongation,
   Nodal→symmetry breaking): open the source papers, confirm observation_type classification,
   note which figures contain the perturbation data
3. Compile the evidence-weighted edge table (columns: edge / Tier 1 count / Tier 2 count /
   species covered / protocol diversity note)
4. Build slides (outline below)

---

## Slide outline for Wednesday

1. **Search and corpus** — 152 papers, documented queries, species/pathway breakdown (Papers tab)
2. **Preliminary regulatory network** — top edges ranked by Tier 1 (perturbation) support;
   distinguish solid lines (perturbation-supported) from dashed (correlation only)
3. **Network validation** — Wnt↔Nodal mutual inhibition: N independent perturbation experiments,
   consistent with Dias et al. 2025 Fig. 6; edge holds across mouse and human
4. **Protocol landscape** — culture conditions table from extraction_table.csv; CHIR range,
   cell lines, harvest times; which conditions have morphological outcome data
5. **DevSim alignment** — which inferred edges map to existing DevSim parameters; which are
   unmapped (extension candidates)
6. **Open questions + plan** — what causal evidence is missing; proposed next steps
   (full-text verification of key papers, ABC-SMC fitting, experimental design)
