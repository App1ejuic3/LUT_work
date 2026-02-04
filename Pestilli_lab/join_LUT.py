import pandas as pd

# Load the CSVs
snomed_file = 'csvOutput/WMT_LUT_SNOMED_results.csv'  
uberon_file = 'csvOutput/WMT_LUT_UBERON_results.csv' 

snomed_df = pd.read_csv(snomed_file, sep='\t')
uberon_df = pd.read_csv(uberon_file, sep='\t')
snomed_df.columns = snomed_df.columns.str.strip()
uberon_df.columns = uberon_df.columns.str.strip()


# Inspect the first few rows to confirm loading
'''
print("SNOMED columns:", snomed_df.columns.tolist())
print(snomed_df.head(3))
print("\nUBERON columns:", uberon_df.columns.tolist())
print(uberon_df.head(3))
'''

# Merge on 'Label' with a full outer join
merged_df = pd.merge(
    snomed_df,
    uberon_df,
    on='Label',
    how='outer',
    suffixes=('_snomed', '_uberon')
)

# Inspect the merged result
print("\nMerged DataFrame:")
print(merged_df.head(10))

# Save the merged CSV
merged_df.to_csv('merged_white_matter.csv', index=False, sep='\t')
print("\nMerged CSV saved as 'merged_white_matter.csv'")
