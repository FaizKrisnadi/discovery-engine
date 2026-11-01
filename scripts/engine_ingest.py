"""Ingest existing evidence into the evidence engine (reproducible, no network).

Integrity rules implemented here (supervisor review 2026-10-30):
- Every verbatim quote is substring-verified against the cached original
  (PDF text / HTML text / dataset row / artifact JSON) and the verification
  result is stored on the observation.
- Analyst inferences (renewable-procurement status, physical-supply status,
  AI-workload status, grid-context subtotal, identifier limitations) are
  attributed to recorded analysis artifacts (source_ref starts with
  "analysis:this-project:..."), NEVER to fetched sources, and are phrased as
  bounded-search findings whose absence claims do not extend beyond the
  documented search.
- Source versions hash RAW bytes / raw dataset rows, not derived annotations.
  Retrieval attempts are recorded per source; access_status distinguishes
  fetched / notice_page / missing / failed / not_fetched.
- Entities carry identifiers where they exist; name-only entities are
  provisional_name_only and never silently merged (homonym guard).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery.engine import (ClaimIn, Engine, SourceIn, canonical, content_hash)

FINDINGS = ROOT / "findings"
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
DB = PROC / "engine.sqlite3"

AIDDATA_LICENSE = "ODC-By 1.0 (stated in the License sheet of the dataset workbook, verified 2026-10-30)"
IJGLOBAL_LICENSE = "IJGlobal deal sheet reprint; quoted for research attribution only (copyright IJGlobal)"
PRN_LICENSE = "PR Newswire release text; quoted for research attribution only"
IBVOGT_LICENSE = "ib vogt website press release; quoted for research attribution only"
GEM_LICENSE = "CC BY 4.0 (globalenergymonitor.org/creative-commons-license/, verified 2026-10-30)"
ANALYST_BYLINE = "this project (deterministic scripts; AI-generated, unreviewed)"

IJ_REF = "https://www.ijglobal.com/data/Transaction/69665/gds-nusajaya-tech-park-data-centre-phase-1-699mw-green-loan-2023"
PRN_REF = "https://www.prnewswire.com/apac/news-releases/gds-secures-myr1-27-billion-syndicated-green-financing-to-complete-the-next-phase-of-nusajaya-tech-park-data-center-campus-development-302009836.html"
IBV_REF = "https://www.ibvogt.com/airtrunk-and-ib-vogt-sign-malaysias-first-renewable-virtual-ppa-for-a-data-center"
AID_REF = "aiddata:clg-lmic-v1.0:record-106768"
ANALYSIS_SCAN = "analysis:this-project:ai-infra-re-scan"
ANALYSIS_DOSSIER = "analysis:this-project:gds106768-dossier"


def html_unescape(s: str) -> str:
    import html as _h
    return _h.unescape(s)


def _html_text(path: Path) -> str:
    h = path.read_text(errors="ignore")
    txt = re.sub(r"\s+", " ", html_unescape(re.sub(r"<(script|style)[^>]*>.*?</\1>", " ",
                                                   h, flags=re.S | re.I)))
    return re.sub(r"<[^>]+>", " ", txt)


_ROW_CACHE = PROC / "aiddata_106768_row.json"


def aiddata_row() -> dict:
    """Raw record values. Cached content-identically keyed to the workbook's
    mtime+size so repeat ingests skip the 28 MB parse without changing output."""
    xlsx = RAW / "AidDatas_CLG_LMIC_Dataset_v1.0.xlsx"
    stat = f"{xlsx.stat().st_mtime_ns}:{xlsx.stat().st_size}"
    if _ROW_CACHE.exists():
        cached = json.loads(_ROW_CACHE.read_text())
        if cached.get("_workbook_stat") == stat:
            cached.pop("_workbook_stat")
            return cached
    df = pd.read_excel(xlsx, sheet_name="CLG-LMIC 1.0_Records")
    r = df[df["AidData_Record_ID"] == 106768].iloc[0]
    row = {"record_id": 106768, "Title": str(r["Title"]), "Status": str(r["Status"]),
           "Commitment_Year": int(r["Commitment_Year"]),
           "Amount_Nominal_USD": float(r["Amount_Nominal_USD"]),
           "Funding_Agencies": str(r["Funding_Agencies"]),
           "Direct_Receiving_Agencies": str(r["Direct_Receiving_Agencies"]),
           "All_Source_URLs": str(r["All_Source_URLs"])}
    _ROW_CACHE.write_text(json.dumps({"_workbook_stat": stat, **row}, ensure_ascii=False))
    return row


def quote_texts() -> dict[str, str]:
    """Cached original text per source_ref, used to verify verbatim quotes."""
    from pypdf import PdfReader
    r = PdfReader(RAW / "gds_nusajaya_ijglobal.pdf")
    ij = "\n".join((p.extract_text() or "") for p in r.pages)
    return {
        IJ_REF: ij,
        PRN_REF: _html_text(RAW / "gds106768_prnewswire.html"),
        IBV_REF: _html_text(RAW / "airtrunk_ibvogt_release.html"),
        AID_REF: canonical(aiddata_row()),
        ANALYSIS_DOSSIER: (FINDINGS / "gds106768_dossier.json").read_text(),
        ANALYSIS_SCAN: (FINDINGS / "ai_infra_re_scan.json").read_text(),
        "gleif:lookup-log-2026-10-30": (PROC / "gleif_enrichment.json").read_text(),
        "gem:ownership-api:malaysia-assets-2026-10-29": (RAW / "gem_malaysia_assets.json").read_text(),
    }


def gds_fetch_log() -> dict:
    return json.loads((RAW / "gds106768_fetch_log.json").read_text())


def airtrunk_fetch_log() -> dict:
    return json.loads((RAW / "airtrunk_fetch_log.json").read_text())


def sources() -> list[SourceIn]:
    row = aiddata_row()
    gfl, afl = gds_fetch_log(), airtrunk_fetch_log()
    return [
        SourceIn(source_ref=AID_REF, publisher="AidData (CLG-LMIC v1.0)", license=AIDDATA_LICENSE,
                 source_type="dataset record", document_date="2023", access_status="fetched",
                 fetched_at_utc=gfl["ijglobal_dropbox_pdf"]["attempted_at"],
                 raw_path=RAW / "AidDatas_CLG_LMIC_Dataset_v1.0.xlsx", raw_row=row,
                 retrieval_attempts=[{"ts": gfl["ijglobal_dropbox_pdf"]["attempted_at"],
                                      "note": "zip downloaded 2026-10-30 05:46 WIB, sha256 recorded"}]),
        SourceIn(source_ref=IJ_REF, publisher="IJGlobal", license=IJGLOBAL_LICENSE,
                 source_type="deal sheet reprint (media report)", document_date="2023-12-10",
                 access_status="fetched", fetched_at_utc=gfl["ijglobal_dropbox_pdf"]["attempted_at"],
                 raw_path=RAW / "gds_nusajaya_ijglobal.pdf",
                 retrieval_attempts=[{"ts": gfl["ijglobal_dropbox_pdf"]["attempted_at"],
                                      "via": "public Dropbox share link (dl=1)", "status": 200}]),
        SourceIn(source_ref=PRN_REF, publisher="PR Newswire (provided by GDS)", license=PRN_LICENSE,
                 source_type="company/banks' announcement", document_date="2023-12-08",
                 access_status="fetched", fetched_at_utc=gfl["prnewswire"]["attempted_at"],
                 raw_path=RAW / "gds106768_prnewswire.html",
                 retrieval_attempts=[{"ts": gfl["prnewswire"]["attempted_at"], "status": 200}]),
        SourceIn(source_ref="https://www.gds-services.com/en/newsshow_82.html",
                 publisher="GDS Holdings", license="company website; quoted for research attribution only",
                 source_type="company announcement (official source per AidData)",
                 access_status="notice_page", fetched_at_utc=gfl["gds_official"]["attempted_at"],
                 raw_path=RAW / "gds106768_gds_official.html",
                 retrieval_attempts=[{"ts": gfl["gds_official"]["attempted_at"], "status": 200,
                                      "note": "HTTP 200 but body is a site-notice template; article no longer served"}]),
        SourceIn(source_ref="https://www.google.com/maps/place/GDS+International+Nusajaya+Data+Center/@1.4337777,103.5973506,18z/",
                 publisher="Google Maps", license="Google ToS; URL/coordinates recorded only",
                 source_type="location reference", access_status="not_fetched",
                 raw_row={"coordinates_stated": "1.4337777,103.5973506",
                          "note": "JavaScript application; not machine-fetchable; not verified"},
                 retrieval_attempts=[]),
        SourceIn(source_ref="gleif:lookup-log-2026-10-30", publisher="GLEIF API (targeted lookups)",
                 license="GLEIF data under CC BY 4.0", source_type="dataset locator (lookup log)",
                 document_date="2026-10-30", access_status="fetched",
                 raw_path=PROC / "gleif_enrichment.json",
                 retrieval_attempts=[{"ts": "2026-10-30", "note": "15 legalName queries, cached"}]),
        SourceIn(source_ref=IBV_REF, publisher="ib vogt", license=IBVOGT_LICENSE,
                 source_type="company press release (co-announcement)", document_date="2024-03-05",
                 access_status="fetched", fetched_at_utc=afl["ibvogt_release"]["attempted_at"],
                 raw_path=RAW / "airtrunk_ibvogt_release.html",
                 retrieval_attempts=[{"ts": afl["ibvogt_release"]["attempted_at"], "status": 200}]),
        SourceIn(source_ref="https://www.airtrunk.com/news/airtrunk-signs-malaysias-first-data-centre-renewable-vppa/",
                 publisher="AirTrunk", license="company website; quoted for research attribution only",
                 source_type="company announcement (guessed URL)", access_status="missing",
                 fetched_at_utc=afl["airtrunk_news"]["attempted_at"],
                 raw_path=RAW / "airtrunk_airtrunk_news.html",
                 retrieval_attempts=[{"ts": afl["airtrunk_news"]["attempted_at"], "status": 404,
                                      "note": "guessed slug; own announcement not located in JS-paginated news index"}]),
        SourceIn(source_ref="websearch:transcript-2026-10-30:airtrunk-ibvogt-started",
                 publisher="Asian Power (via WebSearch transcript)",
                 license="search-result summary; article not fetched",
                 source_type="media report (unfetched)", document_date="2026-07 (per search summary)",
                 access_status="not_fetched",
                 raw_row={"claim_in_summary": "AirTrunk, ib vogt start 30-MW solar project to power Malaysia data centre (Jul 2026)",
                          "note": "URL not available in transcript"}),
        SourceIn(source_ref="gem:ownership-api:malaysia-assets-2026-10-29",
                 publisher="GEM Ownership Tracing API", license=GEM_LICENSE,
                 source_type="API snapshot (dataset locator)", document_date="2026-10-29",
                 access_status="fetched", raw_path=RAW / "gem_malaysia_assets.json",
                 retrieval_attempts=[{"ts": "2026-10-29/30", "note": "4 paged /assets requests + /metadata; cached in data/http_cache, logged"}]),
        SourceIn(source_ref=ANALYSIS_SCAN, publisher=ANALYST_BYLINE,
                 license="internal artifact (this project)", source_type="analysis artifact",
                 document_date="2026-10-30", access_status="fetched",
                 raw_path=FINDINGS / "ai_infra_re_scan.json"),
        SourceIn(source_ref=ANALYSIS_DOSSIER, publisher=ANALYST_BYLINE,
                 license="internal artifact (this project)", source_type="analysis artifact",
                 document_date="2026-10-30", access_status="fetched",
                 raw_path=FINDINGS / "gds106768_dossier.json"),
    ]


def gds_claims() -> list[ClaimIn]:
    row = aiddata_row()
    P = "gds-nusajaya-ntp1"
    a = lambda **kw: ClaimIn(subject_key=f"project:{P}", subject_type="project", **kw)
    return [
        a(predicate="HAS_RECORD_STATUS", object_literal=f"{row['Status']} (AidData status category; definition ambiguous)",
          claim_time="2023", time_precision="year", certainty="documented", evidence_kind="verbatim",
          source_ref=AID_REF, locator="field: Status", field="Status", quote=row["Status"],
          grain="dataset status category (AidData)"),
        a(predicate="HAS_FINANCING_EVENT", object_literal=row["Title"],
          claim_time="2023", time_precision="year", certainty="documented", evidence_kind="verbatim",
          source_ref=AID_REF, locator="field: Title", field="Title", quote=row["Title"],
          grain="dataset record title"),
        a(predicate="HAS_TOTAL_FACILITY_AMOUNT", object_literal="MYR 1,270.00m (USD 272.12m)",
          claim_time="2023-12-08", time_precision="day", certainty="documented", evidence_kind="verbatim",
          unit="USD", grain="total facility amount (deal sheet)",
          source_ref=IJ_REF, locator="TRANSACTION DATA / Transaction Key Facts", field="amount",
          quote="Amount: MYR 1,270.00m (USD 272.12m)"),
        a(predicate="HAS_RECORD_STATUS", object_literal="Current Stage: Pre-construction (construction stage, IJGlobal data field)",
          claim_time="2023-12-10", time_precision="day", certainty="documented", evidence_kind="verbatim",
          source_ref=IJ_REF, locator="Projects block: Current Stage", field="status",
          quote="Current Stage: Pre-construction", grain="construction stage (IJGlobal data field)"),
        a(predicate="HAS_RECORD_STATUS", object_literal="Financial close (deal stage, 8 Dec 2023)",
          claim_time="2023-12-08", time_precision="day", certainty="documented", evidence_kind="verbatim",
          source_ref=IJ_REF, locator="Transaction Key Facts", field="stage",
          quote="Stage: Financial close", grain="deal stage (IJGlobal)"),
        a(predicate="HAS_CAPACITY_CLAIM", object_literal="54.00 MW (IJGlobal Capacity field)",
          claim_time="2023-12-10", time_precision="day", certainty="documented", evidence_kind="verbatim",
          unit="MW", grain="listed plant capacity (IJGlobal data field; rating basis not stated)",
          source_ref=IJ_REF, locator="Projects block", field="capacity",
          quote="Capacity: 54.00 MW"),
        a(predicate="HAS_CAPACITY_CLAIM", object_literal="IT power capacity 69.9 MW (company-stated)",
          claim_time="2023-12-08", time_precision="day", certainty="reported", evidence_kind="verbatim",
          unit="MW", grain="IT power capacity (company announcement)",
          source_ref=PRN_REF, locator="release body", field="capacity",
          quote="boasts an IT power capacity of 69.9 MW"),
        a(predicate="HAS_FINANCING_PARTICIPANT", object_key="org:bank-of-china-malaysia", object_type="organization",
          object_literal="Bond Arranger, MYR 317.50m (USD 68.03m)", claim_time="2023-12-08",
          time_precision="day", certainty="documented", evidence_kind="verbatim",
          unit="USD", grain="arranger tranche (deal sheet)",
          source_ref=IJ_REF, locator="Tranche Roles", field="arranger",
          quote="Bond Arranger Bank of China MYR 317.50m (USD 68.03m)"),
        a(predicate="HAS_FINANCING_PARTICIPANT", object_key="org:ocbc-bank", object_type="organization",
          object_literal="Bond Arranger, MYR 317.50m (USD 68.03m)", claim_time="2023-12-08",
          time_precision="day", certainty="documented", evidence_kind="verbatim",
          unit="USD", grain="arranger tranche (deal sheet)",
          source_ref=IJ_REF, locator="Tranche Roles", field="arranger",
          quote="Bond Arranger OCBC Bank MYR 317.50m (USD 68.03m)"),
        a(predicate="HAS_FINANCING_PARTICIPANT", object_key="org:standard-chartered", object_type="organization",
          object_literal="Bond Arranger, MYR 317.50m (USD 68.03m); also ESG Coordinator", claim_time="2023-12-08",
          time_precision="day", certainty="documented", evidence_kind="verbatim",
          unit="USD", grain="arranger tranche (deal sheet)",
          source_ref=IJ_REF, locator="Tranche Roles / Other Roles", field="arranger",
          quote="Bond Arranger Standard Chartered Bank MYR 317.50m (USD 68.03m)"),
        a(predicate="HAS_FINANCING_PARTICIPANT", object_key="org:united-overseas-bank", object_type="organization",
          object_literal="Bond Arranger, MYR 317.50m (USD 68.03m); also ESG Coordinator", claim_time="2023-12-08",
          time_precision="day", certainty="documented", evidence_kind="verbatim",
          unit="USD", grain="arranger tranche (deal sheet)",
          source_ref=IJ_REF, locator="Tranche Roles / Other Roles", field="arranger",
          quote="Bond Arranger United Overseas Bank MYR 317.50m (USD 68.03m)"),
        a(predicate="HAS_GREEN_LABEL", object_literal="Green Loan designation (participant-asserted; no framework or second-party opinion among accessible sources)",
          claim_time="2023-12-10", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=IJ_REF, locator="transaction title", field="green label",
          quote="GDS Nusajaya Tech Park Data Centre Phase 1 (69.9MW) Green Loan 2023",
          grain="financing label (not an energy attribute)"),
        a(predicate="HAS_USE_OF_PROCEEDS", object_literal="complete the development of NTP Data Center Campus Plot 1 (NTP1) in Johor, Malaysia",
          claim_time="2023-12-08", time_precision="day", certainty="documented", evidence_kind="verbatim",
          source_ref=PRN_REF, locator="release body", field="use of proceeds",
          quote="Proceeds from the loan will be used to complete the development of Nusajaya Tech Park (NTP) Data Center Campus Plot 1 in Johor, Malaysia"),
        a(predicate="HAS_RENEWABLE_TARGET", object_literal="aspiration: carbon neutrality + 100% renewable energy by 2030 (quoted by OCBC executive; a stated target, not current procurement)",
          claim_time="2023-12-08", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=PRN_REF, locator="OCBC quote", field="renewable target",
          quote="its aspiration of becoming the first data center operator to achieve carbon neutrality in this region, with 100% use of renewable energy by 2030"),
        a(predicate="LOCATED_IN", object_literal="Johor, Malaysia",
          claim_time="2023-12-10", time_precision="day", certainty="documented", evidence_kind="verbatim",
          source_ref=IJ_REF, locator="Deal Timeline", field="location",
          quote="The 54MW data centre is located in Johor, Malaysia"),
        a(predicate="HAS_SPONSOR", object_key="org:gds-holdings", object_type="organization",
          claim_time="2023-12-10", time_precision="day", certainty="documented", evidence_kind="verbatim",
          source_ref=IJ_REF, locator="Equity Tranche Roles", field="sponsor",
          quote="Sponsor GDS Holdings 100"),
        # analyst synthesis: cited to analysis artifacts, bounded-search wording
        a(predicate="RENEWABLE_PROCUREMENT_STATUS",
          object_literal=("not surfaced within the bounded search documented in "
                          "findings/gds106768_dossier.json (4 linked sources inspected, 2026-10-30); "
                          "absence is not established beyond that search"),
          claim_time=None, time_precision="unknown", certainty="inferred",
          evidence_kind="analyst_synthesis",
          source_ref=ANALYSIS_DOSSIER, locator="unknowns[1]", field="renewable procurement",
          quote="Any actual renewable-energy procurement by the facility (REC, PPA, on-site solar): no evidence either way."),
        a(predicate="HAS_IDENTIFIER_LIMITATION",
          object_literal=("facility agreement not accessible (AidData Original_Agreement_URL empty); "
                          "no Green Loan Framework or second-party opinion among accessible sources"),
          claim_time=None, time_precision="unknown", certainty="inferred", evidence_kind="analyst_synthesis",
          source_ref=ANALYSIS_DOSSIER, locator="unknowns[0]", field="documentation gap",
          quote="Whether a Green Loan Framework / second-party opinion exists for this facility (not among accessible sources)."),
        ClaimIn(subject_key="org:bank-of-china-malaysia", subject_type="organization",
                predicate="HAS_IDENTIFIER_LIMITATION",
                object_literal=("name-only identity: 'Bank of China (Malaysia) Berhad' is a branch/"
                                "subsidiary of Bank of China Limited and DISTINCT from the HQ; no "
                                "registry identifier adjudicated in this project"),
                certainty="inferred", review_status="machine_extracted", evidence_kind="analyst_synthesis",
                source_ref=ANALYSIS_SCAN, locator="gap_register gleif limitation", field="identity",
                quote="name-collision trap: China Development Industrial Bank (TW) is not China Development Bank"),
    ]


def airtrunk_claims() -> list[ClaimIn]:
    P = "airtrunk-jhb1-vppa"
    a = lambda **kw: ClaimIn(subject_key=f"project:{P}", subject_type="project", **kw)
    return [
        a(predicate="HAS_VPPA_SIGNED", object_literal="AirTrunk (offtaker) x ib vogt: first data-centre renewable VPPA under Malaysia's CGPP",
          claim_time="2024-03-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=IBV_REF, locator="release body", field="vppa",
          quote="have signed the first data centre renewable energy Virtual Power Purchase Agreement (VPPA) under Malaysia\u2019s Corporate Green Power Programme"),
        a(predicate="HAS_OFFTAKER", object_key="org:airtrunk", object_type="organization",
          claim_time="2024-03-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=IBV_REF, locator="release body", field="offtaker",
          quote="AirTrunk, as the offtaker, will procure renewable energy from the 29.99MW solar farm that ib vogt is currently developing under the CGPP"),
        a(predicate="HAS_GENERATOR_DEVELOPER", object_key="org:ib-vogt", object_type="organization",
          claim_time="2024-03-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=IBV_REF, locator="release body", field="developer",
          quote="the 29.99MW solar farm that ib vogt is currently developing under the CGPP"),
        a(predicate="HAS_CAPACITY_CLAIM", object_literal="29.99 MW solar farm (VPPA capacity)",
          claim_time="2024-03-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          unit="MW", grain="solar farm capacity under the VPPA",
          source_ref=IBV_REF, locator="release body", field="capacity",
          quote="the 29.99MW solar farm"),
        a(predicate="HAS_CAPACITY_CLAIM", object_literal="150 MW AirTrunk JHB1 data centre (company-stated)",
          claim_time="2024-03-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          unit="MW", grain="data-centre building capacity (CTO quote)",
          source_ref=IBV_REF, locator="CTO quote", field="capacity",
          quote="our 150MW AirTrunk JHB1 data centre"),
        a(predicate="UNDER_POLICY_PROGRAMME", object_literal="Malaysia CGPP (Suruhanjaya Tenaga); 800 MW solar quota; 30 MW max per developer with secured offtaker",
          claim_time="2024-03-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=IBV_REF, locator="release body", field="programme",
          quote="A quota of 800 megawatts (MW) of solar energy generation capacity is allocated to the programme and developers can apply for a maximum capacity of 30MW with a secured offtaker"),
        a(predicate="HAS_CONSTRUCTION_SCHEDULE", object_literal="solar farm construction scheduled mid-2024",
          claim_time="2024-03-05", time_precision="month", certainty="reported", evidence_kind="verbatim",
          source_ref=IBV_REF, locator="release body", field="schedule",
          quote="Construction is scheduled to begin in mid-2024"),
        a(predicate="HAS_OPERATION_STATUS", object_literal="reported started (Jul 2026, Asian Power via search transcript) — UNFETCHED, no URL; not verified",
          claim_time="2026-07", time_precision="month", certainty="reported", evidence_kind="paraphrase",
          source_ref="websearch:transcript-2026-10-30:airtrunk-ibvogt-started",
          locator="WebSearch transcript 2026-10-30", field="operation status",
          quote="AirTrunk, ib vogt start 30-MW solar project to power Malaysia data centre (as summarised in the search transcript; article not fetched)"),
        a(predicate="IS_PHYSICAL_SUPPLY_OF",
          object_literal=("NOT ESTABLISHED: a VPPA is a financial contract for differences; no "
                          "inspected source states that the solar farm physically supplies JHB1"),
          claim_time=None, time_precision="unknown", certainty="inferred", evidence_kind="analyst_synthesis",
          source_ref=ANALYSIS_SCAN, locator="exploratory_example.non_claims (engine adaptation)",
          field="physical supply",
          quote="No claim of physical supply from any plant"),
        a(predicate="IS_AI_WORKLOAD",
          object_literal=("NOT INFERABLE: no tenant/workload information in any source; a data-centre "
                          "announcement does not evidence AI workloads"),
          claim_time=None, time_precision="unknown", certainty="inferred", evidence_kind="analyst_synthesis",
          source_ref=ANALYSIS_SCAN, locator="supervisory guardrail (engine adaptation)",
          field="ai workload",
          quote="do not conflate general data centres with proven AI workloads"),
    ]


def gem_context_claims() -> list[ClaimIn]:
    scan = json.loads((FINDINGS / "ai_infra_re_scan.json").read_text())
    ctx = scan["gem_supply_context"]
    return [ClaimIn(
        subject_key="asset:grid:peninsular-malaysia", subject_type="asset",
        predicate="HAS_GEM_LISTED_OPERATING_SUBTOTAL",
        object_literal=json.dumps(ctx["peninsular_malaysia_gem_listed_operating_mw_subtotal"], sort_keys=True) +
                       f"; unassigned {json.dumps(ctx['unassigned_state_gem_listed_operating_mw'], sort_keys=True)}; "
                       "INCOMPLETE subtotal of API-listed units (analyst computation)",
        claim_time="2026-10-29", time_precision="day", certainty="inferred",
        evidence_kind="analyst_synthesis", unit="MW",
        grain="unit-level MW sums computed by this project from GEM API unit records",
        source_ref=ANALYSIS_SCAN, locator="gem_supply_context", field="capacity subtotal",
        quote="A subtotal of GEM-API-LISTED operating generation units (unit-level MW sums) in Peninsular Malaysia after state-name normalization")]


def main() -> None:
    eng = Engine(DB)
    # engine-case working identifiers (disclosed: internal keys, not registry ids)
    eng.register_global_key("project:gds-nusajaya-ntp1", "project", "gds-nusajaya-ntp1",
                            identifier="engine-case:gds-nusajaya-ntp1")
    eng.register_global_key("project:airtrunk-jhb1-vppa", "project", "airtrunk-jhb1-vppa",
                            identifier="engine-case:airtrunk-jhb1-vppa")
    eng.register_global_key("asset:grid:peninsular-malaysia", "asset", "grid:peninsular-malaysia",
                            identifier="engine-case:grid-peninsular-malaysia")
    inputs = content_hash({
        "aiddata_row": canonical(aiddata_row()),
        "gds_fetch_log": (RAW / "gds106768_fetch_log.json").read_text(),
        "airtrunk_fetch_log": (RAW / "airtrunk_fetch_log.json").read_text(),
        "gem_malaysia": (RAW / "gem_malaysia_assets.json").read_text(),
        "scan": (FINDINGS / "ai_infra_re_scan.json").read_text(),
        "dossier": (FINDINGS / "gds106768_dossier.json").read_text(),
        "gleif": (PROC / "gleif_enrichment.json").read_text(),
        "raw_file_sizes": {str(p): p.stat().st_size for p in [
            RAW / "gds_nusajaya_ijglobal.pdf", RAW / "gds106768_prnewswire.html",
            RAW / "gds106768_gds_official.html", RAW / "airtrunk_ibvogt_release.html",
            RAW / "airtrunk_airtrunk_news.html", RAW / "gem_malaysia_assets.json"]},
    })
    run_id = "run-" + inputs[:16]

    events = {}
    for src in sources():
        _, ev = eng.record_source(src, run_id)
        events[src.source_ref] = ev
    seen = set(events)
    not_present = eng.not_present_sources(seen)

    qv = quote_texts()
    n = eng.ingest_claims(gds_claims(), run_id, quote_verification=qv)
    n += eng.ingest_claims(airtrunk_claims(), run_id, quote_verification=qv)
    n += eng.ingest_claims(gem_context_claims(), run_id, quote_verification=qv)

    # identity: orgs have NO verified registry ids in hand, so every mention is
    # source-scoped (two sources mentioning the same name yield two entities
    # until explicitly adjudicated). Aliases attach to the scoped entity.
    gds_ij = eng.latest_source_pk(IJ_REF)
    gds_pk = eng.ensure_entity("organization", "gds-holdings", scope=IJ_REF)
    eng.add_alias("gds", gds_pk, "ambiguous")
    eng.add_alias("dayone", gds_pk, "ambiguous")   # GDS-affiliated operator — NOT merged
    eng.add_alias("gds holdings limited", gds_pk, "canonical")
    at_pk = eng.ensure_entity("organization", "airtrunk", scope=IBV_REF)
    eng.add_alias("airtrunk pte ltd", at_pk, "ambiguous")
    # the same-name org mentioned by the analysis artifact is a DISTINCT scoped
    # entity until adjudicated; we record the pair as explicitly unadjudicated
    boc_ij = eng.ensure_entity("organization", "bank-of-china-malaysia", scope=IJ_REF)
    boc_an = eng.ensure_entity("organization", "bank-of-china-malaysia", scope=ANALYSIS_SCAN)
    if boc_ij != boc_an:
        eng.adjudicate(boc_ij, boc_an, "unadjudicated",
                       decided_by="this project (AI-generated, unreviewed; no registry id available)")
    # name-homonym demonstration required by audit: same name, two sources
    acme1 = eng.ensure_entity("organization", "acme-power", scope=IJ_REF)
    acme2 = eng.ensure_entity("organization", "acme-power", scope=IBV_REF)
    assert acme1 != acme2, "same name from distinct sources must NOT silently merge"

    contradictions = eng.detect_contradictions()
    det = eng.finish_run(run_id, script="scripts/engine_ingest.py", inputs_hash=inputs,
                         sources_new=sum(1 for e in events.values() if e == "new"),
                         sources_changed=sum(1 for e in events.values() if e == "changed"),
                         sources_not_present=len(not_present), claims_ingested=n)
    eng.commit()
    print(json.dumps({
        "run_id": run_id,
        "sources": {k[:60]: v for k, v in sorted(events.items())},
        "not_present": not_present, "claims": n,
        "contradiction_groups": len(contradictions),
        "deterministic_hash": det}, indent=1))


if __name__ == "__main__":
    main()
