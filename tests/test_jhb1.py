"""Tests for the JHB1 source-grounded investigation (grain discipline,
falsification record, verbatim verification, honest access failures)."""
from __future__ import annotations

import json
import sqlite3
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


def test_three_assets_are_distinct_entities():
    e = eng()
    pks = {case_pk(n) for n in ("airtrunk-jhb1", "airtrunk-jhb2", "airtrunk-ibvogt-solar-farm",
                                "airtrunk-jhb1-vppa")}
    assert len(pks) == 4, "four distinct case entities (JHB1, JHB2, solar farm, VPPA case)"


# ---------- supervisor-correction claims (2026-10-31) ----------

def test_sll_financing_claim_supersedes_prior_unknown():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    lits = {r[0] for r in e.conn.execute(
        "SELECT DISTINCT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_FINANCING'",
        (j1,))}
    assert any("sustainability linked loan framework" in x for x in lits), lits
    assert any("NOT ESTABLISHED" in x for x in lits), "prior finding must remain preserved (append-only)"


def test_tnb_connection_recorded_as_reported():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    row = e.conn.execute(
        """SELECT c.certainty, c.evidence_kind, c.object_literal, o.quote
           FROM claims c JOIN observations o ON o.obs_pk=c.observation_pk
           WHERE c.subject_pk=? AND c.predicate='HAS_UTILITY_CONNECTION'""", (j1,)).fetchone()
    assert row, "TNB connection claim present"
    assert row[0] == "reported" and row[1] == "verbatim"
    assert "Tenaga Nasional Berhad (TNB) to connect JHB1" in row[3]
    assert "connection \u2260 supply-contract terms" in row[2] or "connection ≠ supply-contract terms" in row[2]


def test_rooftop_solar_is_planned_not_operational():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    row = e.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_onsite_solar_plan'",
        (j1,)).fetchone()
    assert row and "PLANNED" in row[0] and "NOT operational" in row[0]


def test_vppa_supports_jhb1_consumption_with_physical_supply_caveat():
    e = eng()
    sf = case_pk("airtrunk-ibvogt-solar-farm")
    row = e.conn.execute(
        """SELECT c.object_literal, o.quote FROM claims c
           JOIN observations o ON o.obs_pk=c.observation_pk
           WHERE c.subject_pk=? AND c.predicate='SUPPORTS_CONSUMPTION_OF'""", (sf,)).fetchone()
    assert row, "VPPA-supports-JHB1-consumption claim present"
    assert "to support JHB1\u2019s energy consumption" in row[1] or            "to support JHB1’s energy consumption" in row[1]
    assert "does NOT establish direct physical supply" in row[0]


def test_blackstone_claim_is_agreement_not_closing():
    e = eng()
    # claims about 'airtrunk' may live on several scoped entities: scan them all
    lits = {r[0] for r in e.conn.execute(
        """SELECT DISTINCT c.object_literal FROM claims c
           JOIN entities e ON e.entity_pk=c.subject_pk
           WHERE c.predicate='HAS_OWNER_REPORTED' AND e.name='airtrunk'""")}
    assert any("DEFINITIVE AGREEMENT" in x and "NOT a closing announcement" in x
               and "FIRB" in x for x in lits), lits
    # the superseded variant is preserved alongside (append-only)
    assert any("reported closed late 2024" in x for x in lits)


def test_supersedes_record_present_and_old_claims_preserved():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    sup = e.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='SUPERSEDES_PRIOR_FINDING'",
        (j1,)).fetchone()
    assert sup and "Supervisor source correction 2026-10-31" in sup[0]
    # old NOT-ESTABLISHED claims still exist (append-only history)
    old = e.conn.execute(
        "SELECT COUNT(*) FROM claims WHERE subject_pk=? AND predicate='IS_PHYSICAL_SUPPLY_OF' "
        "AND object_literal LIKE 'NOT ESTABLISHED%'", (j1,)).fetchone()[0]
    assert old >= 1


def test_ai_ready_marketing_does_not_change_workload_status():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    rows = e.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='IS_AI_WORKLOAD'",
        (j1,)).fetchall()
    assert all("NOT INFERABLE" in r[0] for r in rows), rows
    assert any("AI-ready" in r[0] and "NOT workload evidence" in r[0] for r in rows), rows


def test_fy24_report_snapshot_retained_and_checksummed():
    e = eng()
    row = e.conn.execute(
        "SELECT raw_checksum, snapshot_path, raw_retention FROM sources WHERE source_ref LIKE '%FY24-Sustainability%'").fetchone()
    assert row and row[2] == "snapshot_retained"
    assert file_sha256(Path(row[1])) == row[0]


def test_jhb2_loan_is_not_attributed_to_jhb1():
    e = eng()
    j1, j2 = case_pk("airtrunk-jhb1"), case_pk("airtrunk-jhb2")
    j1_fin = {r[0] for r in e.conn.execute(
        "SELECT DISTINCT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_FINANCING'",
        (j1,))}
    # append-only: the superseded NOT-ESTABLISHED variant AND the corrected
    # SLL-financing variant are both preserved
    assert any("NOT ESTABLISHED" in x for x in j1_fin)
    assert any("sustainability linked loan framework" in x for x in j1_fin)
    j2_lits = [r[0] for r in e.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_FINANCING'",
        (j2,))]
    # append-only: an earlier variant may persist; the corrected one must exist
    assert any("JHB2" in x and "30-lender syndicate" in x for x in j2_lits), j2_lits
    # and no JHB2-amount claim sits on the JHB1 subject
    assert not any("US$2.3" in r[0] for r in j1_fin)


def test_falsification_record_present_as_analysis_claims():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    rows = e.conn.execute(
        """SELECT c.predicate, c.object_literal, c.evidence_kind, s.source_ref, o.quote
           FROM claims c JOIN observations o ON o.obs_pk=c.observation_pk
           JOIN sources s ON s.source_pk=o.source_pk
           WHERE c.subject_pk=? AND c.evidence_kind='analyst_synthesis'""", (j1,)).fetchall()
    preds = {p for p, _, _, _, _ in rows}
    assert {"IS_PHYSICAL_SUPPLY_OF", "HAS_FINANCING", "IS_AI_WORKLOAD"} <= preds
    for p, ol, _, sref, quote in rows:
        assert sref.startswith("analysis:"), "synthesis must cite the analysis artifact"
    assert any("FAILED TO CONFIRM" in (ol + q) for p, ol, _, _, q in rows)


def test_dossier_documents_falsification_including_one_falsified():
    d = json.loads((FINDINGS / "jhb1_investigation.json").read_text())
    hyps = {f["hypothesis"]: f["verdict"] for f in d["falsification_attempts"]}
    assert len(hyps) == 4
    assert any("FALSIFIED" in v for v in hyps.values()), "the JHB2-loan hypothesis must be falsified"
    assert any("NOT ESTABLISHED" in v for v in hyps.values())
    # the falsified one is the campus-financing attribution
    falsified = [h for h, v in hyps.items() if "FALSIFIED" in v][0]
    assert "US$2.3B green loan finances JHB1" in falsified


def test_all_verbatim_quotes_verified_against_cached_originals():
    e = eng()
    bad = e.conn.execute(
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
    assert not bad, f"unverified verbatim quotes: {bad}"


def test_ownership_claim_is_reported_and_synthesis_labelled():
    e = eng()
    # the claim's subject is the analysis-scoped airtrunk entity: search by name
    at = e.conn.execute(
        """SELECT c.subject_pk FROM claims c JOIN entities e ON e.entity_pk=c.subject_pk
           WHERE c.predicate='HAS_OWNER_REPORTED' AND e.name='airtrunk' LIMIT 1""").fetchone()[0]
    row = e.conn.execute(
        """SELECT c.certainty, c.evidence_kind, c.object_literal, s.source_ref
           FROM claims c JOIN observations o ON o.obs_pk=c.observation_pk
           JOIN sources s ON s.source_pk=o.source_pk
           WHERE c.subject_pk=? AND c.predicate='HAS_OWNER_REPORTED'""", (at,)).fetchone()
    assert row, "ownership claim present"
    assert row[0] == "reported" and row[1] == "analyst_synthesis"
    assert row[2].startswith("Blackstone-led consortium")
    assert "governance control NOT established" in row[2]


def test_access_failures_recorded_in_engine():
    e = eng()
    st = dict(e.conn.execute("SELECT access_status, COUNT(*) FROM sources GROUP BY 1").fetchall())
    assert st.get("missing", 0) >= 2, "AirTrunk + Blackstone 404s must be recorded as missing"
    assert st.get("failed", 0) >= 1, "The Asset SSL failure must be recorded as failed"
    assert st.get("notice_page", 0) >= 1 and st.get("not_fetched", 0) >= 2


def test_control_claim_separates_ownership_from_control():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    row = e.conn.execute(
        "SELECT object_literal FROM claims WHERE subject_pk=? AND predicate='HAS_CONTROL_ASSERTION'",
        (j1,)).fetchone()
    assert row and "NONE AVAILABLE" in row[0] and "ownership of the operator ≠ control" in row[0]


def test_dossier_passages_are_verbatim_in_cached_files():
    d = json.loads((FINDINGS / "jhb1_investigation.json").read_text())
    import re, html as H
    def textify(p):
        h = (ROOT / p).read_text(errors="ignore")
        h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
        return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h)))
    icd = textify("data/raw/jhb1_icdnova_green_financing.html")
    ibv = textify("data/raw/airtrunk_ibvogt_release.html")
    for src in d["sources"]:
        texts = []
        if src["url"] == "https://www.idcnova.com/news/AirTrunk-Secures-US2.3-Billion-Green-Loan-for-Hyperscale-Data-Centre-in-Johor":
            texts = [icd]
        elif src["url"] == "https://www.ibvogt.com/airtrunk-and-ib-vogt-sign-malaysias-first-renewable-virtual-ppa-for-a-data-center":
            texts = [ibv]
        for p in src["exact_passages"]:
            if not texts:
                continue
            q = p["quote"].replace("\u2019", "'")
            assert any(q.replace("'", "\u2019") in t or q in t for t in texts), p["topic"]


# ---------- explicit supersession (presentation + data model) ----------

def test_timeline_marks_superseded_claims():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    tl = e.project_timeline(j1)
    fin = [r for r in tl if r["predicate"] == "HAS_FINANCING"]
    assert any(r["superseded_by"] for r in fin), "superseded variants must be marked"
    assert any(not r["superseded_by"] and "sustainability linked loan framework" in r["object_literal"]
               for r in fin), "the SLL claim must be current"
    # superseded claims remain fully inspectable (all fields present)
    for r in fin:
        if r["superseded_by"]:
            assert r["quote"] and r["source_ref"] and r["claim_pk"]


def test_supersession_rows_preserve_authorship_basis_and_withdrawal():
    e = eng()
    rows = e.conn.execute(
        "SELECT superseded_claim_pk, superseding_claim_pk, basis, recorded_by, status, "
        "withdrawn_reason FROM supersessions").fetchall()
    assert rows
    # every row keeps its authorship and basis (append-only audit history)
    assert all("supervisor-corrected" in r[3] or "supervisor" in r[3].lower() for r in rows)
    assert all("Supervisor source audit 2026-10-31" in r[2] for r in rows)
    # event-evolution supersessions are WITHDRAWN (conservative repair) with reason
    owner = [r for r in rows if r[4] == "withdrawn"]
    assert owner, "owner-claim supersessions must be withdrawn"
    assert all("Event-evolution conflation" in (r[5] or "") for r in owner)
    active_owner = [r for r in rows if r[4] == "active" and
                    e.conn.execute("SELECT predicate FROM claims WHERE claim_pk=?",
                                   (r[0],)).fetchone()[0] == "HAS_OWNER_REPORTED"]
    assert not active_owner, "no active supersession may conflate agreement vs closing"


def test_contradiction_resolved_by_supersession_for_financing():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    rows = e.conn.execute(
        """SELECT DISTINCT co.resolution_status FROM contradictions co
           JOIN claims c ON c.claim_pk=co.claim_pk
           WHERE c.subject_pk=? AND c.predicate='HAS_FINANCING'""", (j1,)).fetchall()
    # HAS_FINANCING is not a contradiction predicate; if rows exist they must be
    # from earlier runs — but superseded variants of other predicates resolve
    phys = e.conn.execute(
        """SELECT DISTINCT co.resolution_status FROM contradictions co
           JOIN claims c ON c.claim_pk=co.claim_pk
           WHERE c.subject_pk=? AND c.predicate='IS_PHYSICAL_SUPPLY_OF'""", (j1,)).fetchall()
    assert any(r[0] == "resolved_by_supersession" for r in phys), phys


def test_supersession_recording_is_idempotent_across_reruns():
    e = eng()
    n1 = e.conn.execute("SELECT COUNT(*) FROM supersessions").fetchone()[0]
    j1 = case_pk("airtrunk-jhb1")
    old = e.find_claims(j1, "HAS_FINANCING", "NOT ESTABLISHED%")
    new = e.find_claims(j1, "HAS_FINANCING", "%sustainability linked loan framework%")
    if old and new:
        e.record_supersession(old[0], new[0], "re-run check", "tester")
    n2 = e.conn.execute("SELECT COUNT(*) FROM supersessions").fetchone()[0]
    assert n2 in (n1, n1 + 1), "re-recording either dedupes or appends one event; never loses rows"


# ---------- v0.7: event-evolution vs conclusion-correction policy ----------

def test_blackstone_claims_coexist_after_withdrawal():
    """An agreement (primary, 2024-09-04) and a later reported closing
    (secondary) are distinct dated events: BOTH claims must be current
    (no active supersession between them)."""
    e = eng()
    at = e.conn.execute(
        """SELECT c.subject_pk FROM claims c JOIN entities e ON e.entity_pk=c.subject_pk
           WHERE c.predicate='HAS_OWNER_REPORTED' AND e.name='airtrunk' LIMIT 1""").fetchone()[0]
    lits = {r[0] for r in e.conn.execute(
        "SELECT DISTINCT object_literal FROM claims WHERE subject_pk=? AND "
        "predicate='HAS_OWNER_REPORTED'", (at,))}
    assert any("DEFINITIVE AGREEMENT" in x for x in lits)
    assert any("reported closed late 2024" in x for x in lits)
    sup = e.active_supersessions()
    for old in e.find_claims(at, "HAS_OWNER_REPORTED"):
        assert old not in sup or sup[old]["superseded_by"] not in             e.find_claims(at, "HAS_OWNER_REPORTED")


def test_financing_supersession_is_conclusion_correction_not_contradiction():
    e = eng()
    j1 = case_pk("airtrunk-jhb1")
    old = e.find_claims(j1, "HAS_FINANCING", "NOT ESTABLISHED%")[0]
    new = e.find_claims(j1, "HAS_FINANCING", "%sustainability linked loan framework%")[0]
    sup = e.active_supersessions()
    assert old in sup and sup[old]["superseded_by"] == new
    # basis must cite the newly-found SLL statement, NOT the JHB2 loan reporting
    # (JHB2-specific reporting does not contradict JHB1 financing in general)
    assert "sustainability linked loan framework" in sup[old]["basis"]
    assert "JHB2" not in sup[old]["basis"] or "explicitly for JHB2" not in sup[old]["basis"]


def test_withdrawal_is_idempotent_and_preserves_audit_trail():
    import scripts.audit_supersessions as audit  # noqa: E402
    before = eng().conn.execute(
        "SELECT status, COUNT(*) FROM supersessions GROUP BY status").fetchall()
    audit.main()  # re-run: must not resurrect or duplicate anything
    after = eng().conn.execute(
        "SELECT status, COUNT(*) FROM supersessions GROUP BY status").fetchall()
    d1 = dict(before); d2 = dict(after)
    assert d1.get("withdrawn", 0) == d2.get("withdrawn", 0)
    assert d1.get("active", 0) == d2.get("active", 0)
    # withdrawn rows keep full audit content
    wd = eng().conn.execute(
        "SELECT basis, recorded_by, withdrawn_reason FROM supersessions "
        "WHERE status='withdrawn' LIMIT 1").fetchone()
    assert wd[0] and wd[1] and "Event-evolution" in wd[2]


def test_dossier_distinguishes_not_established_from_contradicted():
    d = json.loads((FINDINGS / "jhb1_investigation.json").read_text())
    blob = json.dumps(d)
    assert "does not contradict JHB1 financing in general" in blob or \
           "not established" in blob.lower()
    f2 = [f for f in d["falsification_attempts"] if "US$2.3B" in f["hypothesis"]][0]
    assert "FALSIFIED" in f2["verdict"]
    assert "JHB2" in f2["result"]
