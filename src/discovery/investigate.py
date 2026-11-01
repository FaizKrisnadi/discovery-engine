"""Investigation CLI: follow one project through finance, energy, status and
identity over time, showing what is known, what is uncertain and what is
contradicted — every line reversible to a source version.

Usage:
  .venv/bin/python -m discovery.investigate gds-nusajaya-ntp1
  .venv/bin/python -m discovery.investigate airtrunk-jhb1-vppa
"""
from __future__ import annotations

import sys
from pathlib import Path

from .engine import Engine, content_hash

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "processed" / "engine.sqlite3"

DIMENSIONS = {
    "finance": ["HAS_FINANCING_PARTICIPANT", "HAS_TOTAL_FACILITY_AMOUNT", "HAS_VPPA_SIGNED",
                "HAS_OFFTAKER", "HAS_GREEN_LABEL", "HAS_USE_OF_PROCEEDS", "HAS_FINANCING_EVENT",
                "HAS_FINANCING", "HAS_PPA_SIGNED", "HAS_PPA_COUNTERPARTY", "HAS_INVESTMENT",
                "HAS_DEVELOPMENT_PARTNER", "HAS_PROCEEDS_ALLOCATION"],
    "energy": ["RENEWABLE_PROCUREMENT_STATUS", "HAS_RENEWABLE_TARGET", "IS_PHYSICAL_SUPPLY_OF",
               "UNDER_POLICY_PROGRAMME", "HAS_GEM_LISTED_OPERATING_SUBTOTAL",
               "HAS_GENERATOR_DEVELOPER", "HAS_CONSTRUCTION_SCHEDULE",
               "SUPPORTS_CONSUMPTION_OF", "HAS_onsite_solar_plan", "HAS_UTILITY_CONNECTION",
               "IS_RENEWABLE_SUPPLY"],
    "status": ["HAS_RECORD_STATUS", "HAS_OPERATION_STATUS", "HAS_SUPPLY_SCHEDULE"],
    "capacity": ["HAS_CAPACITY_CLAIM"],
    "identity": ["HAS_SPONSOR", "LOCATED_IN", "IS_AI_WORKLOAD", "HAS_IDENTIFIER_LIMITATION",
                 "HAS_OPERATOR", "HAS_CONTROL_ASSERTION", "HAS_OWNER_REPORTED",
                 "HAS_INSTITUTIONAL_CONTEXT", "HAS_GDS_RELATIONSHIP_CLAIM",
                 "HAS_COMPANY_AI_DEPLOYMENT_CLAIM", "HAS_JOINT_VENTURE_CLAIM",
                 "CORRECTION_RECORD", "SUPERSEDES_PRIOR_FINDING"],
}


def fmt_time(t: str | None, prec: str) -> str:
    return f"{t or 'time unknown'} ({prec})" if t else "time unknown"


def show(project_key: str) -> None:
    eng = Engine(DB)
    row = eng.conn.execute(
        """SELECT entity_pk, name FROM entities
           WHERE entity_type='project' AND name=?
           ORDER BY (identifier IS NULL), entity_pk LIMIT 1""", (project_key,)).fetchone()
    if not row:
        projects = [r[0] for r in eng.conn.execute(
            "SELECT name FROM entities WHERE entity_type='project'")]
        print(f"no project '{project_key}' in engine DB; ingested projects: {projects}")
        raise SystemExit(1)
    epk = row[0]
    tl = eng.project_timeline(epk)
    ident = eng.conn.execute(
        "SELECT name, identifier, identity_status, scope FROM entities WHERE entity_pk=?",
        (epk,)).fetchone()
    print(f"PROJECT {project_key} — {len(tl)} claim(s) on record")
    print(f"  identity: name={ident[0]!r} identifier={ident[1]!r} "
          f"status={ident[2]} (engine-assigned case key, not a registry id) scope={ident[3]}")
    ev = eng.conn.execute(
        "SELECT ts, outcome, COUNT(*) FROM retrieval_events WHERE source_ref IN "
        "(SELECT DISTINCT source_ref FROM sources s JOIN observations o ON o.source_pk=s.source_pk "
        "JOIN claims c ON c.observation_pk=o.obs_pk WHERE c.subject_pk=?) "
        "GROUP BY ts, outcome ORDER BY ts", (epk,)).fetchall()
    if ev:
        print(f"  retrieval history (append-only): {sum(x[2] for x in ev)} event(s)")
        for ts, outcome, n in ev:
            print(f"    {ts[:19]}  {outcome} x{n}")
    snaps = eng.conn.execute(
        "SELECT DISTINCT s.source_ref, s.version_index, s.raw_checksum, s.snapshot_path, "
        "s.raw_retention, s.checksum_basis FROM sources s "
        "WHERE s.source_ref IN (SELECT DISTINCT source_ref FROM sources s2 "
        "JOIN observations o ON o.source_pk=s2.source_pk JOIN claims c ON c.observation_pk=o.obs_pk "
        "WHERE c.subject_pk=?) ORDER BY s.source_ref, s.version_index", (epk,)).fetchall()
    print(f"  source versions/snapshots: {len(snaps)} row(s)")
    for ref, vi, ck, snap, ret, basis in snaps:
        print(f"    v{vi} {basis} {ck[:12]} retention={ret} snap={Path(snap).name if snap else '-'} {ref[:60]}")
    adj = eng.conn.execute(
        "SELECT a.decision, a.decided_by, e1.name, e2.name FROM adjudications a "
        "JOIN entities e1 ON e1.entity_pk=a.entity_pk_a JOIN entities e2 ON e2.entity_pk=a.entity_pk_b"
    ).fetchall()
    if adj:
        print("  identity adjudications:")
        for d, by, n1, n2 in adj:
            print(f"    {d}: {n1} vs {n2} (by {by})")
    print()

    supersession_map = eng.active_supersessions()
    for dim, preds in DIMENSIONS.items():
        rows = [r for r in tl if r["predicate"] in preds]
        current = [r for r in rows if not r.get("superseded_by")]
        superseded = [r for r in rows if r.get("superseded_by")]
        print(f"== {dim.upper()} ({len(current)} current claim(s), {len(superseded)} superseded) ==")
        groups = eng.contradictions_for(epk)
        gmap = {}
        for g in groups:
            gmap.setdefault(g["claim_pk"], g)
        for r in current:
            val = r["object_name"] or r["object_literal"] or ""
            g = gmap.get(r["claim_pk"])
            flag = f"  << POSSIBLE CONTRADICTION (kind={g['kind']}; unproven)" if g else ""
            if r["predicate"] == "SUPERSEDES_PRIOR_FINDING":
                flag = "  << CORRECTION RECORD"
            ev = r["evidence_kind"]
            ver = f", raw-verified={r['verified_against_raw']}" if r["verified_against_raw"] is not None else ""
            unit = f" unit={r['unit']}" if r["unit"] else ""
            grain = f" grain={r['grain']}" if r["grain"] else ""
            print(f"  [{fmt_time(r['claim_time'], r['time_precision'])}] {r['predicate']}: {val[:150]}{flag}")
            print(f"      certainty={r['certainty']} review={r['review_status']} evidence={ev}{ver}{unit}{grain}")
            print(f"      source: {r['publisher']} v{r['source_version']} ({r['access_status']}) {r['source_ref'][:80]}")
            print(f"      quote: {r['quote'][:220]}")
        for r in superseded:
            val = (r["object_literal"] or "")[:110]
            print(f"  [SUPERSEDED — not current] {r['predicate']}: {val}")
            print(f"      superseded by {r['superseded_by'][:16]}… — basis: {(r['supersession_basis'] or '')[:160]}")
            print(f"      (still inspectable: /claim/{r['claim_pk']})")
        if not rows:
            print("  (no claims)")
        print()

    groups = eng.contradictions_for(epk)
    print(f"== CONTRADICTIONS: {len(groups)} flagged claim(s); ALL groups kind='possible' (unproven) ==")
    seen_groups = set()
    for g in groups:
        if g["group_pk"] in seen_groups:
            continue
        seen_groups.add(g["group_pk"])
        row = eng.conn.execute(
            """SELECT c.predicate, c.object_literal, o.quote, s.publisher
               FROM claims c JOIN observations o ON o.obs_pk=c.observation_pk
               JOIN sources s ON s.source_pk=o.source_pk WHERE c.claim_pk=?""",
            (g["claim_pk"],)).fetchone()
        if row:
            print(f"  [{row[0]}] {row[1]}")
            print(f"      {row[3]}: “{row[2][:130]}”")
            print(f"      scope: {g['scope_note']}")
    print()

    print("== WHAT IS KNOWN / UNKNOWN ==")
    for dim, res in eng.unknowns_for(epk, DIMENSIONS).items():
        print(f"  {dim}: {res}")
    print("\nReview status: all claims are machine_extracted; no human verification is claimed.")
    print("Identity ambiguity guard: aliases with status 'ambiguous' are never merged "
          "(e.g., 'dayone' vs 'gds-holdings').")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    show(sys.argv[1].strip())
