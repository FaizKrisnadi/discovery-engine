"""Tests for the GDS 106768 primary-source dossier and the scan audit."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / "findings"
RAW = ROOT / "data" / "raw"


def dossier():
    return json.loads((FINDINGS / "gds106768_dossier.json").read_text())


def test_dossier_covers_all_four_linked_sources():
    d = dossier()
    assert len(d["sources"]) == 4
    statuses = {s["name"].split()[0]: s["access"]["status"] for s in d["sources"]}
    assert statuses["IJGlobal"] == 200 and statuses["PR"] == 200 and statuses["GDS"] == 200
    assert statuses["Google"] == "NOT FETCHED"


def test_gds_official_access_failure_recorded():
    d = dossier()
    gds = next(s for s in d["sources"] if s["name"].startswith("GDS"))
    obs = gds["access"]["observation"]
    assert "no longer served" in obs or "notice" in obs
    assert all(v == "no" for k, v in gds["supports"].items() if k != "facility_identity")


def test_quotes_are_verbatim_and_load_bearing():
    d = dossier()
    prn = next(s for s in d["sources"] if s["name"].startswith("PR"))
    quotes = {q["topic"]: q["quote"] for q in prn["exact_passages"]}
    assert "IT power capacity of 69.9 MW" in quotes["capacity"]
    assert "100% use of renewable energy by 2030" in quotes["renewable target"]
    assert "aspiration" in quotes["renewable target"].lower()
    assert "not current procurement" in quotes["renewable target"]
    assert "complete the development of" in quotes["use of proceeds"]


def test_disagreements_and_unknowns_visible():
    d = dossier()
    dims = {x["dimension"]: x for x in d["disagreements"]}
    assert {"capacity", "instrument type", "status"} <= set(dims)
    cap = {c["source"]: c["value"] for c in dims["capacity"]["claims"]}
    assert "69.9MW" in str(cap.values()) and "54.00 MW" in str(cap.values())
    assert "no winner" in dims["capacity"]["note"] or "both recorded" in dims["capacity"]["note"]
    st = {c["source"]: c["value"] for c in dims["status"]["claims"]}
    assert "Pre-construction" in str(st.values()) and "Completion" in str(st.values())
    assert len(d["unknowns"]) >= 5
    assert any("renewable-energy procurement" in u for u in d["unknowns"])


def test_renewable_procurement_and_ai_workloads_not_inferred():
    d = dossier()
    pa = d["per_dimension_assessment"]
    assert "UNKNOWN" in pa["renewable_procurement"] or "NOT EVIDENCED" in pa["renewable_procurement"]
    assert "aspiration" in pa["renewable_procurement"].lower()
    assert "NOT INFERABLE" in pa["ai_workloads"]
    assert "NOT EVIDENCED" in pa["green_use_of_proceeds"] or "unverified" in pa["green_use_of_proceeds"]


def test_scan_audit_documented_universe_and_bug_fix():
    a = dossier()["scan_audit"]
    assert "Narrative_Description" in a["defined_search_universe"]["fields_searched"]
    assert "Staff_Comments" in a["defined_search_universe"]["fields_NOT_searched"]
    assert "case-SENSITIVE" in a["defined_search_universe"]["keyword_regex"]
    fp = {x["record_id"]: x for x in a["false_positives_found_and_fixed"]}
    assert 34762 in fp and "Ting'ai" in str(fp[34762]["cause"])
    assert 100460 in fp and "out-of-scope subject" in str(fp[100460]["fix"])
    assert a["hit_count"] == {"before_ai_case_fix": 37, "after": 36}


def test_scan_hits_match_audit_count_and_exclude_false_positive():
    scan = json.loads((FINDINGS / "ai_infra_re_scan.json").read_text())
    ids = {h["record_id"] for h in scan["aiddata_hits"]}
    assert 34762 not in ids
    assert len(ids) == 36
    assert 106768 in ids


def test_absence_claims_are_limited_search_language():
    reg = json.dumps(json.loads((FINDINGS / "ai_infra_re_scan.json").read_text())["gap_register"]).lower()
    assert "does not establish" in reg or "not established" in reg
    assert "limited" in reg
    assessment = (ROOT / "docs" / "ai_infra_re_assessment.md").read_text().lower()
    assert "not proof of absence" in assessment or "does not establish" in assessment
