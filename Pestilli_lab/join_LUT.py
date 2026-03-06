import pandas as pd
import re
from pathlib import Path

# Load the CSVs
snomed_file = 'csvOutput/WMT_LUT_SNOMED_results_mar.csv'  
uberon_file = 'csvOutput/WMT_LUT_UBERON_results_mar.csv' 

snomed_df = pd.read_csv(snomed_file, sep=',')
uberon_df = pd.read_csv(uberon_file, sep=',')
snomed_df.columns = snomed_df.columns.str.strip()
uberon_df.columns = uberon_df.columns.str.strip()


# Inspect the first few rows to confirm loading
'''
print("SNOMED columns:", snomed_df.columns.tolist())
print(snomed_df.head(3))
print("\nUBERON columns:", uberon_df.columns.tolist())
print(uberon_df.head(3))
'''
# Function to clean SNOMED labels
def clean_snomed_label(label):
    label = label.strip().lower()
    label = re.sub(r'^structure of ', '', label)  # remove "Structure of" prefix
    label = re.sub(r' structure$', '', label)     # remove "structure" suffix
    label = re.sub(r' of brain$', '', label)     # remove "of brain" suffix
    label = re.sub(r'^\s+|\s+$', '', label)      # remove extra whitespace
    return label

# Apply cleaning
snomed_df['clean_label'] = snomed_df['Label'].apply(clean_snomed_label)
uberon_df['clean_label'] = uberon_df['Label'].str.lower().str.strip()

# Merge on clean_label (PRIMARY KEY)
# -------------------
merged_df = pd.merge(
    snomed_df,
    uberon_df,
    on='clean_label',
    how='outer',
    suffixes=('_snomed', '_uberon')
)

# -------------------
# Merge SNOMED synonym-related columns
# -------------------
synonym_cols = [
    'Synonyms_snomed',
    'Annotation: alternative label',
    'Annotation: preferred label'
]

def merge_synonyms(row):
    """
    Merge synonym-related columns into a single column.
    input: pandas series (row) -- containing the synonym-related columns
    delete the original synonym-related columns after merging
    output: string -- merged synonyms separated by ' ; ' or pd.NA if none
    """
    values = []
    for col in synonym_cols:
        if col in row and pd.notna(row[col]):
            values.append(str(row[col]))
    # Optionally, drop the original synonym-related columns
    for col in synonym_cols:
        if col in row:
            row.drop(col, inplace=True)
    return ' ; '.join(values) if values else pd.NA

merged_df['synonyms'] = merged_df.apply(merge_synonyms, axis=1)

# -------------------
# Column reordering
# -------------------
preferred_order = [
    'clean_label',
    'Id_snomed',
    'Id_uberon',
    'Label_uberon',
    'Label_snomed',
    'synonyms',
    'Definition'
]

# Keep remaining columns after preferred ones
remaining_cols = [c for c in merged_df.columns if c not in preferred_order]
merged_df = merged_df[preferred_order + remaining_cols]


# Inspect the merged result
# print("\nMerged DataFrame:")
# print(merged_df.head(10))

# Save the merged CSV
merged_df.to_csv('./csvOutput/merged_white_matter_part2.csv', index=False, sep='\t')
print("\nMerged CSV saved as './csvOutput/merged_white_matter_part2.csv'")
