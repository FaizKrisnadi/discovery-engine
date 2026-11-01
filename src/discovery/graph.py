"""Build the evidence graph: entities, typed dated edges, and evidence records.

Everything the graph asserts carries at least one evidence id pointing to an
evidence record that quotes the exact source value(s), their locator, license
and retrieval time. Machine matching edges are claim_status='inferred' and cite
the provisional label note; they are never silently promoted to facts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if __name__ == "__main__" else Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
LABELS = ROOT / "data" / "labels"

AIDDATA_VERSION = "AidData China's Loans and Grants to Low- and Middle-Income Countries, v1.0 (2025-11-18)"
GEM_VERSION = "GEM Ownership Tracing API, build 2026-10-29 (metadata endpoint)"
GLEIF_VERSION = "GLEIF API v1, golden copy 2026-10-29"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


GEM_OBSERVED_AT = "2026-10-29"  # API build timestamp from /metadata (observation date, not validity date)


def _snapshot_validity() -> dict:
    """Validity block for relationships taken from GEM's current-state snapshot.

    GEM records no ownership start/end dates, so validity is UNKNOWN by
    construction: the API build date is when the relationship was OBSERVED,
    never evidence that it held earlier. No validity date is ever invented.
    """
    return {
        "status": "unknown",
        "observed_at": GEM_OBSERVED_AT,
        "valid_from": None,
        "valid_to": None,
        "date_basis": "none",
        "note": ("relationship as recorded by GEM's current-state snapshot; no ownership "
                 "start/end date is available from the source, so validity at any earlier "
                 "date is unknown and is never inferred from this snapshot"),
    }


class GraphBuilder:
    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.evidence: dict[str, dict] = {}
        self._ev_n = 0
        self._edge_n = 0

    def add_evidence(self, *, source: str, source_version: str, license_: str, locator: str,
                     field: str, value, quote: str, url: str | None = None) -> str:
        self._ev_n += 1
        eid = f"EV{self._ev_n:05d}"
        self.evidence[eid] = {
            "evidence_id": eid, "source": source, "source_version": source_version,
            "license": license_, "locator": locator, "field": field, "value": value,
            "quote": quote, "url": url, "retrieved_at": _now(),
        }
        return eid

    def add_edge(self, *, edge_type: str, subject: str, object_: str, statement: str,
                 evidence_ids: list[str], claim_status: str = "documented",
                 attributes: dict | None = None, valid_from=None) -> str:
        assert evidence_ids, f"edge {edge_type} {subject}->{object_} has no evidence"
        for e in evidence_ids:
            assert e in self.evidence, f"unknown evidence id {e}"
        self._edge_n += 1
        eid = f"EG{self._edge_n:05d}"
        self.edges.append({
            "edge_id": eid, "edge_type": edge_type, "subject": subject, "object": object_,
            "statement": statement, "claim_status": claim_status,
            "evidence_ids": evidence_ids, "attributes": attributes or {},
            "valid_from": valid_from, "created_at": _now(),
        })
        return eid

    def add_entity(self, ent_id: str, ent_type: str, name: str, **extra) -> str:
        if ent_id not in self.entities:
            self.entities[ent_id] = {"entity_id": ent_id, "entity_type": ent_type, "name": name, **extra}
        return ent_id


def norm_org(name: str) -> str:
    return " ".join(str(name).lower().replace("(", " ").replace(")", " ").split())


def build() -> GraphBuilder:
    gb = GraphBuilder()

    events = json.loads((PROC / "aiddata_idn_energy.json").read_text())
    plants = {p["location_id"]: p for p in json.loads((PROC / "gem_idn_plants.json").read_text())}
    loc_details = {l["location_id"]: l for l in json.loads((RAW / "gem_idn_matched_locations.json").read_text())["locations"]}
    labels = {x["record_id"]: x for x in json.loads((LABELS / "match_labels.json").read_text())["labels"]}
    gleif = json.loads((PROC / "gleif_enrichment.json").read_text())

    def org_ent(name: str, origin: str) -> str:
        eid = f"ORG::{norm_org(name)}"
        gb.add_entity(eid, "organization", name, name_origin=origin)
        return eid

    # --- GEM plants, owners, parents ---
    for lid, p in plants.items():
        pid = f"GEM::{lid}"
        det = loc_details.get(lid)
        ev_fields = {}
        if det:
            # /locations/{id} nests per-unit field blocks; plant-level fields
            # (owner, parent, status) repeat per unit, start_year can differ
            fsets = [u.get("coal_plant_fields") or {} for u in det.get("units", [])]
            fsets = [f for f in fsets if f]
            if fsets:
                starts = sorted({f.get("start_year") for f in fsets if f.get("start_year") is not None})
                ev_fields = {
                    "start_year": starts[0] if starts else None,
                    "start_year_all_units": starts,
                    "status": fsets[0].get("status"),
                    "owner": fsets[0].get("owner"),
                    "parent": fsets[0].get("parent"),
                    "captive": fsets[0].get("captive"),
                    "capacity_megawatts": fsets[0].get("capacity_megawatts"),
                }
                ev_fields = {k: v for k, v in ev_fields.items() if v is not None}
        ev_cap = gb.add_evidence(
            source="GEM Ownership Tracing API", source_version=GEM_VERSION, license_=p["license"],
            locator=f"/assets?country=Indonesia (location {lid})", field="units[]",
            value={"capacity_mw_by_status": p["capacity_mw_by_status"], "unit_count": p["unit_count"],
                   "unit_statuses": p["unit_statuses"], "owners": p["owners"]},
            quote=json.dumps({k: p[k] for k in ("plant_name", "unit_count", "capacity_mw_by_status", "unit_statuses")}, ensure_ascii=False),
            url=p["wiki_url"])
        gb.add_entity(pid, "power_plant", p["plant_name"], location_id=lid, asset_type=p["asset_type"],
                      state_province=p["state_province"], wiki_url=p["wiki_url"])
        gb.add_edge(edge_type="HAS_CAPACITY", subject=pid, object_=pid,  # self-edge carries attributes
                    statement=f"{p['plant_name']} has {p['unit_count']} unit(s); capacity by status {p['capacity_mw_by_status']} MW (GEM, unit-level)",
                    evidence_ids=[ev_cap], attributes={"capacity_mw_by_status": p["capacity_mw_by_status"]})
        if det and ev_fields:
            ev_det = gb.add_evidence(
                source="GEM Ownership Tracing API", source_version=GEM_VERSION, license_=p["license"],
                locator=f"/locations/{lid}", field="coal_plant_fields", value=ev_fields,
                quote=json.dumps(ev_fields, ensure_ascii=False), url=f"https://api.globalenergymonitor.org/locations/{lid}")
            gb.add_edge(edge_type="PLANT_ATTRIBUTES", subject=pid, object_=pid,
                        statement=f"{p['plant_name']}: start_year={ev_fields.get('start_year')}, status={ev_fields.get('status')}, owner={ev_fields.get('owner')}, parent={ev_fields.get('parent')}",
                        evidence_ids=[ev_det], attributes=ev_fields)
        for o in p["owners"]:
            if o["name"] in ("to be determined",):
                continue
            oe = org_ent(o["name"], "gem_owner")
            ev = gb.add_evidence(
                source="GEM Ownership Tracing API", source_version=GEM_VERSION, license_=p["license"],
                locator=f"/assets?country=Indonesia (location {lid}, owner {o['entity_id']})",
                field="owners[].ownership_share", value=o,
                quote=f"{o['name']} (entity {o['entity_id']}) listed as owner of {p['plant_name']} with share {o['max_share']}",
                url=p["wiki_url"])
            gb.add_edge(edge_type="OWNER_OF", subject=oe, object_=pid,
                        statement=f"{o['name']} is listed as an owner of {p['plant_name']} (max unit-level share {o['max_share']}%) as of the {GEM_OBSERVED_AT} GEM snapshot; validity at earlier dates unknown",
                        evidence_ids=[ev], attributes={"max_share_pct": o["max_share"], "hq_country": o["hq_country"],
                                                       "validity": _snapshot_validity()})

    # --- AidData events ---
    for r in events:
        eid_ = f"AID::{r['record_id']}"
        ev = gb.add_evidence(
            source="AidData CLG-LMIC v1.0", source_version=AIDDATA_VERSION,
            license_="ODC-By 1.0 (License sheet of dataset workbook)",
            locator=f"Record {r['record_id']}", field="row",
            value=r,
            quote=json.dumps({k: r[k] for k in ("title", "status", "commitment_year", "amount_nominal_usd",
                                                "funding_agencies_parent", "direct_receiving_agencies")}, ensure_ascii=False),
            url=(r["source_urls"][0] if r["source_urls"] else None))
        gb.add_entity(eid_, "financing_event", r["title"], record_id=r["record_id"])
        gb.add_edge(edge_type="FINANCING_EVENT", subject=eid_, object_=eid_,
                    statement=r["title"], evidence_ids=[ev],
                    attributes={"status": r["status"], "commitment_year": r["commitment_year"],
                                "amount_nominal_usd": r["amount_nominal_usd"],
                                "linked_record_ids": r["linked_record_ids"],
                                "source_urls": r["source_urls"]})
        for fa in r["funding_agencies_parent"]:
            oe = org_ent(fa, "aiddata_financier")
            gb.add_edge(edge_type="LENDER", subject=oe, object_=eid_,
                        statement=f"{fa} is recorded as a funding agency of record {r['record_id']}",
                        evidence_ids=[ev], valid_from=r["commitment_year"])
        for ra in r["direct_receiving_agencies"]:
            oe = org_ent(ra, "aiddata_receiver")
            gb.add_edge(edge_type="RECEIVER", subject=eid_, object_=oe,
                        statement=f"{ra} is recorded as a direct receiving agency of record {r['record_id']}",
                        evidence_ids=[ev], valid_from=r["commitment_year"])

    # --- match edges (inferred, provisional labels) ---
    for rec_id, lab in labels.items():
        if lab["label"] != "MATCH" or not lab["gem_location_id"]:
            continue
        ev_lab = gb.add_evidence(
            source="provisional match labels (AI-generated)", source_version="data/labels/match_labels.json",
            license_="internal artifact", locator=f"record {rec_id}",
            field="label/note", value=lab,
            quote=lab["note"] + (f" [machine top candidate: {lab['machine_top_location_id']}]" if lab.get("machine_top_location_id") else ""),
            url=None)
        ev_rec = gb.add_evidence(
            source="AidData CLG-LMIC v1.0", source_version=AIDDATA_VERSION, license_="ODC-By 1.0",
            locator=f"Record {rec_id}", field="Title", value=None,
            quote=next(e["quote"] for e in gb.evidence.values() if e["locator"] == f"Record {rec_id}"))
        ev_gem = gb.add_evidence(
            source="GEM Ownership Tracing API", source_version=GEM_VERSION, license_="CC BY 4.0",
            locator=f"/locations/{lab['gem_location_id']}", field="plant_name", value=None,
            quote=plants[lab["gem_location_id"]]["plant_name"],
            url=plants[lab["gem_location_id"]]["wiki_url"])
        gb.add_edge(edge_type="SAME_PLANT_AS", subject=f"AID::{rec_id}", object_=f"GEM::{lab['gem_location_id']}",
                    statement=f"Record {rec_id} is provisionally matched to GEM plant {plants[lab['gem_location_id']]['plant_name']}",
                    evidence_ids=[ev_rec, ev_gem, ev_lab], claim_status="inferred",
                    attributes={"label": lab["label"], "human_added": lab.get("human_added", False),
                                "machine_top_wrong": lab.get("machine_top_wrong", False)})

    # --- GLEIF identifiers ---
    for key, q in gleif["queries"].items():
        cands = gleif["queries"][key]["candidates"]
        oe = org_ent(key, "aiddata_or_gem")
        ev_g = gb.add_evidence(
            source="GLEIF API", source_version=GLEIF_VERSION, license_=gleif["license"],
            locator=f"/lei-records?filter[entity.legalName]={q}", field="lei-records",
            value=q, quote=json.dumps(q, ensure_ascii=False), url="https://api.gleif.org")
        gb.add_edge(edge_type="GLEIF_QUERY", subject=oe, object_=oe,
                    statement=f"GLEIF legalName query '{q}' returned {len(cands)} candidate(s)",
                    evidence_ids=[ev_g])
        for c in cands:
            ev_lei = gb.add_evidence(
                source="GLEIF API", source_version=GLEIF_VERSION, license_=gleif["license"],
                locator=f"/lei-records/{c['lei']}", field="entity.legalName",
                value=c["legal_name"], quote=f"{c['legal_name']} [{c['lei']}] country={c['country']} status={c['registration_status']}",
                url=f"https://api.gleif.org/api/v1/lei-records/{c['lei']}")
            gb.add_edge(edge_type="HAS_LEI_CANDIDATE", subject=oe, object_=f"LEI::{c['lei']}",
                        statement=f"{key} has GLEIF candidate {c['legal_name']} ({c['country']})",
                        evidence_ids=[ev_lei], claim_status="reported",
                        attributes={"lei": c["lei"], "country": c["country"]})
            gb.add_entity(f"LEI::{c['lei']}", "lei_record", c["legal_name"], country=c["country"])

    # --- dated REPORTED ownership events (the only dated anchors we have) ---
    # From the 2026-10-30 baseline search (transcript in findings/evaluation.json):
    # press reports of China Datang acquiring a majority stake in Dian Swastatika
    # Sentosa's thermal plants (~$394M), December 2020. This is a dated REPORTED
    # event at portfolio level; it is NOT validity evidence for any specific
    # plant and never upgrades snapshot-based ownership edges.
    datang = org_ent("China Datang Overseas Investment Co Ltd", "gem_owner")
    dss = org_ent("PT Dian Swastatika Sentosa Tbk", "gem_owner")
    ev_acq = gb.add_evidence(
        source="web search (baseline transcript)", source_version="findings/evaluation.json baseline_searches[0]",
        license_="cited press references (Business Times, Caixin Global; retrieved 2026-10-30)",
        locator="findings/evaluation.json -> baseline_searches[0].references_retrieved",
        field="reported acquisition", value={"year": 2020, "month": 12, "precision": "month"},
        quote=("China Datang bought a majority stake in PT Dian Swastatika Sentosa's (DSS) thermal "
               "power plants in Indonesia for $394 million; deal reported late December 2020"),
        url="https://www.businesstimes.com.sg")
    gb.add_edge(edge_type="OWNERSHIP_EVENT_REPORTED", subject=datang, object_=dss,
                statement=("Press-reported acquisition (Dec 2020) of a majority stake in DSS thermal "
                           "plants by China Datang; portfolio-level report, not plant-level validity evidence"),
                evidence_ids=[ev_acq], claim_status="reported",
                attributes={"event_year": 2020, "date_precision": "month",
                            "caveat": ("does not establish which plants transferred, when ownership of "
                                       "Sumsel-5/Kendari-3 specifically began, or any pre-2021 state")})

    return gb


def main() -> None:
    gb = build()
    out = ROOT / "data" / "processed" / "evidence_graph.json"
    out.write_text(json.dumps({
        "generated_at": _now(),
        "entities": list(gb.entities.values()),
        "edges": gb.edges,
        "evidence": list(gb.evidence.values()),
    }, ensure_ascii=False, indent=1))
    print(f"entities={len(gb.entities)} edges={len(gb.edges)} evidence={len(gb.evidence)}")


if __name__ == "__main__":
    main()
