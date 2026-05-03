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

from pathlib import Path
import pandas as pd

folder = Path("/Users/applejuiceleigh/Documents/GitHub/LUT_work/Pestilli_lab/LUT_contents")

# find all csv files in that folder
files = list(folder.glob("*.csv"))

print(files)  # optional: check that files were found

dfs = []

for file in files:
    df = pd.read_csv(file)
    dfs.append(df)

for df in dfs:
    for col in final_columns:
        if col not in df.columns:
            df[col] = None

def merge_synonyms(row):
    s1 = str(row.get("synonyms", ""))
    s2 = str(row.get("Synonyms_uberon", ""))

    combined = s1 + ";" + s2
    parts = [x.strip() for x in combined.split(";") if x.strip()]

    return "; ".join(sorted(set(parts)))
df["synonyms"] = df.apply(merge_synonyms, axis=1)
df = df[final_columns]
final_df = pd.concat(dfs, ignore_index=True)

# drop duplicates
'''
final_df = final_df.drop_duplicates(
    subset=["Id_uberon", "Id_snomed"],
    keep="first"
)
'''
final_df.to_csv("./ontology_merged.csv", index=False)