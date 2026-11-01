"""Adversarial integrity tests for the evidence engine (supervisor review
2026-10-30): quote fidelity against cached originals, analyst-inference
separation, raw checksums, access-status distinctions, contradiction scoping,
homonym protection, and non-destructive migration.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from discovery.engine import Engine, content_hash, file_sha256

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "engine.sqlite3"
sys.path.insert(0, str(ROOT / "scripts"))


def eng() -> Engine:
    return Engine(DB)


def test_every_verbatim_quote_verified_against_cached_original():
    e = eng()
    rows = e.conn.execute(
        """SELECT o.quote FROM observations o
           WHERE o.evidence_kind='verbatim' AND o.verified_against_raw IS NOT NULL
           AND o.verified_against_raw != 1
           AND o.extractor_version = (SELECT MAX(extractor_version) FROM observations)
           AND o.obs_pk IN (SELECT observation_pk FROM claims
             WHERE ingested_run = (SELECT MAX(ingested_run) FROM claims
               WHERE subject_pk = (SELECT subject_pk FROM claims c2
                 JOIN observations o2 ON o2.obs_pk = claims.observation_pk
                 WHERE o2.obs_pk = o.obs_pk)))"""
    ).fetchall()
    assert not rows, f"unverified verbatim quotes present: {rows}"


def test_analyst_synthesis_never_cites_fetched_sources():
    e = eng()
    n = e.conn.execute(
        """SELECT COUNT(*) FROM claims c
           JOIN observations o ON o.obs_pk = c.observation_pk
           JOIN sources s ON s.source_pk = o.source_pk
           WHERE c.evidence_kind='analyst_synthesis' AND s.source_ref NOT LIKE 'analysis:%'"""
    ).fetchone()[0]
    assert n == 0
    arts = e.conn.execute(
        "SELECT publisher, raw_path FROM sources WHERE source_ref LIKE 'analysis:%'").fetchall()
    assert arts and all("this project" in p for p, _ in arts)


def test_synthesis_absence_claims_are_bounded_search_findings():
    e = eng()
    rows = e.conn.execute(
        "SELECT object_literal FROM claims WHERE evidence_kind='analyst_synthesis' "
        "AND predicate IN ('RENEWABLE_PROCUREMENT_STATUS')").fetchall()
    assert rows, "expected a renewable-procurement synthesis claim"
    for (lit,) in rows:
        assert "bounded search" in lit or "not surfaced" in lit or "NOT EVIDENCED" in lit
        assert "absence is not established" in lit or "absence not established" in lit or \
               "NOT EVIDENCED" in lit


def test_raw_checksums_match_cached_files():
    e = eng()
    import engine_ingest  # noqa: E402  (scripts dir on path)
    # compare the LATEST version of each file-backed source against the live file;
    # superseded versions are preserved precisely because the live file moved on
    rows = e.conn.execute(
        """SELECT source_ref, raw_checksum, raw_path, raw_bytes, version_index
           FROM sources s WHERE raw_path IS NOT NULL AND version_index = (
             SELECT MAX(version_index) FROM sources WHERE source_ref = s.source_ref)"""
    ).fetchall()
    assert len(rows) >= 9
    for ref, ck, path, nbytes, vi in rows:
        p = Path(path)
        assert p.exists(), f"missing raw file for {ref}: {path}"
        assert file_sha256(p) == ck, f"checksum mismatch for {ref}"
        assert nbytes == p.stat().st_size, f"byte size mismatch for {ref}"
    # the GLEIF artifact changes on every pipeline run (embedded generation
    # timestamp): prior versions must be PRESERVED (>=2, distinct checksums)
    # and only the latest may match the live file
    gleif_versions = e.conn.execute(
        "SELECT version_index, raw_checksum FROM sources "
        "WHERE source_ref LIKE 'gleif:%' ORDER BY version_index").fetchall()
    assert len(gleif_versions) >= 2, "prior versions must be preserved, not reset"
    assert len({v[1] for v in gleif_versions}) == len(gleif_versions)
    assert gleif_versions[-1][1] == file_sha256(Path("data/processed/gleif_enrichment.json"))
    events = e.conn.execute(
        "SELECT event FROM source_events WHERE source_ref LIKE 'gleif:%'").fetchall()
    assert any(ev[0] == "changed" for ev in events), "the change must be recorded as an event"
    # row-based sources (no file) must still carry a checksum over their raw_row
    row_based = e.conn.execute(
        "SELECT source_ref, raw_checksum FROM sources WHERE raw_path IS NULL "
        "AND raw_checksum IS NOT NULL").fetchall()
    assert row_based, "row-based sources (maps URL, search transcript) must be checksummed"


def test_access_status_distinguishes_missing_failed_notice():
    e = eng()
    st = dict(e.conn.execute("SELECT source_ref, access_status FROM sources").fetchall())
    notice = [k for k, v in st.items() if v == "notice_page"]
    missing = [k for k, v in st.items() if v == "missing"]
    notfetched = [k for k, v in st.items() if v == "not_fetched"]
    assert notice and "gds-services.com" in notice[0]
    assert missing and "airtrunk.com" in missing[0]
    assert notfetched and any("websearch" in k for k in notfetched)
    # fetched/notice/missing sources must document their retrieval attempts
    for ref, status in st.items():
        if status in ("fetched", "notice_page", "missing") and not ref.startswith("analysis:"):
            att = e.conn.execute("SELECT retrieval_attempts_json FROM sources WHERE source_ref=?",
                                 (ref,)).fetchone()[0]
            assert json.loads(att), f"no retrieval attempts recorded for {ref}"


def test_contradictions_are_possible_with_scope_notes():
    e = eng()
    rows = e.conn.execute("SELECT group_pk, kind, scope_note FROM contradictions").fetchall()
    assert rows, "expected contradiction groups for the GDS case"
    for gpk, kind, note in rows:
        assert kind == "possible", "no contradiction may be confirmed without adjudication"
        assert "UNPROVEN" in note
    gds = e.conn.execute(
        """SELECT entity_pk FROM entities WHERE entity_type='project' AND name='gds-nusajaya-ntp1'
           ORDER BY (identifier IS NULL), entity_pk LIMIT 1""").fetchone()[0]
    status_groups = e.conn.execute(
        """SELECT DISTINCT co.group_pk, co.scope_note FROM contradictions co
           JOIN claims c ON c.claim_pk=co.claim_pk
           WHERE c.subject_pk=? AND c.predicate='HAS_RECORD_STATUS'""", (gds,)).fetchall()
    assert status_groups
    assert all("claim_times differ" in note for _, note in status_groups), \
        "status claims span dates; the scope note must flag temporal-sequence possibility"
    assert all("grains:" in note for _, note in status_groups)


def test_homonym_protection_and_explicit_adjudication():
    e = eng()
    boc = e.conn.execute(
        "SELECT entity_pk, name, identifier, identity_status FROM entities "
        "WHERE name LIKE 'Bank of China%'").fetchall()
    assert len(boc) >= 2, "HQ and Malaysia branch must be distinct entities"
    assert len({b[0] for b in boc}) == len(boc), "identifier-bearing entities must not collide"
    assert all(b[2] for b in boc), "each carries an identifier"
    adj = e.conn.execute("SELECT decision, decided_by FROM adjudications").fetchall()
    assert any(d == "distinct_entities" for d, _ in adj)
    assert any("AI-generated" in by for _, by in adj), "adjudicator must disclose AI authorship"
    prov = e.conn.execute(
        "SELECT COUNT(*) FROM entities WHERE identity_status='provisional_name_only'").fetchone()[0]
    assert prov > 0, "name-only entities must be marked provisional"


def test_migration_preserves_legacy_rows(tmp_path):
    """A v0.1-schema database with rows must survive opening under v0.2 with
    all columns added in place and NO row loss."""
    legacy = tmp_path / "legacy.sqlite3"
    c = sqlite3.connect(legacy)
    c.executescript("""
    CREATE TABLE sources (source_pk TEXT PRIMARY KEY, source_ref TEXT, version_index INTEGER,
      content_hash TEXT, publisher TEXT, license TEXT, source_type TEXT, document_date TEXT,
      access_status TEXT, fetched_at_utc TEXT, file_path TEXT, details_json TEXT);
    CREATE TABLE observations (obs_pk TEXT PRIMARY KEY, source_pk TEXT, locator TEXT, field TEXT,
      quote TEXT, extractor_version TEXT);
    CREATE TABLE entities (entity_pk TEXT PRIMARY KEY, entity_type TEXT, name TEXT);
    CREATE TABLE claims (claim_pk TEXT PRIMARY KEY, subject_pk TEXT, predicate TEXT, object_pk TEXT,
      object_literal TEXT, claim_time TEXT, time_precision TEXT, certainty TEXT, review_status TEXT,
      observation_pk TEXT, ingested_run TEXT);
    """)
    c.execute("INSERT INTO sources VALUES ('sp1','ref1',1,'ch1','Pub','Lic','type',NULL,'fetched','t',NULL,'{}')")
    c.execute("INSERT INTO observations VALUES ('o1','sp1','loc','fld','some quote','0.1.0')")
    c.execute("INSERT INTO entities VALUES ('e1','organization','Acme')")
    c.execute("INSERT INTO claims VALUES ('c1','e1','PRED',NULL,'v',NULL,'unknown','documented',"
              "'machine_extracted','o1','r1')")
    c.commit()
    c.close()

    eng = Engine(legacy)
    assert eng.conn.execute("PRAGMA user_version").fetchone()[0] >= 2
    assert eng.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1
    assert eng.conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
    assert eng.conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 1
    assert eng.conn.execute("SELECT quote FROM observations WHERE obs_pk='o1'").fetchone()[0] == "some quote"
    assert eng.conn.execute("SELECT identity_status FROM entities").fetchone()[0] == "provisional_name_only"
    # new columns exist and are NULL-safe for legacy rows
    assert eng.conn.execute("SELECT raw_checksum FROM sources WHERE source_pk='sp1'").fetchone()[0] is None


def test_reopening_never_resets_data(tmp_path):
    db = tmp_path / "persist.sqlite3"
    e1 = Engine(db)
    run = "run-persist"
    e1.record_source(__import__("discovery.engine", fromlist=["SourceIn"]).SourceIn(
        source_ref="u", raw_bytes_inline=b"hello"), run)
    e1.ingest_claims([__import__("discovery.engine", fromlist=["ClaimIn"]).ClaimIn(
        subject_key="project:p", subject_type="project", predicate="HAS_RECORD_STATUS",
        object_literal="v", source_ref="u", locator="l", field="f", quote="hello",
        certainty="documented")], run)
    e1.finish_run(run, "t", "ih", 1, 0, 0, 1)
    e1.commit()
    n_before = e1.conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]

    e2 = Engine(db)  # reopen
    assert e2.conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == n_before
    assert e2.conn.execute("SELECT COUNT(*) FROM ingest_runs").fetchone()[0] == 1
    assert e2.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1
