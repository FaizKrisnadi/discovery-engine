"""Local, READ-ONLY investigation interface over the evidence engine.

Pure route functions return (status, content_type, html_body) so they are
directly testable; scripts/serve_investigation.py wraps them in a stdlib
http.server bound to 127.0.0.1. The database is opened with SQLite URI
mode=ro — the interface physically cannot write. No destructive operation
exists on this path.

Discipline carried into every page:
- A persistent banner states all content is AI-generated and unreviewed.
- Claims show evidence kind, raw-verification, certainty, review status,
  unit/grain, and their exact quote with source version + snapshot retention.
- Identity pages show scope, identity status, aliases, adjudications and any
  unresolved adjudication conflicts.
- Nothing implies physical electricity supply, AI workloads, or renewable
  procurement beyond what recorded claims say (negations are explicit claims).
"""
from __future__ import annotations

import html
import json
import sqlite3
from pathlib import Path

import sys

from discovery.engine import file_sha256

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "processed" / "engine.sqlite3"
SNAP_ROOT = ROOT / "data" / "processed" / "evidence_snapshots"  # must match Engine.snap_dir

BANNER = (
    "<div class='banner'>AI-generated investigation workspace — every claim is "
    "<b>machine_extracted</b> (unreviewed). Provenance is shown per claim; nothing here "
    "asserts physical electricity supply, AI workloads or renewable procurement beyond "
    "the recorded claims.</div>")


def _esc(x) -> str:
    return html.escape(str(x if x is not None else "-"))


def _ro_conn(db_path: Path | None = None) -> sqlite3.Connection:
    p = db_path or DB
    if not p.exists():
        raise FileNotFoundError(p)
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def _same_entity_closure(conn: sqlite3.Connection, entity_pk: str) -> tuple[set[str], list[dict]]:
    """Read-only transitive closure with the engine's conservative policy:
    latest-decision-per-pair (rowid order); conflicting operative decisions
    are reported and cause a no-merge. Never writes."""
    operative: dict[frozenset, str] = {}
    for rowid, a, b, d in conn.execute(
            "SELECT rowid, entity_pk_a, entity_pk_b, decision FROM adjudications ORDER BY rowid"):
        operative[frozenset((a, b))] = d
    same: dict[str, set[str]] = {}
    distinct: set[frozenset] = set()
    for pair, d in operative.items():
        a, b = tuple(pair)
        if d == "same_entity":
            same.setdefault(a, set()).add(b)
            same.setdefault(b, set()).add(a)
        elif d == "distinct_entities":
            distinct.add(pair)
    closure = {entity_pk}
    frontier = [entity_pk]
    while frontier:
        cur = frontier.pop()
        for nxt in same.get(cur, ()):
            if nxt not in closure:
                closure.add(nxt)
                frontier.append(nxt)
    conflicts = [sorted(p) for p in distinct if p <= closure]
    if conflicts:
        return {entity_pk}, [{"conflicting_entities": c} for c in conflicts]
    return closure, []


def _page(title: str, body: str, status: int = 200) -> tuple[int, str, str]:
    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{_esc(title)} — SEA AI-infrastructure evidence engine</title>
<style>
 body {{ font-family: -apple-system, Helvetica, sans-serif; margin: 0; color: #1a1a1a; }}
 header {{ background: #10243e; color: #fff; padding: 10px 18px; }}
 header a {{ color: #9fd0ff; margin-right: 14px; text-decoration: none; }}
 .banner {{ background: #fff3cd; padding: 8px 18px; border-bottom: 1px solid #e0c970; font-size: 14px; }}
 main {{ padding: 14px 18px; max-width: 1100px; }}
 h2 {{ border-bottom: 2px solid #10243e; padding-bottom: 2px; margin-top: 22px; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
 td, th {{ border: 1px solid #ccd; padding: 4px 8px; vertical-align: top; text-align: left; }}
 .quote {{ font-family: Georgia, serif; background: #f4f6f8; padding: 4px 8px; display: block; }}
 .tag {{ display: inline-block; background: #e8eef5; border-radius: 3px; padding: 0 6px; margin: 0 2px; font-size: 12px; }}
 .contra {{ background: #ffe3e3; border: 1px solid #e08a8a; padding: 6px 10px; margin: 6px 0; }}
 .unknown {{ color: #7a5c00; }}
 .empty {{ background: #eef7ee; border: 1px solid #9ec99e; padding: 10px 14px; }}
 .err {{ background: #fdecec; border: 1px solid #d99; padding: 10px 14px; }}
 code {{ background: #eef; padding: 0 4px; }}
 form {{ margin: 8px 0; }}
</style></head><body>
<header><a href="/"><b>SEA AI-infra evidence engine</b></a>
<a href="/cases">Cases</a><a href="/orgs">Organizations</a><a href="/sources">Sources</a>
<form action="/search" method="get" style="display:inline">
<input name="q" placeholder="search cases, orgs, aliases, sources…" size="34">
<button>search</button></form></header>
{BANNER}<main>{body}</main>
<footer style="padding:10px 18px;color:#666;font-size:12px">
Read-only local view over data/processed/engine.sqlite3 · claims are content-addressed ·
snapshots under data/evidence_snapshots/</footer>
</body></html>"""
    return status, "text/html; charset=utf-8", doc


def _claim_rows(conn, entity_pk: str) -> list[dict]:
    rows = conn.execute(
        """SELECT c.claim_pk, c.predicate, c.object_literal, c.object_pk, c.claim_time,
                  c.time_precision, c.certainty, c.review_status, c.evidence_kind,
                  c.unit, c.grain, o.quote, o.locator, o.verified_against_raw,
                  s.source_ref, s.version_index, s.publisher, s.access_status,
                  s.snapshot_path, s.raw_retention, s.checksum_basis, e2.name
           FROM claims c
           JOIN observations o ON o.obs_pk = c.observation_pk
           JOIN sources s ON s.source_pk = o.source_pk
           LEFT JOIN entities e2 ON e2.entity_pk = c.object_pk
           WHERE c.subject_pk = ? OR c.object_pk = ?
           ORDER BY COALESCE(c.claim_time, '9999') ASC""", (entity_pk, entity_pk)).fetchall()
    sup = {r[0]: {"superseded_by": r[1], "supersession_basis": r[2]}
           for r in conn.execute(
        "SELECT superseded_claim_pk, superseding_claim_pk, basis FROM supersessions "
        "WHERE status='active'")}
    out = []
    for r in rows:
        d = dict(zip(["claim_pk", "predicate", "object_literal", "object_pk", "claim_time",
                      "time_precision", "certainty", "review_status", "evidence_kind", "unit",
                      "grain", "quote", "locator", "verified_against_raw", "source_ref",
                      "source_version", "publisher", "access_status", "snapshot_path",
                      "raw_retention", "checksum_basis", "object_name"], r))
        sd = sup.get(d["claim_pk"])
        d["superseded_by"] = sd["superseded_by"] if sd else None
        d["supersession_basis"] = sd["supersession_basis"] if sd else None
        out.append(d)
    return out


def _dedupe(rows: list[dict]) -> tuple[list[dict], int]:
    seen, out, sup = {}, [], 0
    for r in rows:
        k = (r["predicate"], r["object_literal"], r["object_pk"], r["claim_time"], r["quote"])
        if k in seen:
            sup += 1
            continue
        seen[k] = r
        out.append(r)
    return out, sup


def _split_superseded(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split into current claims and explicitly superseded ones (still
    inspectable, never presented as current)."""
    current = [r for r in rows if not r.get("superseded_by")]
    superseded = [r for r in rows if r.get("superseded_by")]
    return current, superseded


def _claim_rows_by_org_name(conn, org_name: str, predicate: str) -> list[dict]:
    """Org-level claims by NAME across scopes (identity unadjudicated)."""
    rows = conn.execute(
        """SELECT c.claim_pk, c.predicate, c.object_literal, c.object_pk, c.claim_time,
                  c.time_precision, c.certainty, c.review_status, c.evidence_kind,
                  c.unit, c.grain, o.quote, o.locator, o.verified_against_raw,
                  s.source_ref, s.version_index, s.publisher, s.access_status,
                  s.snapshot_path, s.raw_retention, s.checksum_basis, e2.name
           FROM claims c
           JOIN observations o ON o.obs_pk = c.observation_pk
           JOIN sources s ON s.source_pk = o.source_pk
           JOIN entities e1 ON e1.entity_pk = c.subject_pk
           LEFT JOIN entities e2 ON e2.entity_pk = c.object_pk
           WHERE e1.name = ? AND c.predicate = ?""",
        (org_name, predicate)).fetchall()
    sup = {r[0]: r[1] for r in conn.execute(
        "SELECT superseded_claim_pk, superseding_claim_pk FROM supersessions WHERE status='active'")}
    out = []
    for r in rows:
        d = dict(zip(["claim_pk", "predicate", "object_literal", "object_pk", "claim_time",
                      "time_precision", "certainty", "review_status", "evidence_kind", "unit",
                      "grain", "quote", "locator", "verified_against_raw", "source_ref",
                      "source_version", "publisher", "access_status", "snapshot_path",
                      "raw_retention", "checksum_basis", "object_name"], r))
        d["superseded_by"] = sup.get(d["claim_pk"])
        out.append(d)
    return out


def _superseded_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    trs = []
    for r in rows:
        trs.append(
            f"<tr><td>{_esc(r['predicate'])}</td><td>{_esc((r['object_literal'] or '')[:160])}</td>"
            f"<td><a href='/claim/{_esc(r['claim_pk'])}'>inspect</a> "
            f"(superseded by <a href='/claim/{_esc(r['superseded_by'])}'>{_esc(r['superseded_by'][:12])}…</a>)"
            f"<br><small>{_esc(r['supersession_basis'])[:200]}</small></td></tr>")
    return ("<p class='unknown'><b>SUPERSEDED — historical claims, NOT current "
            "(preserved and inspectable):</b></p><table><tr><th>predicate</th>"
            "<th>superseded claim</th><th>supersession</th></tr>" + "".join(trs) + "</table>")


def _claims_table(rows: list[dict]) -> str:
    if not rows:
        return "<div class='empty'>No claims recorded for this dimension yet. " \
               "This is an explicit unknown, not an absence of facts.</div>"
    trs = []
    for r in rows:
        val = r["object_name"] or r["object_literal"] or ""
        ver = ("raw-verified ✓" if r["verified_against_raw"] == 1 else
               ("raw-verified ✗" if r["verified_against_raw"] == 0 else "n/a"))
        trs.append(
            f"<tr><td>{_esc(r['claim_time'] or 'time unknown')} <span class='tag'>{_esc(r['time_precision'])}</span></td>"
            f"<td><code>{_esc(r['predicate'])}</code><br>{_esc(val)[:220]}"
            f"<br><span class='quote'>{_esc(r['quote'])[:260]}</span>"
            f"<br><span class='tag'>{_esc(r['evidence_kind'])}</span>"
            f"<span class='tag'>certainty: {_esc(r['certainty'])}</span>"
            f"<span class='tag'>review: {_esc(r['review_status'])}</span>"
            f"<span class='tag'>raw-verified: {ver}</span>"
            + (f"<span class='tag'>unit: {_esc(r['unit'])}</span>" if r["unit"] else "")
            + (f"<span class='tag'>grain: {_esc(r['grain'])}</span>" if r["grain"] else "")
            + f"</td><td>{_esc(r['publisher'])} v{_esc(r['source_version'])} "
              f"<span class='tag'>{_esc(r['access_status'])}</span><br>"
              f"<a href='/claim/{_esc(r['claim_pk'])}'>claim detail →</a><br>"
              f"<small>{_esc(r['source_ref'])[:90]}</small></td></tr>")
    return "<table><tr><th>time</th><th>claim</th><th>source version</th></tr>" + "".join(trs) + "</table>"


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


# ---------------- routes ----------------

def route_home() -> tuple[int, str, str]:
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    projects = conn.execute(
        "SELECT name, identifier FROM entities WHERE entity_type='project' "
        "AND identifier LIKE 'engine-case:%' ORDER BY name").fetchall()
    n_orgs = conn.execute("SELECT COUNT(*) FROM entities WHERE entity_type='organization'").fetchone()[0]
    n_claims = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    n_sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    items = "".join(f"<li><a href='/case/{_esc(n)}'>{_esc(n)}</a> "
                    f"<a href='/involved/{_esc(n)}'>[who is involved?]</a> "
                    f"<span class='tag'>{_esc(i)}</span></li>" for n, i in projects) or \
            "<li>No cases ingested yet — run scripts/engine_ingest.py.</li>"
    body = f"""
<h2>Investigation cases</h2>
<ul>{items}</ul>
<p><span class='tag'>{n_orgs} organizations</span> <span class='tag'>{n_claims} claim rows (incl. superseded variants)</span>
<span class='tag'>{n_sources} source versions</span>
<span class='tag'>read-only</span></p>
<p>Follow a case through <b>finance → ownership/energy → status over time</b>; every claim
links to its exact provenance. Unknowns are shown as unknowns; contradictions are shown
unresolved.</p>"""
    conn.close()
    return _page("Home", body)


def route_cases() -> tuple[int, str, str]:
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    rows = conn.execute(
        "SELECT name, identifier, identity_status FROM entities "
        "WHERE entity_type='project' ORDER BY name").fetchall()
    if not rows:
        return _page("Cases", "<div class='empty'>No projects ingested yet. Run "
                              "<code>scripts/engine_ingest.py</code> and reload.</div>")
    body = "<h2>All project entities</h2><table><tr><th>name</th><th>identifier</th><th>identity status</th></tr>" + "".join(
        f"<tr><td><a href='/case/{_esc(n)}'>{_esc(n)}</a></td><td>{_esc(i)}</td><td>{_esc(st)}</td></tr>"
        for n, i, st in rows) + "</table>"
    return _page("Cases", body)


def route_case(name: str) -> tuple[int, str, str]:
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    row = conn.execute(
        "SELECT entity_pk, identifier, identity_status, scope FROM entities "
        "WHERE entity_type='project' AND name=? ORDER BY (identifier IS NULL) LIMIT 1",
        (name,)).fetchone()
    if not row:
            return route_not_found(f"case '{name}'")
    epk, ident, idstatus, scope = row
    tl_all, superseded_count = _dedupe(_claim_rows(conn, epk))
    tl, tl_sup_hist = _split_superseded(tl_all)
    superseded_rows = tl_sup_hist
    superseded = superseded_count
    contra = conn.execute(
        """SELECT DISTINCT co.group_pk, co.claim_pk, co.kind, co.scope_note
           FROM contradictions co JOIN claims c ON c.claim_pk=co.claim_pk
           WHERE c.subject_pk=? OR c.object_pk=?""", (epk, epk)).fetchall()
    contra_by_claim = {c: (g, k, n) for g, c, k, n in contra}
    ev = conn.execute(
        """SELECT re.ts, re.outcome, COUNT(*) FROM retrieval_events re
           WHERE re.source_ref IN (SELECT DISTINCT s.source_ref FROM sources s
             JOIN observations o ON o.source_pk=s.source_pk
             JOIN claims c ON c.observation_pk=o.obs_pk WHERE c.subject_pk=?)
           GROUP BY re.ts, re.outcome ORDER BY re.ts""", (epk,)).fetchall()
    snaps = conn.execute(
        """SELECT s.source_ref, s.version_index, s.raw_checksum, s.snapshot_path,
                  s.raw_retention, s.checksum_basis FROM sources s
           WHERE s.source_ref IN (SELECT DISTINCT source_ref FROM sources s2
             JOIN observations o ON o.source_pk=s2.source_pk
             JOIN claims c ON c.observation_pk=o.obs_pk WHERE c.subject_pk=?)
           ORDER BY s.source_ref, s.version_index""", (epk,)).fetchall()

    parts = [f"<h1>Case: {_esc(name)}</h1>"
             f"<p><a href='/involved/{_esc(name)}'>Who is involved? — role view (developer, owner/investor, lender, operator, electricity supplier/PPA counterparty, tenant)</a></p>"
             f"<p>identity: <span class='tag'>identifier {_esc(ident)}</span>"
             f"<span class='tag'>{_esc(idstatus)}</span>"
             f"<span class='tag'>scope {_esc(scope)}</span> — engine-assigned case key, "
             f"not a registry id</p>"
             f"<p>{len(tl)} distinct claim(s) ({superseded} superseded cross-run variant(s) "
             f"preserved in the database).</p>"]
    for dim, preds in DIMENSIONS.items():
        rows = [r for r in tl if r["predicate"] in preds]
        sup_rows = [r for r in tl_sup_hist if r["predicate"] in preds]
        parts.append(f"<h2>{dim}</h2>" + _claims_table(rows) + _superseded_table(sup_rows))
    parts.append("<h2>contradictions (all unresolved)</h2>")
    if not contra_by_claim:
        parts.append("<div class='empty'>No contradiction groups flagged for this case.</div>")
    else:
        seen_groups = set()
        for r in tl:
            g = contra_by_claim.get(r["claim_pk"])
            if g and g[0] not in seen_groups:
                seen_groups.add(g[0])
                parts.append(f"<div class='contra'><b>{_esc(r['predicate'])}</b> — {_esc(r['object_literal'])}"
                             f"<br><span class='tag'>kind: {_esc(g[1])} (unproven)</span><br>"
                             f"scope: {_esc(g[2])}</div>")
    known = []
    for dim, preds in DIMENSIONS.items():
        n = len([r for r in tl if r["predicate"] in preds])
        known.append(f"<span class='tag'>{dim}: {'unknown' if n == 0 else f'{n} claim(s)'}</span>")
    parts.append("<h2>known / unknown</h2><p>" + " ".join(known) + "</p>")
    parts.append("<h2>retrieval history (append-only)</h2>")
    if ev:
        parts.append("<table><tr><th>ts</th><th>outcome</th><th>count</th></tr>" + "".join(
            f"<tr><td>{_esc(t)[:19]}</td><td>{_esc(o)}</td><td>{_esc(c)}</td></tr>"
            for t, o, c in ev) + "</table>")
    else:
        parts.append("<div class='empty'>No retrieval events recorded.</div>")
    fails = conn.execute(
        """SELECT source_ref, publisher, access_status, retrieval_attempts_json FROM sources
           WHERE access_status IN ('missing','failed','notice_page','not_fetched')
           GROUP BY source_ref""").fetchall()
    parts.append("<h2>access failures &amp; limits (preserved)</h2>")
    if fails:
        parts.append("<table><tr><th>source</th><th>publisher</th><th>status</th><th>attempt notes</th></tr>"
                     + "".join(
            f"<tr><td>{_esc(r[:70])}</td><td>{_esc(p)}</td><td><span class='tag'>{_esc(st)}</span></td><td>{_esc((json.loads(att)[0].get('note') if json.loads(att) else '-') if att else '-')}</td></tr>"
            for r, p, st, att in fails) + "</table>")
    else:
        parts.append("<div class='empty'>No access failures recorded.</div>")
    parts.append("<h2>source versions &amp; snapshots</h2>")
    parts.append("<table><tr><th>source</th><th>v</th><th>checksum</th><th>basis</th>"
                 "<th>retention</th><th>snapshot</th></tr>" + "".join(
        f"<tr><td>{_esc(ref)[:70]}</td><td>v{_esc(vi)}</td><td><code>{_esc(ck)[:16]}</code></td>"
        f"<td>{_esc(basis)}</td><td>{_esc(ret)}</td><td>{_esc(Path(sp).name if sp else '-')}</td></tr>"
        for ref, vi, ck, sp, ret, basis in snaps) + "</table>")
    conn.close()
    return _page(f"Case {name}", "".join(parts))


def route_orgs() -> tuple[int, str, str]:
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    rows = conn.execute(
        "SELECT entity_pk, name, identifier, identity_status, scope FROM entities "
        "WHERE entity_type='organization' ORDER BY name, scope LIMIT 200").fetchall()
    conn.close()
    if not rows:
        return _page("Organizations", "<div class='empty'>No organizations ingested yet.</div>")
    body = ("<h2>Organizations (name-only entities are source-scoped)</h2>"
            "<table><tr><th>name</th><th>identifier</th><th>identity status</th><th>scope</th><th></th></tr>"
            + "".join(f"<tr><td>{_esc(n)}</td><td>{_esc(i)}</td><td>{_esc(st)}</td>"
                      f"<td>{_esc(sc)[:40]}</td><td><a href='/org/{_esc(pk)}'>view →</a></td></tr>"
                      for pk, n, i, st, sc in rows) + "</table>"
            "<p class='unknown'>Same name + different scope = different entities until "
            "explicitly adjudicated.</p>")
    return _page("Organizations", body)


def route_org(pk: str) -> tuple[int, str, str]:
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    row = conn.execute(
        "SELECT name, identifier, identity_status, scope FROM entities WHERE entity_pk=?",
        (pk,)).fetchone()
    if not row:
            return route_not_found(f"organization {pk[:12]}…")
    name, identifier, idstatus, scope = row
    closure, conflicts = _same_entity_closure(conn, pk)
    names = [r[0] for r in conn.execute(
        f"SELECT DISTINCT name FROM entities WHERE entity_pk IN ({','.join('?'*len(closure))})",
        tuple(closure))]
    aliases = conn.execute(
        f"SELECT alias, status FROM entity_aliases WHERE entity_pk IN ({','.join('?'*len(closure))})",
        tuple(closure)).fetchall()
    claims = []
    sup_total = 0
    for cpk in closure:
        rows, sup = _dedupe(_claim_rows(conn, cpk))
        claims.extend(rows)
        sup_total += sup
    claims.sort(key=lambda r: r["claim_time"] or "9999")
    parts = [f"<h1>Organization: {_esc(name)}</h1>",
             f"<p><span class='tag'>identity status: {_esc(idstatus)}</span>"
             f"<span class='tag'>scope: {_esc(scope)}</span>"
             f"<span class='tag'>identifier: {_esc(identifier)}</span></p>"]
    if len(closure) > 1:
        parts.append(f"<p class='unknown'>Adjudicated same-entity group ({len(closure)} members): "
                     f"{_esc(', '.join(names))}</p>")
    if conflicts:
        parts.append(f"<div class='err'>CONFLICTING adjudications detected — conservative "
                     f"no-merge applied: {_esc(json.dumps(conflicts))}</div>")
    if aliases:
        parts.append("<p>aliases: " + " ".join(
            f"<span class='tag'>{_esc(a)} ({_esc(st)})</span>" for a, st in aliases) + "</p>")
    # identity candidates: all adjudications involving ANY same-named entity
    # across scopes (the homonym question is about the name, not one scope)
    hist = conn.execute(
        """SELECT a.sequence, a.decision, a.decided_by, a.decided_at, e1.name, e2.name
           FROM adjudications a
           JOIN entities e1 ON e1.entity_pk=a.entity_pk_a
           JOIN entities e2 ON e2.entity_pk=a.entity_pk_b
           WHERE (e1.name = ? AND e1.entity_type = 'organization')
              OR (e2.name = ? AND e2.entity_type = 'organization')
           ORDER BY COALESCE(a.sequence, -a.rowid)""", (name, name)).fetchall()
    if hist:
        parts.append("<h2>adjudication history (append-only, latest wins)</h2>"
                     "<table><tr><th>seq</th><th>decision</th><th>between</th>"
                     "<th>decided by</th><th>decided at</th></tr>" + "".join(
            f"<tr><td>{_esc(sq if sq is not None else 'legacy')}</td><td>{_esc(d)}</td>"
            f"<td>{_esc(n1)} vs {_esc(n2)}</td><td>{_esc(by)}</td><td>{_esc(da or 'unknown (legacy)')}</td></tr>"
            for sq, d, by, da, n1, n2 in hist) + "</table>")
    parts.append(f"<h2>claims mentioning this identity ({len(claims)} distinct, "
                 f"{sup_total} superseded variants preserved)</h2>" + _claims_table(claims))
    conn.close()
    return _page(f"Org {name}", "".join(parts))


def route_claim(pk: str) -> tuple[int, str, str]:
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    row = conn.execute(
        """SELECT c.predicate, c.object_literal, c.object_pk, c.claim_time, c.time_precision,
                  c.certainty, c.review_status, c.evidence_kind, c.unit, c.grain,
                  o.quote, o.locator, o.verified_against_raw, o.extractor_version,
                  s.source_ref, s.version_index, s.publisher, s.license, s.access_status,
                  s.raw_checksum, s.checksum_basis, s.snapshot_path, s.raw_retention,
                  s.document_date, e1.name, e2.name, s.source_pk
           FROM claims c JOIN observations o ON o.obs_pk=c.observation_pk
           JOIN sources s ON s.source_pk=o.source_pk
           JOIN entities e1 ON e1.entity_pk=c.subject_pk
           LEFT JOIN entities e2 ON e2.entity_pk=c.object_pk
           WHERE c.claim_pk=?""", (pk,)).fetchone()
    if not row:
        conn.close()
        return route_not_found(f"claim {pk[:12]}…")
    (pred, olit, opk, t, prec, cert, rev, kind, unit, grain, quote, loc, ver, exv,
     sref, svi, pub, lic, acc, rck, basis, snap, ret, ddate, sname, oname, spk) = row
    sup = conn.execute(
        "SELECT superseding_claim_pk, basis, recorded_by, recorded_at FROM supersessions "
        "WHERE superseded_claim_pk=? AND status='active'", (pk,)).fetchone()
    sup_history = conn.execute(
        "SELECT superseded_claim_pk, basis, recorded_at FROM supersessions "
        "WHERE superseding_claim_pk=? ORDER BY recorded_at", (pk,)).fetchall()
    conn.close()
    if sup:
        sup_html = (f"<div class='err'>This claim is SUPERSEDED and is NOT current. "
                    f"Superseded by <a href='/claim/{_esc(sup[0])}'>{_esc(sup[0][:16])}…</a> "
                    f"at {_esc(sup[3])[:19]} by {_esc(sup[2])}.<br>Basis: {_esc(sup[1])}</div>")
    elif sup_history:
        links = "; ".join(f"<a href='/claim/{_esc(o)}'>{_esc(o[:12])}…</a>" for o, _, _ in sup_history)
        sup_html = (f"<p>This claim is current (no active supersession). It supersedes "
                    f"{len(sup_history)} earlier claim(s): {links}</p>")
    else:
        sup_html = "<p>This claim is current (no active supersession).</p>"
    body = f"""<h1>Claim detail</h1>
<table>
<tr><th>predicate</th><td><code>{_esc(pred)}</code></td></tr>
<tr><th>subject</th><td>{_esc(sname)}</td></tr>
<tr><th>object</th><td>{_esc(oname or olit or '-')}</td></tr>
<tr><th>claim time</th><td>{_esc(t or 'unknown')} <span class='tag'>{_esc(prec)}</span></td></tr>
<tr><th>certainty / review</th><td><span class='tag'>{_esc(cert)}</span>
<span class='tag'>{_esc(rev)} (AI-generated, unreviewed)</span>
<span class='tag'>evidence: {_esc(kind)}</span></td></tr>
<tr><th>unit / grain</th><td>{_esc(unit or '-')} / {_esc(grain or '-')}</td></tr>
<tr><th>exact quote</th><td><span class='quote'>{_esc(quote)}</span></td></tr>
<tr><th>locator</th><td>{_esc(loc)}</td></tr>
<tr><th>raw verification</th><td>{'verified ✓' if ver == 1 else ('failed ✗' if ver == 0 else 'n/a (synthesis/paraphrase)')}
 <span class='tag'>extractor {_esc(exv)}</span></td></tr>
<tr><th>source</th><td>{_esc(pub)} v{_esc(svi)} <span class='tag'>{_esc(acc)}</span><br>
{_esc(sref)}<br>license: {_esc(lic)} · document date: {_esc(ddate or 'unknown')}</td></tr>
<tr><th>content checksum</th><td><code>{_esc(rck)}</code> <span class='tag'>basis: {_esc(basis)}</span></td></tr>
<tr><th>snapshot</th><td>{f"<a href='/raw/{_esc(spk)}'>{_esc(Path(snap).name)}</a> (immutable, checksum-verified on serve)" if snap and ret == 'snapshot_retained' else 'no snapshot — content not retained'}
 <span class='tag'>retention: {_esc(ret)}</span></td></tr>
<tr><th>supersession</th><td>{sup_html}</td></tr>
<tr><th>original source</th><td>{f"<a href='{_esc(sref)}' rel='noopener'>{_esc(sref)[:90]}</a>" if sref.startswith('http') else _esc(sref)}
<br><small>External links open the live web; the snapshot link above opens the retained copy.</small></td></tr>
</table>"""
    return _page("Claim", body)


# Role definitions: role label -> (project predicates, direction note).
# Direction discipline: HAS_OFFTAKER means the named org is the BUYER of the
# PPA output, not a supplier; HAS_PPA_COUNTERPARTY is the utility counterparty.
ROLE_MAP = [
    ("Developer", ["HAS_DEVELOPER", "HAS_SPONSOR"],
     "entity recorded as developing/sponsoring the asset"),
    ("Owner / investor (project level)", ["HAS_DEVELOPMENT_PARTNER", "HAS_JOINT_VENTURE_CLAIM",
                                          "HAS_INVESTMENT"],
     "recorded investors or development partners at project level"),
    ("Lender", ["HAS_FINANCING_PARTICIPANT"],
     "recorded lenders to the asset's financing events"),
    ("Operator", ["HAS_OPERATOR"],
     "entity recorded as operating the asset"),
    ("Electricity supplier / PPA counterparty", ["HAS_PPA_COUNTERPARTY", "HAS_OFFTAKER",
                                                 "HAS_UTILITY_CONNECTION"],
     "PPA/utility counterparties; a VPPA is a FINANCIAL contract and an offtaker "
     "is a BUYER — neither is evidence of physical supply"),
    ("Tenant / customer / offtaker of the data centre", [],
     "no predicate exists for tenants or customers: no claims can appear here "
     "without dedicated evidence"),
]
ORG_LEVEL_ROLES = ("Owner / investor (project level)",)


def route_involved(name: str) -> tuple[int, str, str]:
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    row = conn.execute(
        """SELECT entity_pk, name, identifier, identity_status FROM entities
           WHERE entity_type='project' AND name=?
           ORDER BY (identifier IS NULL), entity_pk LIMIT 1""", (name,)).fetchone()
    if not row:
        conn.close()
        return route_not_found(f"case '{name}'")
    epk = row[0]
    all_rows, _ = _dedupe(_claim_rows(conn, epk))
    current = [r for r in all_rows if not r.get("superseded_by")]
    superseded = [r for r in all_rows if r.get("superseded_by")]

    # operator-linked org-level claims (e.g., ownership of the operator)
    op_pks = [r["object_pk"] for r in current
              if r["predicate"] in ("HAS_OPERATOR", "HAS_SPONSOR") and r["object_pk"]]
    org_claims, name_bridge = [], []
    op_names = set()
    for opk in op_pks:
        nm = conn.execute("SELECT name FROM entities WHERE entity_pk=?", (opk,)).fetchone()
        if nm:
            op_names.add(nm[0])
    for nm in op_names:
        # NAME-MATCH bridge across scoped entities: the operator's name may map
        # to several scoped entity rows (unadjudicated). Claims are pulled by
        # name and every row is labelled with the unadjudicated caveat.
        for r in _dedupe(_claim_rows_by_org_name(conn, nm,
                predicate="HAS_OWNER_REPORTED"))[0]:
            if not r.get("superseded_by"):
                org_claims.append(r)
                name_bridge.append((r["claim_pk"], nm))

    parts = [f"<h1>Who is involved? — {_esc(name)}</h1>"
             f"<p class='unknown'>Roles are shown <b>only where recorded claims exist</b>, each "
             f"with its exact quote, source version, date and review status. An empty role means "
             f"<b>unknown — not evidence of absence</b>. No tenants, corporate control, physical "
             f"supply or AI workloads are inferred from names or promotional language. All content "
             f"is AI-generated and unreviewed.</p>"]

    def render_role(label, rows, note=""):
        out = f"<h2>{_esc(label)}</h2>"
        if not rows:
            return out + ("<div class='empty'>No claims recorded for this role — "
                          "<b>unknown</b> (not evidence that no such party exists).</div>")
        out += f"<p><small>{_esc(note)}</small></p>" if note else ""
        trs = []
        for r in rows:
            who = r["object_name"] or r["object_literal"] or ""
            role_dir = ""
            if r["predicate"] == "HAS_OFFTAKER":
                role_dir = "<span class='tag'>direction: offtaker = BUYER of PPA output (not a supplier)</span>"
            if r["predicate"] == "HAS_PPA_COUNTERPARTY":
                role_dir = "<span class='tag'>direction: PPA counterparty (utility)</span>"
            if "VPPA" in (r["quote"] or "") or "VPPA" in (r["object_literal"] or ""):
                role_dir += " <span class='tag'>VPPA = financial contract, not physical supply</span>"
            date = r["claim_time"] or "date unknown"
            trs.append(
                f"<tr><td><b>{_esc(who)[:120]}</b>"
                f"<br><span class='tag'>{_esc(r['predicate'])}</span>{role_dir}"
                f"<br><span class='quote'>{_esc(r['quote'])[:240]}</span>"
                f"<br><span class='tag'>claim date: {_esc(date)}</span>"
                f"<span class='tag'>certainty: {_esc(r['certainty'])}</span>"
                f"<span class='tag'>review: {_esc(r['review_status'])} (unreviewed)</span></td>"
                f"<td>{_esc(r['publisher'])} v{_esc(r['source_version'])} "
                f"<span class='tag'>{_esc(r['access_status'])}</span><br>"
                f"<small>{_esc(r['source_ref'])[:80]}</small><br>"
                f"<a href='/claim/{_esc(r['claim_pk'])}'>full provenance →</a></td></tr>")
        return out + "<table><tr><th>party (as recorded)</th><th>provenance</th></tr>" + "".join(trs) + "</table>"

    ENERGY_PREDS = {"HAS_PPA_COUNTERPARTY", "HAS_OFFTAKER", "HAS_UTILITY_CONNECTION"}
    for label, preds, note in ROLE_MAP:
        rows = [r for r in current if r["predicate"] in preds]
        if label in ORG_LEVEL_ROLES:
            rows = rows + org_claims
        note_full = note
        if label in ORG_LEVEL_ROLES and name_bridge:
            note_full = ("IDENTITY CAVEAT: owner claims are joined to the operator BY NAME across "
                         "scoped entities (unadjudicated — see the org pages). " + note)
        parts.append(render_role(label, rows, note_full))
        if label.startswith("Electricity"):
            # same-operator fallback: energy claims on SIBLING projects of the
            # same operator, explicitly NOT established as this asset's supply
            sib = []
            seen_subjects = set()
            op_names = {r["object_name"] for r in current
                        if r["predicate"] in ("HAS_OPERATOR", "HAS_SPONSOR") and r["object_name"]}
            for r in current:  # collect sibling project pks via operator org claims
                pass
            for r in all_rows:  # include superseded-searchable universe: sibling pks
                pass
            # find sibling projects sharing the operator name
            sib_pks = set()
            for (spk,) in conn.execute(
                    """SELECT DISTINCT c.subject_pk FROM claims c
                       JOIN observations o ON o.obs_pk=c.observation_pk
                       JOIN sources s ON s.source_pk=o.source_pk
                       JOIN entities e2 ON e2.entity_pk=c.object_pk
                       WHERE c.predicate IN ('HAS_OFFTAKER','HAS_PPA_SIGNED','HAS_PPA_COUNTERPARTY')
                       AND e2.name IN (SELECT DISTINCT name FROM entities WHERE entity_pk IN
                         (SELECT object_pk FROM claims WHERE predicate='HAS_OPERATOR'
                          AND subject_pk=?)) AND c.subject_pk != ?""",
                    (epk, epk)).fetchall():
                sib_pks.add(spk)
            for spk in sib_pks:
                sname = conn.execute("SELECT name FROM entities WHERE entity_pk=?", (spk,)).fetchone()
                sname = sname[0] if sname else spk
                for r in _dedupe(_claim_rows(conn, spk))[0]:
                    if r["predicate"] in ENERGY_PREDS | {"HAS_PPA_SIGNED"} and not r.get("superseded_by"):
                        rr = dict(r)
                        rr["sibling_project"] = sname
                        sib.append(rr)
            if sib:
                trs = []
                for r in sib:
                    direction = ""
                    if r["predicate"] == "HAS_OFFTAKER":
                        direction = "<span class='tag'>direction: offtaker = BUYER of PPA output (not a supplier)</span>"
                    trs.append(
                        f"<tr><td><b>{_esc(r.get('sibling_project',''))}</b> (related project, same operator)"
                        f"<br><code>{_esc(r['predicate'])}</code> — {_esc((r['object_name'] or r['object_literal'] or '')[:120])}{direction}"
                        f"<br><span class='quote'>{_esc(r['quote'])[:200]}</span>"
                        f"<br><span class='tag'>claim date: {_esc(r['claim_time'] or 'unknown')}</span>"
                        f"<span class='tag'>certainty: {_esc(r['certainty'])}</span>"
                        f"<span class='tag'>review: {_esc(r['review_status'])}</span></td>"
                        f"<td>{_esc(r['publisher'])} v{_esc(r['source_version'])}<br>"
                        f"<a href='/claim/{_esc(r['claim_pk'])}'>full provenance →</a></td></tr>")
                parts.append("<h2>Electricity — related project, same operator (grain caveat)</h2>"
                             "<div class='err'>The claims below belong to a RELATED project of the same "
                             "operator. They are NOT established as this asset's electricity supply: "
                             "a VPPA is a financial contract and an announcement is not operational "
                             "delivery.</div>"
                             "<table><tr><th>related-project claim</th><th>provenance</th></tr>"
                             + "".join(trs) + "</table>")

    sup_rows = [r for r in superseded]
    parts.append(_superseded_table(sup_rows))
    parts.append("<h2>unknowns across all roles</h2><p class='unknown'>Roles shown empty above "
                 "are unknown. In addition: no source consulted states this project's tenant or "
                 "customer; energy mix (where a PPA exists) is unstated; completeness of sources "
                 "is NOT asserted.</p>")
    conn.close()
    # role matrix
    import importlib
    try:
        ra = importlib.import_module("discovery.role_matrix_data")
        matrix = ra.get_matrix()
        m = matrix.get(name)
        parts.append(f"<p class='tag'>DEBUG matrix keys: {list(matrix.keys())}, name: {name}, m: {bool(m)}</p>")
        if m:
            parts.append("<h2>role matrix (source-to-screen audit)</h2>")
            parts.append("<table><tr><th>role</th><th>status</th></tr>")
            status_colors = {"documented": "#c8e6c9", "candidate": "#fff9c4",
                             "conflicting": "#ffcdd2", "unknown": "#f5f5f5"}
            for role, cell in m.items():
                color = status_colors.get(cell["status"], "#f5f5f5")
                parts.append(f"<tr><td>{_esc(role)}</td>"
                             f"<td style='background:{color}'>{_esc(cell['status'])}"
                             f" <span class='tag'>{len(cell.get('claims', []))} claim(s)</span></td></tr>")
            parts.append("</table>")
            parts.append("<p class='unknown'><b>Cell statuses:</b> documented = current, dated, "
                         "non-superseded claim from an identified source · candidate = role described "
                         "but party unnamed or identity unadjudicated · conflicting = multiple current "
                         "claims with distinct values (unresolved) · unknown = no claims for this role "
                         "(not evidence of absence). All content is AI-generated and unreviewed.</p>")
    except Exception:
        pass  # matrix module optional

    return _page(f"Who is involved — {name}", "".join(parts))


def route_sources() -> tuple[int, str, str]:
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    rows = conn.execute(
        """SELECT source_ref, MAX(version_index), publisher, access_status, checksum_basis,
                  raw_retention, COUNT(*) FROM sources GROUP BY source_ref
           ORDER BY source_ref LIMIT 200""").fetchall()
    n_events = conn.execute("SELECT COUNT(*) FROM retrieval_events").fetchone()[0]
    conn.close()
    body = (f"<h2>Sources ({len(rows)} logical, {n_events} retrieval events)</h2>"
            "<table><tr><th>source_ref</th><th>versions</th><th>publisher</th>"
            "<th>access</th><th>checksum basis</th><th>retention</th></tr>" + "".join(
        f"<tr><td>{_esc(r[:80])}</td><td>{_esc(v)}</td><td>{_esc(p)}</td><td>{_esc(a)}</td>"
        f"<td>{_esc(cb)}</td><td>{_esc(rr)}</td></tr>"
        for r, v, p, a, cb, rr, _ in rows) + "</table>")
    return _page("Sources", body)


def route_search(q: str) -> tuple[int, str, str]:
    q = (q or "").strip()
    if not q:
        return _page("Search", "<div class='empty'>Type a query to search cases, organizations, "
                               "aliases and sources. Empty searches return nothing by design.</div>")
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    like = f"%{q}%"
    cases = conn.execute("SELECT name, identifier FROM entities WHERE entity_type='project' "
                         "AND name LIKE ? LIMIT 20", (like,)).fetchall()
    orgs = conn.execute("SELECT entity_pk, name, scope FROM entities WHERE entity_type='organization' "
                        "AND name LIKE ? LIMIT 20", (like,)).fetchall()
    aliases = conn.execute("SELECT alias, entity_pk, status FROM entity_aliases WHERE alias LIKE ? "
                           "LIMIT 20", (like,)).fetchall()
    srcs = conn.execute("SELECT DISTINCT source_ref, publisher FROM sources WHERE source_ref LIKE ? "
                        "OR publisher LIKE ? LIMIT 20", (like, like)).fetchall()
    conn.close()
    n = len(cases) + len(orgs) + len(aliases) + len(srcs)
    if n == 0:
        return _page("Search", f"<div class='empty'>No results for <b>{_esc(q)}</b> in the "
                               f"ingested universe (2 cases, 12 sources). Try 'gds', 'airtrunk', "
                               f"'vppa', or 'bank of china'. This search covers only what has been "
                               f"ingested — it is not a general web search.</div>")
    out = [f"<h2>Search: {_esc(q)} ({n} hit(s) within the ingested universe)</h2>"]
    if cases:
        out.append("<h3>cases</h3><ul>" + "".join(
            f"<li><a href='/case/{_esc(n)}'>{_esc(n)}</a> <span class='tag'>{_esc(i)}</span></li>"
            for n, i in cases) + "</ul>")
    if orgs:
        out.append("<h3>organizations</h3><ul>" + "".join(
            f"<li><a href='/org/{_esc(pk)}'>{_esc(nm)}</a> "
            f"<span class='tag'>scope {_esc(sc)[:36]}</span></li>" for pk, nm, sc in orgs) + "</ul>")
    if aliases:
        out.append("<h3>aliases</h3><ul>" + "".join(
            f"<li>{_esc(a)} → <a href='/org/{_esc(pk)}'>entity</a> <span class='tag'>{_esc(st)}</span></li>"
            for a, pk, st in aliases) + "</ul>")
    if srcs:
        out.append("<h3>sources</h3><ul>" + "".join(
            f"<li>{_esc(r[:90])} <span class='tag'>{_esc(p)}</span></li>" for r, p in srcs) + "</ul>")
    return _page("Search", "".join(out))


def route_not_found(what: str) -> tuple[int, str, str]:
    return _page("Not found", f"<div class='err'>Not found: "
                 f"{_esc(what)}.</div><p>Use the navigation above, or <a href='/'>return home</a>. "
                 f"URLs are content-addressed; a stale link may point at a claim from a previous "
                 f"session — the database is append-only, so nothing was deleted.</p>", status=404)


def route_db_missing() -> tuple[int, str, str]:
    return _page("Database missing", "<div class='err'>The "
                 f"evidence database was not found at <code>data/processed/engine.sqlite3</code>.</div>"
                 f"<p>Setup: run <code>bash scripts/run_all.sh</code> (builds the database from cached "
                 f"raw sources), then reload this page.</p>", status=500)


def dispatch(method: str, path: str, query: dict) -> tuple[int, str, str]:
    """Route table. Read-only GET-only by design."""
    if method != "GET":
        return 405, "text/plain; charset=utf-8", "method not allowed (read-only interface)"
    path = path.rstrip("/") or "/"
    if path == "/":
        return route_home()
    if path == "/cases":
        return route_cases()
    if path == "/orgs":
        return route_orgs()
    if path == "/sources":
        return route_sources()
    if path == "/search":
        return route_search(query.get("q", [""])[0])
    if path.startswith("/case/"):
        return route_case(path[len("/case/"):])
    if path.startswith("/org/"):
        return route_org(path[len("/org/"):])
    if path.startswith("/claim/"):
        return route_claim(path[len("/claim/"):])
    if path.startswith("/involved/"):
        return route_involved(path[len("/involved/"):])
    if path.startswith("/raw/"):
        return route_raw(path[len("/raw/"):])
    return route_not_found(path)


def route_raw(source_pk: str) -> tuple[int, str, bytes]:
    """Serve the IMMUTABLE snapshot bytes for a source version (original
    evidence access) as a DOWNLOAD: application/octet-stream so third-party
    HTML can never execute same-origin, with the resolved path enforced to
    stay inside the snapshots root (symlinks and outside paths rejected)."""
    try:
        conn = _ro_conn()
    except FileNotFoundError:
        return route_db_missing()
    row = conn.execute(
        "SELECT snapshot_path, raw_checksum, raw_retention, source_ref FROM sources "
        "WHERE source_pk=?", (source_pk,)).fetchall()
    conn.close()
    if not row:
        return route_not_found(f"source {source_pk[:12]}…")
    snap, ck, retention, ref = row[0]
    if not snap or retention != "snapshot_retained":
        body = (f"<!doctype html><html><body><div class='err'>Original content not retained "
                f"for this source version.</div><p>source: {_esc(ref)}<br>checksum basis: "
                f"{_esc(ck)}</p><p>Row/metadata hashes are not raw content — this is an "
                f"honest limitation, not a broken link.</p></body></html>")
        return 404, "text/html; charset=utf-8", body.encode()
    # ENFORCED root confinement: resolved path (following symlinks) must sit
    # inside the snapshots root; outside paths are refused without reading.
    snap_root = Path(SNAP_ROOT).resolve()
    resolved = Path(snap).resolve()
    if snap_root not in resolved.parents:
        return 403, "text/html; charset=utf-8", (
            "<!doctype html><html><body><div class='err'>Refused: the snapshot path "
            "resolves outside the snapshots root. This may indicate tampering or a "
            "misconfigured row; nothing was read.</div></body></html>").encode()
    p = resolved
    if not p.exists() or file_sha256(p) != ck:
        return 500, "text/html; charset=utf-8", (
            "<!doctype html><html><body><div class='err'>Snapshot checksum mismatch — "
            "the retained copy does not match its recorded hash. This is a serious "
            "integrity failure and must be investigated.</div></body></html>").encode()
    # ALWAYS octet-stream: evidence is downloaded/inspected, never rendered as
    # same-origin HTML (third-party pages must not execute scripts here)
    return 200, "application/octet-stream", p.read_bytes()
