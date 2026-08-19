"""
build_overlap_matrix.py

Generates an N x N tract-by-tract matrix from overlap/tract_overlap_pairs.csv
for visualization. The matrix is NEVER stored as a file you hand-edit --
it's regenerated from the pairs table every time. Edit the pairs table,
not the matrix.

Usage:
    python build_overlap_matrix.py

Outputs:
    csvOutput/overlap_matrix_dice.csv       -- Dice coefficients, symmetric, NaN where unmeasured
    csvOutput/overlap_matrix_flagged.csv    -- 1/0 matrix marking which pairs have ANY logged
                                                relationship (spatial or nomenclature_only),
                                                useful for spotting where attention is needed
                                                before numbers exist
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from overlap_schema import validate_overlap_table

LUT_PATH = '../June_master_v6_cleaned.csv'   # update to your actual current LUT filename
PAIRS_PATH = 'tract_overlap_pairs.csv'
OUT_DIR = Path('../csvOutput')


def build_matrices(lut_df: pd.DataFrame, pairs_df: pd.DataFrame):
    labels = sorted(lut_df['clean_label'].dropna().unique())
    n = len(labels)
    idx = {label.lower(): i for i, label in enumerate(labels)}

    dice_matrix = pd.DataFrame(np.nan, index=labels, columns=labels)
    flagged_matrix = pd.DataFrame(0, index=labels, columns=labels)

    for _, row in pairs_df.iterrows():
        a, b = str(row['tract_a']).strip(), str(row['tract_b']).strip()
        if a.lower() not in idx or b.lower() not in idx:
            continue  # validation step should catch this earlier; skip defensively here

        flagged_matrix.loc[a, b] = 1
        flagged_matrix.loc[b, a] = 1

        dice_val = row.get('dice_coefficient')
        if pd.notna(dice_val) and str(dice_val).strip() not in ('', 'N/A'):
            try:
                d = float(dice_val)
                dice_matrix.loc[a, b] = d
                dice_matrix.loc[b, a] = d  # Dice is symmetric
            except ValueError:
                pass

    # Diagonal: a tract trivially has Dice = 1.0 with itself
    for label in labels:
        dice_matrix.loc[label, label] = 1.0

    return dice_matrix, flagged_matrix


def main():
    lut_df = pd.read_csv(LUT_PATH, keep_default_na=False, na_values=[''])
    pairs_df = pd.read_csv(PAIRS_PATH, keep_default_na=False, na_values=[''])

    problems = validate_overlap_table(pairs_df, lut_df)
    if problems:
        print("VALIDATION ISSUES -- fix before trusting the matrix output:")
        for p in problems:
            print(f"  - {p}")
        print()

    dice_matrix, flagged_matrix = build_matrices(lut_df, pairs_df)

    OUT_DIR.mkdir(exist_ok=True)
    dice_matrix.to_csv(OUT_DIR / 'overlap_matrix_dice.csv')
    flagged_matrix.to_csv(OUT_DIR / 'overlap_matrix_flagged.csv')

    n_flagged_pairs = (flagged_matrix.values.sum()) // 2
    n_computed_pairs = pairs_df[
        pairs_df['dice_coefficient'].notna() &
        (pairs_df['dice_coefficient'].astype(str).str.strip() != 'N/A') &
        (pairs_df['dice_coefficient'].astype(str).str.strip() != '')
    ].shape[0]

    print(f"Matrix built: {len(dice_matrix)} x {len(dice_matrix)} tracts")
    print(f"Pairs flagged for relationship (spatial or nomenclature_only): {int(n_flagged_pairs)}")
    print(f"Pairs with an actual computed Dice coefficient: {n_computed_pairs}")
    print(f"Saved: {OUT_DIR / 'overlap_matrix_dice.csv'}")
    print(f"Saved: {OUT_DIR / 'overlap_matrix_flagged.csv'}")


if __name__ == '__main__':
    main()
