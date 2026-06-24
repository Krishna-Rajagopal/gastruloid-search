# Presentation Protocol — Gastruloid Variability & Literature GRN
**Meeting with André Dias + postdoc**
**Prepared by: Krishna Rajagopal, Hormoz Lab, Harvard Medical School**

---

## Format

- 6 slides, target 15–20 min talk + 20 min discussion
- Slides are sparse by design — most detail lives in speaker notes
- Live demo option: have Streamlit app open in browser for Slide 4

---

## SLIDE 1 — Title

**Title:** Systematic extraction of the gastruloid gene regulatory network from the experimental literature

**Subtitle:** A computational pipeline to map signaling evidence onto the DevSim minimal model

**Speaker notes:**
> "I want to walk you through a tool I've been building to answer a specific question: given everything published on gastruloids, what do we actually know with confidence about the GRN, and how does that compare to what DevSim assumes? The goal today is partly to show you what I've extracted, but mostly to get your input on what's reliable and what's missing."

---

## SLIDE 2 — The question and the model

**Title:** What determines where a gastruloid lands in morphological space?

**Body:**
- Gastruloids show a **continuous spectrum** of morphologies — elongated, multi-lobed, asymmetric, spherical — shaped by culture conditions, GRN noise, and signaling interactions not fully captured by any current model
- **DevSim** (Guan et al. 2025): minimal mechanistic model — outer/inner cell populations, adhesion (α) + chemotaxis (β) parameters, timer gene G1 feeding a bistable Wnt/Nodal (G2/G3) mutual inhibition circuit
- **The gap:** which edges in DevSim are experimentally grounded, and is the wiring sufficient to explain morphological diversity — or are inputs missing?

**Visual left:** Grid of 9 gastruloid images showing full morphological spectrum (see Gemini prompt A below)
**Visual right:** DevSim Fig. 5B circuit (G1 → G2 ⊣ G3, G3 ⊣ G2; outer/inner labels)

**Speaker notes:**
> "This isn't just 'why do some gastruloids elongate and others don't' — that framing makes it binary. The real phenomenon is a distribution across a morphological landscape, and that distribution shifts depending on CHIR dose, cell number, cell line, passage. The question I'm building toward is whether DevSim's parameter space can reproduce those shifts, or whether the model needs new biology. Beccari 2018 showed that even under well-controlled conditions you get a spread of aspect ratios — nobody has cleanly explained whether that's GRN stochasticity, pipetting variability, or something about the bistable circuit itself. André, what's your intuition on the dominant source of that spread?"

---

## SLIDE 3 — The pipeline

**Title:** 156 papers → 982 structured GRN observations

**Body:**
```
PubMed 2014–2025  →  156 papers  →  Classification (pathway / phenotype / species)
     ↓
Abstract extraction     439 obs   (Claude API, all papers)
Full-text extraction    532 obs   (73/156 open-access via PMC)
Manual curation          11 obs
     ↓
982 observations  ·  source-ranked  ·  DevSim-mapped  ·  interactive curation interface
```

**Visual:** Gemini pipeline diagram (see prompt B below)

**Speaker notes:**
> "Each step makes deliberate choices. Abstract extraction is fast but shallow — it captures direction-of-effect but misses quantitative data. Full-text extraction adds figure references and an evidence-type field distinguishing 'this paper's experiments' from 'cited claim' from 'interpretive review.' The deduplication keeps the highest-quality source when the same observation appears in multiple tiers. After filtering for high-confidence, direct, perturbation-type edges — the ones that actually constrain a model — you're down to about 80 observations. The Curate tab in the app lets me annotate those manually after this meeting based on your input."

---

## SLIDE 4 — GRN results

**Title:** Literature-derived GRN: what the evidence actually supports

**Body:**
- **[Live demo or screenshot — GRN tab, Tier 1 view]**
- Edge color: green (consensus activating) · red (consensus inhibitory) · amber (conflicting)
- Edge width ∝ independent papers

**DevSim parameter categories and literature support:**

| Category | Parameter / edge | Biological identity | Literature support |
|---|---|---|---|
| **GRN topology** | Wnt (G2) ⊣ Nodal (G3) | β-catenin ⊣ SMAD2/3 | ⚠️ conflicting: 1 inh (Dias 2025) / 1 act (Massey 2019) |
| **GRN topology** | Nodal (G3) ⊣ Wnt (G2) | SMAD2/3 ⊣ β-catenin | ⚠️ conflicting: same two papers |
| **GRN topology** | G1 → Wnt/Nodal onset | **CHIR pulse** (most likely) — exogenous GSK3β inhibitor that decays; upstream candidates in GRN: OTX2, TGF-β, BMP (all shown activating Wnt, but likely bidirectional in reality) | no CHIR = spheroids only; G1 is probably the CHIR stimulus itself |
| **GRN — downstream** | Wnt → TBXT | β-catenin → Brachyury | ✓ strongly supported ~12 papers |
| **GRN — downstream** | BMP → posterior identity | BMP4 → CDX2/posterior | ✓ moderate ~7 papers |
| **Physical (α)** | α_oo, α_ii, α_io | outer/inner cell adhesion — layer formation | not constrained by GRN literature |
| **Physical (β)** | β_oo, β_io | outer/inner chemotaxis — directed movement | not constrained by GRN literature |
| **Unmapped** | FGF ↔ BMP | FGF8 ↔ BMP4 crosstalk | ~5 papers; absent from DevSim |
| **Unmapped** | Retinoic acid → anterior | RA → OTX2/anterior | ~4 papers; absent from DevSim |
| **Alternative pathway** | SUMOylation inhibition → elongation | hypoSUMOylation drives CHIR-independent morphogenesis | Traboulsi 2023 (in corpus); alternate GRN entry point |

**Speaker notes:**
> "The physical parameters — α and β — govern cell sorting and movement and aren't constrained by the GRN literature at all; those have to come from morphological fitting. The GRN topology is what this tool addresses. The downstream edges — Wnt→TBXT, BMP→posterior — are well-supported and I'd treat them as fixed.
>
> The G1 identity is worth discussing. I initially suggested TBXT, but that's wrong — the circuit diagram shows Wnt activating TBXT, so TBXT is downstream of G2, not upstream. The GRN graph does show OTX2, TGF-β, and BMP all activating Wnt, which makes them upstream G1 candidates — but these are almost certainly bidirectional relationships that appear unidirectional in our data because of experimental context. The most compelling G1 candidate is actually CHIR itself: without CHIR, gastruloids form spheroids and don't elongate, which means CHIR is the necessary initiating input. It's also a natural timer because it gets metabolised. The interesting exception is SUMOylation inhibition — Traboulsi 2023 showed that hypoSUMOylated aggregates can elongate without CHIR, which implies an alternative GRN entry point that bypasses G1 entirely and may illuminate other wiring. André, does G1 correspond to anything biologically specific in your view, or is it purely a model abstraction for the CHIR stimulus?"

---

## SLIDE 5 — What the literature can't yet answer

**Title:** Three gaps between what we have and what we need

**Body:**

1. **Morphological distributions are not reported**
   Almost no paper reports a full shape distribution (n ≥ 30) — let alone across a condition sweep. Representative images dominate. We can't fit a model to data that doesn't exist in the literature.

2. **Protocol heterogeneity is uncontrolled**
   CHIR ranges 3–12 µM, aggregate size 300–1000 cells, diverse cell lines. When papers contradict each other on GRN wiring, they may both be right at their protocol's operating point.

3. **The field is 10 years old**
   ~80 high-confidence perturbation observations total. Most papers report expression patterns, not causal experiments.

**Speaker notes:**
> "These aren't fatal — they just change the inference strategy. For point 1: if André's lab has unpublished morphological distributions, or knows of a paper I've missed that reports them systematically, that's the single highest-value data input for everything downstream. For point 2: the protocol heterogeneity is actually useful if we treat it as a multi-condition fitting target — a model that reproduces why high CHIR gives more elongated gastruloids than low CHIR is much more constrained than one fit to a single condition. For point 3: this is where DevSim's existing topology becomes an asset — we can use it as a structural prior and update it only where the evidence is unambiguous, rather than trying to learn the whole GRN from scratch."

---

## SLIDE 6 — Discussion + next steps

**Title:** Where this goes next

**Body:**

**GRN ground truth**
- Which papers anchor the wiring? → manual curation + directed full-text review of André's recommendations
- Wnt/Nodal conflict (Massey vs. Dias): protocol artefact or genuine context-dependence?

**Culture conditions as model input**
- CHIR is likely G1 — does a systematic dose-response with quantitative morphological readout exist?
- If yes: use condition sweep to constrain DevSim parameter fitting across regimes
- SUMOylation inhibition (Traboulsi 2023) as alternative GRN entry point — worth examining what wiring it reveals

**Morphological data gap**
- Extract shape distributions from Beccari 2018, Suppinger 2023
- What is the hardest phenotype to explain — the one no current model captures?

**Longer-term: model validation**
- Sweep DevSim parameter space; compare simulated morphological distributions to literature
- ABC-SMC to fit parameters to real distributions if data available

**Speaker notes:**
> "I've organised this around three threads rather than a flat list of questions, because they're connected. The GRN thread and the culture conditions thread both feed into the model validation thread — you can't fit DevSim parameters without knowing which GRN edges to hold fixed and what morphological distributions to fit to.
>
> On GRN ground truth: the single most useful output from this conversation is a list of papers André considers authoritative. That directly drives what I manually curate next. The Wnt/Nodal conflict is the most pressing specific question — if André thinks it's a protocol artefact, we can resolve it by looking at CHIR concentrations across those two papers. If it's genuine context-dependence, that's a more interesting biological problem.
>
> On culture conditions: CHIR is almost certainly G1 in DevSim — without it, you get spheroids, not elongation. That means varying CHIR is the most direct experimental handle on G1, and a systematic dose-response with quantitative morphological readout is the single most useful experiment for model fitting. The SUMOylation paper is interesting precisely because it bypasses CHIR — it must activate Wnt or an equivalent signal through a different route, and understanding that route might reveal GRN wiring that CHIR-based experiments obscure.
>
> The longer-term computation — sweeping DevSim parameters and eventually ABC-SMC — is contingent on having the morphological data. I'm flagging it as the destination, not the current step."

---

## Appendix: Gemini image generation prompts

### A. Gastruloid morphological landscape (Slide 2, left panel)

> "Create a scientific illustration for an academic presentation slide showing the full spectrum of gastruloid morphological variability. Arrange 9–12 gastruloid shapes in a loose grid, roughly ordered from most to least morphologically complex. Include: 2 clearly elongated with a distinct anterior-posterior axis (aspect ratio ~2.5, subtle blue-to-red AP gradient, slightly tapered posterior end), 2 partially elongated with irregular or asymmetric shape, 2 with multi-lobed or bifurcated morphology, 2 compact but slightly asymmetric, and 2 spherical. Each shape should have a subtle cell-boundary texture and a semi-transparent surface. All shapes at the same scale. Dark background (#1a1a2e). No text labels. Style: Nature Cell Biology figure panel, clean, no cartoonish features. Do not show any scale bar or axes."

### B. Pipeline diagram (Slide 3)

> "Create a clean scientific diagram for an academic presentation showing a bioinformatics data pipeline. The diagram should be horizontal with 6 numbered steps connected by right-pointing arrows. Use a dark navy background (#1a1a2e) with white text and teal accent colors.
>
> Step 1 (icon: database): 'PubMed / NCBI Entrez' — subtitle: '156 papers, 2014–2025'
> Step 2 (icon: tag): 'Classification' — subtitle: 'Pathway · Phenotype · Species'
> Step 3 (icon: document): 'Abstract Extraction' — subtitle: '439 observations · Claude API'
> Step 4 (icon: open book): 'Full-Text Extraction' — subtitle: '532 observations · 73 PMC papers'
> Step 5 (icon: funnel): 'Normalize & Deduplicate' — subtitle: 'Manual > Fulltext > Abstract'
> Step 6 (icon: network): 'GRN + Curation Interface' — subtitle: '982 total observations'
>
> Small teal count badge below each step. Arrows thick and slightly rounded. Style: Nature Methods figure panel, minimal sans-serif font, 16:9 widescreen."

### C. DevSim GRN circuit (Slide 2, right panel)

> "Create a gene regulatory network diagram for an academic presentation slide. Three labeled circle nodes: 'G1 / CHIR input' in grey on the left (representing the exogenous Wnt agonist that acts as a timer), 'G2 / Wnt·β-catenin' in blue top-right, 'G3 / Nodal·SMAD2/3' in orange bottom-right. Green arrows from G1 to both G2 and G3 (labeled 'activates'). Red blunt-ended inhibition arrows between G2 and G3 in both directions (labeled 'inhibits' — make this mutual inhibition the most visually prominent feature). A separate green arrow from G2 pointing down-right to a smaller node labeled 'TBXT' (labeled 'activates'), showing Wnt's downstream output. Dashed boundary labeled 'outer cells' loosely around G2, dashed boundary labeled 'inner cells' loosely around G3. Dark navy background (#1a1a2e), white text, clean sans-serif. Style: Nature Reviews Molecular Cell Biology circuit diagram."
