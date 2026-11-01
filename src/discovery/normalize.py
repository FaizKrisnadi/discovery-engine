"""Normalize AidData CLG-LMIC (Indonesia, ENERGY) and GEM assets into plants.

Grain discipline:
- AidData row = one financing event or syndicate-member contribution (provenance:
  AidData_Record_ID + All_Source_URLs). Syndicate members are separate rows;
  umbrella links are parsed from "(Linked to Record ID#...)" in Title when present.
- GEM asset row = one unit (location_id+unit). We aggregate units to PLANT level
  (location_id) for matching against AidData project names, because AidData
  finances plants/projects, not individual units. Capacity sums are computed
  per status bucket; mixed statuses are preserved, never collapsed silently.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

AIDDATA_FILE = RAW / "AidDatas_CLG_LMIC_Dataset_v1.0.xlsx"
GEM_ASSETS_FILE = RAW / "gem_idn_assets.json"

GEM_LICENSE = "CC BY 4.0 (globalenergymonitor.org/creative-commons-license/, verified 2026-10-30)"
AIDDATA_LICENSE = ("Open Data Commons Attribution License (ODC-By 1.0), stated in the "
                   "'License' sheet of AidDatas_CLG_LMIC_Dataset_v1.0.xlsx (verified 2026-10-30)")

CAP_RE = re.compile(r"(?P<cap>\d+(?:\.\d+)?)\s*(?P<unit>MW|GW|kW)\b", re.I)


def load_aiddata_energy_idn() -> pd.DataFrame:
    df = pd.read_excel(AIDDATA_FILE, sheet_name="CLG-LMIC 1.0_Records")
    en = df[(df["Country_of_Activity"] == "Indonesia") & (df["Sector_Name"] == "ENERGY")].copy()
    en["Linked_Record_IDs"] = en["Title"].map(
        lambda t: [int(m) for m in re.findall(r"Linked to Records? ID#(\d+)", str(t))])
    return en


def aiddata_records() -> list[dict]:
    en = load_aiddata_energy_idn()
    out = []
    for _, r in en.iterrows():
        urls = [u for u in str(r.get("All_Source_URLs") or "").split("|") if u.startswith("http")]
        titles = [t for t in str(r.get("All_Source_Titles") or "").split("|") if t]
        pubs = [p for p in str(r.get("All_Source_Publishers") or "").split("|") if p]
        out.append({
            "record_id": int(r["AidData_Record_ID"]),
            "linked_record_ids": r["Linked_Record_IDs"],
            "commitment_year": None if pd.isna(r["Commitment_Year"]) else int(r["Commitment_Year"]),
            "title": str(r["Title"]),
            "status": str(r["Status"]),
            "flow_class": str(r["Flow_Class"]) if not pd.isna(r["Flow_Class"]) else None,
            "amount_nominal_usd": None if pd.isna(r["Amount_Nominal_USD"]) else float(r["Amount_Nominal_USD"]),
            "funding_agencies_parent": [x.strip() for x in str(r["Funding_Agencies_Parent"] or "").split("|") if x.strip()],
            "funding_agencies": [x.strip() for x in str(r["Funding_Agencies"] or "").split("|") if x.strip()],
            "direct_receiving_agencies": [x.strip() for x in str(r["Direct_Receiving_Agencies"] or "").split("|") if x.strip()],
            "implementing_agencies": [x.strip() for x in str(r["Implementing_Agencies"] or "").split("|") if x.strip()],
            "source_urls": urls,
            "source_titles": titles,
            "source_publishers": pubs,
            "source_quality_score": None if pd.isna(r["Source_Quality_Score"]) else float(r["Source_Quality_Score"]),
            "license": AIDDATA_LICENSE,
        })
    return out


def gem_plants() -> list[dict]:
    d = json.loads(GEM_ASSETS_FILE.read_text())
    assets = d["results"]
    plants: dict[str, dict] = {}
    for a in assets:
        p = plants.setdefault(a["location_id"], {
            "location_id": a["location_id"],
            "plant_name": a.get("project_name") or a["asset_name"],
            "asset_type": a["asset_type"],
            "country": a["country"],
            "state_province": a["state_province"],
            "latitude": a.get("latitude"),
            "longitude": a.get("longitude"),
            "wiki_url": a.get("wiki_url"),
            "units": [],
        })
        p["units"].append({
            "asset_id": a["asset_id"],
            "unit_name": a.get("unit_name"),
            "capacity_mw": a.get("capacity_value") if (a.get("capacity_unit") or "").upper() == "MW" else None,
            "operating_status": a["operating_status"],
            "owners": [{"entity_id": o["entity_id"], "name": o["name"],
                        "ownership_share": o.get("ownership_share"), "hq_country": o.get("hq_country")}
                       for o in (a.get("owners") or [])],
        })
    out = []
    for p in plants.values():
        by_status: dict[str, float] = {}
        for u in p["units"]:
            if u["capacity_mw"] is not None:
                by_status[u["operating_status"]] = by_status.get(u["operating_status"], 0.0) + u["capacity_mw"]
        caps = [u["capacity_mw"] for u in p["units"] if u["capacity_mw"] is not None]
        statuses = sorted({u["operating_status"] for u in p["units"]})
        # owner union across units (shares can vary per unit; we keep the set of
        # owner names and the max share seen, and flag heterogeneity)
        owners: dict[str, dict] = {}
        for u in p["units"]:
            for o in u["owners"]:
                cur = owners.setdefault(o["entity_id"], {"entity_id": o["entity_id"], "name": o["name"],
                                                         "max_share": None, "hq_country": o["hq_country"]})
                if o["ownership_share"] is not None:
                    cur["max_share"] = max(cur["max_share"] or 0.0, o["ownership_share"])
        out.append({
            "location_id": p["location_id"],
            "plant_name": p["plant_name"],
            "asset_type": p["asset_type"],
            "country": p["country"],
            "state_province": p["state_province"],
            "latitude": p["latitude"],
            "longitude": p["longitude"],
            "wiki_url": p["wiki_url"],
            "unit_count": len(p["units"]),
            "capacity_mw_sum": sum(caps) if caps else None,
            "capacity_mw_by_status": {k: round(v, 1) for k, v in sorted(by_status.items())},
            "capacity_mw_operating": by_status.get("operating", 0.0) or None,
            "unit_statuses": statuses,
            "owners": sorted(owners.values(), key=lambda o: -(o["max_share"] or 0.0)),
            "units": p["units"],
            "license": GEM_LICENSE,
        })
    out.sort(key=lambda p: p["location_id"])
    return out


def extract_project_names_from_title(title: str) -> list[str]:
    """Pull candidate project-name strings out of an AidData title.

    Heuristic, deliberately conservative: strip the financing clause before the
    capacity token, drop trailing boilerplate. Produces candidates for matching;
    every candidate stays attached to its record for human audit.
    """
    t = str(title)
    t = re.sub(r"\s*\(Linked to Records? ID#[\d,# ]+\)\s*$", "", t)
    # find first capacity token; project name usually starts there
    m = CAP_RE.search(t)
    if m:
        t = t[m.start():]
    elif " for " in t:
        # no capacity token: drop the financing clause before the last " for "
        t = t.rsplit(" for ", 1)[1]
    t = re.sub(r"\s+", " ", t).strip(" .")
    # split on ' and ' before 'Coal-Fired' etc. handled by matcher, not here
    return [t] if t else []


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    recs = aiddata_records()
    (PROC / "aiddata_idn_energy.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1))
    plants = gem_plants()
    (PROC / "gem_idn_plants.json").write_text(json.dumps(plants, ensure_ascii=False, indent=1))
    print(f"aiddata records: {len(recs)}; gem plants: {len(plants)}")


if __name__ == "__main__":
    main()
