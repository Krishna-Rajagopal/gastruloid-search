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

**DevSim homology (key rows):**

| Edge | DevSim | Literature | Status |
|---|---|---|---|
| Wnt → TBXT | activates | ~12 papers | ✓ strongly supported |
| BMP → posterior | activates | ~7 papers | ✓ moderate support |
| Wnt ⊣ Nodal | inhibits | 1 inh / 1 act | ⚠️ conflicting |
| Nodal ⊣ Wnt | inhibits | 1 inh / 1 act | ⚠️ conflicting |
| FGF ↔ BMP crosstalk | absent | ~5 papers | unmapped |

**Speaker notes:**
> "The most important thing on this graph is the amber Wnt↔Nodal edge. Massey 2019 describes them as synergistic — each promoting the other in the context of primitive streak specification. André's 2025 paper describes mutual inhibition — which is what DevSim also assumes. These may not be contradictory if the relationship is concentration- or context-dependent, but the literature currently can't distinguish these. That's the single highest-value question to resolve for model validation. The unmapped edges — FGF/BMP, Retinoic acid, YAP1/mechanosensing — appear in 3–5 papers each but aren't in DevSim. I don't know yet whether they matter for variability or are second-order. That's a judgment call I need from you."

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

**Title:** Questions for André + where this goes next

**Body:**

**Questions:**
- Which papers do you consider ground truth for GRN wiring?
- How do you read the Massey vs. Dias Wnt/Nodal discrepancy?
- Does your lab have quantitative morphological distributions (n ≥ 30) across conditions?
- Which unmapped edges (FGF, RA, YAP1) matter most for morphological variability?
- What is the 'hardest' morphological phenotype to explain — the one no current model captures?

**Immediate next steps:**
- Manual curation of high-priority GRN edges based on this conversation
- Directed full-text review of ~10 papers André flags as authoritative
- Extract quantitative shape data from Beccari 2018, Suppinger 2023

**Longer-term:**
- Homotopy check: sweep DevSim parameters, compare simulated morphological distributions
- Multi-condition ABC-SMC fitting if shape distribution data becomes available

**Speaker notes:**
> "The tool is in a state where manual curation is the highest-leverage activity — the AI extraction gets us 80% of the way there efficiently, but the next increment has to come from expert judgment. The longer-term computational track — fitting DevSim parameters to morphological distributions using ABC-SMC — is only tractable once we have the right data. ABC-SMC is approximate Bayesian computation: you run the simulation many times with different parameter values, compare the output statistics to observed data, and build up a posterior distribution over parameters. It doesn't require writing down a likelihood function, which is why it's attractive for a spatial model like DevSim. But the bottleneck is data, not computation, so I'm flagging it as a possibility rather than a plan."

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

> "Create a gene regulatory network diagram for an academic presentation slide. Three labeled circle nodes: 'G1 Timer' in grey on the left, 'G2 Wnt' in blue top-right, 'G3 Nodal' in orange bottom-right. Green arrows from G1 to both G2 and G3 (labeled 'activates'). Red blunt-ended inhibition arrows between G2 and G3 in both directions (labeled 'inhibits'). The G2↔G3 mutual inhibition should be visually prominent. Dashed boundary labeled 'outer cells' around G2, dashed boundary labeled 'inner cells' around G3. Dark navy background, white text, clean sans-serif. Style: Nature Reviews circuit diagram."
