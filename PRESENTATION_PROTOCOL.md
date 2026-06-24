# Presentation Protocol — Gastruloid Variability & Literature GRN
**Meeting with André Dias + postdoc**
**Prepared by: Krishna Rajagopal, Hormoz Lab, Harvard Medical School**

---

## Format

- ~12 slides, target 25–30 min talk + 15–20 min discussion
- Slides 1–5: context + tool (move through quickly; Dias knows the biology)
- Slides 6–7: GRN results — spend most time here
- Slides 8–10: open questions — structured to elicit Dias's input
- Software: Google Slides or PowerPoint; use dark background (#1a1a2e or white)
- Live demo option: have Streamlit app open in browser for slide 6 (GRN tab)

---

## SLIDE 1 — Title

**Title:** Systematic extraction of the gastruloid gene regulatory network from the experimental literature

**Subtitle:** A computational pipeline to map signaling evidence onto the DevSim minimal model

**Speaker notes:**
> "I want to walk you through a tool I've been building to answer a specific question: given everything published on gastruloids, what do we actually know with confidence about the GRN, and how does that compare to what DevSim assumes? The goal today is partly to show you what I've extracted, but mostly to get your input on what's reliable and what's missing."

---

## SLIDE 2 — The biological question

**Title:** What drives variability in gastruloid symmetry breaking?

**Body:**
- Gastruloids under identical conditions produce a distribution of outcomes: elongated, partially elongated, and spherical
- Two distinct sources of variability:
  - **Intrinsic**: stochasticity in the GRN (Wnt/Nodal bistable switch fires probabilistically)
  - **Extrinsic**: sensitivity to protocol parameters (CHIR dose, cell number, passage)
- Distinguishing these has direct consequences for DevSim: intrinsic → add noise term; extrinsic → parameter regime shift; both → different model architecture

**Central question for this meeting:**
> *Does the DevSim GRN topology, as currently specified, have the right wiring to generate the observed variability distribution — or are edges missing or incorrectly signed?*

**Visual:** Two bright-field images side by side — one elongated gastruloid, one spherical — from any published paper (van den Brink 2014 or Beccari 2018 are ideal). Label: "Same protocol. Same batch."

**Speaker notes:**
> "This is the core tension. Beccari showed that even in well-controlled conditions, you get a distribution of aspect ratios — and nobody has really explained whether that distribution is a feature of the GRN itself or an artifact of pipetting variability. André, I suspect you've thought about this — I'd love to hear your intuition on which it is before I show you what the literature says."

---

## SLIDE 3 — DevSim: the starting point

**Title:** DevSim — a minimal mechanistic model of AP axis formation (Guan et al. 2025)

**Body:**
- Two cell populations: outer (O) and inner (I)
- Adhesion parameters α_oo, α_ii, α_io govern cell sorting
- Chemotaxis/migration parameters β_oo, β_io govern directed movement
- GRN: timer gene G1 → bistable Wnt (G2) / Nodal (G3) mutual inhibition circuit
- Model reproduces elongation and symmetry breaking *in silico*
- **Open question:** Which GRN edges are experimentally grounded, and which are inferred by necessity?

**Visual:** DevSim Fig. 5B circuit schematic (from Guan et al. 2025). Can recreate in slides as: G1 → [G2 ⊣ G3, G3 ⊣ G2], with outer/inner cell layer labels.

**Speaker notes:**
> "DevSim already has a minimal wiring diagram — G1 feeds a bistable Wnt/Nodal circuit. That's the model I'm trying to evaluate against the literature. The question I'll come back to is: is this topology sufficient, or do we need additional edges? And critically — is the Wnt/Nodal relationship inhibitory, activating, or context-dependent?"

---

## SLIDE 4 — The pipeline

**Title:** A systematic pipeline from PubMed to structured GRN observations

**Body (computational detail for slide):**

```
Step 1 — Literature retrieval
  Tool: fetch_papers.py via NCBI Entrez (Biopython)
  Query: ("gastruloid" OR "gastruloids") AND ("signaling" OR "gene expression" ...)
  Filters: 2014–2025, English, human/mouse
  Output: data/papers.csv — 156 papers

Step 2 — Classification
  Tool: classify.py
  Assigns: pathway tags (Wnt, Nodal, BMP, FGF, RA),
           phenotype tags (AP axis, elongation, symmetry breaking, variability...),
           species (human / mouse / both)

Step 3 — Abstract-level extraction
  Tool: extract.py → Claude Haiku API
  Input: each abstract
  Output: 439 structured observations (data/observations.csv, source="abstract")

Step 4 — Full-text extraction
  Tool: fetch_fulltext.py → PMC XML via Entrez
         extract_fulltext_grn.py → Claude Haiku API
  Coverage: 73/156 papers (open-access only)
  Sections used: Results + Discussion (not Methods)
  Output: 532 additional observations (source="fulltext")
  Extra fields: evidence_type (direct/cited/review), figure_ref

Step 5 — Normalization + deduplication
  Tool: normalize_entities.py
  Canonicalizes: "WNT" / "Wnt signaling" / "Wnt activation" → "Wnt"
  Deduplication priority: manual > fulltext > abstract
  Final corpus: 982 observations across 156 papers

Step 6 — Manual curation
  Interface: Streamlit app → Curate tab
  Allows: per-row review, confidence editing, adding manual observations
  Current manual rows: 11 (including Dias 2025 Wnt/Nodal key edges)
```

**Visual:** *See Gemini image generation prompt below*

**Speaker notes:**
> "Each step in this pipeline makes deliberate choices. I'm not treating a claim from a review article the same as a direct experimental result — the evidence_type field distinguishes those. And I'm not treating an abstract-level claim the same as a full-text figure result. The deduplication keeps the highest-quality source when the same observation appears multiple times. The total is 982 observations, which sounds like a lot, but once you filter for high-confidence, direct, perturbation-type edges, you're down to maybe 60–80 that are genuinely informative about the GRN."

---

### Gemini image generation prompt (pipeline diagram)

> **Paste this into Gemini with image generation enabled:**
>
> "Create a clean scientific diagram for an academic presentation showing a bioinformatics data pipeline. The diagram should be horizontal with 6 numbered steps connected by right-pointing arrows. Use a dark navy background (#1a1a2e) with white text and accent colors for icons/labels.
>
> Step 1 (icon: database): 'PubMed / NCBI Entrez' — subtitle: '156 papers, 2014–2025'
> Step 2 (icon: tag/label): 'Classification' — subtitle: 'Pathway · Phenotype · Species'
> Step 3 (icon: text document): 'Abstract Extraction' — subtitle: '439 observations · Claude API'
> Step 4 (icon: open book): 'Full-Text Extraction' — subtitle: '532 observations · 73 papers · PMC'
> Step 5 (icon: funnel/filter): 'Normalize & Deduplicate' — subtitle: 'Manual > Fulltext > Abstract'
> Step 6 (icon: network graph): 'GRN + Curation' — subtitle: '982 total observations'
>
> Below each step, show a small count badge in teal/green. The arrows between steps should be thick and slightly rounded. Overall aesthetic: Nature Methods figure panel, minimal, no decorative elements. Font: clean sans-serif. The diagram should fit a 16:9 widescreen slide at ~70% width, leaving room for a title above."

---

## SLIDE 5 — The web interface (brief)

**Title:** Interactive exploration via Streamlit app

**Body (screenshot or live demo):**
- **Papers tab**: 156 papers, filterable by year / species / pathway / phenotype
- **GRN Summary tab**: network diagram + entity manipulation counts
- **Observations tab**: all 982 rows, filterable
- **Culture Conditions tab**: protocol metadata per paper (CHIR dose, cell line, imaging)
- **Curate tab**: manual review and annotation interface

**Speaker notes:**
> "I'll show this briefly and then come back to it for the GRN. The key thing is the Curate tab — after this meeting, I'll use your input to manually annotate the high-priority edges, flag papers you consider ground truth, and correct anything the AI got wrong."

---

## SLIDE 6 — GRN results: the network

**Title:** Literature-derived GRN: 982 observations across 156 papers

**Body:**
- **[Use screenshot or live demo of the GRN tab — Tier 1 / experimental manipulation view]**
- Edge color encodes evidence consensus:
  - Green = all papers show activation
  - Red = all papers show inhibition
  - Amber = conflicting evidence (labelled N+/M−)
- Edge width ∝ number of independent papers
- Node color: blue = mouse, orange = human, green = both

**Highlight callout:**
> "Amber edge: Wnt ↔ Nodal — 1 paper activating (Massey 2019 PNAS), 1 paper inhibiting (Dias 2025 bioRxiv). This is the most critical unresolved question in the GRN."

**Speaker notes:**
> "The most important thing on this graph is the amber edge between Wnt and Nodal. Massey 2019 describes them as synergistic — each promoting the other in the context of primitive streak specification. Your 2025 paper describes mutual inhibition — which is what DevSim also assumes. These aren't necessarily contradictory if the relationship is context- or concentration-dependent, but I want to flag it explicitly. André, can you speak to how you'd reconcile these?"

---

## SLIDE 7 — GRN results: DevSim homology

**Title:** How well does DevSim's wiring match the experimental evidence?

**Body (table):**

| DevSim edge | Sign in DevSim | Literature support | Papers | Confidence |
|---|---|---|---|---|
| G1 (timer) → Wnt/Nodal onset | activates | indirect — TBXT precedes Wnt reporters | ~6 | medium |
| Wnt (G2) ⊣ Nodal (G3) | inhibits | **conflicting** (Massey 2019 / Dias 2025) | 2 | ⚠️ amber |
| Nodal (G3) ⊣ Wnt (G2) | inhibits | conflicting | 2 | ⚠️ amber |
| Wnt → TBXT (Brachyury) | activates | strong consensus | ~12 | high ✓ |
| BMP → posterior | activates | moderate consensus | ~7 | medium |

**Unmapped edges (extension candidates — not in DevSim):**
- FGF ↔ BMP crosstalk (~5 papers)
- Retinoic acid → anterior identity (~4 papers)
- YAP1 / mechanosensing → elongation (~3 papers)

**Speaker notes:**
> "The green edges — Wnt activating TBXT, BMP in the posterior — are well-supported and consistent with DevSim. The timer gene G1 is harder to evaluate because the literature doesn't use DevSim's notation — I'm inferring it from TBXT/SOX2 timing data. The unmapped edges are where things get interesting. FGF/BMP crosstalk appears in ~5 papers but isn't in DevSim at all. Does that matter for variability? That's a question only a computational experiment can answer."

---

## SLIDE 8 — Culture conditions

**Title:** Protocol diversity across 156 papers — a confounder for GRN inference

**Body:**
- CHIR concentrations: ranges from 3–12 µM across published protocols
- Cell lines: mouse (v6.5, E14, CGR8), human (H9, H1, iPSC)
- Aggregate size: 300–1000 cells per aggregate
- **Key gap: fewer than ~15 papers report quantitative shape distributions with n ≥ 30**
- Culture condition variation is a likely extrinsic source of variability — but has not been systematically tested

**Speaker notes:**
> "This slide is partly a caveat and partly a question. The CHIR concentration alone varies fourfold across the literature. When one paper says 'Wnt activates X' and another says 'Wnt inhibits X', they may both be right in their protocol — and this is why I didn't use culture conditions for statistical inference. André, in your lab's experience, how sensitive is the Wnt/Nodal relationship to CHIR dose?"

---

## SLIDE 9 — The sparse data problem

**Title:** How do we build a quantitative model when the field is 10 years old?

**Body:**

**The problem:**
- 156 papers, but most report expression patterns, not causal perturbation experiments
- High-confidence, direct perturbation observations: ~80 after filtering
- No paper reports a shape distribution with n ≥ 50 + mechanistic perturbation in the same experiment

**Three complementary approaches:**

1. **DevSim as structural prior**
   Use the minimal model's topology as a Bayesian prior on edge existence and sign.
   Update only where direct experimental evidence is strong and unambiguous.
   Advantage: avoids overfitting; preserves model interpretability.

2. **Homotopy evaluation**
   Ask: can DevSim's GRN be continuously deformed (parameter values only, no new edges) to match observed behavior? If yes → topology is sufficient. If no → identify which new edge resolves the discrepancy.
   In practice: sweep α/β/GRN rate constants in DevSim; compare simulated AR distribution to published distributions.

3. **Focus inference on conflict edges**
   The amber Wnt↔Nodal edge has maximum model-selection value.
   A single well-designed experiment (reporter line + genetic KO, not just CHIR) resolves the GRN topology more efficiently than 20 more descriptive papers.

**Speaker notes:**
> "The honest answer is that for ABC-SMC to work well, I need shape distributions with sample sizes that don't currently exist in the literature. So I'm thinking about this in two parallel tracks: use what exists to constrain the prior and check DevSim's topology, and identify what new data would most efficiently reduce model uncertainty. That second question is really one for you — what experiment would you design to resolve the Wnt/Nodal sign?"

---

## SLIDE 10 — Computational next steps: ABC-SMC

**Title:** Approximate Bayesian Computation — Sequential Monte Carlo (ABC-SMC)

**Body:**

**Goal:** Infer posterior distributions over DevSim parameters given observed gastruloid shape distributions

**Parameters to infer:**
- α_oo, α_ii, α_io (adhesion — cell sorting)
- β_oo, β_io (chemotaxis — directed migration)
- GRN rate constants (G1 decay rate, G2/G3 mutual inhibition strength)

**Summary statistics:**
- Aspect ratio distribution at 96h and 120h
- % elongated (AR > 1.5 threshold)
- Circularity distribution

**Algorithm:**
```
1. Sample parameter vector θ from prior (DevSim-informed)
2. Run DevSim simulation → synthetic gastruloid population
3. Compute summary statistics on synthetic population
4. Accept θ if distance(synthetic stats, observed stats) < ε
5. Iterate, tightening ε each generation (SMC)
→ Output: posterior p(θ | data)
```

**Current bottleneck:** Need morphological measurements from ≥50 gastruloids per condition as the observed target

**Questions for André:**
- Does your lab have unpublished AR distributions?
- Which published paper has the most reliable quantitative shape data?

**Speaker notes:**
> "ABC-SMC doesn't require likelihood evaluation — it just needs to run the model and compare outputs to data. The main bottleneck isn't computational, it's data: I need a real shape distribution to fit to. The literature mostly shows representative images, not distributions. If you have measurements sitting in a lab notebook somewhere, or know of a paper I've missed, that would unlock this whole approach."

---

## SLIDE 11 — Questions for André (discussion guide)

**Title:** What I need from this conversation

**Body:**

**On ground truth:**
- Which 5 papers do you consider mechanistically most reliable? *(to anchor high-confidence GRN curation)*
- Are there key papers missing from this corpus of 156?
- How do you read the Massey 2019 vs. Dias 2025 Wnt/Nodal discrepancy?

**On experimental design:**
- What single experiment would most efficiently resolve the GRN topology?
- Does your lab have quantitative shape distributions (n ≥ 30) that could serve as ABC targets?
- Is CHIR variation a genuine perturbation or a confounder? *(for deciding whether to include it in inference)*

**On the DevSim model:**
- Is the G1 → G2/G3 timer wiring biologically motivated, or a modeling convenience?
- Which unmapped edges (FGF/BMP, RA, YAP1) do you think matter most for variability?

**Speaker notes:**
> "I've been deliberately saving these questions rather than answering them computationally, because they need biological judgment. The tool is only as good as the ground truth it's anchored to — and that's what you can provide."

---

## SLIDE 12 — Summary

**Title:** Summary and immediate next steps

**Body:**

**What exists now:**
- 982 structured observations, 156 papers, 2014–2025
- Literature GRN with gradient confidence coloring
- Full-text extraction for 73 open-access papers
- Interactive curation interface

**Immediate next steps (this week, post-meeting):**
1. Manually annotate top-tier papers André identifies as ground truth
2. Resolve Wnt/Nodal conflict edge via directed full-text review
3. Extract quantitative shape data from Beccari 2018, Suppinger 2023 (manual)

**Medium-term (1–2 months):**
4. Homotopy check — sweep DevSim parameters, compare AR distributions
5. ABC-SMC pilot — if shape distribution data available
6. Add any papers André recommends

**Speaker notes:**
> "The tool is in a state where manual curation is the highest-leverage activity. The AI extraction got us to 982 observations efficiently, but the next 20% of quality improvement has to come from expert judgment — yours and ours. I'm hoping this meeting gives me a clear list of the 10–15 papers to read end-to-end and the 5–10 GRN edges to prioritize."

---

## Appendix: Additional Gemini image generation prompts

### A. Gastruloid biology intro image (Slide 2)

> "Create a scientific illustration showing gastruloid variability for an academic presentation slide. Show a row of 6–8 gastruloid cross-sections at the same scale with varying morphologies: 2 clearly elongated (aspect ratio ~2.5, with a visible anterior-posterior axis marked by a blue-to-red color gradient), 3 intermediate (partially elongated, irregular), and 2 spherical. Each shape should have a faint cell-boundary texture. Use a dark background. Include a small axis label below the elongated ones ('anterior' on the left in blue, 'posterior' on the right in red). Style: clean, Nature Cell Biology figure, no text except the axis labels. Do not include cartoon faces or stylized art."

### B. ABC-SMC schematic (Slide 10)

> "Create a clean scientific diagram illustrating the Approximate Bayesian Computation Sequential Monte Carlo (ABC-SMC) algorithm for an academic talk slide. The diagram should show a circular loop with 4 labeled steps: (1) 'Sample θ from prior' with an icon of a probability distribution curve; (2) 'Run DevSim simulation' with an icon of a simple elongated oval shape (gastruloid); (3) 'Compute summary statistics: aspect ratio, % elongated, circularity' with a bar chart icon; (4) 'Accept if distance < ε' with a green checkmark for accept and a red cross for reject. An arrow from accept feeds back to 'Update prior → next SMC generation'. Below the loop: 'Output: posterior p(θ | data)' with a narrow bell curve compared to the wide prior. Color scheme: dark navy background, white text, teal accents. Style: clean, minimal, suitable for a computational biology talk."

### C. DevSim GRN circuit (Slide 3, alternative to copying from paper)

> "Create a gene regulatory network diagram for an academic presentation slide. Show three nodes as labeled circles: 'G1 (Timer)' in grey on the left, 'G2 Wnt' in blue in the top right, 'G3 Nodal' in orange in the bottom right. Draw a green arrow from G1 to G2 and a green arrow from G1 to G3 (both labeled 'activates'). Draw a red blunt-ended inhibition arrow from G2 to G3 and another from G3 to G2 (both labeled 'inhibits'). The G2↔G3 mutual inhibition should be visually prominent. Add a dashed outer boundary labeled 'outer cells' around G2 and a dashed inner boundary labeled 'inner cells' around G3. Dark navy background, white text, clean sans-serif font. Style: Nature Reviews Molecular Cell Biology circuit diagram."
