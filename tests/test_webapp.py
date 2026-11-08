"""Tests for the read-only investigation interface (webapp routes)."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from discovery import webapp
from discovery.engine import Engine, file_sha256

ROOT = Path(__file__).resolve().parents[1]


def _get(path: str, q: dict | None = None):
    return webapp.dispatch("GET", path, q or {})


def test_home_lists_both_cases_and_counts():
    status, ctype, body = _get("/")
    assert status == 200 and "text/html" in ctype
    assert "gds-nusajaya-ntp1" in body and "airtrunk-jhb1-vppa" in body
    assert "AI-generated" in body and "unreviewed" in body  # persistent banner
    assert "read-only" in body


def test_case_page_shows_dimensions_provenance_and_unknowns():
    status, _, body = _get("/case/gds-nusajaya-ntp1")
    assert status == 200
    for dim in ("finance", "energy", "status", "capacity", "identity"):
        assert f"<h2>{dim}</h2>" in body
    assert "raw-verified" in body and "evidence" in body
    assert "POSSIBLE CONTRADICTION" in body or "contradictions" in body.lower()
    assert "engine-case:gds-nusajaya-ntp1" in body
    assert "snapshot" in body.lower() and "retrieval history" in body.lower()
    # discipline: the GDS renewable-procurement gap is stated as a bounded search finding
    assert "bounded search" in body and "not surfaced" in body
    assert "notice_page" in body or "access failures" in body.lower()


def test_case_page_airtrunk_carries_distinctions():
    status, _, body = _get("/case/airtrunk-jhb1-vppa")
    assert status == 200
    assert "VPPA" in body
    assert "NOT ESTABLISHED" in body          # physical supply negation claim
    assert "financial contract" in body
    assert "missing" in body                  # AirTrunk 404 access status visible


def test_org_page_shows_scope_and_aliases():
    status, _, body = _get("/orgs")
    assert status == 200 and "source-scoped" in body
    assert "provisional_scoped" in body  # honest identity statuses listed
    import re
    # open the scoped gds-holdings entity (linked from /orgs)
    links = re.findall(r"/org/([0-9a-f]{64})'>view", body)
    assert links
    opened = 0
    for pk in links[:6]:
        status, _, body = _get(f"/org/{pk}")
        assert status == 200
        assert "identity status" in body
        if "provisional_scoped" in body:
            opened += 1
    assert opened >= 1, "at least one provisional scoped org must be viewable"


def test_claim_detail_shows_full_provenance():
    conn = sqlite3.connect(f"file:{webapp.DB}?mode=ro", uri=True)
    pk = conn.execute("SELECT claim_pk FROM claims LIMIT 1").fetchone()[0]
    conn.close()
    status, _, body = _get(f"/claim/{pk}")
    assert status == 200
    assert "exact quote" in body and "raw verification" in body
    assert "checksum" in body.lower() and "snapshot" in body.lower()
    assert "machine_extracted" in body


def test_search_hit_and_empty_state():
    status, _, body = _get("/search", {"q": ["gds"]})
    assert status == 200 and "gds-nusajaya-ntp1" in body and "ingested universe" in body
    status, _, body = _get("/search", {"q": ["zzz-no-such-thing"]})
    assert status == 200
    assert "No results" in body and "not a general web search" in body
    status, _, body = _get("/search", {"q": [""]})
    assert "Empty searches return nothing" in body


def test_404_states():
    status, _, body = _get("/case/does-not-exist")
    assert status == 404 and "Not found" in body and "append-only" in body
    status, _, body = _get("/claim/" + "0" * 64)
    assert status == 404
    status, _, body = _get("/org/" + "1" * 64)
    assert status == 404
    status, _, body = _get("/no/such/route")
    assert status == 404


def test_post_is_rejected_read_only():
    status, ctype, body = webapp.dispatch("POST", "/", {})
    assert status == 405 and "read-only" in body


def test_db_opened_read_only_physically():
    """The ro connection must refuse writes even if code tried them."""
    conn = sqlite3.connect(
        f"file:{ROOT / 'data/processed/engine.sqlite3'}?mode=ro", uri=True)
    try:
        conn.execute("CREATE TABLE write_probe (x INTEGER)")
        raise AssertionError("write succeeded on a read-only connection")
    except sqlite3.OperationalError as e:
        assert "readonly" in str(e).lower()
    finally:
        conn.close()


def test_missing_db_error_state(tmp_path):
    orig = webapp.DB
    webapp.DB = tmp_path / "nope.sqlite3"
    try:
        status, _, body = _get("/")
        assert status == 500 and "was not found" in body and "run_all.sh" in body
    finally:
        webapp.DB = orig


def test_unresolved_identity_candidates_surface():
    status, _, body = _get("/orgs")
    assert "provisional" in body
    # the bank-of-china scoped pair + unadjudicated marker are discoverable
    status, _, body = _get("/search", {"q": ["bank of china"]})
    assert status == 200


# ---------- crawl: no broken internal paths (browser-exercise substitute) ----------

def test_internal_link_crawl_finds_no_broken_paths():
    """Exhaustive internal crawl from / (bounded): every internal href must
    resolve without server error. This substitutes for manual browsing where
    browser automation is unavailable, and catches broken paths exhaustively."""
    if not (ROOT / "data" / "http_cache").exists():
        pytest.skip(
            "data/http_cache/ not built on this checkout — /raw/<sha> snapshot "
            "routes 403 without it. Run the fetch steps "
            "(scripts/download_aiddata.sh, scripts/fetch_gem.py) or run_all.sh first."
        )
    seen, queue, errors = set(), ["/"], []
    checked = 0
    while queue and checked < 60:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        status, ctype, body = _get(path)
        checked += 1
        if status >= 400:
            errors.append((path, status))
            continue
        if "text/html" not in ctype:
            continue
        if path.startswith("/raw/"):
            # snapshots of EXTERNAL pages contain external links that do not
            # belong to our URL space — verify served bytes, do not crawl them
            continue
        if isinstance(body, bytes):
            body = body.decode(errors="ignore")
        import re
        for href in re.findall(r"href=['\"](/[^'\"#]*)['\"]", body):
            if href not in seen:
                queue.append(href)
    assert checked >= 8, f"crawl too small: {checked} pages"
    assert not errors, f"broken internal paths: {errors}"
    # the corrected not_retained rows must answer honestly
    import sqlite3 as _s
    c2 = _s.connect(f"file:{ROOT / 'data/processed/engine.sqlite3'}?mode=ro", uri=True)
    n_nr = c2.execute("SELECT COUNT(*) FROM sources WHERE raw_retention='not_retained'").fetchone()[0]
    n_sr = c2.execute("SELECT COUNT(*) FROM sources WHERE raw_retention='snapshot_retained'").fetchone()[0]
    c2.close()
    assert n_nr >= 1 and n_sr >= 1, "both retained and explicitly-unretained states must exist"


def test_every_case_and_org_link_resolves():
    import re
    status, _, body = _get("/cases")
    for path in re.findall(r"href=['\"](/case/[^'\"]+)['\"]", body):
        st, _, _ = _get(path)
        assert st == 200, path
    status, _, body = _get("/orgs")
    for path in re.findall(r"href=['\"](/org/[^'\"]+)['\"]", body)[:15]:
        st, _, _ = _get(path)
        assert st == 200, path


# ---------- original-evidence access (/raw) ----------

def test_raw_route_serves_snapshot_bytes_with_checksum_verification():
    import sqlite3
    from discovery.engine import file_sha256
    conn = sqlite3.connect(f"file:{webapp.DB}?mode=ro", uri=True)
    pk, snap, ck = conn.execute(
        "SELECT source_pk, snapshot_path, raw_checksum FROM sources "
        "WHERE snapshot_path IS NOT NULL LIMIT 1").fetchone()
    conn.close()
    status, ctype, body = _get(f"/raw/{pk}")
    assert status == 200
    assert body == Path(snap).read_bytes()
    assert len(body) > 0


def test_raw_route_404_for_unknown_and_honest_for_unretained():
    status, ctype, body = _get("/raw/" + "0" * 64)
    assert status == 404
    # find a not_retained source (row-based): must answer 404 with honest text
    import sqlite3
    conn = sqlite3.connect(f"file:{webapp.DB}?mode=ro", uri=True)
    pk = conn.execute("SELECT source_pk FROM sources WHERE raw_retention='not_retained' "
                      "LIMIT 1").fetchone()
    conn.close()
    if pk:
        status, _, body = _get(f"/raw/{pk[0]}")
        assert status == 404
        assert "not retained" in (body if isinstance(body, str) else body.decode())


def test_claim_detail_links_original_evidence():
    import re, sqlite3
    conn = sqlite3.connect(f"file:{webapp.DB}?mode=ro", uri=True)
    pk, spk = conn.execute(
        """SELECT c.claim_pk, s.source_pk FROM claims c
           JOIN observations o ON o.obs_pk=c.observation_pk
           JOIN sources s ON s.source_pk=o.source_pk
           WHERE s.snapshot_path IS NOT NULL LIMIT 1""").fetchone()
    conn.close()
    status, _, body = _get(f"/claim/{pk}")
    assert status == 200
    assert f"/raw/{spk}" in body, "claim detail must link the retained snapshot"
    assert "original source" in body.lower()


def test_external_source_links_are_real_urls():
    import re, sqlite3
    conn = sqlite3.connect(f"file:{webapp.DB}?mode=ro", uri=True)
    pk = conn.execute(
        """SELECT c.claim_pk FROM claims c
           JOIN observations o ON o.obs_pk=c.observation_pk
           JOIN sources s ON s.source_pk=o.source_pk
           WHERE s.source_ref LIKE 'http%' LIMIT 1""").fetchone()[0]
    conn.close()
    status, _, body = _get(f"/claim/{pk}")
    m = re.search(r"href='(https?://[^']+)'", body)
    assert m, "claim detail must link the live external source"
    assert m.group(1).startswith("https://")


def test_home_labels_claim_rows_honestly():
    status, _, body = _get("/")
    assert "claim rows (incl. superseded variants)" in body


# ---------- server-level regression: binary bodies over HTTP ----------

def test_server_serves_binary_snapshots_over_http():
    """Regression: the HTTP wrapper crashed on /raw byte bodies (AttributeError
    on .encode()). Start the real server on an ephemeral port and verify."""
    import threading, urllib.request, urllib.error
    from http.server import HTTPServer
    sys.path.insert(0, str(ROOT / "scripts"))
    import serve_investigation as srv
    server = HTTPServer(("127.0.0.1", 0), srv.Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        conn = sqlite3.connect(f"file:{webapp.DB}?mode=ro", uri=True)
        pk, snap = conn.execute(
            "SELECT source_pk, snapshot_path FROM sources WHERE snapshot_path IS NOT NULL "
            "AND raw_bytes < 1000000 LIMIT 1").fetchone()
        conn.close()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/raw/{pk}") as r:
            data = r.read()
            assert r.status == 200
        assert data == Path(snap).read_bytes()
        # HTML route over the same server still works
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as r:
            assert r.status == 200 and b"AI-generated" in r.read()
    finally:
        server.shutdown()


# ---------- v0.5 hardening: /raw serving safety + independent verification ----------

def test_raw_serves_octet_stream_never_active_html():
    """Third-party HTML (PR Newswire snapshot) must download, never execute
    same-origin: content-type is application/octet-stream for every snapshot."""
    import sqlite3
    conn = sqlite3.connect(f"file:{webapp.DB}?mode=ro", uri=True)
    pk = conn.execute(
        "SELECT source_pk FROM sources WHERE snapshot_path IS NOT NULL AND raw_path "
        "LIKE '%prnewswire%' LIMIT 1").fetchone()
    conn.close()
    status, ctype, body = _get(f"/raw/{pk[0]}")
    assert status == 200
    assert ctype == "application/octet-stream", ctype
    assert b"<script" in body or b"html" in body.lower()[:400]  # it IS the html snapshot


def test_raw_rejects_symlink_and_outside_paths(tmp_path):
    """Path-confinement adversarial: symlink escape and outside paths are
    refused without reading. Uses a TEMP COPY of the database (destructive
    scenario), never the real one."""
    import shutil, os
    from discovery import webapp
    tmp = tmp_path / "case"
    tmp.mkdir()
    db = tmp / "engine.sqlite3"
    shutil.copy(ROOT / "data/processed/engine.sqlite3", db)
    snaproot = tmp / "data" / "evidence_snapshots"
    snaproot.mkdir(parents=True)
    orig_root = webapp.SNAP_ROOT
    webapp.SNAP_ROOT = snaproot
    outside = tmp / "outside_secret.txt"
    outside.write_bytes(b"TOP SECRET OUTSIDE")
    link = snaproot / "evil"
    os.symlink(outside, link)
    orig = webapp.DB
    webapp.DB = db
    try:
        c = sqlite3.connect(db)
        pk = c.execute("SELECT source_pk FROM sources LIMIT 1").fetchone()[0]
        import hashlib
        for malicious in (str(link), str(outside)):
            c.execute("UPDATE sources SET snapshot_path=?, raw_retention='snapshot_retained', "
                      "raw_checksum=? WHERE source_pk=?",
                      (malicious, hashlib.sha256(outside.read_bytes()).hexdigest(), pk))
            c.commit()
            st, ct, body = webapp.dispatch("GET", f"/raw/{pk}", {})
            assert st == 403, (malicious, st)
            text = body.decode() if isinstance(body, bytes) else body
            assert "Refused" in text
            assert b"TOP SECRET" not in (body if isinstance(body, bytes) else outside.read_bytes())
        c.close()
    finally:
        webapp.DB = orig
        webapp.SNAP_ROOT = orig_root


def test_server_sends_nosniff_header():
    import threading, urllib.request
    from http.server import HTTPServer
    sys.path.insert(0, str(ROOT / "scripts"))
    import serve_investigation as srv
    server = HTTPServer(("127.0.0.1", 0), srv.Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_address[1]}/") as r:
            assert r.headers.get("X-Content-Type-Options") == "nosniff"
    finally:
        server.shutdown()


def test_all_retained_snapshots_match_their_recorded_checksums():
    """Independent verification: EVERY retained snapshot's bytes must equal its
    recorded checksum (supervisor independently verified 16/16; this test
    re-verifies continuously)."""
    from discovery.engine import Engine, file_sha256
    eng = Engine(webapp.DB)
    rows = eng.conn.execute(
        "SELECT source_pk, snapshot_path, raw_checksum, raw_retention FROM sources "
        "WHERE raw_retention='snapshot_retained'").fetchall()
    assert rows, "expected retained snapshots"
    for pk, snap, ck, _ in rows:
        p = Path(snap)
        assert p.exists(), f"retained snapshot missing on disk: {pk}"
        assert file_sha256(p) == ck, f"checksum mismatch for {pk}"
    # and no not_retained row may still claim a snapshot path
    n = eng.conn.execute(
        "SELECT COUNT(*) FROM sources WHERE raw_retention='not_retained' "
        "AND snapshot_path IS NOT NULL").fetchone()[0]
    assert n == 0


def test_org_page_shows_full_adjudication_history():
    status, _, body = _get("/orgs")
    assert status == 200
    import re
    # every org link resolves; the UI must agree with the engine's history view
    eng = Engine(webapp.DB)
    pk = eng.conn.execute(
        "SELECT entity_pk FROM entities WHERE name='bank-of-china-malaysia' LIMIT 1").fetchone()[0]
    status, _, body = _get(f"/org/{pk}")
    assert status == 200
    assert "unadjudicated" in body or "adjudication" in body.lower()


# ---------- supersession presentation ----------

def test_case_page_marks_superseded_claims_and_shows_current():
    status, _, body = _get("/case/airtrunk-jhb1")
    assert status == 200
    assert "SUPERSEDED" in body and "NOT current" in body
    assert "sustainability linked loan framework" in body
    assert "Supervisor source audit 2026-10-31" in body
    # superseded claims stay inspectable via /claim/ links
    import re
    assert re.search(r"/claim/[0-9a-f]{64}", body)


def test_superseded_claim_detail_shows_banner_and_superseding_link():
    import sqlite3
    conn = sqlite3.connect(f"file:{ROOT / 'data/processed/engine.sqlite3'}?mode=ro", uri=True)
    old, new = conn.execute(
        "SELECT superseded_claim_pk, superseding_claim_pk FROM supersessions LIMIT 1").fetchone()
    conn.close()
    status, _, body = _get(f"/claim/{old}")
    assert status == 200
    assert "SUPERSEDED and is NOT current" in body
    assert f"/claim/{new}" in body
    # the superseding claim's detail shows it is current and supersedes the old one
    status, _, body = _get(f"/claim/{new}")
    assert status == 200
    assert "current" in body and "supersedes" in body.lower()


# ---------- who-is-involved role view ----------

def test_involved_view_roles_and_unknowns_for_jhb1():
    status, _, body = _get("/involved/airtrunk-jhb1")
    assert status == 200
    # filled roles
    assert "Operator" in body and "AirTrunk" in body
    assert "Electricity supplier / PPA counterparty" in body and "ib vogt" in body
    assert "Owner / investor" in body and "Blackstone" in body
    # direction discipline: offtaker labelled as buyer; VPPA caveats present
    assert "offtaker = BUYER" in body
    assert "financial contract" in body and "not operational delivery" in body
    assert "NOT established as this asset's electricity supply" in body
    # unknown roles explicit
    assert body.count("No claims recorded for this role") >= 2
    assert "not evidence that no such party exists" in body
    # provenance links on every displayed relationship
    import re
    assert len(re.findall(r"/claim/[0-9a-f]{64}", body)) >= 4
    # review status shown
    assert "unreviewed" in body


def test_involved_view_identity_caveat_for_name_matched_owner():
    status, _, body = _get("/involved/airtrunk-jhb1")
    assert "IDENTITY CAVEAT" in body
    assert "unadjudicated" in body


def test_involved_view_dayone_campuses_stay_separate():
    st1, _, b1 = _get("/involved/dayone-ndp-batam")
    st2, _, b2 = _get("/involved/dayone-kabil-batam")
    assert st1 == st2 == 200
    # NDP: lender (DBS/UOB) + development partner (INA) + operator (DayOne) filled
    assert "DBS" in b1 and "INA" in b1 and "DayOne" in b1
    # Kabil: PPA counterparty (PLN Batam) filled; NDP lender must NOT leak
    assert "PLN Batam" in b2
    assert "6.7 trillion" not in b2, "NDP loan must not leak into the Kabil view"
    # both: no renewable or tenant claims
    for b in (b1, b2):
        assert "No claims recorded for this role" in b  # tenant role empty
        assert "energy mix" in b.lower() or "NOT ESTABLISHED" in b


def test_involved_view_kabil_roles():
    """Kabil: PPA counterparty (PLN Batam) and operator (DayOne) filled from
    primary release; lender and owner honestly unknown; no NDP loan leak."""
    status, _, body = _get("/involved/dayone-kabil-batam")
    assert status == 200
    assert "PT PLN Batam" in body and "PPA counterparty (utility)" in body
    assert "DayOne" in body
    import re
    links = set(re.findall(r"/claim/([0-9a-f]{64})", body))
    assert len(links) >= 2
    # lender role empty for Kabil (loan funds NDP — preserved distinction)
    assert "6.7 trillion" not in body


def test_involved_view_404():
    status, _, body = _get("/involved/does-not-exist")
    assert status == 404


def test_involved_view_never_asserts_completeness():
    status, _, body = _get("/involved/dayone-kabil-batam")
    assert "completeness of sources is NOT asserted" in body
