"""Exploratory scan: AI/digital infrastructure vs renewable energy, Indonesia + SEA.

Produces findings/ai_infra_re_scan.json with four parts:
  A. AidData keyword scan (titles + narratives) for data-center / AI / cloud /
     5G / semiconductor records across SEA — every hit with provenance.
  B. GEM physical-supply context: Peninsular Malaysia operating capacity mix
     (the grid that would serve Johor data centers), plus the documented fact
     that the GEM API asset list contains no solar/wind/hydro assets at all
     (an API coverage gap, NOT a claim that SEA has no renewables).
  C. Gap register: assessed public-data paths for connecting AI infrastructure
     to renewable-energy procurement/supply, with access, license and coverage
     findings, and the honest conclusion that no permitted reproducible path
     currently connects them.
  D. One evidence-linked exploratory example (GDS Nusajaya green-labeled loan
     x Peninsular supply context) with explicit non-claims.

Nothing here asserts that any data center procures renewable energy: the
financing label ("green loan"), operating facility status, procurement claims
and physical supply are kept strictly separate.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery.http import cached_get_json  # noqa: E402

API = "https://api.globalenergymonitor.org"
SEA = ["Indonesia", "Malaysia", "Singapore", "Thailand", "Vietnam", "Philippines",
       "Brunei", "Cambodia", "Laos", "Timor-Leste", "Myanmar"]
# GEM state_province spellings vary; verified against the actual Malaysia fetch
# (data/raw/gem_malaysia_assets.json). Labuan is East Malaysia and is EXCLUDED.
STATE_NORMALIZATION = {
    "melaka": "Melaka", "malacca": "Melaka",
    "negeri sembilan": "Negeri Sembilan", "negiria sembilan": "Negeri Sembilan",
    "negeri semblian": "Negeri Sembilan",
    "penang": "Penang", "pulau pinang": "Penang",
}
PENINSULAR = {"Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang",
              "Perak", "Perlis", "Penang", "Selangor", "Terengganu"}


def _state(a) -> str:
    raw = str(a.get("state_province") or "").strip()
    return STATE_NORMALIZATION.get(raw.lower(), raw) if raw else "UNASSIGNED"
KW = re.compile(r"data\s*cent(?:er|re)|datacent|artificial intelligence|(?-i:\bAI\b)|machine learning"
                r"|cloud comput|supercomput|digital econom|5G|hyperscal|semiconductor", re.I)

AIDDATA_LICENSE = ("Open Data Commons Attribution License (ODC-By 1.0), stated in the "
                   "'License' sheet of AidDatas_CLG_LMIC_Dataset_v1.0.xlsx (verified 2026-10-30)")
GEM_LICENSE = "CC BY 4.0 (globalenergymonitor.org/creative-commons-license/, verified 2026-10-30)"


def scan_aiddata() -> list[dict]:
    import pandas as pd
    df = pd.read_excel(ROOT / "data/raw/AidDatas_CLG_LMIC_Dataset_v1.0.xlsx",
                       sheet_name="CLG-LMIC 1.0_Records")
    sub = df[df["Country_of_Activity"].isin(SEA)]
    hits = []
    for _, r in sub.iterrows():
        title, narr = str(r["Title"]), str(r["Narrative_Description"])
        m_t, m_n = KW.search(title), KW.search(narr)
        if not (m_t or m_n):
            continue
        urls = [u for u in str(r.get("All_Source_URLs") or "").split("|") if u.startswith("http")]
        hits.append({
            "record_id": int(r["AidData_Record_ID"]),
            "country": r["Country_of_Activity"],
            "commitment_year": None if pd.isna(r["Commitment_Year"]) else int(r["Commitment_Year"]),
            "status": r["Status"],
            "sector": r["Sector_Name"],
            "amount_nominal_usd": None if pd.isna(r["Amount_Nominal_USD"]) else float(r["Amount_Nominal_USD"]),
            "title": title,
            "matched_keyword": (m_t or m_n).group(0).lower(),
            "matched_in": "title" if m_t else "narrative",
            "direct_receiving_agencies": [x.strip() for x in str(r["Direct_Receiving_Agencies"] or "").split("|") if x.strip()],
            "source_urls": urls[:2],
            "layer": "financing event (announcement layer when status is pledge/pipeline)",
            "license": AIDDATA_LICENSE,
        })
    return sorted(hits, key=lambda h: -h["record_id"])


def gem_supply_context() -> dict:
    d = json.loads((ROOT / "data/raw/gem_malaysia_assets.json").read_text())
    pen_mw, pen_units, unassigned_mw = Counter(), Counter(), Counter()
    for a in d:
        if a["operating_status"] == "operating" and a.get("capacity_unit") == "MW" \
                and a.get("capacity_value") and a["asset_type"] in ("Coal Plant", "Oil & Gas Plant", "Bioenergy Plant"):
            st = _state(a)
            if st in PENINSULAR:
                pen_mw[a["asset_type"]] += a["capacity_value"]
                pen_units[a["asset_type"]] += 1
            elif st == "UNASSIGNED":
                # geography cannot be established from the API field alone:
                # kept as an explicit unassigned bucket, never dropped or guessed
                unassigned_mw[a["asset_type"]] += a["capacity_value"]
    meta = cached_get_json(f"{API}/metadata")
    api_types = sorted(meta["database"]["asset_types"])
    return {
        "what_this_is": ("A subtotal of GEM-API-LISTED operating generation units (unit-level MW "
                         "sums) in Peninsular Malaysia after state-name normalization. It is "
                         "INCOMPLETE: the API asset list has no solar/wind/hydro class, units below "
                         "GEM thresholds are unlisted, and units with no API state are shown "
                         "separately as unassigned."),
        "what_this_is_not": [
            "NOT a generation mix (the API omits solar/wind/hydro entirely).",
            "NOT a grid-emissions factor.",
            "NOT evidence of electricity supplied to any specific data centre (no supply linkage exists in any dataset inspected).",
            "NOT a complete inventory of Malaysian generating capacity.",
        ],
        "gem_api_types": api_types,
        "re_types_in_api": [t for t in api_types if "Bioenergy" in t],
        "coverage_gap": ("The GEM Ownership API asset list contains no solar, wind or hydro "
                         "assets at all; bioenergy is the only renewable class present. This is "
                         "an API coverage gap, NOT evidence that Southeast Asia lacks renewables."),
        "geography_notes": ("State spellings normalized (Melaka/Malacca, three Negeri Sembilan "
                            "variants, Penang/Pulau Pinang). Labuan is East Malaysia and excluded. "
                            "Units whose API state is missing are reported in unassigned_mw, not "
                            "silently dropped."),
        "peninsular_malaysia_gem_listed_operating_mw_subtotal": {k: round(v, 1) for k, v in pen_mw.items()},
        "peninsular_malaysia_gem_listed_operating_units": dict(pen_units),
        "unassigned_state_gem_listed_operating_mw": {k: round(v, 1) for k, v in unassigned_mw.items()},
        "observation_date": "2026-10-29 (GEM API build)",
        "license": GEM_LICENSE,
    }


def gap_register() -> list[dict]:
    return [
        {"path": "AidData CLG-LMIC v1.0 keyword scan", "status": "INGESTED",
         "access": "direct zip, verified 2026-10-30", "license": AIDDATA_LICENSE,
         "contribution": "identifies Chinese-financed digital/AI/telecom infrastructure events (announcement/financing layer)",
         "limitation": "no energy-procurement fields; sector codes are coarse (COMMUNICATIONS); no operating-facility status"},
        {"path": "GEM Ownership Tracing API", "status": "INGESTED",
         "access": "documented unauthenticated API, verified 2026-10-29/30", "license": GEM_LICENSE,
         "contribution": "operating generation assets with owners (physical-supply context)",
         "limitation": "API asset list contains NO solar/wind/hydro; no electricity-procurement or customer data"},
        {"path": "GEM Global Solar/Wind Power Tracker xlsx", "status": "ASSESSED, NOT ACCESSED",
         "access": "downloads gated behind a JS form (auxunjnrktkmeqyoyngm.supabase.co presign); no static file link found",
         "license": "CC BY 4.0 stated by GEM for tracker data; form submission not automated to avoid circumventing the access path",
         "contribution": "would add solar/wind operating capacity (physical-supply side)",
         "limitation": "manual form download required for reproducibility; next step: one manual download with checksum, then re-run"},
        {"path": "PLN tradable renewable energy certificates (REC)", "status": "ASSESSED VIA NEWS",
         "access": "news-verified since ~2020 (Jakarta Post 2020-01-28; Indonesia Business Post 2024-10; SolarQuarter 2025-09)",
         "license": "no public license found for PLN publications; web.pln.co.id unreachable during this session",
         "contribution": "the mechanism by which Indonesian corporates (incl. data centers) claim renewable consumption",
         "limitation": "no public per-customer REC registry or volumes surfaced in our limited (news + one unreachable site) search; this does NOT establish that no registry or disclosure path exists — a targeted check of PLN/ESDM regulations and filings is a next step"},
        {"path": "Vendor/government announcements (Microsoft $1.7B Indonesia 2024, NVIDIA-Indosat Solo AI region, Oracle, AWS $5B)",
         "status": "ASSESSED, NOT INGESTED",
         "access": "newsroom pages; standard site terms; no structured license-clean dataset",
         "license": "newsroom text is copyrighted; quotation for research with attribution only",
         "contribution": "announcement layer only",
         "limitation": "announcements are not operating facilities, procurement or physical supply; no reproducible machine-readable coverage"},
        {"path": "I-REC / international certificate registries for SEA", "status": "ASSESSED, NOT ACCESSED",
         "access": "registry data behind account/fees; no public bulk license identified this session",
         "license": "registry terms; not reproduced here",
         "contribution": "would evidence procurement claims (certificate layer)",
         "limitation": "no public bulk path identified in our limited search; registry access may exist via accounts/fees or jurisdictional disclosures — absence not established"},
    ]


def main() -> None:
    hits = scan_aiddata()
    supply = gem_supply_context()
    gds = [h for h in hits if h["record_id"] == 106768]
    example = None
    if gds:
        g = gds[0]
        example = {
            "name": "GDS Nusajaya Tech Park Data Center Project, Phase 1 (Johor, Malaysia)",
            "layer_1_financing": {
                "record_id": g["record_id"], "title": g["title"],
                "status": g["status"], "amount_usd": g["amount_nominal_usd"],
                "green_label_note": ("AidData narrative quotes the facility agreement as a 'syndicated "
                                     "green term loan' (Dec 2023). This is GREEN-LABELLED FINANCING — "
                                     "a loan-market label quoted from the record. It is NOT evidence "
                                     "of renewable procurement, RECs, or the facility's energy mix; "
                                     "no procurement data was found in any inspected source."),
                "license": g["license"],
            },
            "layer_2_grid_context": {
                "peninsular_malaysia_gem_listed_operating_mw_subtotal":
                    supply["peninsular_malaysia_gem_listed_operating_mw_subtotal"],
                "unassigned_state_gem_listed_operating_mw": supply["unassigned_state_gem_listed_operating_mw"],
                "what_this_is_not": supply["what_this_is_not"],
                "note": ("Context only, NOT a supply link and NOT a generation mix: this is a "
                         "subtotal of GEM-API-listed operating units (incomplete by construction); "
                         "no dataset inspected connects this facility to any specific generator."),
            },
            "non_claims": [
                "No claim that GDS Nusajaya procures renewable energy (no procurement data found).",
                "No claim that the facility is physically supplied by any specific plant.",
                "The 'green loan' label is quoted as a financing attribute, not as an energy attribute.",
                "The absence of solar/wind in the GEM API is a coverage gap, not evidence about Malaysian renewables.",
            ],
            "claim_status": ("two documented context layers (financing record + grid asset snapshot) "
                             "with NO causal or contractual connection asserted"),
        }
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "question": ("Is there a permitted, reproducible public-data path connecting AI/digital "
                     "infrastructure with renewable energy in Indonesia or Southeast Asia?"),
        "answer": ("Partially: the announcement/financing layer and the physical-generation context "
                   "layer are each reproducibly accessible; the layers between them — operating "
                   "facility registries for data centers, renewable-procurement claims, and "
                   "certificate/REC registries — have no permitted, reproducible public path that "
                   "we could verify this session. Gap register below."),
        "aiddata_hits": hits,
        "gem_supply_context": supply,
        "gap_register": gap_register(),
        "exploratory_example": example,
    }
    (ROOT / "findings/ai_infra_re_scan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"AidData keyword hits: {len(hits)}; GEM-listed peninsular operating MW subtotal: "
          f"{supply['peninsular_malaysia_gem_listed_operating_mw_subtotal']} "
          f"(unassigned: {supply['unassigned_state_gem_listed_operating_mw']}); example: {bool(example)}")


if __name__ == "__main__":
    main()
