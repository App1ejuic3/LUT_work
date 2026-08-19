"""
overlap_schema.py

Defines the schema for the tract-pair overlap table that will eventually
hold Dice coefficients and percent-overlap values between LUT tracts.

This is a RELATIONAL table, not a matrix. Each row is one (tract_a, tract_b)
pair. The N x N matrix used for visualization is generated FROM this table
(see build_overlap_matrix.py), never stored directly -- storing it as a
matrix would mean ~8000+ mostly-empty cells for ~91 tracts and would need
restructuring every time a row is added to the main LUT.

tract_a / tract_b reference `clean_label` in the main LUT as a soft foreign
key. No enforced join here (CSV has no FK constraints) but
validate_overlap_table() checks both labels exist in the current LUT before
any pair is accepted.
"""

import pandas as pd
from pathlib import Path

OVERLAP_COLUMNS = [
    'tract_a',              # clean_label of first tract (alphabetically first, see normalize_pair)
    'tract_b',              # clean_label of second tract
    'overlap_type',         # 'spatial' (measured) or 'nomenclature_only' (definitional judgment, unmeasured)
    'dice_coefficient',     # 2|A∩B| / (|A|+|B|) -- symmetric. N/A until spatial data exists.
    'percent_overlap_a',    # |A∩B| / |A| as a percent -- what fraction of A's volume sits inside B
    'percent_overlap_b',    # |A∩B| / |B| as a percent -- what fraction of B's volume sits inside A
    'basis',                # how it was computed: space (e.g. MNI152), n subjects, mask type (volumetric/streamline density)
    'source_a',             # atlas/toolbox the tract_a mask came from
    'source_b',             # atlas/toolbox the tract_b mask came from
    'notes',                # free text -- e.g. "definitions both reference genu of CC as boundary"
    'date_added',           # ISO date the pair was logged
    'status',                # 'flagged' | 'computed' | 'verified'
]

REQUIRED_ON_CREATE = ['tract_a', 'tract_b', 'overlap_type', 'source_a', 'source_b', 'status']


def normalize_pair(tract_a: str, tract_b: str) -> tuple[str, str]:
    """
    Force alphabetical order so (A,B) and (B,A) are never logged as two
    separate rows. Dice coefficients are symmetric, so the pair itself
    is unordered even though percent_overlap_a/b are not.
    """
    a, b = tract_a.strip(), tract_b.strip()
    return (a, b) if a.lower() <= b.lower() else (b, a)


def empty_overlap_table() -> pd.DataFrame:
    return pd.DataFrame(columns=OVERLAP_COLUMNS)


def validate_overlap_table(overlap_df: pd.DataFrame, lut_df: pd.DataFrame) -> list[str]:
    """
    Returns a list of validation problems (empty list = clean).
    Checks:
      - tract_a/tract_b exist as clean_label values in the current LUT
      - no duplicate (tract_a, tract_b) pairs after normalization
      - overlap_type is one of the two allowed values
      - if overlap_type == 'spatial', dice/percent fields should not all be blank
        (a spatial row with no numbers logged yet should be status='flagged', not 'computed')
    """
    problems = []
    valid_labels = set(lut_df['clean_label'].str.strip().str.lower())

    seen_pairs = set()
    for i, row in overlap_df.iterrows():
        a, b = normalize_pair(str(row['tract_a']), str(row['tract_b']))
        pair_key = (a.lower(), b.lower())

        if a.lower() not in valid_labels:
            problems.append(f"Row {i}: tract_a '{a}' not found in LUT clean_label column")
        if b.lower() not in valid_labels:
            problems.append(f"Row {i}: tract_b '{b}' not found in LUT clean_label column")
        if pair_key in seen_pairs:
            problems.append(f"Row {i}: duplicate pair ({a}, {b})")
        seen_pairs.add(pair_key)

        if row['overlap_type'] not in ('spatial', 'nomenclature_only'):
            problems.append(f"Row {i}: overlap_type must be 'spatial' or 'nomenclature_only', got '{row['overlap_type']}'")

        if row['overlap_type'] == 'spatial' and row['status'] == 'computed':
            has_numbers = any(
                pd.notna(row.get(c)) and str(row.get(c)).strip() not in ('', 'N/A')
                for c in ['dice_coefficient', 'percent_overlap_a', 'percent_overlap_b']
            )
            if not has_numbers:
                problems.append(f"Row {i}: status='computed' but no dice/percent values present")

    return problems


def add_pair(overlap_df: pd.DataFrame, tract_a: str, tract_b: str, overlap_type: str,
             source_a: str, source_b: str, notes: str = '', basis: str = 'N/A',
             dice_coefficient='N/A', percent_overlap_a='N/A', percent_overlap_b='N/A',
             status: str = 'flagged') -> pd.DataFrame:
    """
    Adds one normalized, deduplicated pair to the overlap table.
    Use this instead of manually appending rows -- it enforces alphabetical
    ordering and prevents (A,B)/(B,A) duplicates.
    """
    a, b = normalize_pair(tract_a, tract_b)

    existing = overlap_df[
        (overlap_df['tract_a'].str.lower() == a.lower()) &
        (overlap_df['tract_b'].str.lower() == b.lower())
    ]
    if len(existing) > 0:
        raise ValueError(f"Pair ({a}, {b}) already exists in overlap table at index {existing.index[0]}")

    from datetime import date
    new_row = {
        'tract_a': a, 'tract_b': b, 'overlap_type': overlap_type,
        'dice_coefficient': dice_coefficient,
        'percent_overlap_a': percent_overlap_a, 'percent_overlap_b': percent_overlap_b,
        'basis': basis, 'source_a': source_a, 'source_b': source_b,
        'notes': notes, 'date_added': date.today().isoformat(), 'status': status,
    }
    return pd.concat([overlap_df, pd.DataFrame([new_row])], ignore_index=True)
