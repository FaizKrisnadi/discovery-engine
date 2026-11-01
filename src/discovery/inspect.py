"""Evidence inspector CLI: every finding/edge is reversible to its sources.

Usage:
  python -m discovery.inspect finding D2-shared-sponsor-groups
  python -m discovery.inspect record 62064
  python -m discovery.inspect plant L100000102804
  python -m discovery.inspect edge EG00123
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if __name__ == "__main__" else Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FINDINGS = ROOT / "findings"


def load():
    g = json.loads((PROC / "evidence_graph.json").read_text())
    return ({e["entity_id"]: e for e in g["entities"]}, g["edges"],
            {e["evidence_id"]: e for e in g["evidence"]})


def print_evidence(ev: dict, indent: str = "      ") -> None:
    print(f"{indent}evidence {ev['evidence_id']}: source={ev['source']} ({ev['source_version']}, {ev['license']})")
    print(f"{indent}  locator: {ev['locator']} field: {ev['field']}")
    q = ev["quote"]
    print(f"{indent}  quote: {q[:400]}{'…' if len(q) > 400 else ''}")
    if ev.get("url"):
        print(f"{indent}  url: {ev['url']}")


def show_finding(fid: str) -> None:
    findings = json.loads((FINDINGS / "findings.json").read_text())
    f = next((x for x in findings if x["finding_id"] == fid), None)
    if not f:
        print(f"no finding {fid}; have: {[x['finding_id'] for x in findings]}")
        return
    print(f"FINDING {f['finding_id']}\n  question: {f['question']}\n  claim_status: {f['claim_status']}\n  baseline: {f['baseline']}")
    print(json.dumps(f["results"], ensure_ascii=False, indent=1)[:4000])


def show_record(rec_id: str) -> None:
    ents, edges, ev = load()
    subj = f"AID::{rec_id}"
    print(f"RECORD {rec_id}: {ents.get(subj, {}).get('name')}")
    for e in edges:
        if e["subject"] == subj or e["object"] == subj:
            print(f"\n  [{e['edge_id']}] {e['edge_type']} ({e['claim_status']}): {e['statement']}")
            for eid in e["evidence_ids"]:
                print_evidence(ev[eid])


def show_plant(lid: str) -> None:
    ents, edges, ev = load()
    subj = f"GEM::{lid}"
    print(f"PLANT {lid}: {ents.get(subj, {}).get('name')}")
    for e in edges:
        if e["subject"] == subj or e["object"] == subj:
            print(f"\n  [{e['edge_id']}] {e['edge_type']} ({e['claim_status']}): {e['statement'][:300]}")
            for eid in e["evidence_ids"][:4]:
                print_evidence(ev[eid])


def show_edge(eid: str) -> None:
    _, edges, ev = load()
    e = next((x for x in edges if x["edge_id"] == eid), None)
    if not e:
        print("no such edge")
        return
    print(f"[{e['edge_id']}] {e['edge_type']} ({e['claim_status']}): {e['statement']}")
    print(f"  attributes: {json.dumps(e['attributes'], ensure_ascii=False)[:400]}")
    for x in e["evidence_ids"]:
        print_evidence(ev[x])


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, arg = sys.argv[1], sys.argv[2]
    {"finding": show_finding, "record": show_record, "plant": show_plant, "edge": show_edge}[cmd](arg)


if __name__ == "__main__":
    main()
