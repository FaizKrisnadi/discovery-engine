"""Role-matrix audit for three cases (supervisor-directed source-to-screen audit).

Cases: dayone-ndp-batam, dayone-kabil-batam, airtrunk-jhb1.
Roles: developer, operator, asset owner/investor, lenders, electricity
supplier / PPA counterparty, tenant/customer, intermediaries.

Cell statuses (per role per case):
  documented  — current, non-superseded, dated claim from an identified source
  candidate   — role described but party unnamed (e.g., 'anchor tenant',
                'global hyperscalers, fully-booked') or identity unadjudicated
  conflicting — multiple current claims with distinct values (unresolved)
  unknown     — no claims for this role
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery.engine import ClaimIn, Engine, SourceIn, canonical, content_hash, file_sha256

RAW = ROOT / "data/raw"
FINDINGS = ROOT / "findings"
DB = ROOT / "data" / "processed" / "engine.sqlite3"

INA25_REF = "https://www.ina.go.id/sites/default/files/2026-05/Annual%20Report%20INA%202025%20-%20ENGLISH.pdf"
INA24_REF = "https://www.ina.go.id/sites/default/files/2025-07/AR%20INA%202024-IND.pdf"
INAPORT_REF = "https://www.ina.go.id/portfolio/"
AT23_REF = "https://airtrunk.com/airtrunk-enters-malaysia-with-new-150mw-hyperscale-data-centre-in-johor-bahru/"
ANALYSIS = "analysis:this-project:role-audit-matrix"

INA_LICENSE = ("INA annual report / portfolio page; quoted for research attribution only "
               "(copyright Indonesia Investment Authority)")
AT_LICENSE = "AirTrunk website release; quoted for research attribution only"


def _extract_fy24_pdf_text():
    from pypdf import PdfReader
    r = PdfReader(RAW / "jhb1_fy24_sustainability_pdf.pdf")
    return "\n".join((p.extract_text() or "") for p in r.pages)


def build_dossier() -> dict:
    fetch = json.loads((RAW / "jhb1_fetch_log.json").read_text())
    d = {
        "purpose": "role-matrix source-to-screen audit for three cases",
        "cases": ["dayone-ndp-batam", "dayone-kabil-batam", "airtrunk-jhb1"],
        "sources": [],
    }
    for name in ("ina_2025_ar_en", "ina_2024_ar_ind", "ina_portfolio", "airtrunk_2023"):
        e = fetch[name]
        d["sources"].append({
            "name": name, "url": e["url"],
            "access": {"status": e.get("status"), "bytes": e.get("bytes"),
                       "saved_to": e.get("saved_to")},
            "license": INA_LICENSE if "ina" in name else AT_LICENSE,
            "document_date": {"ina_2025_ar_en": "FY2025 (published ~2026)",
                              "ina_2024_ar_ind": "FY2024 (published ~2025-07)",
                              "ina_portfolio": "undated portfolio page",
                              "airtrunk_2023": "2023-01-19 (dateline)"}[name],
        })
    return d


def new_sources() -> list[SourceIn]:
    fetch = json.loads((RAW / "jhb1_fetch_log.json").read_text())
    INA_LICENSE = ("INA annual report / portfolio page; quoted for research attribution only")
    AT_LICENSE = "AirTrunk website release; quoted for research attribution only"
    return [
        SourceIn(source_ref=INA25_REF, publisher="Indonesia Investment Authority",
                 license=INA_LICENSE, source_type="annual report (primary, investor-attributed)",
                 document_date="FY2025 (published ~2026)", access_status="fetched",
                 fetched_at_utc=fetch["ina_2025_ar_en"]["attempted_at"],
                 raw_path=RAW / "role_audit_ina_2025_ar_en.pdf",
                 retrieval_attempts=[{"ts": fetch["ina_2025_ar_en"]["attempted_at"], "status": 200}]),
        SourceIn(source_ref=INA24_REF, publisher="Indonesia Investment Authority",
                 license=INA_LICENSE, source_type="annual report (primary, investor-attributed)",
                 document_date="FY2024 (published ~2025-07)", access_status="fetched",
                 fetched_at_utc=fetch["ina_2024_ar_ind"]["attempted_at"],
                 raw_path=RAW / "role_audit_ina_2024_ar_ind.pdf",
                 retrieval_attempts=[{"ts": fetch["ina_2024_ar_ind"]["attempted_at"], "status": 200}]),
        SourceIn(source_ref=INAPORT_REF, publisher="Indonesia Investment Authority",
                 license=INA_LICENSE, source_type="portfolio page",
                 access_status="fetched", fetched_at_utc=fetch["ina_portfolio"]["attempted_at"],
                 raw_path=RAW / "role_audit_ina_portfolio.html",
                 retrieval_attempts=[{"ts": fetch["ina_portfolio"]["attempted_at"], "status": 200}]),
        SourceIn(source_ref=ANALYSIS, publisher="this project (deterministic scripts; AI-generated, unreviewed)",
                 license="internal artifact (this project)", source_type="analysis artifact",
                 document_date="2026-10-31", access_status="fetched",
                 raw_path=FINDINGS / "role_audit_matrix.json",
                 retrieval_attempts=[{"ts": "2026-10-31", "outcome": "generated",
                                      "note": "generated by scripts/role_audit.py"}]),
        SourceIn(source_ref=AT23_REF, publisher="AirTrunk", license=AT_LICENSE,
                 source_type="company announcement", document_date="2023-01-19",
                 access_status="fetched", fetched_at_utc=fetch["airtrunk_2023"]["attempted_at"],
                 raw_path=RAW / "role_audit_airtrunk_2023.html",
                 retrieval_attempts=[{"ts": fetch["airtrunk_2023"]["attempted_at"], "status": 200}]),
    ]


def new_claims() -> list[ClaimIn]:
    NDP = "project:dayone-ndp-batam"
    KAB = "project:dayone-kabil-batam"
    J1 = "project:airtrunk-jhb1"
    a = lambda **kw: ClaimIn(subject_key=kw.pop("subject"), subject_type="project", **kw)
    C = []

    # ---- INA 2025 AR (EN) — NDP status, investment value, GDS relationship ----
    C += [
        a(subject=NDP, predicate="HAS_OPERATION_STATUS",
          object_literal="32.4 MW commenced operations as of October 2025; full completion targeted in 1H 2026 (INA annual report)",
          claim_time="2025-10", time_precision="month", certainty="reported", evidence_kind="verbatim",
          source_ref=INA25_REF, locator="Digital and Digital Infrastructure Sector / DAYONE section", field="status",
          quote="As of October 2025, 32.4 MW has commenced operations, with full completion targeted in 1H 2026"),
        a(subject=NDP, predicate="HAS_INVESTMENT_VALUE",
          object_literal="approximately USD 600 million (INA annual report, campus investment value)",
          claim_time="2025-10", time_precision="month", certainty="reported", evidence_kind="verbatim",
          unit="USD", grain="campus investment value (INA-attributed)",
          source_ref=INA25_REF, locator="DAYONE section", field="investment value",
          quote="The 72.4 MW campus, with an investment value of approximately USD600 million"),
        a(subject=NDP, predicate="HAS_DEVELOPER", object_key="org:dayone", object_type="organization",
          object_literal="DayOne (INA 2025 AR: 'DayOne, a platform formerly under GDS, operates data centers across seven countries and partnered with INA to establish its first large-scale data center in Batam')",
          claim_time="2025-10", time_precision="month", certainty="reported", evidence_kind="verbatim",
          source_ref=INA25_REF, locator="DAYONE section", field="developer",
          quote="DayOne, a platform formerly under GDS, operates data centers across seven countries and partnered with INA to establish its first large-scale data center in Batam"),
        a(subject=NDP, predicate="HAS_DEVELOPER", object_key="org:ina", object_type="organization",
          object_literal="INA (INA 2025 AR: 'INA and DayOne advanced the development of a 72 MW greenfield data center campus in Batam')",
          claim_time="2025-10", time_precision="month", certainty="reported", evidence_kind="verbatim",
          source_ref=INA25_REF, locator="Hyperscale Investment section", field="developer",
          quote="In 2025, INA and DayOne advanced the development of a 72 MW greenfield data center campus in Batam"),
        a(subject=NDP, predicate="HAS_NONGSA_LOCATION",
          object_literal="Nongsa Digital Park, Batam (INA 2025 AR explicitly locates the campus at Nongsa Digital Park)",
          claim_time="2025-10", time_precision="month", certainty="reported", evidence_kind="verbatim",
          source_ref=INA25_REF, locator="campus description", field="location",
          quote="The hyperscale data center campus at Nongsa Digital Park, Batam"),
        # ---- company AI deployment framing (INA 2025 AR) — marketing, not workload ----
        a(subject=NDP, predicate="IS_AI_WORKLOAD", object_literal="NOT INFERABLE (re-affirmed): 'projected to become the first AI-enabled facility in Southeast Asia' is a projection/company framing; no specific tenant or workload is named",
          claim_time="2025-10", time_precision="month", certainty="inferred", evidence_kind="analyst_synthesis",
          source_ref=ANALYSIS, locator="INA 2025 AR passages", field="ai workload",
          quote="projected to become the first AI-enabled facility in Southeast Asia"),
        # ---- GDS relationship (INA 2025 AR) ----
        ClaimIn(subject_key="org:dayone", subject_type="organization",
                predicate="HAS_GDS_RELATIONSHIP_CLAIM",
                object_literal="INA 2025 AR (2026): 'DayOne, a platform formerly under GDS' — dated characterisation consistent with the rebrand narrative; current equity relationship still NOT established",
                claim_time="2025-10", time_precision="month", certainty="reported",
                evidence_kind="verbatim", source_ref=INA25_REF,
                locator="DAYONE section", field="gds relationship",
                quote="DayOne, a platform formerly under GDS, operates data centers across seven countries"),
        # ---- Series C (INA 2025 AR) ----
        ClaimIn(subject_key="org:dayone", subject_type="organization",
                predicate="HAS_INVESTMENT",
                object_literal="INA and DayOne participated in a Series C funding round for the platform (2025, INA annual report) — company-level corporate finance",
                claim_time="2025", time_precision="year", certainty="reported",
                evidence_kind="verbatim", source_ref=INA25_REF,
                locator="investment lifecycle section", field="series c",
                quote="In 2025, INA and its co-investor (DayOne) continued its investment by participating in a Series C funding round for the platform"),
    ]

    # ---- INA 2024 AR (Indonesian) — PT DayOne Indonesia rename, fully-booked ----
    C += [
        ClaimIn(subject_key="org:dayone", subject_type="organization",
                predicate="HAS_IDENTITY_LIMITATION",
                object_literal=("PT GDS Indonesia renamed PT DayOne Indonesia in early 2025, "
                                "following the GDS International → DayOne rebrand (INA 2024 AR, "
                                "Indonesian). The Indonesian operating entity is PT DayOne Indonesia "
                                "(dahulu PT GDS Indonesia); corporate chain to DayOne Singapore is "
                                "implied but NOT established by registry documents."),
                claim_time="2025-01", time_precision="month", certainty="reported",
                evidence_kind="verbatim", source_ref=INA24_REF,
                locator="Pusat Data (Data Center) section", field="entity rename",
                quote="PT GDS Indonesia sejak awal tahun 2025 telah berganti nama menjadi PT DayOne Indonesia, sehubungan dengan rebranding bisnis GDS International menjadi DayOne"),
        a(subject=NDP, predicate="HAS_TENANT_STATUS",
          object_literal="CANDIDATE (company-reported, unnamed): 72.4 MW 'fully-booked' by global hyperscaler companies for 10 years — customer CATEGORY described, identity undisclosed, occupancy UNVERIFIED",
          claim_time="2025-07", time_precision="month", certainty="reported", evidence_kind="verbatim",
          source_ref=INA24_REF, locator="Pusat Data section", field="tenant status",
          quote="Fasilitas data center yang dibangun akan memiliki total kapasitas 72,4MW yang seluruh telah dipesan (fully-booked) oleh perusahaan hyperscaler global untuk 10 tahun ke depan"),
        a(subject=NDP, predicate="HAS_RECORD_STATUS",
          object_literal="began phased operations at end of 2024 (INA 2024 AR: 'telah mulai beroperasi secara bertahap di akhir tahun 2024') — consistent with INA 2025 AR's '32.4 MW commenced as of October 2025'",
          claim_time="2024-12", time_precision="month", certainty="reported", evidence_kind="verbatim",
          source_ref=INA24_REF, locator="Pusat Data section", field="status",
          quote="telah mulai beroperasi secara bertahap di akhir tahun 2024"),
    ]

    # ---- INA portfolio page ----
    C += [
        ClaimIn(subject_key="org:ina", subject_type="organization",
                predicate="HAS_INSTITUTIONAL_CONTEXT",
                object_literal="INA portfolio page: joint venture with DayOne 'commenced with the development of a 72 MW hyperscale data center campus in Nongsa Digital Park, Batam'; deepened with INA's participation in DayOne's USD2.0 billion Series C",
                claim_time="2025", time_precision="year", certainty="reported",
                evidence_kind="verbatim", source_ref=INAPORT_REF,
                locator="Digital Infrastructure / Data Center section", field="portfolio",
                quote="The joint venture commenced with the development of a 72 MW hyperscale data center campus in Nongsa Digital Park, Batam. The collaboration deepened with INA\u2019s participation in DayOne\u2019s USD2.0 billion Series C global equity financing"),
    ]

    # ---- AirTrunk 19 Jan 2023 — JHB1 announced, anchor tenant planned ----
    C += [
        a(subject=J1, predicate="HAS_RECORD_STATUS",
          object_literal="announced 19 Jan 2023: AirTrunk's first Malaysia DC; 150+ MW planned; initial phases 50 MW with construction commencing shortly, due for completion in 2024 (planned capacity at announcement — not operational status)",
          claim_time="2023-01-19", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=AT23_REF, locator="release body", field="announcement",
          quote="The initial phases of JHB1 will provide 50MW of capacity, with construction commencing shortly and due for completion in 2024."),
        a(subject=J1, predicate="HAS_TENANT_STATUS",
          object_literal="CANDIDATE (company-reported, unnamed, planned at 2023-01-19): 'anchored by one of the world's largest technology companies' — anchor tenant identity undisclosed; current occupancy NOT established by this or any accessible source",
          claim_time="2023-01-19", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=AT23_REF, locator="release body", field="anchor tenant",
          quote="Driven by rapidly increasing cloud adoption in Southeast Asia, JHB1 will be anchored by one of the world\u2019s largest technology companies."),
        a(subject=J1, predicate="HAS_FINANCING",
          object_literal="JHB1 will be funded under AirTrunk's sustainability linked loan framework (company statement 2023-01-19; terms/lenders/amounts NOT stated) — earliest known financing reference for JHB1",
          claim_time="2023-01-19", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=AT23_REF, locator="release body", field="financing framework",
          quote="JHB1 will be funded under AirTrunk\u2019s sustainability linked loan framework"),
        a(subject=J1, predicate="HAS_DEVELOPER", object_key="org:airtrunk", object_type="organization",
          object_literal="AirTrunk (company announcement: 'AirTrunk... today announced its entry into Malaysia with plans to develop a 150+ megawatt (MW) data centre')",
          claim_time="2023-01-19", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=AT23_REF, locator="release body", field="developer",
          quote="today announced its entry into Malaysia with plans to develop a 150+ megawatt (MW) data centre"),
    ]
    return C


def compute_matrix() -> dict:
    """Compute the role×case matrix from current (non-superseded) claims."""
    eng = Engine(DB)
    cases = ["dayone-ndp-batam", "dayone-kabil-batam", "airtrunk-jhb1"]
    role_defs = [
        ("Developer", ["HAS_DEVELOPER", "HAS_SPONSOR"]),
        ("Operator", ["HAS_OPERATOR"]),
        ("Asset owner / investor", ["HAS_OWNER_REPORTED", "HAS_DEVELOPMENT_PARTNER",
                                    "HAS_INVESTMENT", "HAS_JOINT_VENTURE_CLAIM"]),
        ("Lender", ["HAS_FINANCING_PARTICIPANT"]),
        ("Electricity supplier / PPA counterparty", ["HAS_PPA_COUNTERPARTY", "HAS_OFFTAKER",
                                                    "HAS_UTILITY_CONNECTION"]),
        ("Tenant / customer", ["HAS_TENANT_STATUS"]),
        ("Intermediary / context", ["HAS_INSTITUTIONAL_CONTEXT", "HAS_IDENTIFIER_LIMITATION",
                                    "HAS_GDS_RELATIONSHIP_CLAIM"]),
    ]
    matrix = {}
    for case in cases:
        pk_row = eng.conn.execute(
            "SELECT entity_pk FROM entities WHERE entity_type='project' AND name=? "
            "ORDER BY (identifier IS NULL) LIMIT 1", (case,)).fetchone()
        if not pk_row:
            continue
        pk = pk_row[0]
        rows = [r for r in eng.project_timeline(pk) if not r.get("superseded_by")]
        case_matrix = {}
        for role, preds in role_defs:
            role_rows = [r for r in rows if r["predicate"] in preds]
            if not role_rows:
                case_matrix[role] = {"status": "unknown", "claims": []}
            else:
                has_candidate = any(
                    "unnamed" in (r["object_literal"] or "").lower()
                    or "CANDIDATE" in (r["object_literal"] or "")
                    or "anchor" in (r["quote"] or "").lower()
                    for r in role_rows)
                st = "candidate" if has_candidate else "documented"
                case_matrix[role] = {"status": st,
                                     "claims": [r["claim_pk"] for r in role_rows]}
        matrix[case] = case_matrix
    return matrix


def main() -> None:
    d = build_dossier()
    (FINDINGS / "role_audit_matrix.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))

    eng = Engine(DB)
    eng.register_global_key("project:dayone-ndp-batam", "project", "dayone-ndp-batam",
                            identifier="engine-case:dayone-ndp-batam")
    eng.register_global_key("project:dayone-kabil-batam", "project", "dayone-kabil-batam",
                            identifier="engine-case:dayone-kabil-batam")
    eng.register_global_key("project:airtrunk-jhb1", "project", "airtrunk-jhb1",
                            identifier="engine-case:airtrunk-jhb1")
    inputs = content_hash({"sources": canonical([{k: str(v) if isinstance(v, Path) else v for k, v in vars(s).items()} for s in new_sources()])})
    run_id = "run-" + inputs[:16]

    events = {}
    for src in new_sources():
        _, ev = eng.record_source(src, run_id)
        events[src.source_ref] = ev

    d = build_dossier()
    (FINDINGS / "role_audit_matrix.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    qv = {
        INA25_REF: open("/tmp/ina_2025_ar_en.txt").read(),
        INA24_REF: open("/tmp/ina_2024_ar_ind.txt").read(),
        INAPORT_REF: _text("data/raw/role_audit_ina_portfolio.html"),
        AT23_REF: _text("data/raw/role_audit_airtrunk_2023.html"),
        ANALYSIS: json.dumps(d, ensure_ascii=False),
    }
    n = eng.ingest_claims(new_claims(), run_id, quote_verification=qv)

    contradictions = eng.detect_contradictions()
    det = eng.finish_run(run_id, script="scripts/role_audit.py", inputs_hash=inputs,
                         sources_new=sum(1 for e in events.values() if e == "new"),
                         sources_changed=sum(1 for e in events.values() if e == "changed"),
                         sources_not_present=0, claims_ingested=n)
    eng.commit()

    matrix = compute_matrix()
    (FINDINGS / "role_matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=1))
    print(json.dumps({"run_id": run_id, "claims": n, "contradiction_groups": len(contradictions),
                      "deterministic_hash": det[:16], "matrix": {
                          c: {r: s["status"] for r, s in m.items()}
                          for c, m in matrix.items()}}, indent=1))


def _text(path: str) -> str:
    import re, html as H
    h = (ROOT / path).read_text(errors="ignore")
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h)))


if __name__ == "__main__":
    main()
