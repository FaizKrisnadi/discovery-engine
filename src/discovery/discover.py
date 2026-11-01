"""Discovery queries over the evidence graph.

Each finding is emitted with: the statement, the evidence chain (edge ids ->
evidence ids -> quoted source values), an explicit claim status, and what
single-dataset baselines would/would not show. Findings are candidates for
audit, never pre-labeled "verified".
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .graph import GEM_OBSERVED_AT
from .temporal import OwnershipClaim, classify_at, UNKNOWN

ROOT = Path(__file__).resolve().parents[2] if __name__ == "__main__" else Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FINDINGS = ROOT / "findings"

FINDINGS.mkdir(exist_ok=True)


def load_graph():
    d = json.loads((PROC / "evidence_graph.json").read_text())
    ents = {e["entity_id"]: e for e in d["entities"]}
    edges = d["edges"]
    ev = {e["evidence_id"]: e for e in d["evidence"]}
    return ents, edges, ev


def chain(edge_ids: list[str], edges: list[dict], ev: dict) -> list[dict]:
    by_id = {e["edge_id"]: e for e in edges}
    out = []
    for eid in edge_ids:
        e = by_id[eid]
        out.append({
            "edge_id": eid, "type": e["edge_type"], "statement": e["statement"],
            "claim_status": e["claim_status"], "attributes": e["attributes"],
            "evidence": [{"evidence_id": x["evidence_id"], "source": x["source"],
                          "locator": x["locator"], "field": x["field"], "quote": x["quote"],
                          "url": x["url"]} for x in (ev[i] for i in e["evidence_ids"])],
        })
    return out


def main() -> None:
    ents, edges, ev = load_graph()

    # indexes
    match_edges = [e for e in edges if e["edge_type"] == "SAME_PLANT_AS"]
    lender_edges = [e for e in edges if e["edge_type"] == "LENDER"]
    event_attr = {e["subject"]: e["attributes"] for e in edges if e["edge_type"] == "FINANCING_EVENT"}
    plant_attr = {e["subject"]: e["attributes"] for e in edges if e["edge_type"] == "PLANT_ATTRIBUTES"}
    owner_edges = [e for e in edges if e["edge_type"] == "OWNER_OF"]

    plant_name = {k: v["name"] for k, v in ents.items() if v["entity_type"] == "power_plant"}
    org_name = {k: v["name"] for k, v in ents.items() if v["entity_type"] == "organization"}
    event_plant = {e["subject"]: e["object"] for e in match_edges}

    findings = []

    # ---------- D1: financiers of multiple provisionally-matched plants ----------
    fin_plants = defaultdict(lambda: defaultdict(list))  # financier -> plant -> [records]
    for le in lender_edges:
        fin, ev_id = le["subject"], le["object"]
        rec_id = ev_id.split("::")[1]
        p = event_plant.get(ev_id)
        if not p:
            continue
        fin_plants[fin][p].append(rec_id)
    d1 = []
    for fin, pm in sorted(fin_plants.items(), key=lambda kv: -len(kv[1])):
        if len(pm) < 2:
            continue
        plant_list = []
        for p, recs in sorted(pm.items()):
            pa = plant_attr.get(p, {})
            plant_list.append({
                "plant": plant_name.get(p, p), "gem_location_id": p.split("::")[1],
                "gem_status": pa.get("status"), "gem_start_year": pa.get("start_year"),
                "records": recs,
                "plant_owner_parents": pa.get("parent"),
                "match_basis": "provisional AI match label (data/labels/match_labels.json), not human-verified",
            })
        d1.append({
            "financier": org_name.get(fin, fin),
            "distinct_matched_plants": len(pm),
            "plants": plant_list,
        })
    findings.append({
        "finding_id": "D1-shared-financiers",
        "question": "Which financiers have AidData-recorded loans to multiple Indonesian power plants that also appear in GEM (identity per provisional match labels)?",
        "claim_status": ("Loan records and plant records are each as stated by their secondary datasets "
                         "(AidData CLG-LMIC v1.0; GEM Ownership API build 2026-10-29). The record-to-plant "
                         "pairings are PROVISIONAL AI match labels, not human-verified facts, and a GEM "
                         "plant record does not independently verify either the identity or the finance "
                         "relationship."),
        "results": d1,
        "baseline": ("Within one dataset the combined view (loan rows with plant status/ownership fields "
                     "from the other dataset) does not exist; ordinary search surfaces such links case by "
                     "case (see evaluation.json for what one query surfaced and did not)."),
    })

    # ---------- D2: same sponsor name behind multiple provisionally-matched plants ----------
    by_parent = defaultdict(list)
    for p, pa in plant_attr.items():
        par = pa.get("parent")
        if not par:
            continue
        for part in par.split(";"):
            part = part.strip()
            name = part.split("[")[0].strip()
            if name and name.lower() not in ("pt pln (persero)", "to be determined"):
                by_parent[name].append((p, part))
    groups = defaultdict(list)
    for name, items in by_parent.items():
        groups[name].extend(items)
    d2 = []
    for name, items in groups.items():
        plants_hit = sorted({p for p, _ in items})
        if len(plants_hit) < 2:
            continue
        with_fin = []
        for p in plants_hit:
            recs = [e["subject"] for e in match_edges if e["object"] == p]
            if recs:
                # temporal classification per loan: does any SOURCE-DATED
                # ownership evidence cover the commitment year? GEM snapshot
                # edges are undated -> UNKNOWN; a later snapshot never
                # supports an earlier claim, and no validity date is invented.
                pair_results = []
                for r in recs:
                    cy = event_attr.get(r, {}).get("commitment_year")
                    # provenance-carrying but undated: GEM records no ownership
                    # dates, so date_basis stays "none" and no validity date is
                    # fabricated; the classifier must return UNKNOWN
                    claims = [OwnershipClaim(
                        source="GEM Ownership API snapshot",
                        locator=f"evidence_graph.json OWNER_OF edges into {p} (API build {GEM_OBSERVED_AT})",
                        observed_at=GEM_OBSERVED_AT,
                        valid_from=None, valid_to=None,
                        date_basis="none", holder=name)]
                    res = classify_at(claims, int(cy)) if cy else {
                        "status": UNKNOWN, "explanation": "no commitment year on record"}
                    pair_results.append({
                        "record_id": r.split("::")[1], "commitment_year": cy,
                        "ownership_at_commitment": res["status"],
                        "explanation": res["explanation"],
                    })
                with_fin.append({
                    "plant": plant_name.get(p, p),
                    "records": [r.split("::")[1] for r in recs],
                    "record_commitment_years": [event_attr.get(r, {}).get("commitment_year") for r in recs],
                    "temporal_support_per_loan": pair_results,
                })
        if not with_fin:
            continue
        d2.append({
            "parent_name_as_recorded_by_gem": name,
            "matched_plants": [plant_name.get(p, p) for p in plants_hit],
            "aiddata_financed": with_fin,
            "temporal_caveat": ("GEM parent fields describe the CURRENT state (API build "
                                f"{GEM_OBSERVED_AT}). Group composition at each loan's commitment "
                                "year is NOT established here; temporal_support_per_loan records "
                                "the classification explicitly. The only dated anchor available "
                                "is the press-reported Dec-2020 Datang-DSSP acquisition (graph "
                                "edge type OWNERSHIP_EVENT_REPORTED), which is portfolio-level, "
                                "postdates the 2012/2015 commitments, and never upgrades the "
                                "classification."),
            "identity_caveat": ("'Same sponsor group' is inferred from identical parent-name strings in GEM "
                                "across plants; no corporate registry document was inspected."),
        })
    findings.append({
        "finding_id": "D2-shared-sponsor-groups",
        "question": "Which GEM-recorded parent names appear across multiple Indonesian power plants that also have separate AidData-recorded Chinese financing?",
        "claim_status": ("Name-string co-occurrence across two secondary datasets. NOT a verified corporate "
                         "relationship; ownership applies to GEM's current snapshot, not to loan commitment "
                         "dates. Pairings rest on provisional match labels."),
        "results": d2,
        "baseline": ("Neither dataset alone joins equity-parent names to lending records across projects; "
                     "one ordinary web search surfaced the 2020 Datang-DSSP acquisition but not the "
                     "per-plant loan records (see evaluation.json)."),
    })

    # ---------- D3: status discrepancies between AidData event status and GEM plant status ----------
    d3 = []
    for me in match_edges:
        rec = me["subject"]
        p = me["object"]
        ea = event_attr.get(rec, {})
        pa = plant_attr.get(p, {})
        st_a, st_g = ea.get("status"), pa.get("status")
        if not st_a or not st_g:
            continue
        pair = (st_a, st_g)
        # candidate discrepancy pairs (conservative list; reviewed with evidence)
        discrepant = (
            (st_a == "Completion" and st_g == "construction")
            or (st_a == "Cancelled" and st_g == "operating")
            or (st_a == "Completion" and st_g == "planned")
            or (st_a.startswith("Pipeline") and st_g == "operating")
        )
        if discrepant:
            d3.append({
                "record_id": rec.split("::")[1], "title": ents[rec]["name"],
                "aiddata_status": st_a, "commitment_year": ea.get("commitment_year"),
                "gem_plant": plant_name.get(p, p), "gem_status": st_g,
                "gem_start_year": pa.get("start_year"),
                "gem_capacity_by_status": None,
                "caveat": ("AidData 'Completion' may refer to the financing agreement or a phase, not the "
                           "current plant; project/phase identity under the same name is not established."),
            })
    # attach gem capacity by status via HAS_CAPACITY self edges
    cap_by_plant = {e["subject"]: e["attributes"]["capacity_mw_by_status"] for e in edges if e["edge_type"] == "HAS_CAPACITY"}
    for x in d3:
        pid = next(e["object"] for e in match_edges if e["subject"] == f"AID::{x['record_id']}")
        x["gem_capacity_by_status"] = cap_by_plant.get(pid)
        x["gem_plant_id"] = pid.split("::")[1]
    findings.append({
        "finding_id": "D3-status-discrepancies",
        "question": "Where do AidData event statuses and GEM plant statuses conflict for the same provisionally-matched project?",
        "claim_status": ("Status fields from two secondary datasets disagree as recorded; whether they "
                         "describe the same project/phase is unresolved, and AidData 'Completion' may "
                         "refer to a financing agreement or phase rather than plant completion."),
        "results": d3,
        "baseline": "Each source states its own status without flagging the conflict; a single-dataset user never sees it.",
    })

    # ---------- D5: identity conflicts surfaced then downgraded / kept ambiguous ----------
    label_data = json.loads((ROOT / "data/labels/match_labels.json").read_text())
    amb = [x for x in label_data["labels"] if x["label"] == "AMBIGUOUS"]
    d5 = [{
        "record_id": x["record_id"], "note": x["note"],
        "machine_top_location_id": x.get("machine_top_location_id"),
    } for x in amb]
    findings.append({
        "finding_id": "D5-identity-conflicts",
        "question": "Which records plausibly correspond to a GEM asset but were NOT merged because identity could not be established (incl. baseline-search conflicts)?",
        "claim_status": "unresolved by design; no merge performed; absence from one baseline search is limited search results, not proof of non-existence",
        "results": d5,
        "baseline": "A name-search user would either merge them silently (false positive) or never notice the conflict.",
    })

    # ---------- D4: commitment year vs GEM start year (timeline gaps) ----------
    d4 = []
    for me in match_edges:
        rec, p = me["subject"], me["object"]
        ea, pa = event_attr.get(rec, {}), plant_attr.get(p, {})
        cy, sy = ea.get("commitment_year"), pa.get("start_year")
        try:
            sy, cy = int(sy), int(cy)
        except (TypeError, ValueError):
            continue
        d4.append({"record_id": rec.split("::")[1], "plant": plant_name.get(p, p),
                   "commitment_year": cy, "gem_start_year": sy, "gap_years": sy - cy})
    d4.sort(key=lambda x: -x["gap_years"])
    findings.append({
        "finding_id": "D4-commitment-to-cod-gaps",
        "question": "How long elapses between recorded Chinese commitment and GEM plant start year for matched plants?",
        "claim_status": ("Dates as recorded by two secondary datasets; the gap is descriptive, not causal, "
                         "and pairings rest on provisional match labels."),
        "results": d4,
        "baseline": "AidData has implementation years for some records; GEM start_year is plant-level; the combined view is not in either source.",
    })

    (FINDINGS / "findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=1))
    print(f"findings written: {[(f['finding_id'], len(f['results'])) for f in findings]}")


if __name__ == "__main__":
    main()
