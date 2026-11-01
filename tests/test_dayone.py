"""Tests for the DayOne Batam investigation (grain discipline, source layers,
falsification record, no conflation)."""
from __future__ import annotations

import json
from pathlib import Path

from discovery.engine import Engine, file_sha256

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "engine.sqlite3"
FINDINGS = ROOT / "findings"


def eng() -> Engine:
    return Engine(DB)


def case_pk(name: str) -> str:
    return eng().conn.execute(
        """SELECT entity_pk FROM entities WHERE entity_type='project' AND name=?
           ORDER BY (identifier IS NULL), entity_pk LIMIT 1""", (name,)).fetchone()[0]


def test_two_batam_campuses_are_distinct_entities():
    e = eng()
    pks = {case_pk(n) for n in ("dayone-ndp-batam", "dayone-kabil-batam",
                                "airtrunk-jhb1", "gds-nusajaya-ntp1")}
    assert len(pks) == 4


def test_ndp_loan_not_attributed_to_kabil():
    e = eng()
    ndp, kab = case_pk("dayone-ndp-batam"), case_pk("dayone-kabil-batam")
    ndp_fin = {r[0] for r in e.conn.execute(
        "SELECT DISTINCT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_FINANCING'",
        (ndp,))}
    assert any("DBS" in x and "6.7 trillion" in x for x in ndp_fin)
    kab_fin = {r[0] for r in e.conn.execute(
        "SELECT DISTINCT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_FINANCING'",
        (kab,))}
    assert kab_fin == set() or all("NOT ESTABLISHED" in x for x in kab_fin), \
        "no Kabil financing claim may exist (none was found)"
    assert not any("412" in x for x in kab_fin)


def test_kabil_ppa_is_grid_capacity_with_no_renewable_claim():
    e = eng()
    kab = case_pk("dayone-kabil-batam")
    ren = e.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='IS_RENEWABLE_SUPPLY'",
        (kab,)).fetchone()[0]
    assert "NOT ESTABLISHED" in ren and "grid capacity" in ren
    ppa = e.conn.execute(
        """SELECT o.quote FROM claims c JOIN observations o ON o.obs_pk=c.observation_pk
           WHERE c.subject_pk=? AND c.predicate='HAS_PPA_SIGNED'""", (kab,)).fetchone()[0]
    assert "grid capacity" in ppa
    assert "renew" not in ppa.lower(), "the release quote must not be quoted as renewable"


def test_ai_ready_marketing_does_not_change_workload_status():
    e = eng()
    for name in ("dayone-kabil-batam", "dayone-ndp-batam"):
        pk = case_pk(name)
        rows = e.conn.execute(
            "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='IS_AI_WORKLOAD'",
            (pk,)).fetchall()
        assert rows and all("NOT INFERABLE" in r[0] for r in rows), name


def test_gds_relationship_claim_is_contested_not_resolved():
    e = eng()
    rows = e.conn.execute(
        """SELECT DISTINCT c.object_literal FROM claims c
           JOIN entities e ON e.entity_pk=c.subject_pk
           WHERE c.predicate='HAS_GDS_RELATIONSHIP_CLAIM' AND e.name='dayone'""").fetchall()
    assert rows
    lit = rows[0][0]
    assert "EVOLVING/CONTESTED" in lit and "international unit" in lit
    assert "NOT established" in lit or "NOT established." in lit


def test_identity_limitation_pt_digitalland_recorded():
    e = eng()
    row = e.conn.execute(
        """SELECT c.object_literal FROM claims c
           JOIN entities e ON e.entity_pk=c.subject_pk
           WHERE c.predicate='HAS_IDENTITY_LIMITATION' AND e.name='dayone'""").fetchone()
    assert row and "PT Digitalland Service One" in row[0] and "NOT established" in row[0]


def test_access_failures_recorded():
    e = eng()
    st = dict(e.conn.execute("SELECT access_status, COUNT(*) FROM sources GROUP BY 1").fetchall())
    assert st.get("missing", 0) >= 3, "newsroom 404s must be recorded as missing"


def test_all_verbatim_quotes_verified():
    e = eng()
    bad = e.conn.execute(
        """SELECT o.quote FROM observations o
           WHERE o.evidence_kind='verbatim' AND o.verified_against_raw != 1
           AND o.obs_pk IN (SELECT observation_pk FROM claims WHERE review_status='machine_extracted')
           AND o.extractor_version = (SELECT MAX(extractor_version) FROM observations)
           AND o.obs_pk IN (SELECT observation_pk FROM claims
             WHERE ingested_run = (SELECT MAX(ingested_run) FROM claims
               WHERE subject_pk = (SELECT subject_pk FROM claims c2
                 JOIN observations o2 ON o2.obs_pk = claims.observation_pk
                 WHERE o2.obs_pk = o.obs_pk)))"""
    ).fetchall()
    assert not bad, bad


def test_dossier_grain_and_falsifications():
    d = json.loads((FINDINGS / "dayone_batam_investigation.json").read_text())
    assert "NDP" in d["grain_discipline"]["A_ndp"] and "Kabil" in d["grain_discipline"]["B_kabil"]
    hyps = {f["hypothesis"]: f["verdict"] for f in d["falsification_attempts"]}
    assert len(hyps) == 4
    assert any("FALSIFIED" in v for v in hyps.values())
    assert any("NOT ESTABLISHED" in v and "renewable" in h.lower()
               for h, v in hyps.items() if "renewable" in h.lower())
    assert any("NOT ESTABLISHED" in v and "GDS" in h for h, v in hyps.items())


def test_source_snapshots_retained_and_checksummed():
    e = eng()
    rows = e.conn.execute(
        "SELECT snapshot_path, raw_checksum FROM sources WHERE source_ref LIKE '%dayonedc%' "
        "OR source_ref LIKE '%dayone-secures%' OR source_ref LIKE '%inks-450mw%'").fetchall()
    assert len(rows) == 3
    for snap, ck in rows:
        assert file_sha256(Path(snap)) == ck


# ---------- supervisor source audit (UOB primary release) ----------

def test_uob_primary_release_ingested_and_verified():
    e = eng()
    row = e.conn.execute(
        "SELECT raw_checksum, snapshot_path, raw_retention FROM sources WHERE source_ref LIKE '%uobgroup%'").fetchone()
    assert row and row[2] == "snapshot_retained"
    assert file_sha256(Path(row[1])) == row[0]
    bad = e.conn.execute(
        "SELECT COUNT(*) FROM observations o JOIN sources s ON s.source_pk=o.source_pk "
        "WHERE s.source_ref LIKE '%uobgroup%' AND o.evidence_kind='verbatim' "
        "AND o.verified_against_raw != 1").fetchone()[0]
    assert bad == 0


def test_uob_primary_claims_present():
    e = eng()
    ndp = case_pk("dayone-ndp-batam")
    lits = {r[0] for r in e.conn.execute(
        "SELECT DISTINCT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_FINANCING'",
        (ndp,))}
    assert any("PRIMARY BANK RELEASE" in x for x in lits), lits
    alloc = e.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_PROCEEDS_ALLOCATION'",
        (ndp,)).fetchone()[0]
    assert "three data centres" in alloc and "does not mention Kabil" in alloc


def test_ndp_schedule_distinguishes_target_from_status():
    e = eng()
    ndp = case_pk("dayone-ndp-batam")
    row = e.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_SUPPLY_SCHEDULE' "
        "AND object_literal LIKE '%UNVERIFIED%'", (ndp,)).fetchone()
    assert row and "Upon completion by end-2025" in row[0]


def test_ndp_ai_deployment_claim_is_company_reported():
    e = eng()
    ndp = case_pk("dayone-ndp-batam")
    row = e.conn.execute(
        """SELECT c.object_literal, o.quote FROM claims c
           JOIN observations o ON o.obs_pk=c.observation_pk
           WHERE c.subject_pk=? AND c.predicate='HAS_COMPANY_AI_DEPLOYMENT_CLAIM'""",
        (ndp,)).fetchone()
    assert row, "company AI deployment claim present"
    assert "company-reported" in row[0] and "NOT verified specific workloads" in row[0]
    assert "already supports advanced AI infrastructure deployments" in row[1]


def test_no_falsified_verdict_for_present_supply_or_kabil_financing():
    d = json.loads((FINDINGS / "dayone_batam_investigation.json").read_text())
    for f in d["falsification_attempts"]:
        if "power is already being delivered" in f["hypothesis"]:
            assert "DOWNGRADED" in f["verdict"] and "UNVERIFIED" in f["verdict"]
            # 'FALSIFIED' may appear only inside the quoted prior assertion
            assert "FALSIFIED by a phased" not in f["verdict"]
        if "$412M loan finances the Kabil campus" in f["hypothesis"]:
            assert "NOT SUPPORTED" in f["verdict"]
            assert "overstated as FALSIFIED" in f["verdict"]  # quoted correction
            assert "ZERO Kabil mentions" in f["result"]


def test_correction_record_claim_present():
    e = eng()
    kab = case_pk("dayone-kabil-batam")
    row = e.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='CORRECTION_RECORD'",
        (kab,)).fetchone()
    assert row and "Supervisor source audit 2026-10-31" in row[0]
    assert "DOWNGRADED" in row[0] and "company-reported claim" in row[0]


def test_jv_and_ina_context_recorded():
    e = eng()
    row = e.conn.execute(
        "SELECT object_literal FROM claims WHERE predicate='HAS_JOINT_VENTURE_CLAIM'").fetchone()
    assert row and "NOT stated" in row[0]
    ina = e.conn.execute(
        "SELECT object_literal FROM claims WHERE predicate='HAS_INSTITUTIONAL_CONTEXT' "
        "AND object_literal LIKE '%first investment%'").fetchone()
    assert ina
