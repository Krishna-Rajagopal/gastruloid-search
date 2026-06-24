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

**Title:** Gastruloid morphology is highly variable — and we don't know why

**Body:**
- Gastruloids produced under nominally identical conditions show a wide spectrum of morphologies: elongated, partially elongated, multi-lobed, spherical, fragmented
- This is not just a binary elongated/failed outcome — it is a **continuous morphological landscape**
- Multiple overlapping sources:
  - **Culture conditions**: CHIR dose, timing, cell number, cell line, passage number, media
  - **GRN noise**: stochastic gene expression, bistable switch firing
  - **Other signaling**: BMP, FGF, RA gradients — not all captured in DevSim
  - **Mechanical/physical**: aggregate geometry, cell sorting dynamics, surface tension
- The sources are not independent — CHIR dose changes the GRN operating point, which changes sensitivity to noise

**Central question:**
> *What determines where a gastruloid lands in morphological space — and can a minimal mechanistic model (DevSim) explain the observed distribution, or is the model missing key inputs?*

**Visual:** A 3×3 grid of bright-field gastruloid images showing diverse morphologies — elongated, asymmetric, spherical, multi-lobed — all from the same or comparable protocol. Source: Beccari 2018 or Suppinger 2023. No labels needed; let the diversity speak.

**Speaker notes:**
> "I want to be precise about what we're trying to explain. This isn't just 'why do some gastruloids elongate and others don't' — that framing makes it sound like a binary switch. The actual phenomenon is richer: you get a distribution across a morphological landscape, and that distribution shifts depending on culture conditions, noise, and presumably the GRN wiring. The question I'm building toward computationally is whether DevSim's parameter space can reproduce that landscape, or whether the model needs new biology. André, what in your experience is the dominant source of the morphological spread — protocol variation, or something intrinsic?"

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

**Title:** Culture conditions shift the morphological landscape — not just a confounder

**Body:**
- CHIR concentrations: 3–12 µM across 156 papers (fourfold range)
- Cell lines: mouse (v6.5, E14, CGR8), human (H9, H1, iPSC)
- Aggregate size: 300–1000 cells per aggregate
- Harvest timepoints: 72h–168h
- **Culture conditions are not merely a confounder — they move the system through parameter space, shifting the morphological distribution itself**
- Suppinger 2023: systematic variation of aggregate size and CHIR timing shifts outcome frequencies
- **Key gap: almost no paper reports a full morphological distribution (n ≥ 30) across a condition sweep in the same experiment**
- Without this, we cannot distinguish "CHIR dose changes the mean morphology" from "CHIR dose changes the variance"

**Speaker notes:**
> "I want to reframe this slide slightly from the version you might expect. Culture conditions aren't just noise in the dataset — they're actually part of what we're trying to model. If CHIR dose moves you from 40% elongated to 80% elongated, that's a shift in the morphological landscape, and a good model should reproduce it. The problem is that almost no paper systematically sweeps a condition and reports the full distribution. They show you the best-looking gastruloids, or representative images, or a mean. André, are there papers — published or unpublished — that actually report distributions across a condition sweep?"

---

## SLIDE 9 — The sparse data problem

**Title:** How do we model a continuous morphological landscape from sparse, heterogeneous data?

**Body:**

**The problem has three layers:**
1. **Literature sparsity**: 156 papers, but most report expression patterns or representative images — not morphological distributions. High-confidence perturbation observations: ~80 after filtering.
2. **Protocol heterogeneity**: GRN observations come from different CHIR doses, cell lines, timepoints — the GRN operating point varies across papers, so apparent contradictions may both be true
3. **Morphological underspecification**: the phenomenon we want to explain (the full shape landscape) is almost never directly measured in the same paper that reports a mechanistic perturbation

**Three complementary approaches:**

1. **DevSim as structural prior**
   Treat the minimal model's topology as a prior on GRN edge existence and sign. Update only where direct experimental evidence is strong. Advantage: avoids overfitting a 10-year-old field; keeps the model interpretable. The question is whether the prior is correctly specified — that's what the GRN extraction is testing.

2. **Homotopy evaluation**
   Can DevSim's parameter space (α, β, GRN rates) be swept to reproduce diverse morphological outcomes — elongated, spherical, multi-lobed — without changing topology? If yes, the wiring is sufficient and variability is parametric. If no, identify the minimum new edge that recovers missing behaviors.

3. **Cross-protocol comparison as a feature, not a bug**
   The fact that different protocols give different morphological distributions is *data*, not noise. A model that can reproduce the distribution shift between CHIR 3 µM and CHIR 8 µM is more constrained than one fit to a single condition. Use the culture conditions table to define a multi-condition fitting target.

**Speaker notes:**
> "The broadened question actually makes the modelling problem harder in one sense but more tractable in another. Harder: because I can't just fit to 'elongated vs. not elongated.' More tractable: because the variation across protocols is actually a richer constraint on the model than any single condition. If DevSim can reproduce why high CHIR gives more elongated gastruloids than low CHIR, that's a much stronger validation than just matching one distribution. The key question for this meeting is whether the data exists to do that — and whether the GRN we've extracted has the right inputs."

---

## SLIDE 10 — Computational next steps: ABC-SMC

**Title:** Approximate Bayesian Computation — Sequential Monte Carlo (ABC-SMC)

**Body:**

**Goal:** Infer posterior distributions over DevSim parameters given observed gastruloid morphological distributions — ideally across multiple conditions

**Parameters to infer:**
- α_oo, α_ii, α_io (adhesion — cell sorting and layer formation)
- β_oo, β_io (chemotaxis — directed migration)
- GRN rate constants (G1 decay rate, G2/G3 mutual inhibition strength, noise amplitude)

**Summary statistics — capturing the full morphological landscape, not just elongation:**
- Aspect ratio distribution at 96h and 120h (shape of the histogram, not just mean)
- Circularity distribution (distinguishes multi-lobed from smooth)
- Coefficient of variation of AR across a population (a direct readout of variability)
- Proportion in each morphological class: elongated / partially elongated / spherical / fragmented
- *(If fluorescence available)*: TBXT polarity index — fraction of aggregate with posterior marker

**Algorithm:**
```
1. Sample parameter vector θ from prior (DevSim topology + GRN literature constraints)
2. Run DevSim simulation → synthetic population of N gastruloids
3. Compute summary statistics vector S(sim)
4. Compare to observed S(data) — ideally across ≥2 conditions (e.g. CHIR 3µM vs 8µM)
5. Accept θ if distance(S(sim), S(data)) < ε
6. Iterate, tightening ε each SMC generation
→ Output: posterior p(θ | data) — where in parameter space can DevSim match the landscape?
```

**Multi-condition fitting** is the key advance over naive single-condition ABC:
a model that reproduces the morphological distribution under two different CHIR doses simultaneously is much more constrained, and more biologically meaningful

**Current bottleneck:** Morphological measurements from ≥50 gastruloids per condition, at ≥2 conditions

**Speaker notes:**
> "The important change here from standard ABC is the summary statistics. If I just use 'aspect ratio mean,' I'm throwing away most of the information. The shape of the distribution — is it bimodal? skewed? does the variance increase with CHIR? — is actually what discriminates between model variants. A noise-driven model gives a unimodal distribution with high variance; a bistable model gives a bimodal distribution. Those are different, and the summary statistics have to capture that difference. The second key point is multi-condition fitting: if the model can reproduce what happens under two CHIR doses, not just one, the parameter posterior is much narrower."

---

## SLIDE 11 — Questions for André (discussion guide)

**Title:** What I need from this conversation

**Body:**

**On the morphological landscape:**
- What morphological classes do you actually observe in practice? Is it a continuum or are there discrete attractors?
- Is the variability you see dominated by between-batch differences (protocol) or within-batch differences (intrinsic noise)?
- Does morphological outcome correlate with early reporter dynamics — e.g. can you predict the final shape from TBXT/Wnt expression at 48h?

**On ground truth:**
- Which 5 papers do you consider most mechanistically reliable for GRN wiring? *(to anchor manual curation)*
- Are there key papers missing from this corpus of 156?
- How do you read the Massey 2019 vs. Dias 2025 Wnt/Nodal discrepancy — protocol difference, or genuine biological context-dependence?

**On data availability:**
- Does your lab have quantitative morphological distributions (n ≥ 30) at ≥2 CHIR doses? *(This is the single highest-value dataset for ABC-SMC)*
- Are there unpublished condition sweeps — aggregate size, CHIR timing — that haven't made it into a paper yet?

**On model scope:**
- Is the G1 → G2/G3 timer wiring biologically motivated, or a modeling convenience?
- Which signaling axes not currently in DevSim (FGF, BMP, RA, YAP1/mechanosensing) do you think are most important for explaining morphological diversity — not just elongation, but the full spectrum?
- Is there a 'worst case' morphological phenotype — something the field has observed that no current model can explain?

**Speaker notes:**
> "I've structured these questions in three tiers deliberately. The first tier — what is the phenomenon — is actually the most important and most underspecified in the literature. If we don't agree on what we're trying to explain, we can't agree on what a good model looks like. The second tier gets at data: the single most useful thing that could come from this conversation is knowing whether a multi-condition morphological distribution already exists somewhere. The third tier is about model scope — and I want your biological intuition on which missing edges would actually change the outcome distribution, versus which are real but second-order."

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

### A. Gastruloid morphological landscape image (Slide 2)

> "Create a scientific illustration for an academic presentation slide showing the full spectrum of gastruloid morphological variability — not just elongated vs. spherical, but a continuum. Arrange 9–12 gastruloid shapes in a loose grid or arc, roughly ordered from most to least morphologically complex. Include: 2 clearly elongated with distinct AP axis (aspect ratio ~2.5, blue-to-red anterior-posterior gradient, slightly tapered posterior end), 2 partially elongated with irregular or asymmetric shape, 2 with a multi-lobed or bifurcated morphology, 2 compact but slightly asymmetric, and 2 spherical. Each shape should have a subtle cell-boundary texture and a semi-transparent surface. All shapes at the same scale. Dark background (#1a1a2e). No text labels. Style: Nature Cell Biology figure panel, clean, no cartoonish features, no faces. Do not show any scale bar or axes."

### B. ABC-SMC schematic (Slide 10)

> "Create a clean scientific diagram illustrating the Approximate Bayesian Computation Sequential Monte Carlo (ABC-SMC) algorithm for an academic talk slide. The diagram should show a circular loop with 4 labeled steps: (1) 'Sample θ from prior' with an icon of a probability distribution curve; (2) 'Run DevSim simulation' with an icon of a simple elongated oval shape (gastruloid); (3) 'Compute summary statistics: aspect ratio, % elongated, circularity' with a bar chart icon; (4) 'Accept if distance < ε' with a green checkmark for accept and a red cross for reject. An arrow from accept feeds back to 'Update prior → next SMC generation'. Below the loop: 'Output: posterior p(θ | data)' with a narrow bell curve compared to the wide prior. Color scheme: dark navy background, white text, teal accents. Style: clean, minimal, suitable for a computational biology talk."

### C. DevSim GRN circuit (Slide 3, alternative to copying from paper)

> "Create a gene regulatory network diagram for an academic presentation slide. Show three nodes as labeled circles: 'G1 (Timer)' in grey on the left, 'G2 Wnt' in blue in the top right, 'G3 Nodal' in orange in the bottom right. Draw a green arrow from G1 to G2 and a green arrow from G1 to G3 (both labeled 'activates'). Draw a red blunt-ended inhibition arrow from G2 to G3 and another from G3 to G2 (both labeled 'inhibits'). The G2↔G3 mutual inhibition should be visually prominent. Add a dashed outer boundary labeled 'outer cells' around G2 and a dashed inner boundary labeled 'inner cells' around G3. Dark navy background, white text, clean sans-serif font. Style: Nature Reviews Molecular Cell Biology circuit diagram."
