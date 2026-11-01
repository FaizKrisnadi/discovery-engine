"""Pipeline integrity tests. Run: PYTHONPATH=src .venv/bin/python -m pytest tests -q

These tests assert internal consistency and honest-labeling invariants; they
do NOT assert that AI-generated labels are correct.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
LABELS = ROOT / "data" / "labels"
FINDINGS = ROOT / "findings"


@pytest.fixture(scope="module")
def graph():
    return json.loads((PROC / "evidence_graph.json").read_text())


@pytest.fixture(scope="module")
def labels():
    return json.loads((LABELS / "match_labels.json").read_text())


def test_raw_inputs_present():
    assert (RAW / "AidDatas_CLG_LMIC_Dataset_v1.0.xlsx").exists()
    assert (RAW / "gem_idn_assets.json").exists()
    assets = json.loads((RAW / "gem_idn_assets.json").read_text())
    assert assets["meta"]["license"].startswith("CC BY 4.0")
    assert len(assets["results"]) == 1516


def test_graph_evidence_integrity(graph):
    ev_ids = {e["evidence_id"] for e in graph["evidence"]}
    for e in graph["edges"]:
        assert e["evidence_ids"], f"edge {e['edge_id']} has no evidence"
        for x in e["evidence_ids"]:
            assert x in ev_ids, f"edge {e['edge_id']} cites missing evidence {x}"


def test_every_evidence_record_has_source_version_license_quote(graph):
    for e in graph["evidence"]:
        assert e["source"] and e["source_version"] and e["license"] and e["quote"]


def test_match_edges_are_provisional(graph):
    for e in graph["edges"]:
        if e["edge_type"] == "SAME_PLANT_AS":
            assert e["claim_status"] == "inferred"
            assert "provisional" in e["statement"].lower()


def test_labels_declare_provisional_status(labels):
    assert labels["label_status"] == "provisional"
    assert "NOT human-verified" in labels["auditor"]
    assert "leakage" in labels["leakage_note"]


def test_parity_baru_is_ambiguous_not_merged(labels):
    x = next(l for l in labels["labels"] if l["record_id"] == 34992)
    assert x["label"] == "AMBIGUOUS" and x["gem_location_id"] is None


def test_retrospective_sample_honestly_documented(labels):
    h = json.loads((LABELS / "heldout_sample.json").read_text())
    # must be disclosed as development-exposed, never as a clean held-out set
    assert "RETROSPECTIVE" in h["status"] and "NOT a clean held-out set" in h["status"]
    assert "candidate table" in h["exposure_disclosure"]
    assert h.get("original_file_created_at_filesystem", "").startswith("2026-10-30T06:09:08")
    assert "selected_at" not in h  # fabricated timestamp must stay removed
    assert len(h["record_ids"]) >= 10
    labeled = {l["record_id"] for l in labels["labels"]}
    assert set(h["record_ids"]) <= labeled


def test_normalize_unit_grain():
    plants = json.loads((PROC / "gem_idn_plants.json").read_text())
    suralaya = next(p for p in plants if p["plant_name"] == "Banten Suralaya power station")
    # units 09/10 must exist at 1000MW each; the plant total must not be used as a match key
    big = [u for u in suralaya["units"] if (u["capacity_mw"] or 0) >= 1000]
    assert len(big) == 2
    assert suralaya["capacity_mw_by_status"]["operating"] == 6025.0


def test_celukan_bawang_operating_capacity_excludes_cancelled():
    plants = json.loads((PROC / "gem_idn_plants.json").read_text())
    cb = next(p for p in plants if p["plant_name"] == "Celukan Bawang power station")
    assert cb["capacity_mw_by_status"] == {"cancelled": 660.0, "operating": 426.0}


def test_findings_language_discipline():
    findings = json.loads((FINDINGS / "findings.json").read_text())
    blob = json.dumps(findings).lower()
    assert "independently verified" not in blob
    assert "novel" not in blob
    for f in findings:
        if f["finding_id"].startswith(("D1", "D2", "D3", "D4")):
            assert "provisional" in f["claim_status"].lower() or "unresolved" in f["claim_status"].lower()


def test_evaluation_discloses_denominators_and_baselines():
    ev = json.loads((FINDINGS / "evaluation.json").read_text())
    m = ev["matching_metrics"]
    d = m["denominators"]
    assert d["retrospective_sample_excluded_not_a_clean_heldout"]
    assert "NO independent" in d["retrospective_sample_note"]
    assert d["excluded_from_pr_ambiguous_unadjudicated"]
    assert "direction and magnitude" in m["status"]
    for b in ev["baseline_searches"]:
        assert b["references_retrieved"], f"baseline {b['finding']} lacks retrieved references"
        assert "not proof of novelty" in b["verdict"] or "novelty" in ev["baseline_limitations"]


def test_api_request_log_exists_and_bounded():
    log = (ROOT / "data" / "processed" / "api_request_log.jsonl").read_text().strip().splitlines()
    assert 0 < len(log) < 500, f"unexpected request volume: {len(log)}"
