"""Adversarial tests for engine v0.3 (supervisor audit 2026-10-31):
source-scoped identity (homonyms cannot silently merge), append-only
retrieval history, immutable snapshots surviving source mutation AND
reversion, and re-ingestion without data loss.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from discovery.engine import (ClaimIn, Engine, SourceIn, file_sha256, now_iso)

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "engine.sqlite3"


# ---------- scoped identity: homonyms cannot silently merge ----------

def test_same_name_from_two_sources_yields_two_entities(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    run = "r1"
    for ref in ("source-one", "source-two"):
        eng.record_source(SourceIn(source_ref=ref, raw_bytes_inline=b"x"), run)
        eng.ingest_claims([ClaimIn(
            subject_key="org:acme-power", subject_type="organization",
            predicate="HAS_OPERATION_STATUS", object_literal="operating",
            claim_time="2024", time_precision="year", certainty="reported",
            source_ref=ref, locator="l", field="f", quote="q")], run)
    rows = eng.conn.execute(
        "SELECT entity_pk, scope, identity_status FROM entities "
        "WHERE name='acme-power'").fetchall()
    assert len(rows) == 2, "same name from distinct sources must be two entities"
    assert len({r[0] for r in rows}) == 2
    assert {r[1] for r in rows} == {"source-one", "source-two"}
    assert all(r[2] == "provisional_scoped" for r in rows)
    # no contradiction is asserted across the two scoped entities
    assert eng.detect_contradictions() == {}


def test_explicit_adjudication_merges_visibility_not_rows(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    run = "r1"
    for ref in ("source-one", "source-two"):
        eng.record_source(SourceIn(source_ref=ref, raw_bytes_inline=b"x"), run)
        eng.ingest_claims([ClaimIn(
            subject_key="org:acme-power", subject_type="organization",
            predicate="HAS_OPERATION_STATUS", object_literal="operating",
            claim_time="2024", time_precision="year", certainty="reported",
            source_ref=ref, locator="l", field="f", quote="q")], run)
    a = eng.conn.execute("SELECT entity_pk FROM entities WHERE scope='source-one'").fetchone()[0]
    b = eng.conn.execute("SELECT entity_pk FROM entities WHERE scope='source-two'").fetchone()[0]
    assert a != b
    eng.adjudicate(a, b, "same_entity",
                   decided_by="human reviewer (hypothetical)")  # recorded, not fabricated as done
    assert eng.same_entity_pks(a) == {a, b}
    assert eng.same_entity_pks(b) == {a, b}
    # rows are NOT rewritten: both scoped entities remain, the decision is additive
    assert eng.conn.execute("SELECT COUNT(*) FROM entities WHERE name='acme-power'").fetchone()[0] == 2


def test_real_db_scope_separation_gds_sources():
    eng = Engine(DB)
    # bank-of-china-malaysia exists as scoped entities from two sources
    rows = eng.conn.execute(
        "SELECT entity_pk, scope, identity_status FROM entities "
        "WHERE name='bank-of-china-malaysia'").fetchall()
    scopes = {r[1] for r in rows}
    assert len(rows) >= 2 and len(scopes) >= 2
    # and an explicit unadjudicated pair is recorded
    adj = eng.conn.execute(
        "SELECT decision FROM adjudications WHERE decision='unadjudicated'").fetchall()
    assert adj


# ---------- append-only retrieval history ----------

def test_retrieval_events_append_only_never_lost(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    ref = "u1"
    eng.record_source(SourceIn(source_ref=ref, raw_bytes_inline=b"A",
                               retrieval_attempts=[{"ts": "t1", "status": 200}]), "r1")
    eng.record_source(SourceIn(source_ref=ref, raw_bytes_inline=b"A",
                               retrieval_attempts=[{"ts": "t2", "status": 200},
                                                   {"ts": "t3", "status": 304}]), "r2")
    events = eng.conn.execute(
        "SELECT ts, outcome FROM retrieval_events WHERE source_ref=? ORDER BY ts",
        (ref,)).fetchall()
    assert [(e[0]) for e in events] == ["t1", "t2", "t3"], \
        "every attempt must survive; nothing may be overwritten"


def test_real_db_retrieval_events_recorded():
    eng = Engine(DB)
    n, distinct = eng.conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT source_ref) FROM retrieval_events").fetchone()
    assert n >= 8 and distinct >= 6
    # GDS sources each carry their fetch attempt as an immutable event
    gds = eng.conn.execute(
        "SELECT COUNT(*) FROM retrieval_events WHERE source_ref LIKE '%prnewswire%'").fetchone()[0]
    assert gds >= 1


# ---------- immutable snapshots across mutation AND reversion ----------

def test_snapshots_survive_mutation_and_reversion(tmp_path):
    db = tmp_path / "t.sqlite3"
    workdir = tmp_path / "raw"
    workdir.mkdir()
    live = workdir / "report.html"
    live.write_bytes(b"VERSION-ONE-CONTENT")

    eng = Engine(db)
    ref = "https://example.org/report"
    v1, ev1 = eng.record_source(SourceIn(source_ref=ref, publisher="X", license="L",
                                         access_status="fetched", raw_path=live,
                                         retrieval_attempts=[{"ts": "t1", "status": 200}]), "r1")
    snap1 = eng.conn.execute("SELECT snapshot_path FROM sources WHERE source_pk=?", (v1,)).fetchone()[0]
    assert Path(snap1).read_bytes() == b"VERSION-ONE-CONTENT"
    assert eng.conn.execute("SELECT raw_retention FROM sources WHERE source_pk=?",
                            (v1,)).fetchone()[0] == "snapshot_retained"

    # mutation -> new version, OLD snapshot still readable with old bytes
    live.write_bytes(b"VERSION-TWO-CONTENT")
    v2, ev2 = eng.record_source(SourceIn(source_ref=ref, publisher="X", license="L",
                                         access_status="fetched", raw_path=live,
                                         retrieval_attempts=[{"ts": "t2", "status": 200}]), "r2")
    assert ev2 == "changed" and v2 != v1
    assert Path(snap1).read_bytes() == b"VERSION-ONE-CONTENT", "prior snapshot must be immutable"
    snap2 = eng.conn.execute("SELECT snapshot_path FROM sources WHERE source_pk=?", (v2,)).fetchone()[0]
    assert Path(snap2).read_bytes() == b"VERSION-TWO-CONTENT"

    # reversion to the original bytes -> third version; all three snapshots intact
    live.write_bytes(b"VERSION-ONE-CONTENT")
    v3, ev3 = eng.record_source(SourceIn(source_ref=ref, publisher="X", license="L",
                                         access_status="fetched", raw_path=live,
                                         retrieval_attempts=[{"ts": "t3", "status": 200}]), "r3")
    assert ev3 == "changed"
    versions = eng.conn.execute(
        "SELECT version_index, snapshot_path, raw_checksum FROM sources "
        "WHERE source_ref=? ORDER BY version_index", (ref,)).fetchall()
    assert [v[0] for v in versions] == [1, 2, 3]
    expected = [b"VERSION-ONE-CONTENT", b"VERSION-TWO-CONTENT", b"VERSION-ONE-CONTENT"]
    for (_vi, snap, _ck), want in zip(versions, expected):
        assert Path(snap).read_bytes() == want, \
            "every version must resolve to a snapshot holding its exact bytes"
    # identical content shares one content-addressed snapshot (correct dedup);
    # distinct content must never share one
    assert len({v[1] for v in versions}) == 2
    events = eng.conn.execute(
        "SELECT outcome FROM retrieval_events WHERE source_ref=? ORDER BY ts", (ref,)).fetchall()
    assert [e[0] for e in events] == ["200", "200", "200"]


def test_metadata_row_checksum_is_labelled_not_retained(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    eng.record_source(SourceIn(source_ref="row-based", raw_row={"k": "v"},
                               access_status="not_fetched"), "r1")
    row = eng.conn.execute(
        "SELECT checksum_basis, raw_retention, snapshot_path FROM sources "
        "WHERE source_ref='row-based'").fetchone()
    assert row[0] == "metadata_row", "a metadata hash must never be presented as raw content"
    assert row[1] == "not_retained" and row[2] is None


# ---------- re-ingestion without data loss ----------

def test_reingest_preserves_all_prior_state():
    """Two consecutive real ingests: no rows may disappear; claim sets only grow
    or stay identical; source versions are never removed."""
    def counts():
        e = Engine(DB)
        return tuple(e.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                     for t in ("sources", "observations", "claims", "retrieval_events"))
    before = counts()
    r = subprocess.run([sys.executable, "scripts/engine_ingest.py"], capture_output=True,
                       text=True, cwd=ROOT, env={"PATH": "/usr/bin:/bin",
                                                 "PYTHONPATH": str(ROOT / "src")})
    assert r.returncode == 0, r.stderr[-300:]
    after = counts()
    assert all(a >= b for a, b in zip(after, before)), (before, after)


def test_real_db_deterministic_across_runs():
    hashes = []
    for _ in range(2):
        r = subprocess.run([sys.executable, "scripts/engine_ingest.py"], capture_output=True,
                           text=True, cwd=ROOT, env={"PATH": "/usr/bin:/bin",
                                                     "PYTHONPATH": str(ROOT / "src")})
        hashes.append(json.loads(r.stdout)["deterministic_hash"])
    assert len(set(hashes)) == 1


# ---------- v0.3.1: read-only identity resolution (supervisor audit) ----------

def _mk_ids(eng, *names):
    return {n: eng.ensure_entity("organization", n, identifier=f"id-{n}") for n in names}


def test_identity_resolution_is_order_independent_and_transitive(tmp_path):
    for order in ([("A", "B"), ("B", "C")], [("B", "C"), ("A", "B")]):
        eng = Engine(tmp_path / f"t{order[0][0]}{order[0][1]}.sqlite3")
        ids = _mk_ids(eng, "A", "B", "C")
        for pair in order:
            eng.adjudicate(ids[pair[0]], ids[pair[1]], "same_entity", "reviewer")
        res = eng.identity_resolution(ids["A"])
        assert res["merged"] is True and res["conflicts"] == []
        assert res["closure"] == set(ids.values()), order


def test_superseded_adjudication_latest_wins_both_orders(tmp_path):
    # same then distinct -> operative decision is distinct -> no merge
    e1 = Engine(tmp_path / "t1.sqlite3")
    ids = _mk_ids(e1, "A", "B")
    e1.adjudicate(ids["A"], ids["B"], "same_entity", "r1")
    e1.adjudicate(ids["A"], ids["B"], "distinct_entities", "r2")
    assert e1.identity_resolution(ids["A"])["merged"] is False
    # distinct then same -> operative decision is same -> merge
    e2 = Engine(tmp_path / "t2.sqlite3")
    ids2 = _mk_ids(e2, "A", "B")
    e2.adjudicate(ids2["A"], ids2["B"], "distinct_entities", "r1")
    e2.adjudicate(ids2["A"], ids2["B"], "same_entity", "r2")
    assert e2.identity_resolution(ids2["A"])["merged"] is True
    # historical rows preserved in both databases
    assert e1.conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0] == 2
    assert e2.conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0] == 2


def test_same_entity_pks_never_writes_or_commits(tmp_path):
    """Transaction regression: a resolution query must not commit unrelated
    pending work, must not write conflict rows, and must not lose them either."""
    eng = Engine(tmp_path / "t.sqlite3")
    ids = _mk_ids(eng, "A", "B")
    eng.adjudicate(ids["A"], ids["B"], "same_entity", "r1")
    eng.adjudicate(ids["A"], ids["B"], "distinct_entities", "r2")  # conflict
    # unrelated pending work in the caller's transaction
    eng.conn.execute(
        "INSERT INTO entities(entity_pk, entity_type, name, identity_status) "
        "VALUES ('pending-1','organization','PendingWork','provisional_name_only')")
    eng.conn.execute(
        "INSERT INTO observations(obs_pk, source_pk, locator, field, quote, evidence_kind, "
        "extractor_version) VALUES ('pending-obs','no-such-source','l','f','q','verbatim','test')")
    res = eng.same_entity_pks(ids["A"])  # conflict path (was: INSERT + commit)
    assert res == {ids["A"]}             # conservative no-merge
    # verify via a SECOND connection that nothing was committed
    probe = sqlite3.connect(eng.db_path)
    assert probe.execute(
        "SELECT COUNT(*) FROM entities WHERE entity_pk='pending-1'").fetchone()[0] == 0
    assert probe.execute("SELECT COUNT(*) FROM adjudication_conflicts").fetchone()[0] == 0
    probe.close()
    # caller may roll back and explicitly record the conflict instead
    eng.conn.rollback()
    n = eng.record_identity_conflicts([sorted([ids["A"], ids["B"]])], entity_pk=ids["A"])
    assert n == 1
    assert eng.conn.execute(
        "SELECT status FROM adjudication_conflicts").fetchone()[0] == "unresolved"


def test_real_db_adjudications_survive_resolution_queries():
    eng = Engine(DB)
    before = eng.conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0]
    conf_before = eng.conn.execute("SELECT COUNT(*) FROM adjudication_conflicts").fetchone()[0]
    for (pk,) in eng.conn.execute("SELECT entity_pk FROM entities LIMIT 30").fetchall():
        eng.same_entity_pks(pk)
    assert eng.conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0] == before
    assert eng.conn.execute("SELECT COUNT(*) FROM adjudication_conflicts").fetchone()[0] == conf_before


# ---------- v0.5: append-only adjudications (supervisor audit) ----------

def test_adjudication_is_append_only_with_authors_preserved(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    ids = _mk_ids(eng, "A", "B")
    src_pk, _ = eng.record_source(SourceIn(source_ref="adjud-basis", raw_bytes_inline=b"b"), "r0")
    o1 = eng.add_observation(src_pk, "l1", "f", "basis one")
    o2 = eng.add_observation(src_pk, "l2", "f", "basis two")
    eng.adjudicate(ids["A"], ids["B"], "same_entity", "reviewer-1", basis_obs=o1)
    eng.adjudicate(ids["A"], ids["B"], "distinct_entities", "reviewer-2", basis_obs=o2)
    eng.adjudicate(ids["A"], ids["B"], "same_entity", "reviewer-3", basis_obs=None)
    hist = eng.adjudication_history(ids["A"], ids["B"])
    assert len(hist) == 3, "repeat decisions append; nothing overwritten"
    assert [h["decided_by"] for h in hist] == ["reviewer-1", "reviewer-2", "reviewer-3"]
    assert [h["sequence"] for h in hist] == [1, 2, 3]
    assert eng.conn.execute("SELECT basis_observation_pk FROM adjudications WHERE sequence=1").fetchone()[0] == o1
    # operative decision = latest (sequence 3, same_entity)
    assert eng.identity_resolution(ids["A"])["merged"] is True


def test_repeat_identical_decision_appends_new_row(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    ids = _mk_ids(eng, "A", "B")
    eng.adjudicate(ids["A"], ids["B"], "same_entity", "reviewer-1")
    eng.adjudicate(ids["A"], ids["B"], "same_entity", "reviewer-1")
    n = eng.conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0]
    assert n == 2, "INSERT OR REPLACE must not collapse repeat events"


def test_adjudicate_does_not_commit_caller_transaction(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    ids = _mk_ids(eng, "A", "B")
    eng.conn.execute(
        "INSERT INTO entities(entity_pk, entity_type, name, identity_status) "
        "VALUES ('pending-x','organization','Pending','provisional_name_only')")
    eng.adjudicate(ids["A"], ids["B"], "same_entity", "reviewer-1")
    probe = sqlite3.connect(eng.db_path)
    assert probe.execute(
        "SELECT COUNT(*) FROM entities WHERE entity_pk='pending-x'").fetchone()[0] == 0
    assert probe.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0] == 0
    probe.close()
    eng.conn.rollback()


def test_legacy_adjudication_history_disclosed_after_migration():
    eng = Engine(DB)
    rows = eng.conn.execute(
        "SELECT decided_by, decided_at, sequence FROM adjudications").fetchall()
    assert rows
    # legacy rows: decided_at honestly NULL (unknown), sequence backfilled
    assert all(r[2] is not None for r in rows)
    assert any(r[1] is None for r in rows), "legacy authorship time must stay disclosed as unknown"
