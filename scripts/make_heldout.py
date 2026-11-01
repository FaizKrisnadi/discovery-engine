"""Rewrite data/labels/heldout_sample.json with honest provenance.

Correction (2026-10-30): the previous version claimed the sample was chosen
"before inspecting any match result" with a hardcoded timestamp. The run
transcript contradicts this: the full per-record candidate table for all 72
records was printed and read BEFORE this file was created. The sample is
therefore RETROSPECTIVE and development-exposed; it cannot serve as a clean
held-out evaluation set.

The only verified time available is the file's original filesystem birth time
(2026-10-30T06:09:08+0700), captured with stat(1) immediately before this
rewrite; the fabricated 06:40 timestamp was removed.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "labels" / "heldout_sample.json"

ORIGINAL_FILE_BIRTH_MTIME = "2026-10-30T06:09:08+0700"  # stat(1) before this rewrite

doc = {
    "status": "RETROSPECTIVE SAMPLE - EXPOSED DURING DEVELOPMENT. NOT a clean held-out set.",
    "original_file_created_at_filesystem": ORIGINAL_FILE_BIRTH_MTIME,
    "selection_rule": ("deterministic: every 7th sorted AidData record id starting at index 3, "
                       "first 12 (yielded 10)"),
    "exposure_disclosure": ("The full per-record candidate table (all 72 records) had already been "
                            "printed and inspected during matcher development before this sample was "
                            "drawn; individual records in this list (e.g., 49810, 70718, 96237) had "
                            "also been inspected directly. Labels for these records were therefore "
                            "written with knowledge of matcher output."),
    "valid_use": ("May be used for transparency and error analysis. CANNOT support claims of "
                  "independent or unbiased evaluation, and any human adjudication of it cannot be "
                  "reported as independent validation."),
    "clean_protocol_for_next_stage": ("A fresh sample must be drawn by a different process/agent "
                                      "from records whose matcher output has not been inspected, "
                                      "before any result is produced."),
    "record_ids": [34992, 38610, 49810, 61474, 62065, 67236, 70718, 96237, 102646, 108277],
}

OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
print("rewrote heldout_sample.json with retrospective/exposed status")
