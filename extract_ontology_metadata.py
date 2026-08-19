#!/usr/bin/env python3
"""
extract_ontology_metadata.py
────────────────────────────
Reads a white-matter-tract LUT CSV that contains UBERON_ID, SNOMED_ID, and
FMA_ID columns, then enriches each row with synonym and cross-reference
metadata pulled from the UBERON OBO file (which itself embeds SNOMED SCTID
and FMA cross-references).


Outputs
-------
  lut_with_ontology_metadata.csv   — original columns + new metadata columns
  ontology_metadata_report.txt     — human-readable per-tract summary

Approach
--------
* UBERON OBO  → parsed locally from the GitHub raw OBO file (~22 MB).
                Provides: label, definition, all synonyms (with scope), and
                all xrefs (including SCTID, FMA, BAMS, Wikipedia, …).
* SNOMED CT   → no freely-accessible REST API within this network. SNOMED
                SCTID values are cross-validated against the SCTID xrefs
                already embedded in UBERON entries. The user-supplied
                SNOMED_ID is confirmed or flagged as unmatched.
* FMA         → FMA is OWL-only and behind access controls. FMA IDs are
                cross-validated against the FMA xrefs already embedded in
                UBERON entries. The user-supplied FMA_ID is confirmed or
                flagged as unmatched.

New columns added to the output CSV
------------------------------------
  uberon_label            canonical name from UBERON
  uberon_definition       full definition string from UBERON
  uberon_synonyms_exact   pipe-separated EXACT synonyms
  uberon_synonyms_related pipe-separated RELATED synonyms
  uberon_synonyms_broad   pipe-separated BROAD synonyms
  uberon_synonyms_narrow  pipe-separated NARROW synonyms
  uberon_xrefs            pipe-separated all xrefs from UBERON
  uberon_snomed_xrefs     SCTID xrefs found in UBERON entry
  uberon_fma_xrefs        FMA xrefs found in UBERON entry
  snomed_id_validated     True/False — user SNOMED_ID found in UBERON xrefs
  fma_id_validated        True/False — user FMA_ID found in UBERON xrefs
  uberon_lookup_status    ok | not_found | missing_id
"""

import re
import sys
import io
import argparse
import logging
from pathlib import Path
from typing import Optional

import requests
import pandas as pd

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

UBERON_OBO_URL = (
    "https://raw.githubusercontent.com/obophenotype/uberon/master/uberon.obo"
)
UBERON_CACHE_PATH = Path("uberon_cache.obo")

# ── OBO parser ─────────────────────────────────────────────────────────────────

def _parse_synonym_line(line: str) -> Optional[dict]:
    """
    Parse a synonym OBO line such as:
      synonym: "commissura anterior cerebri" EXACT OMO:0003011 [NeuroNames:205]
    Returns {'text': ..., 'scope': ...} or None on failure.
    """
    m = re.match(r'synonym:\s+"(.*?)"\s+(\w+)', line)
    if m:
        return {"text": m.group(1), "scope": m.group(2).upper()}
    return None


def _parse_def_line(line: str) -> str:
    """Extract the quoted definition text from a def: OBO line."""
    m = re.match(r'def:\s+"(.*?)"\s+\[', line)
    if m:
        return m.group(1)
    # Fallback: grab everything between first pair of quotes
    m2 = re.search(r'"(.*?)"', line)
    return m2.group(1) if m2 else ""


def load_uberon_obo(use_cache: bool = True) -> dict:
    """
    Download (or load from cache) the UBERON OBO and parse it into a dict
    keyed by term ID (e.g. 'UBERON:0000935').

    Each value is a dict with keys:
        id, name, def, synonyms (list of dicts), xrefs (list of str), obsolete
    """
    # ── Fetch / cache ──────────────────────────────────────────────────────────
    if use_cache and UBERON_CACHE_PATH.exists():
        log.info("Loading UBERON OBO from local cache: %s", UBERON_CACHE_PATH)
        raw = UBERON_CACHE_PATH.read_bytes()
    else:
        log.info("Downloading UBERON OBO from GitHub (~22 MB) …")
        try:
            resp = requests.get(UBERON_OBO_URL, timeout=120)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.error("Failed to download UBERON OBO: %s", exc)
            sys.exit(1)
        raw = resp.content
        if use_cache:
            UBERON_CACHE_PATH.write_bytes(raw)
            log.info("Cached UBERON OBO to %s", UBERON_CACHE_PATH)

    lines = raw.decode("utf-8", errors="replace").splitlines()
    log.info("Parsing %d lines …", len(lines))

    # ── Line-by-line parser ────────────────────────────────────────────────────
    terms: dict = {}
    current: Optional[dict] = None
    in_term = False

    def _save():
        if current and "id" in current:
            terms[current["id"]] = current

    for line in lines:
        stripped = line.strip()

        if stripped == "[Term]":
            _save()
            current = {
                "id": None,
                "name": "",
                "def": "",
                "synonyms": [],
                "xrefs": [],
                "obsolete": False,
            }
            in_term = True
            continue

        if stripped in ("[Typedef]", "[Instance]"):
            _save()
            current = None
            in_term = False
            continue

        if not in_term or current is None:
            continue

        if stripped.startswith("id: "):
            current["id"] = stripped[4:].strip()
        elif stripped.startswith("name: "):
            current["name"] = stripped[6:].strip()
        elif stripped.startswith("def: "):
            current["def"] = _parse_def_line(stripped)
        elif stripped.startswith("synonym: "):
            syn = _parse_synonym_line(stripped)
            if syn:
                current["synonyms"].append(syn)
        elif stripped.startswith("xref: "):
            # Take only the ID part (before any trailing space/comment)
            xref_val = stripped[6:].strip().split(" ")[0]
            if xref_val:
                current["xrefs"].append(xref_val)
        elif stripped == "is_obsolete: true":
            current["obsolete"] = True

    _save()  # last block
    log.info("Parsed %d UBERON terms.", len(terms))
    return terms


# ── ID normalisation helpers ───────────────────────────────────────────────────

def normalise_uberon_id(raw: str) -> Optional[str]:
    """
    Accept 'UBERON:0000935', 'uberon:0000935', 'UBERON_0000935', etc.
    Returns canonical 'UBERON:XXXXXXX' or None if unrecognisable.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip().upper().replace("_", ":")
    if re.match(r"UBERON:\d+", s):
        return s
    return None


def normalise_snomed_id(raw: str) -> Optional[str]:
    """
    Accept 'SNOMED:62872008', 'SCTID:62872008', '62872008', etc.
    Returns bare numeric string, e.g. '62872008'.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip()
    # Strip common prefixes
    s = re.sub(r"^(SNOMED(CT)?|SCTID|SCT)[:_]", "", s, flags=re.IGNORECASE)
    if re.match(r"^\d+$", s):
        return s
    return None


def normalise_fma_id(raw: str) -> Optional[str]:
    """
    Accept 'fma61961', 'FMA:61961', 'FMA_61961', '61961', etc.
    Returns canonical 'FMA:NNNNN'.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip()
    # Strip prefix
    s_num = re.sub(r"^fma[:_]?", "", s, flags=re.IGNORECASE)
    if re.match(r"^\d+$", s_num):
        return f"FMA:{s_num}"
    # Already has colon?
    if re.match(r"^FMA:\d+$", s, re.IGNORECASE):
        return s.upper()
    return None


# ── Per-row enrichment ─────────────────────────────────────────────────────────

def enrich_row(row: pd.Series, uberon_terms: dict) -> dict:
    """Return a dict of new metadata columns for one LUT row."""

    uberon_id = normalise_uberon_id(str(row.get("UBERON_ID", "")))
    snomed_id = normalise_snomed_id(str(row.get("SNOMED_ID", "")))
    fma_id    = normalise_fma_id(str(row.get("FMA_ID", "")))

    result = {
        "uberon_label":            "",
        "uberon_definition":       "",
        "uberon_synonyms_exact":   "",
        "uberon_synonyms_related": "",
        "uberon_synonyms_broad":   "",
        "uberon_synonyms_narrow":  "",
        "uberon_xrefs":            "",
        "uberon_snomed_xrefs":     "",
        "uberon_fma_xrefs":        "",
        "snomed_id_validated":     "",
        "fma_id_validated":        "",
        "uberon_lookup_status":    "missing_id",
    }

    if not uberon_id:
        return result

    term = uberon_terms.get(uberon_id)
    if term is None:
        result["uberon_lookup_status"] = "not_found"
        return result

    if term.get("obsolete"):
        result["uberon_lookup_status"] = "obsolete"

    # ── Basic fields ────────────────────────────────────────────────────────────
    result["uberon_label"]      = term.get("name", "")
    result["uberon_definition"] = term.get("def", "")

    # ── Synonyms by scope ───────────────────────────────────────────────────────
    syns_by_scope: dict = {"EXACT": [], "RELATED": [], "BROAD": [], "NARROW": []}
    for syn in term.get("synonyms", []):
        scope = syn["scope"]
        syns_by_scope.setdefault(scope, []).append(syn["text"])

    result["uberon_synonyms_exact"]   = " | ".join(syns_by_scope.get("EXACT", []))
    result["uberon_synonyms_related"] = " | ".join(syns_by_scope.get("RELATED", []))
    result["uberon_synonyms_broad"]   = " | ".join(syns_by_scope.get("BROAD", []))
    result["uberon_synonyms_narrow"]  = " | ".join(syns_by_scope.get("NARROW", []))

    # ── Cross-references ────────────────────────────────────────────────────────
    xrefs = term.get("xrefs", [])
    result["uberon_xrefs"] = " | ".join(xrefs)

    snomed_xrefs = [x for x in xrefs if x.upper().startswith("SCTID:")]
    fma_xrefs    = [x for x in xrefs if x.upper().startswith("FMA:")]

    result["uberon_snomed_xrefs"] = " | ".join(snomed_xrefs)
    result["uberon_fma_xrefs"]    = " | ".join(fma_xrefs)

    # ── Validation ──────────────────────────────────────────────────────────────
    if snomed_id:
        snomed_in_uberon = any(
            x.split(":", 1)[-1] == snomed_id for x in snomed_xrefs
        )
        result["snomed_id_validated"] = str(snomed_in_uberon)
    else:
        result["snomed_id_validated"] = "no_id_supplied"

    if fma_id:
        fma_in_uberon = fma_id.upper() in [x.upper() for x in fma_xrefs]
        result["fma_id_validated"] = str(fma_in_uberon)
    else:
        result["fma_id_validated"] = "no_id_supplied"

    if not term.get("obsolete"):
        result["uberon_lookup_status"] = "ok"

    return result


# ── Text report ────────────────────────────────────────────────────────────────

def write_report(enriched_df: pd.DataFrame, path: Path):
    """Write a human-readable per-tract report."""
    lines = [
        "Ontology Metadata Extraction Report",
        "=" * 70,
        f"Tracts processed: {len(enriched_df)}",
        "",
    ]

    status_counts = enriched_df["uberon_lookup_status"].value_counts().to_dict()
    lines.append("Lookup status summary:")
    for status, count in status_counts.items():
        lines.append(f"  {status:<20} {count}")
    lines.append("")

    # Validation flags
    snomed_validated = (enriched_df["snomed_id_validated"] == "True").sum()
    snomed_failed    = (enriched_df["snomed_id_validated"] == "False").sum()
    fma_validated    = (enriched_df["fma_id_validated"] == "True").sum()
    fma_failed       = (enriched_df["fma_id_validated"] == "False").sum()

    lines += [
        f"SNOMED IDs validated against UBERON xrefs : {snomed_validated}",
        f"SNOMED IDs NOT found in UBERON xrefs      : {snomed_failed}",
        f"FMA IDs validated against UBERON xrefs    : {fma_validated}",
        f"FMA IDs NOT found in UBERON xrefs         : {fma_failed}",
        "",
        "─" * 70,
        "Per-tract detail",
        "─" * 70,
        "",
    ]

    for _, row in enriched_df.iterrows():
        clean_label = row.get("clean_label", "unknown")
        lines.append(f"▶ {clean_label}")
        lines.append(f"  UBERON ID   : {row.get('UBERON_ID','')}")
        lines.append(f"  UBERON label: {row.get('uberon_label','')}")
        lines.append(f"  Status      : {row.get('uberon_lookup_status','')}")
        lines.append(f"  Definition  : {str(row.get('uberon_definition',''))[:120]}")

        exact  = row.get("uberon_synonyms_exact", "")
        rel    = row.get("uberon_synonyms_related", "")
        broad  = row.get("uberon_synonyms_broad", "")
        narrow = row.get("uberon_synonyms_narrow", "")

        if exact:
            lines.append(f"  Exact syns  : {exact}")
        if rel:
            lines.append(f"  Related syns: {rel}")
        if broad:
            lines.append(f"  Broad syns  : {broad}")
        if narrow:
            lines.append(f"  Narrow syns : {narrow}")

        lines.append(f"  SNOMED ID   : {row.get('SNOMED_ID','')}  validated={row.get('snomed_id_validated','')}")
        lines.append(f"  SNOMED xrefs: {row.get('uberon_snomed_xrefs','')}")
        lines.append(f"  FMA ID      : {row.get('FMA_ID','')}  validated={row.get('fma_id_validated','')}")
        lines.append(f"  FMA xrefs   : {row.get('uberon_fma_xrefs','')}")
        lines.append(f"  All xrefs   : {str(row.get('uberon_xrefs',''))[:120]}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Report written to %s", path)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enrich a white-matter LUT CSV with UBERON/SNOMED/FMA ontology metadata."
    )
    parser.add_argument(
        "input_csv",
        help="Path to the input LUT CSV file.",
    )
    parser.add_argument(
        "-o", "--output",
        default="lut_with_ontology_metadata.csv",
        help="Output CSV path (default: lut_with_ontology_metadata.csv).",
    )
    parser.add_argument(
        "--report",
        default="ontology_metadata_report.txt",
        help="Output text report path (default: ontology_metadata_report.txt).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Always re-download the UBERON OBO even if a local cache exists.",
    )
    parser.add_argument(
        "--sep",
        default=",",
        help="CSV delimiter (default: comma). Use '\\t' for TSV.",
    )
    args = parser.parse_args()

    sep = "\t" if args.sep == r"\t" else args.sep

    # ── Load LUT ────────────────────────────────────────────────────────────────
    input_path = Path(args.input_csv)
    if not input_path.exists():
        log.error("Input file not found: %s", input_path)
        sys.exit(1)

    log.info("Loading LUT from %s", input_path)
    df = pd.read_csv(input_path, sep=sep, dtype=str).fillna("")
    log.info("Loaded %d rows, columns: %s", len(df), list(df.columns))

    required = {"UBERON_ID"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        log.error("Input CSV is missing required column(s): %s", missing_cols)
        sys.exit(1)

    # ── Load UBERON ─────────────────────────────────────────────────────────────
    uberon_terms = load_uberon_obo(use_cache=not args.no_cache)

    # ── Enrich ──────────────────────────────────────────────────────────────────
    log.info("Enriching %d rows …", len(df))
    meta_rows = [enrich_row(row, uberon_terms) for _, row in df.iterrows()]
    meta_df   = pd.DataFrame(meta_rows)
    enriched  = pd.concat([df.reset_index(drop=True), meta_df], axis=1)

    # ── Save CSV ─────────────────────────────────────────────────────────────────
    out_path = Path(args.output)
    enriched.to_csv(out_path, index=False)
    log.info("Enriched CSV written to %s", out_path)

    # ── Save report ──────────────────────────────────────────────────────────────
    write_report(enriched, Path(args.report))

    # ── Quick console summary ────────────────────────────────────────────────────
    ok_count = (enriched["uberon_lookup_status"] == "ok").sum()
    print(f"\n{'─'*55}")
    print(f"  Tracts total          : {len(enriched)}")
    print(f"  UBERON lookups OK     : {ok_count}")
    print(
        f"  SNOMED validated      : "
        f"{(enriched['snomed_id_validated']=='True').sum()} / "
        f"{(enriched['snomed_id_validated'].isin(['True','False'])).sum()}"
    )
    print(
        f"  FMA validated         : "
        f"{(enriched['fma_id_validated']=='True').sum()} / "
        f"{(enriched['fma_id_validated'].isin(['True','False'])).sum()}"
    )
    print(f"  Output CSV            : {out_path}")
    print(f"  Report                : {args.report}")
    print(f"{'─'*55}\n")


if __name__ == "__main__":
    main()
