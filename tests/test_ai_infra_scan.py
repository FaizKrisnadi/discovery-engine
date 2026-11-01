"""Tests for the AI-infrastructure / renewable-energy scan and its discipline."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / "findings"
RAW = ROOT / "data" / "raw"


def scan():
    return json.loads((FINDINGS / "ai_infra_re_scan.json").read_text())


def test_scan_structure_and_licenses():
    d = scan()
    assert d["aiddata_hits"] and d["gap_register"] and d["exploratory_example"]
    for h in d["aiddata_hits"]:
        assert h["record_id"] and h["license"].startswith("Open Data Commons")
        assert h["matched_keyword"]
    assert d["gem_supply_context"]["license"].startswith("CC BY 4.0")


def test_gds_is_the_only_commercial_data_center_project():
    d = scan()
    gds = [h for h in d["aiddata_hits"] if h["record_id"] == 106768]
    assert len(gds) == 1
    g = gds[0]
    assert "Data Center Project" in g["title"] and g["country"] == "Malaysia"
    assert g["sector"] == "COMMUNICATIONS"
    # two literal title hits exist; 100460 is an agriculture data centre (different subject)
    dc_hits = {h["record_id"] for h in d["aiddata_hits"]
               if "data cent" in h["title"].lower() or "datacent" in h["title"].lower()}
    assert dc_hits == {106768, 100460}
    other = next(h for h in d["aiddata_hits"] if h["record_id"] == 100460)
    assert "Myanmar" in other["country"] and "Agricult" in other["title"]


def test_peninsular_context_matches_raw_gem_data():
    d = scan()
    ctx = d["gem_supply_context"]
    assets = json.loads((RAW / "gem_malaysia_assets.json").read_text())
    norm = {"melaka": "Melaka", "malacca": "Melaka", "negeri sembilan": "Negeri Sembilan",
            "negiria sembilan": "Negeri Sembilan", "negeri semblian": "Negeri Sembilan",
            "penang": "Penang", "pulau pinang": "Penang"}
    pen = {"Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang", "Perak",
           "Perlis", "Penang", "Selangor", "Terengganu"}
    def state(a):
        raw = str(a.get("state_province") or "").strip()
        return norm.get(raw.lower(), raw) if raw else "UNASSIGNED"
    coal = round(sum(a["capacity_value"] for a in assets
                     if a["asset_type"] == "Coal Plant" and a["operating_status"] == "operating"
                     and state(a) in pen
                     and a.get("capacity_unit") == "MW" and a.get("capacity_value")))
    sub = ctx["peninsular_malaysia_gem_listed_operating_mw_subtotal"]
    assert sub["Coal Plant"] == coal == 12200.0
    # geography repairs present: variants recovered, unassigned explicit, Labuan excluded
    assert sub["Bioenergy Plant"] == 105.2
    assert ctx["unassigned_state_gem_listed_operating_mw"]["Bioenergy Plant"] == 77.8
    assert "Labuan" not in " ".join(ctx["geography_notes"].split()) or "excluded" in ctx["geography_notes"]
    assert any("NOT a generation mix" in x for x in ctx["what_this_is_not"])
    assert any("grid-emissions factor" in x for x in ctx["what_this_is_not"])
    # API RE coverage gap stated, not hidden
    assert "no solar, wind or hydro" in ctx["coverage_gap"]
    assert ctx["re_types_in_api"] == ["Bioenergy Plant"]


def test_no_procurement_or_supply_claims_are_made():
    d = scan()
    blob = json.dumps({k: v for k, v in d.items() if k != "exploratory_example"}).lower()
    ex = d["exploratory_example"]
    # the phrase may appear only inside the scan's own explicit non-claims
    assert "no claim that gds nusajaya procures renewable" in json.dumps(ex).lower()
    assert "procures renewable" not in blob.replace("no claim that gds nusajaya procures renewable energy (no procurement data found).", "")
    assert "physically supplied by" not in blob.replace("no claim that the facility is physically supplied by any specific plant.", "")
    ex = scan()["exploratory_example"]
    assert any("green-labelled financing" in n.lower() and "not evidence" in n.lower()
               for n in [ex["layer_1_financing"]["green_label_note"]] + ex["non_claims"])
    assert any("renewable procurement" in n.lower() for n in
               [ex["layer_1_financing"]["green_label_note"]] + ex["non_claims"])
    assert "layer_2_grid_context" in ex and any(
        "NOT a generation mix" in x for x in ex["layer_2_grid_context"]["what_this_is_not"])
    assert len(ex["non_claims"]) >= 4
    assert "NO causal or contractual connection asserted" in ex["claim_status"]


def test_gap_register_covers_the_missing_layers():
    reg = scan()["gap_register"]
    paths = " || ".join(json.dumps(g, ensure_ascii=False) for g in reg)
    assert "GEM Global Solar/Wind Power Tracker" in paths and "NOT ACCESSED" in paths
    assert "PLN tradable renewable energy certificates" in paths
    assert "not publicly reproducible" in paths or "no public per-customer REC registry" in paths
    ann = next(g for g in scan()["gap_register"] if "announcement" in g["path"])
    assert "announcement layer only" in ann["contribution"]
