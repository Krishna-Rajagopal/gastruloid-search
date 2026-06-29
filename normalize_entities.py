"""
normalize_entities.py
---------------------
Canonicalizes entity names in observations.csv so that the GRN Summary tab
groups observations correctly (e.g. 'WNT', 'WNT signaling', 'Wnt signaling'
are all the same entity and should aggregate together).

Writes:
  data/observations.csv          — updated in-place (original columns preserved)
  data/observations_prenorm.csv  — backup of original

The original values are preserved in entity_a_raw / entity_b_raw columns so
nothing is irreversibly lost.

Run:
    python3 normalize_entities.py

Check the diff:
    python3 normalize_entities.py --dry-run
"""

import sys
import pandas as pd

OBSERVATIONS_CSV = "data/observations.csv"
BACKUP_CSV       = "data/observations_prenorm.csv"

# ---------------------------------------------------------------------------
# Canonical entity names
# Mapping: raw value → canonical value
# Conservative: only normalize when the entities are unambiguously the same thing.
# Retain specificity where it matters (BMP2 ≠ BMP4, FGF2 ≠ FGF).
# ---------------------------------------------------------------------------

ENTITY_A_MAP = {
    # Wnt
    "WNT":                          "Wnt",
    "WNT signaling":                "Wnt",
    "Wnt activation":               "Wnt",
    "Wnt modulation":               "Wnt",
    "Wnt pathway activator":        "Wnt",
    "Wnt signaling":                "Wnt",
    "Wnt signaling memory":         "Wnt",
    "β-catenin":                    "β-catenin/Wnt",  # downstream effector, keep near-but-distinct
    # WNT and BMP4 is a combination — keep as-is

    # Nodal / TGF-β
    "NODAL":                        "Nodal",
    "TGF-beta":                     "TGF-β",
    "TGF-beta ligands":             "TGF-β",
    "TGF-beta ligands followed by FGF and VEGF": "TGF-β",
    "TGF-β signaling":              "TGF-β",
    "TGF-β signaling and p-Enh-eRNA": "TGF-β",
    "TGFβ receptors":               "TGF-β",

    # BMP
    "Bmp":                          "BMP",
    "BMP signaling":                "BMP",
    "NOG":                          "NOGGIN",

    # FGF
    "FGF signalling":               "FGF",
    "Fgf":                          "FGF",

    # ERK / MAPK
    "Erk phosphorylation":          "ERK",
    "Erk signaling":                "ERK",

    # TBXT / Brachyury
    "T/Bra":                        "TBXT",
    "TBXT dosage reduction":        "TBXT",
    "TBXT dose":                    "TBXT",

    # E-cadherin
    "E-CADHERIN":                   "E-cadherin",
    "E-cadherin expressing cells":  "E-cadherin",
    "E-cadherin relocalization":    "E-cadherin",
    "E-cadherin/CDH1":              "E-cadherin",
    "E-cadherin/CDH1 to N-cadherin":"E-cadherin",
    "E-cadherin/cell-cell contact": "E-cadherin",

    # Retinoic acid
    "RA":                           "Retinoic acid",
    "RA signaling suppression":     "Retinoic acid",
    "RA-gastruloid specification":  "Retinoic acid",
    "retinoic acid biosynthesis":   "Retinoic acid",
    "retinoic acid supplementation":"Retinoic acid",
    "CHIR & RA-pre-treated cells":  "CHIR99021 + Retinoic acid",
    "CHIR99021 & retinoic acid":    "CHIR99021 + Retinoic acid",

    # EMT / Snail family
    "Snai1":                        "Snail",
    "Snail/Slug/Twist":             "Snail",

    # ROCK / Rho
    "Rho kinase pathway":           "ROCK signaling",

    # Akt
    "Akt phosphorylation":          "Akt signaling",
}

ENTITY_B_MAP = {
    # Wnt
    "WNT signaling competence":         "Wnt",
    "Wnt pathway (via Frzb glycosylation)": "Wnt",
    "Wnt signaling":                    "Wnt",
    "Wnt signaling pathway":            "Wnt",
    "Wnt/β-catenin pathway":            "Wnt",
    "WNT signaling":                    "Wnt",
    "WNT signaling pathway":            "Wnt",
    "canonical WNT signaling":          "Wnt",
    "Wnt activity":                     "Wnt",
    "Wnt/β-catenin signaling":          "Wnt",
    "β-catenin signaling":              "β-catenin/Wnt",

    # Nodal / TGF-β
    "NODAL":                            "Nodal",
    "Nodal expression":                 "Nodal",
    "NODAL signaling":                  "Nodal",
    "Nodal signaling":                  "Nodal",
    "TGF-β gradient formation":         "TGF-β",
    "TGF-β signaling":                  "TGF-β",
    "TGF-β signaling response in pluripotent cells": "TGF-β",
    "Tgfβ/Activin signaling":           "TGF-β",
    "activin signaling":                "TGF-β",
    "SMAD2/3":                          "SMAD2/3",
    "SMAD2 signaling":                  "SMAD2/3",
    "SMAD2/3 signaling":                "SMAD2/3",
    "pSMAD1":                           "SMAD2/3",   # BMP downstream, grouped for GRN
    "SMAD1 phosphorylation":            "SMAD2/3",
    "SMAD1/SMAD4 signaling":            "SMAD2/3",

    # BMP
    "BMP signaling":                    "BMP",
    "BMP signaling pathway":            "BMP",
    "BMP4 signaling":                   "BMP4",

    # FGF
    "FGF signaling":                    "FGF",
    "FGF8 expression":                  "FGF8",

    # TBXT / Brachyury
    "T/Bra expression":                 "TBXT",
    "TBXT differentiation":             "TBXT",
    "TBXT (Brachyury)":                 "TBXT",
    "T/BRA expression":                 "TBXT",
    "Brachyury":                        "TBXT",
    "Brachyury expression":             "TBXT",

    # ERK
    "Erk pattern":                      "ERK",
    "Erk signaling":                    "ERK",

    # E-cadherin
    "E-cadherin/CDH1":                  "E-cadherin",
    "E-cadherin/CDH1 persistence":      "E-cadherin",
    "E-cadherin-mediated cell contacts":"E-cadherin",

    # OTX2
    "OTX2 expression":                  "OTX2",

    # SOX2
    "Sox2":                             "SOX2",
    "SOX2 expression":                  "SOX2",

    # AP axis (spatial context — not a molecular entity, keep as-is)
    "A-P axis formation":               "AP axis",
    "AP axis formation":                "AP axis",

    # RA
    "RA signaling":                     "Retinoic acid",

    # Snail
    "Snail":                            "Snail",
}

# ---------------------------------------------------------------------------
# Relationship normalization (conservative — only collapse near-synonyms)
# ---------------------------------------------------------------------------

RELATIONSHIP_MAP = {
    # Activating
    "drives":    "activates",
    "triggers":  "activates",
    "causes":    "activates",

    # Inhibiting
    "impairs":   "inhibits",

    # Keep distinct: abolishes, reduces, enhances, required_for, affects, modulates, etc.
    # 'affects' is intentionally kept vague — it was used when direction was unclear
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def normalize(df: pd.DataFrame, dry_run: bool = False) -> pd.DataFrame:
    df = df.copy()

    # Preserve raw values
    if "entity_a_raw" not in df.columns:
        df["entity_a_raw"] = df["entity_a"]
    if "entity_b_raw" not in df.columns:
        df["entity_b_raw"] = df["entity_b_or_context"]

    a_changed = df["entity_a"].map(ENTITY_A_MAP).notna()
    b_changed = df["entity_b_or_context"].map(ENTITY_B_MAP).notna()
    r_changed = df["relationship"].map(RELATIONSHIP_MAP).notna()

    if dry_run:
        print("\n=== entity_a changes ===")
        for _, row in df[a_changed].iterrows():
            print(f"  {row['entity_a']!r:45s} → {ENTITY_A_MAP[row['entity_a']]!r}")
        print(f"\n  ({a_changed.sum()} rows affected)")

        print("\n=== entity_b_or_context changes ===")
        for _, row in df[b_changed].iterrows():
            print(f"  {row['entity_b_or_context']!r:55s} → {ENTITY_B_MAP[row['entity_b_or_context']]!r}")
        print(f"\n  ({b_changed.sum()} rows affected)")

        print("\n=== relationship changes ===")
        for _, row in df[r_changed].iterrows():
            print(f"  {row['relationship']!r:20s} → {RELATIONSHIP_MAP[row['relationship']]!r}")
        print(f"\n  ({r_changed.sum()} rows affected)")
        return df

    df["entity_a"]           = df["entity_a"].map(ENTITY_A_MAP).fillna(df["entity_a"])
    df["entity_b_or_context"]= df["entity_b_or_context"].map(ENTITY_B_MAP).fillna(df["entity_b_or_context"])
    df["relationship"]       = df["relationship"].map(RELATIONSHIP_MAP).fillna(df["relationship"])

    print(f"entity_a updated:           {a_changed.sum()} rows")
    print(f"entity_b_or_context updated:{b_changed.sum()} rows")
    print(f"relationship updated:        {r_changed.sum()} rows")
    return df


def top_edges(df: pd.DataFrame, obs_type: str = None):
    d = df.copy()
    if obs_type:
        d = d[d["observation_type"] == obs_type]
    grp = (
        d.groupby(["entity_a", "relationship", "entity_b_or_context"])["pmid"]
        .nunique()
        .reset_index(name="papers")
        .sort_values("papers", ascending=False)
    )
    return grp


def main():
    dry_run = "--dry-run" in sys.argv

    df = pd.read_csv(OBSERVATIONS_CSV)
    print(f"Loaded {len(df)} observations from {OBSERVATIONS_CSV}")

    if dry_run:
        print("\n--- DRY RUN (no files written) ---")
        normalize(df, dry_run=True)
        return

    # Backup
    df.to_csv(BACKUP_CSV, index=False)
    print(f"Backup written → {BACKUP_CSV}")

    # Normalize
    df_norm = normalize(df)

    # Show top edges after normalization
    print("\nTop 15 perturbation edges after normalization:")
    print(top_edges(df_norm, obs_type="perturbation").head(15).to_string(index=False))

    print("\nTop 15 edges (all types) after normalization:")
    print(top_edges(df_norm).head(15).to_string(index=False))

    df_norm.to_csv(OBSERVATIONS_CSV, index=False)
    print(f"\nSaved → {OBSERVATIONS_CSV}")


if __name__ == "__main__":
    main()
