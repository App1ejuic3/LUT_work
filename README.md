# LUT_work

**White Matter Tract Lookup Table — Ontology Alignment Pipeline**

Pestilli Lab, The University of Texas at Austin

Authors: Austin Leigh, Stephen Kiilu

Date: May 2, 2025

License: MIT

---
## Current White Matter tract Look Up Table (LUT)
An updated list of the current looktable with 69 different WM tracts listed can be found in the csvOutput folder, titled **8April_master.csv** [text](https://github.com/App1ejuic3/LUT_work/blob/main/csvOutput/8April_master.csv)
## Overview

White matter tract nomenclature is inconsistent across the neuroimaging community. Different research groups and software toolboxes — TRACULA, TractSeg, AFQ, DSI Studio, Brainlife WMC —  assign different names to the same anatomical structures, and many of these definitions overlap or conflict without a single anatomical definition (). This creates barriers to reproducibility and makes cross-study comparison unreliable.

This repository contains a Python pipeline that constructs a structured Lookup Table (LUT) mapping white matter tract labels across two major biomedical ontologies, SNOMED CT and UBERON, and integrates synonym data from both sources into a single, queryable schema. The resulting table covers approximately 65 white matter tracts and is intended to serve as a reference resource for researchers working toward standardized tract nomenclature within the Brain Imaging Data Structure (BIDS) framework.

---

## Repository Structure

```
LUT_work/
│
├── __init__.py                  # Package initializer; exposes library versions
│
├── onto_snomed.py               # Queries SNOMED CT terms via EBI OLS4 REST API
├── onto_uberon.py               # Queries UBERON terms via EBI OLS4 REST API
├── join_LUT.py                  # Merges SNOMED and UBERON outputs into unified schema
├── synonym_integration.ipynb    # Classifies and integrates 300+ synonyms into master table
│
├── csvOutput/                   # Generated outputs (created at runtime)
│   ├── WMT_LUT_SNOMED_results_mar.csv    # Raw SNOMED query results
│   ├── WMT_LUT_UBERON_results_mar.csv    # Raw UBERON query results
│   ├── merged_white_matter_part2.csv     # Merged schema output
│   ├── 8April_master_v5.csv              # Master LUT with integrated synonyms
│   └── misc.csv                          # Ambiguous/discarded synonym log
│
├── requirements.txt             # Python dependencies
└── README.md
```

---

## Pipeline Overview

The pipeline runs in four stages:

**1. Ontology Querying (`onto_snomed.py`, `onto_uberon.py`)**
Each script queries the [EBI OLS4 REST API](https://www.ebi.ac.uk/ols4/) to retrieve structured metadata for a list of white matter tract term IDs. For each term, the pipeline resolves the ID to an IRI, then retrieves the label, ontology ID, synonyms, textual definitions, and both incoming and outgoing ontological relationships via graph traversal. Results are saved as flat CSVs.

Note: SNOMED CT is licensing-restricted on the public EBI OLS4 server. The script handles 403 and 404 responses gracefully, falling back to direct IRI construction using the standard `http://snomed.info/id/{term_id}` format when API search fails.

**2. Schema Merging and Normalization (`join_LUT.py`)**
The SNOMED and UBERON output tables are merged into a unified schema using pandas. A regex-based label normalization function strips SNOMED's verbose clinical prefixes and suffixes ("Structure of", "of brain", "(body structure)") so that labels from both ontologies can be matched on a shared `clean_label` primary key via an outer join. This join strategy preserves all records from both ontologies, including tracts with coverage in only one source. Synonym data distributed across three columns is consolidated into a single unified `synonyms` field.

**3. Synonym Integration (`synonym_integration.ipynb`)**
A curated list of 312 white matter tract synonyms drawn from SNOMED incoming relations, UBERON annotations, and neuroimaging literature is classified into four categories:

| Category | Description | Destination |
|---|---|---|
| `mapped` | Clear 1-to-1 match to a master tract row | Appended to `synonyms` column |
| `new_tract` | Valid tract not yet in master | New row added, flagged for review |
| `ambiguous` | Matches multiple tracts or is a superstructure label | `misc.csv` |
| `discard` | Noise, stub abbreviations, or self-referential entries | `misc.csv` |

Ambiguous and discarded synonyms are logged with explanatory notes in `misc.csv` for future anatomical review.

**4. Output**
The final master table (`8April_master_v5.csv`) covers approximately 69 white matter tracts with the following fields:

| Column | Description |
|---|---|
| `clean_label` | Normalized canonical tract name (primary key) |
| `Id_snomed` | SNOMED CT identifier |
| `Id_uberon` | UBERON ontology identifier |
| `Label_snomed` | Original SNOMED label |
| `Label_uberon` | Original UBERON label |
| `synonyms` | Consolidated synonyms from both ontologies |
| `Definition` | Anatomical definition |
| `source_scheme (toolbox)` | Tractography toolbox source (TRACULA, TractSeg, AFQ, etc.) |
| `Annotation: database_cross_reference` | Cross-references to FMA, MESH, UMLS, neuronames, and others |
| `IRI` | UBERON IRI |

---

## Setup and Installation

Python 3.8 or higher is required.

Install dependencies:

```bash
pip install -r requirements.txt
```

No API keys are required. The pipeline queries the public EBI OLS4 endpoint.

---

## Usage

Run the scripts in order:

```bash
# Step 1: Query ontologies
python onto_snomed.py
python onto_uberon.py

# Step 2: Merge and normalize
python join_LUT.py

# Step 3: Open and run synonym_integration.ipynb in Jupyter
jupyter notebook synonym_integration.ipynb
```

Output files will be written to the `csvOutput/` directory.

---

## Dependencies

See `requirements.txt`. Key libraries:

| Library | Purpose |
|---|---|
| `pandas` | Data loading, merging, normalization |
| `requests` | EBI OLS4 API calls |
| `re` | Regex-based label cleaning |
| `urllib` | IRI encoding and construction |
| `numpy` | Null handling in synonym integration |
| `pathlib` | File path management |
| `jupyter` | Running the synonym integration notebook |

---

## License

MIT License. See `LICENSE` for details.