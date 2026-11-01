"""Evidence-engine tests: attribution, identity ambiguity, contradictions,
changed/removed source versions, reproducible runs, review-status discipline.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from discovery.engine import (ClaimIn, Engine, SourceIn, content_hash, now_iso)

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / "findings"
DB = ROOT / "data" / "processed" / "engine.sqlite3"


# ---------- attribution ----------

def test_every_claim_has_observation_and_source_version():
    eng = Engine(DB)
    orphans = eng.conn.execute(
        """SELECT COUNT(*) FROM claims c
           LEFT JOIN observations o ON o.obs_pk = c.observation_pk
           LEFT JOIN sources s ON s.source_pk = o.source_pk
           WHERE o.obs_pk IS NULL OR s.source_pk IS NULL""").fetchone()[0]
    assert orphans == 0


def test_claims_carry_review_status_and_certainty():
    eng = Engine(DB)
    bad = eng.conn.execute(
        "SELECT COUNT(*) FROM claims WHERE review_status != 'machine_extracted' "
        "OR certainty NOT IN ('documented','reported','inferred')").fetchone()[0]
    assert bad == 0, "no human verification may be fabricated"
    n = eng.conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    assert n >= 25


def test_second_case_present_with_distinction_discipline():
    eng = Engine(DB)
    at = _case_pk(eng, "airtrunk-jhb1-vppa")
    preds = {r[0] for r in eng.conn.execute(
        "SELECT predicate FROM claims WHERE subject_pk=?", (at,))}
    assert {"HAS_VPPA_SIGNED", "HAS_OFFTAKER", "IS_PHYSICAL_SUPPLY_OF",
            "IS_AI_WORKLOAD"} <= preds
    supply = eng.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND "
        "predicate='IS_PHYSICAL_SUPPLY_OF'", (at,)).fetchone()[0]
    assert "NOT ESTABLISHED" in supply and "financial contract" in supply
    ai = eng.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND "
        "predicate='IS_AI_WORKLOAD'", (at,)).fetchone()[0]
    assert "NOT INFERABLE" in ai


# ---------- identity ambiguity ----------

def test_ambiguous_aliases_are_recorded_not_merged():
    eng = Engine(DB)
    amb = eng.ambiguous_aliases()
    aliases = {a["alias"] for a in amb}
    assert {"gds", "dayone", "airtrunk pte ltd"} <= aliases
    # the alias 'dayone' -> gds-holdings stays AMBIGUOUS (never a merge): the
    # DayOne Batam investigation legitimately adds a SEPARATE scoped dayone
    # entity, and the two remain distinct until human adjudication
    gds_pks = {r[0] for r in eng.conn.execute(
        "SELECT entity_pk FROM entities WHERE name='gds-holdings'")}
    dayone_pks = {r[0] for r in eng.conn.execute(
        "SELECT entity_pk FROM entities WHERE name='dayone'")}
    assert gds_pks and dayone_pks and not (gds_pks & dayone_pks), \
        "gds-holdings and dayone must remain distinct entities"
    dayone_alias_rows = [r for r in amb if r["alias"] == "dayone"]
    assert all(r["entity_pk"] in gds_pks for r in dayone_alias_rows)


def test_identity_ambiguity_in_engine_unit(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    run = "run-test"
    src = SourceIn(source_ref="s1", raw_bytes_inline=b"a")
    pk, ev = eng.record_source(src, run)
    assert ev == "new"
    eng.add_observation(pk, "p1", "f", "alias evidence: 'DayOne' is GDS-affiliated")
    obs = eng.conn.execute("SELECT obs_pk FROM observations").fetchone()[0]
    gds = eng.ensure_entity("organization", "gds-holdings", scope="s1")
    eng.add_alias("dayone", gds, "ambiguous", obs)
    # a second entity with a different name coexists; no merge happened
    other = eng.ensure_entity("organization", "dayone-operations", scope="s1")
    assert gds != other
    assert eng.ambiguous_aliases()[0]["alias"] == "dayone"


# ---------- contradictions ----------

def _case_pk(eng: Engine, name: str) -> str:
    """Resolve an investigation case entity by its engine-case identifier."""
    return eng.conn.execute(
        """SELECT entity_pk FROM entities WHERE entity_type='project' AND name=?
           ORDER BY (identifier IS NULL), entity_pk LIMIT 1""", (name,)).fetchone()[0]


def test_contradictions_grouped_only_for_single_valued_predicates():
    eng = Engine(DB)
    gds = _case_pk(eng, "gds-nusajaya-ntp1")
    contra_claims = {r[0] for r in eng.conn.execute(
        "SELECT claim_pk FROM claims WHERE subject_pk=? AND predicate IN "
        "('HAS_RECORD_STATUS','HAS_CAPACITY_CLAIM')", (gds,))}
    groups = {c for g in eng.contradictions_for(gds) for c in [g["claim_pk"]]}
    assert contra_claims <= groups, "status+capacity disagreements must be grouped"
    # financing participants are multi-valued: never contradiction-flagged
    part = eng.conn.execute(
        "SELECT COUNT(*) FROM claims c LEFT JOIN contradictions co ON co.claim_pk=c.claim_pk "
        "WHERE c.subject_pk=? AND c.predicate='HAS_FINANCING_PARTICIPANT' "
        "AND co.claim_pk IS NOT NULL", (gds,)).fetchone()[0]
    assert part == 0


def test_contradiction_unit_scenario(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    run = "run-test"
    pk, _ = eng.record_source(SourceIn(source_ref="s1", raw_bytes_inline=b"a"), run)
    eng.ingest_claims([
        ClaimIn(subject_key="project:x", subject_type="project", predicate="HAS_RECORD_STATUS",
                object_literal="Completion", source_ref="s1", locator="l1", field="f",
                quote="q1", certainty="documented"),
        ClaimIn(subject_key="project:x", subject_type="project", predicate="HAS_RECORD_STATUS",
                object_literal="Pre-construction", source_ref="s1", locator="l2", field="f",
                quote="q2", certainty="documented"),
    ], run)
    groups = eng.detect_contradictions()
    assert len(groups) == 1
    all_res = eng.conn.execute("SELECT DISTINCT resolution_status FROM contradictions").fetchall()
    assert all(r[0] == "unresolved" for r in all_res)


# ---------- changed / removed source versions ----------

def test_source_versioning_change_and_not_present(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    run1 = "run-" + content_hash({"i": 1})
    pk1, ev1 = eng.record_source(SourceIn(source_ref="u1", raw_bytes_inline=b"A"), run1)
    pk2, ev2 = eng.record_source(SourceIn(source_ref="u1", raw_bytes_inline=b"B"), run1)
    assert (ev1, ev2) == ("new", "changed") and pk1 != pk2
    # same content again: unchanged, no new version
    pk3, ev3 = eng.record_source(SourceIn(source_ref="u1", raw_bytes_inline=b"B"), run1)
    assert ev3 == "unchanged" and pk3 == pk2
    # a known source absent from the current ingest is reported, not deleted
    assert eng.not_present_sources({"u1"}) == []
    assert eng.not_present_sources(set()) == ["u1"]
    versions = eng.conn.execute(
        "SELECT version_index, raw_checksum FROM sources WHERE source_ref='u1' "
        "ORDER BY version_index").fetchall()
    assert [v[0] for v in versions] == [1, 2]


# ---------- reproducible runs ----------

def test_engine_ingest_is_reproducible():
    """Run the real ingest twice; the deterministic hash must be identical and
    equal across runs; sources must report 'unchanged' on the second run."""
    out1 = subprocess.run([sys.executable, "scripts/engine_ingest.py"],
                          capture_output=True, text=True, cwd=ROOT,
                          env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT / "src")})
    assert out1.returncode == 0, out1.stderr[-400:]
    h1 = json.loads(out1.stdout)["deterministic_hash"]
    out2 = subprocess.run([sys.executable, "scripts/engine_ingest.py"],
                          capture_output=True, text=True, cwd=ROOT,
                          env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT / "src")})
    h2 = json.loads(out2.stdout)["deterministic_hash"]
    assert h1 == h2
    events = json.loads(out2.stdout)["sources"]
    assert set(events.values()) <= {"unchanged"}


def test_claim_pks_are_content_addressed(tmp_path):
    eng = Engine(tmp_path / "t.sqlite3")
    run = "r"
    eng.record_source(SourceIn(source_ref="s", raw_bytes_inline=b"x"), run)
    c1 = ClaimIn(subject_key="project:p", subject_type="project", predicate="HAS_RECORD_STATUS",
                 object_literal="v", source_ref="s", locator="l", field="f", quote="q",
                 certainty="documented")
    eng.ingest_claims([c1], run)
    pk1 = eng.conn.execute("SELECT claim_pk FROM claims").fetchone()[0]
    # re-ingesting identical content changes nothing
    eng.ingest_claims([ClaimIn(**vars(c1))], run)
    rows = eng.conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    pk2 = eng.conn.execute("SELECT claim_pk FROM claims").fetchone()[0]
    assert rows == 1 and pk1 == pk2


# ---------- timeline query ----------

def test_project_timeline_orders_and_attributes():
    eng = Engine(DB)
    gds = _case_pk(eng, "gds-nusajaya-ntp1")
    tl = eng.project_timeline(gds)
    assert len(tl) >= 12
    times = [r["claim_time"] or "9999" for r in tl]
    assert times == sorted(times)
    assert all(r["source_ref"] and r["quote"] for r in tl)
    # known/unknown map works
    unk = eng.unknowns_for(gds, {"status": ["HAS_RECORD_STATUS"], "energy": ["RENEWABLE_PROCUREMENT_STATUS"]})
    assert unk["status"].endswith("claim(s)") and unk["energy"].endswith("claim(s)")
