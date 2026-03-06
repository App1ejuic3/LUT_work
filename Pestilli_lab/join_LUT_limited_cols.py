'''
Joins SnowMED and UBERON tables but only keeps a limited amount of the columns
final_columns = [
    "clean_label",
    "Abbreviation",
    "Id_snomed",
    "Id_uberon",
    "Label_uberon",
    "Label_snomed",
    "to_merge?",
    "Definition",
    "LLM_definition",
    "Similar Entity",
    "synonyms",
    "Incoming: subClassOf",
    "Annotation: database_cross_reference",
    "Incoming: part of - uberon",
    "Synonyms_uberon",
    "IRI"
]
'''
import pandas as pd
import re
from pathlib import Path

# Load the CSVs
snomed_file = 'csvOutput/WMT_LUT_SNOMED_results_mar.csv'
uberon_file = 'csvOutput/WMT_LUT_UBERON_results_mar.csv'

snomed_df = pd.read_csv(snomed_file)
uberon_df = pd.read_csv(uberon_file)

snomed_df.columns = snomed_df.columns.str.strip()
uberon_df.columns = uberon_df.columns.str.strip()

# -------------------
# Clean SNOMED labels
# -------------------
def clean_snomed_label(label):
    label = str(label).strip().lower()
    label = re.sub(r'^structure of ', '', label)
    label = re.sub(r' structure$', '', label)
    label = re.sub(r' of brain$', '', label)
    return label.strip()

snomed_df['clean_label'] = snomed_df['Label'].apply(clean_snomed_label)
uberon_df['clean_label'] = uberon_df['Label'].str.lower().str.strip()

# -------------------
# Merge on clean_label
# -------------------
merged_df = pd.merge(
    snomed_df,
    uberon_df,
    on='clean_label',
    how='outer',
    suffixes=('_snomed', '_uberon')
)

# -------------------
# Merge SNOMED synonym columns
# -------------------
synonym_cols = [
    'Synonyms_snomed',
    'Annotation: alternative label',
    'Annotation: preferred label'
]

def merge_synonyms(row):
    values = []

    for col in synonym_cols:
        if col in row and pd.notna(row[col]):
            values.extend(str(row[col]).split(';'))

    if 'Synonyms_uberon' in row and pd.notna(row['Synonyms_uberon']):
        values.extend(str(row['Synonyms_uberon']).split(';'))

    cleaned = {v.strip().lower() for v in values if v.strip()}

    return ' ; '.join(sorted(cleaned)) if cleaned else pd.NA

merged_df['synonyms'] = merged_df.apply(merge_synonyms, axis=1)

# -------------------
# Rename ID columns
# -------------------
merged_df = merged_df.rename(columns={
    'Id_snomed_snomed': 'Id_snomed',
    'Id_uberon_uberon': 'Id_uberon'
})

# -------------------
# Ensure required columns exist
# -------------------
final_columns = [
    "clean_label",
    "Abbreviation",
    "Id_snomed",
    "Id_uberon",
    "Label_uberon",
    "Label_snomed",
    "to_merge?",
    "Definition",
    "LLM_definition",
    "Similar Entity",
    "synonyms",
    "Incoming: subClassOf",
    "Annotation: database_cross_reference",
    "Incoming: part of - uberon",
    "Synonyms_uberon",
    "IRI"
]

for col in final_columns:
    if col not in merged_df.columns:
        merged_df[col] = pd.NA

# -------------------
# Reorder columns to schema
# -------------------
merged_df = merged_df[final_columns]

# -------------------
# Save output
# -------------------
merged_df.to_csv(
    './csvOutput/merged_white_matter_part2.csv',
    index=False,
    sep='\t'
)

print("Merged CSV saved as './csvOutput/merged_white_matter_part2.csv'")