# Your email is sent to NCBI with each request — required by their terms of use.
ENTREZ_EMAIL = "ksrajagopal@college.harvard.edu"

# PubMed search queries. Results are pooled and deduplicated.
SEARCH_QUERIES = [
    "gastruloid",
    "gastruloid symmetry breaking",
    "gastruloid axis formation",
    "gastruloid Wnt Nodal patterning",
    "gastruloid elongation primitive streak",
]

YEAR_START = 2014
YEAR_END   = 2025

# ---------------------------------------------------------------------------
# Relevance filter
# A paper passes only if "gastruloid" appears in its title OR
# ("gastruloid" is in the abstract AND at least one term below is too).
# This removes papers that merely cite a gastruloid study in passing.
# ---------------------------------------------------------------------------
RELEVANCE_TERMS = [
    "patterning", "symmetry", "elongation", "anterior", "posterior",
    "primitive streak", "germ layer", "epiblast", "gastrulation",
    "wnt", "nodal", "bmp", "fgf", "cell fate", "self-organiz",
    "axis", "signaling", "differentiation", "specification",
]

# ---------------------------------------------------------------------------
# Signaling pathway categories — only the five that matter for DevSim.
# Wnt and Nodal are the two arms of the inside/outside bifurcation that
# the model directly implements.  BMP, FGF, and RA are the other
# experimentally manipulated pathways in the key gastruloid papers.
# ---------------------------------------------------------------------------
GENE_CATEGORIES = {
    "Wnt": [
        "wnt", "ctnnb1", "beta-catenin", "β-catenin",
        "chir99021", "chir", "tcf", "lef1", "axin",
    ],
    "Nodal": [
        "nodal", "smad2", "smad3", "activin", "foxh1",
        "lefty", "cripto", "nodal signaling",
    ],
    "BMP": [
        "bmp2", "bmp4", "bmp7", "smad1", "smad5",
        "noggin", "chordin", "bmp signaling",
    ],
    "FGF": [
        "fgf2", "fgf4", "fgf8", "fgfr",
        "fibroblast growth factor", "fgf signaling",
    ],
    "Retinoic acid": [
        "retinoic acid", " ra ", "rara", "rarb", "retinoid",
    ],
}

# ---------------------------------------------------------------------------
# Phenotype / outcome categories — tied directly to the questions DevSim asks.
# ---------------------------------------------------------------------------
PHENOTYPE_CATEGORIES = {
    "AP axis / symmetry breaking": [
        "symmetry break", "symmetry-break",
        "anteroposterior", "anterior-posterior", "a-p axis", "a/p axis",
        "axis formation", "axial polarit",
    ],
    "Elongation": [
        "elongat", "axial elongation", "body elongation",
    ],
    "Primitive streak / mesoderm induction": [
        "primitive streak", "gastrulat",
        "tbxt", "brachyury", " bra ", "mesoderm induction",
    ],
    "Germ layer specification": [
        "germ layer", "endoderm", "ectoderm", "neuroectoderm",
        "cell fate", "lineage specification", "sox17", "sox2 fate",
    ],
    "Inside-outside / radial patterning": [
        "inside-out", "inside.outside", "radial", "inner cell", "outer cell",
        "cell sort", "phase separat", "cell segregat", "differential adhesion",
    ],
    "Self-organization": [
        "self-organiz", "self organiz", "emergent", "spontaneous patterning",
    ],
    "Experimental variability / robustness": [
        "variab", "stochastic", "robustness", "reproducib",
        "size-dependent", "size dependent", "batch",
    ],
}

# ---------------------------------------------------------------------------
# Species detection — expanded to catch lines that don't say "mouse" explicitly
# ---------------------------------------------------------------------------
SPECIES_KEYWORDS = {
    "human": [
        "human", "hesc", "hpsc", "h9 ", " h9,", "rues",
        "human embryonic stem", "human gastruloid", "human pluripotent",
    ],
    "mouse": [
        "mouse", "mesc", "murine", "mouse gastruloid", "mouse embryonic stem",
        "epiblast stem cell", " esc ", "46c", "e14 esc", "r1 esc",
        "v6.5", "mouse stem cell",
    ],
    # Some papers say "mammalian stem cells" without naming the species.
    # These are kept (tagged "mammalian") rather than dropped.
    "mammalian": [
        "mammalian stem cell", "mammalian embryo", "mammalian gastruloid",
        "stem cell aggregate", "aggregates of stem cells", "pluripotent stem cell",
        "embryonic stem cell",
    ],
}

# ---------------------------------------------------------------------------
# DevSim parameter mapping
# Maps (entity_a, relationship, entity_b_or_context) tuples to DevSim model
# parameters. Used by extract.py to annotate each observation row.
# "unmapped" = candidate for GRN extension beyond current DevSim model.
# ---------------------------------------------------------------------------
DEVSIM_MAPPING = {
    # Spatial patterning → inside/outside cell populations
    ("wnt",    "high_in",    "outer cells"): "β_oo > 0 (outer-outer long-range attraction)",
    ("wnt",    "high_in",    "peripheral"): "β_oo > 0 (outer-outer long-range attraction)",
    ("nodal",  "high_in",    "inner cells"): "G1→G2 morphogen gradient (inside seeding)",
    ("nodal",  "high_in",    "core"): "G1→G2 morphogen gradient (inside seeding)",
    ("bmp",    "high_in",    "outer cells"): "BMP downstream of Wnt (not core GRN)",
    ("bmp",    "high_in",    "peripheral"): "BMP downstream of Wnt (not core GRN)",

    # GRN mutual inhibition — the bistability circuit (G2/G3)
    ("wnt",   "inhibits",  "nodal"): "G2–G3 mutual inhibition (bistability circuit)",
    ("nodal", "inhibits",  "wnt"):   "G2–G3 mutual inhibition (bistability circuit)",
    ("wnt",   "activates", "nodal"): "G2→G3 activation arm (check circuit logic)",
    ("nodal", "activates", "wnt"):   "G3→G2 activation arm (check circuit logic)",

    # Timer gene (G1) feeds bistability
    ("tbxt",  "activates", "wnt"):   "G1 timer → G2 (Wnt arm) activation",
    ("tbxt",  "high_in",   "anterior"): "TBXT/G1 anterior pole (asymmetric timer output)",
    ("tbxt",  "high_in",   "posterior"): "TBXT/G1 posterior pole (asymmetric timer output)",

    # Perturbation outcomes
    ("chir99021",        "enhances",  "elongation"): "Wnt↑ → β_oo increase + α_oo tuning",
    ("chir",             "enhances",  "elongation"): "Wnt↑ → β_oo increase + α_oo tuning",
    ("wnt activation",   "enhances",  "elongation"): "Wnt↑ → β_oo increase + α_oo tuning",
    ("nodal inhibition", "abolishes", "symmetry breaking"): "Nodal required for inside seeding (G1→G2)",
    ("nodal inhibition", "reduces",   "elongation"): "Nodal required for β_io (inner-outer force)",
    ("bmp inhibition",   "reduces",   "elongation"): "BMP modulates elongation (downstream)",
    ("fgf inhibition",   "reduces",   "elongation"): "FGF modulates elongation (downstream)",
    ("fgf",              "required_for", "elongation"): "FGF modulates elongation (downstream)",

    # Adhesion / mechanical → α parameters
    ("e-cadherin",       "required_for", "cell sorting"): "α_oo / α_ii differential adhesion",
    ("cdh1",             "required_for", "cell sorting"): "α_oo / α_ii differential adhesion",
    ("differential adhesion", "required_for", "inside-outside"): "α parameters set population segregation",
}
