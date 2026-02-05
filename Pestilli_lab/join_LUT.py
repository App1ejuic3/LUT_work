import pandas as pd
import re
from pathlib import Path

# Load the CSVs
snomed_file = 'csvOutput/WMT_LUT_SNOMED_results.csv'  
uberon_file = 'csvOutput/WMT_LUT_UBERON_results.csv' 

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

# Merge on cleaned label
merged_df = pd.merge(
    snomed_df,
    uberon_df,
    on='clean_label',
    how='outer',
    suffixes=('_snomed', '_uberon')
)

# Decide on Label column to show as primary key
# Prefer SNOMED original label if exists, otherwise use UBERON label
merged_df['Label'] = merged_df['Label_snomed'].combine_first(merged_df['Label_uberon'])

# Reorder columns: SNOMED ID, UBERON ID, Label, then all others
cols = ['Id_snomed', 'Id_uberon', 'Label'] + [c for c in merged_df.columns if c not in ['Id_snomed', 'Id_uberon', 'Label']]
merged_df = merged_df[cols]

# Inspect the merged result
print("\nMerged DataFrame:")
print(merged_df.head(10))

# Save the merged CSV
merged_df.to_csv('merged_white_matter.csv', index=False, sep='\t')
print("\nMerged CSV saved as 'merged_white_matter.csv'")
