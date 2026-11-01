"""Conservative audit of claim supersessions (supervisor audit 2026-10-31).

Policy (documented in docs/architecture.md):
  (a) CONCLUSION CORRECTION — a new source supersedes an earlier research
      conclusion (e.g., a bounded-search 'not established' finding overtaken
      by a company statement that was missed). Valid supersession.
  (b) EVENT EVOLUTION — an agreement (2024-09-04) and a later reported
      closing are DIFFERENT DATED EVENTS that coexist; neither is false.
      Superseding one with the other is an ERROR → withdrawn (row preserved
      with reason; audit history intact).
  (c) REFINEMENT — same conclusion, better/complete basis (e.g., physical
      supply still not established, but now with the TNB connection and the
      FY24 consumption-support wording recorded). Valid supersession; the
      conclusion-unchanged fact is part of the basis.

Also distinguishes: 'not established' (bounded search) is NOT the same as
'contradicted' (a source affirming the opposite). The JHB2 loan reporting
contradicts only the claim that the US$2.3B loan finances JHB1 — it does not
contradict JHB1 financing in general; JHB1 financing is now established by
the SLL statement, not by absence of the JHB2 link.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery.engine import Engine, now_iso

DB = ROOT / "data" / "processed" / "engine.sqlite3"
OUT = ROOT / "findings" / "supersession_audit.json"

DECIDED_BY = "this project (AI-generated, unreviewed; conservative audit per supervisor review)"

WITHDRAW_REASON = (
    "Event-evolution conflation: the superseded claim reported AirTrunk's ownership "
    "including a late-2024 closing (secondary, deal tracker), while the superseding claim "
    "records the 2024-09-04 definitive agreement (primary, subject to FIRB approval). An "
    "agreement and a later reported closing are different dated events that COEXIST; "
    "neither is false. Both claims are restored to current status. No claim of control, "
    "ownership terms or AI workloads is implied by either.")


def main() -> None:
    eng = Engine(DB)
    rows = eng.conn.execute(
        "SELECT supersession_pk, superseded_claim_pk, superseding_claim_pk, status, "
        "COALESCE(withdrawn_reason,'') FROM supersessions").fetchall()

    audit = {"audited_at": datetime.now(timezone.utc).isoformat(),
             "policy": {"conclusion_correction": "valid supersession (kept)",
                        "event_evolution": "withdrawn (distinct dated events coexist)",
                        "refinement": "valid supersession; conclusion unchanged (kept)"},
             "actions": [], "already_withdrawn": 0, "kept": {"HAS_FINANCING": 0,
                                                             "IS_PHYSICAL_SUPPLY_OF": 0}}

    for spk, old, new, status, wreason in rows:
        pred = eng.conn.execute("SELECT predicate FROM claims WHERE claim_pk=?",
                                (old,)).fetchone()[0]
        if status == "withdrawn":
            audit["already_withdrawn"] += 1
            continue
        if pred == "HAS_OWNER_REPORTED":
            eng.withdraw_supersession(
                spk, WITHDRAW_REASON, DECIDED_BY)
            audit["actions"].append({"supersession_pk": spk[:16], "predicate": pred,
                                     "action": "withdrawn", "category": "event_evolution"})
        elif pred == "HAS_FINANCING":
            audit["kept"]["HAS_FINANCING"] += 1
            audit["actions"].append({"supersession_pk": spk[:16], "predicate": pred,
                                     "action": "kept", "category": "conclusion_correction"})
        elif pred == "IS_PHYSICAL_SUPPLY_OF":
            audit["kept"]["IS_PHYSICAL_SUPPLY_OF"] += 1
            audit["actions"].append({"supersession_pk": spk[:16], "predicate": pred,
                                     "action": "kept", "category": "refinement"})
        else:
            audit["actions"].append({"supersession_pk": spk[:16], "predicate": pred,
                                     "action": "kept", "category": "unclassified"})
    eng.commit()

    # post-conditions
    active = eng.conn.execute(
        "SELECT c.predicate, COUNT(*) FROM supersessions s JOIN claims c "
        "ON c.claim_pk=s.superseded_claim_pk WHERE s.status='active' "
        "GROUP BY c.predicate").fetchall()
    wd = eng.conn.execute(
        "SELECT COUNT(*) FROM supersessions WHERE status='withdrawn'").fetchone()[0]
    audit["post_state"] = {"active_by_predicate": dict(active), "withdrawn_total": wd}
    (OUT).write_text(json.dumps(audit, ensure_ascii=False, indent=1))
    print(json.dumps({"active_by_predicate": dict(active), "withdrawn_total": wd,
                      "actions": len(audit["actions"])}, indent=1))


if __name__ == "__main__":
    main()
