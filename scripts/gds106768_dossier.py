"""Primary-source dossier for AidData record 106768 (GDS Nusajaya DC green loan).

Builds findings/gds106768_dossier.json from the raw files fetched on
2026-10-30 (data/raw/gds106768_fetch_log.json + saved PDF/HTML). Re-running
re-extracts quotes from the saved files; it does NOT re-fetch. Exact passages
are quoted verbatim; per-source assessments state what each supports about
facility identity, phase, loan amount, green use-of-proceeds, project status
and renewable procurement. Disagreements and unknowns stay visible.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
FINDINGS = ROOT / "findings"

AIDDATA_LICENSE = ("Open Data Commons Attribution License (ODC-By 1.0), stated in the "
                   "'License' sheet of AidDatas_CLG_LMIC_Dataset_v1.0.xlsx (verified 2026-10-30)")

SNIP = 600


def _pdf_text() -> str:
    r = PdfReader(RAW / "gds_nusajaya_ijglobal.pdf")
    return "\n".join((p.extract_text() or "") for p in r.pages)


def _html_text(path: str) -> str:
    h = (RAW / path).read_text(errors="ignore")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))


def _around(txt: str, kw: str, before: int = 150, after: int = 450) -> str:
    i = txt.find(kw)
    return txt[max(0, i - before):i + after] if i >= 0 else ""


def main() -> None:
    fetch_log = json.loads((RAW / "gds106768_fetch_log.json").read_text())
    ij = _pdf_text()
    prn = _html_text("gds106768_prnewswire.html")
    gds = _html_text("gds106768_gds_official.html")

    # access-failure test for the GDS official URL: content is a notice page
    gds_failed = "提示信息" in gds or len(gds.strip()) < 2000

    dossier = {
        "subject": {
            "aiddata_record_id": 106768,
            "aiddata_title": ("Bank of China (Malaysia) contributes to $272.12 million syndicated "
                              "green loan for Phase 1 of GDS Nusajaya Tech Park Data Center Project"),
            "aiddata_status": "Completion", "commitment_year": 2023,
            "aiddata_amount_usd": 68030000.0,
            "license": AIDDATA_LICENSE,
            "note": ("AidData row amount = BoC's tranche (68.03M); total facility USD 272.12M is "
                     "in the title/narrative. Original_Agreement_URL is empty in AidData: the "
                     "facility agreement itself is NOT among the accessible sources."),
        },
        "sources": [],
        "per_dimension_assessment": {},
        "disagreements": [],
        "unknowns": [],
        "scan_audit": {},
    }

    dossier["sources"].append({
        "name": "IJGlobal transaction sheet (reprinted PDF via AidData's public Dropbox link)",
        "url": "https://www.ijglobal.com/data/Transaction/69665/gds-nusajaya-tech-park-data-centre-phase-1-699mw-green-loan-2023",
        "accessed_via": fetch_log["ijglobal_dropbox_pdf"]["url"],
        "access": {"status": fetch_log["ijglobal_dropbox_pdf"]["status"],
                   "bytes": fetch_log["ijglobal_dropbox_pdf"]["bytes"],
                   "saved_to": "data/raw/gds_nusajaya_ijglobal.pdf"},
        "publisher": "IJGlobal (media report; AidData All_Source_Types: 'Media Report')",
        "document_date": "Last Updated 10 Dec 2023; printed 12/13/23",
        "license_note": ("IJGlobal page reprint; quotation here for research attribution only; "
                         "the underlying deal sheet is IJGlobal's copyrighted product"),
        "exact_passages": [
            {"topic": "identity/amount", "quote": "GDS Nusajaya Tech Park Data Centre Phase 1 (69.9MW) Green Loan 2023 | Last Updated 10 Dec 2023  Deal No: 69665"},
            {"topic": "amount/instrument", "quote": "Type: Debt | Amount: MYR 1,270.00m (USD 272.12m) | 08 Dec 2023 — also labelled 'Green Bond (MYR 1,270.00m (USD 272.12m))08 Dec 2023'"},
            {"topic": "tranches", "quote": "Bond Arranger Bank of China MYR 317.50m (USD 68.03m); Bond Arranger OCBC Bank MYR 317.50m (USD 68.03m); Bond Arranger Standard Chartered Bank MYR 317.50m (USD 68.03m); Bond Arranger United Overseas Bank MYR 317.50m (USD 68.03m)"},
            {"topic": "status", "quote": "Current Stage: Pre-construction ... Stage: Financial close | Financial Close: 8th December 2023 | Latest Event: Financial Close Transaction"},
            {"topic": "capacity", "quote": "Capacity: 54.00 MW ... The 54MW data centre is located in Johor, Malaysia"},
            {"topic": "classification", "quote": "Asset Type: Greenfield | Asset Sub-Type: New | Sectors: Telecoms Data Centres | Regions: Asia Pacific Malaysia | Sponsor GDS Holdings 100"},
        ],
        "supports": {
            "facility_identity": "yes (name, Johor location, sponsor GDS Holdings, Deal No 69665)",
            "phase": "yes, as a label ('Phase 1' in the transaction name)",
            "loan_amount": "yes (total MYR 1,270.00m / USD 272.12m; BoC tranche MYR 317.50m / USD 68.03m)",
            "green_use_of_proceeds": "label only ('Green Loan'/'Green Bond' title and type fields; the sheet contains no use-of-proceeds breakdown)",
            "project_status": "deal-stage ('Financial close', 8 Dec 2023) AND construction-stage ('Pre-construction') — both quoted; sheet last updated 10 Dec 2023 (stale)",
            "renewable_procurement": "no evidence (no energy-procurement field appears in the sheet)",
        },
    })

    dossier["sources"].append({
        "name": "PR Newswire company/banks' announcement (provided by GDS)",
        "url": fetch_log["prnewswire"]["url"],
        "access": {"status": fetch_log["prnewswire"]["status"],
                   "bytes": fetch_log["prnewswire"]["bytes"],
                   "saved_to": "data/raw/gds106768_prnewswire.html"},
        "publisher": "PR Newswire (release distributed for GDS; AidData type: 'Media Report')",
        "document_date": "08 Dec, 2023, 14:55 CST (dateline on page)",
        "license_note": "press-release text is copyrighted; quotation here for research attribution only",
        "exact_passages": [
            {"topic": "use of proceeds",
             "quote": "Proceeds from the loan will be used to complete the development of Nusajaya Tech Park (NTP) Data Center Campus Plot 1 in Johor, Malaysia."},
            {"topic": "capacity",
             "quote": "The Phase 1 of the GDS NTP campus covers a total net floor area of 30,312 square meters and boasts an IT power capacity of 69.9 MW."},
            {"topic": "green roles",
             "quote": "UOB Malaysia serves as the Sole Coordinator and jointly acts as Green Loan Coordinator with Standard Chartered Bank (Singapore) Limited for this transaction."},
            {"topic": "marketing claim",
             "quote": "with their support, these green loans will fuel our business with green energy (William Huang, Chairman and CEO of GDS — promotional language, not a procurement fact)"},
            {"topic": "renewable target",
             "quote": "its aspiration of becoming the first data center operator to achieve carbon neutrality in this region, with 100% use of renewable energy by 2030 (Tan Ai Chin, MD, OCBC Bank (Malaysia) Berhad — a stated ASPIRATION/target, not current procurement)"},
            {"topic": "efficiency measures",
             "quote": "notably the utilization of prefabricated infrastructure and liquid-cooling solutions (efficiency measures; not renewable-energy procurement)"},
        ],
        "supports": {
            "facility_identity": "yes (NTP Data Center Campus Plot 1 (NTP1), Johor)",
            "phase": "yes ('Phase 1', NTP1, 14-month delivery timeframe stated as future)",
            "loan_amount": "yes (MYR 1.27 billion headline; consistent with IJGlobal)",
            "green_use_of_proceeds": "proceeds purpose stated (complete development of Plot 1); 'green' designation asserted by participants; NO Green Loan Framework or second-party opinion among the sources",
            "project_status": "announcement-stage as of 8 Dec 2023 (delivery framed as future)",
            "renewable_procurement": "NO actual procurement evidenced; only a 2030 aspiration quoted by a bank executive and marketing language by GDS's CEO",
        },
    })

    dossier["sources"].append({
        "name": "GDS Holdings official news page (AidData 'Donor/Recipient Official Source')",
        "url": fetch_log["gds_official"]["url"],
        "access": {"status": fetch_log["gds_official"]["status"],
                   "bytes": fetch_log["gds_official"]["bytes"],
                   "observation": ("page returned is a site notice/template page (提示信息), not the "
                                   "article: the announcement is no longer served at this URL")},
        "publisher": "GDS Holdings Ltd.",
        "document_date": None,
        "license_note": "company website content; not archived here beyond the fetched HTML",
        "exact_passages": [{"topic": "access failure",
                            "quote": "page content is a navigation/notice template; no article text about the loan is present"}],
        "supports": {
            "facility_identity": "no (page no longer carries the article)",
            "phase": "no", "loan_amount": "no", "green_use_of_proceeds": "no",
            "project_status": "no", "renewable_procurement": "no",
        },
    })

    dossier["sources"].append({
        "name": "Google Maps place link (AidData 'Other')",
        "url": fetch_log.get("prnewswire", {}).get("url") and
               "https://www.google.com/maps/place/GDS+International+Nusajaya+Data+Center/@1.4337777,103.5973506,18z/",
        "access": {"status": "NOT FETCHED",
                   "observation": ("JavaScript application; not machine-fetchable without browser "
                                   "automation. Coordinates embedded in the AidData URL: "
                                   "1.4337777, 103.5973506 — recorded as stated, not verified.")},
        "publisher": "Google Maps", "document_date": None,
        "license_note": "Google Maps content under Google ToS; only the URL/coordinates are recorded",
        "exact_passages": [{"topic": "location", "quote": "URL-embedded coordinates 1.4337777,103.5973506 labelled 'GDS International Nusajaya Data Center'"}],
        "supports": {
            "facility_identity": "weak (place-name in URL, not verified)",
            "phase": "no", "loan_amount": "no", "green_use_of_proceeds": "no",
            "project_status": "no", "renewable_procurement": "no",
        },
    })

    dossier["per_dimension_assessment"] = {
        "facility_identity": ("SUPPORTED by IJGlobal + PR Newswire: GDS Nusajaya Tech Park (NTP) "
                              "Data Center Campus Plot 1 (NTP1), Johor, Malaysia; sponsor GDS Holdings"),
        "phase": ("SUPPORTED as a label ('Phase 1'/NTP1); what Phase 1 includes physically (which "
                  "buildings/units) is not specified in any inspected source beyond net floor area "
                  "30,312 m2 (PRN)"),
        "loan_amount": ("SUPPORTED and cross-consistent: total MYR 1,270.00m (USD 272.12m); BoC "
                        "tranche MYR 317.50m (USD 68.03m) matches the AidData row amount"),
        "green_use_of_proceeds": ("PARTIAL: 'green' designation asserted by deal participants; "
                                  "stated proceeds purpose = completing Plot 1 development; NO "
                                  "Green Loan Framework, second-party opinion or UoP breakdown "
                                  "among accessible sources — the green credential itself is "
                                  "unverified"),
        "project_status": ("DISAGREEMENT kept visible: IJGlobal 'Current Stage: Pre-construction' "
                           "+ 'Financial close (8 Dec 2023)' (deal stage) vs AidData 'Completion' "
                           "(ambiguous: financing completion) vs PRN future-framed delivery; NO "
                           "inspected source states construction completion; IJGlobal data is "
                           "dated 10 Dec 2023 (stale at 2026 retrieval)"),
        "renewable_procurement": ("UNKNOWN / NOT EVIDENCED: only an aspiration quoted by a bank "
                                  "executive ('100% use of renewable energy by 2030') and GDS "
                                  "marketing language; no REC, PPA, on-site generation or supply "
                                  "data in any accessible source"),
        "ai_workloads": ("NOT INFERABLE: the sources describe a data-centre campus; no tenant, "
                         "workload or AI-specific information is present — none is inferred"),
    }

    dossier["disagreements"] = [
        {"dimension": "capacity", "claims": [
            {"source": "IJGlobal title", "value": "69.9MW"},
            {"source": "IJGlobal data fields", "value": "Capacity: 54.00 MW"},
            {"source": "PR Newswire (GDS)", "value": "IT power capacity of 69.9 MW"}],
         "note": ("69.9 (IT power, per the company) vs 54.00 (IJGlobal 'Capacity' field) — the "
                  "sources do not explain the difference (possible IT vs utility/design rating); "
                  "both recorded, no winner chosen")},
        {"dimension": "instrument type", "claims": [
            {"source": "IJGlobal", "value": "Type: Debt — also labelled 'Green Bond'"},
            {"source": "PR Newswire", "value": "secured green term loan facility"}],
         "note": "bond vs term-loan characterisation differs across sources; both quoted"},
        {"dimension": "status", "claims": [
            {"source": "IJGlobal", "value": "Pre-construction (construction stage) / Financial close (deal stage)"},
            {"source": "AidData", "value": "Completion (status category, definition ambiguous)"}],
         "note": "no inspected source states construction completion; AidData 'Completion' cannot be read as plant/facility completion"},
    ]

    dossier["unknowns"] = [
        "Whether a Green Loan Framework / second-party opinion exists for this facility (not among accessible sources).",
        "Any actual renewable-energy procurement by the facility (REC, PPA, on-site solar): no evidence either way.",
        "Construction progress after Dec 2023 (no source inspected is newer than 13 Dec 2023).",
        "The actual electricity supply arrangement for the facility (grid connection, tariff, any supply contract).",
        "Tenants and workloads (incl. any AI workloads): not present in sources; not inferred.",
        "The facility agreement document itself (AidData Original_Agreement_URL is empty).",
    ]

    audit_rows = json.loads((FINDINGS / "ai_infra_re_scan.json").read_text())
    kw_counts = {}
    for h in audit_rows["aiddata_hits"]:
        kw_counts[h["matched_keyword"]] = kw_counts.get(h["matched_keyword"], 0) + 1
    dossier["scan_audit"] = {
        "defined_search_universe": {
            "dataset": "AidData China's Loans and Grants to Low- and Middle-Income Countries, v1.0 (2025-11-18)",
            "geography": "11 Southeast Asian countries by Country_of_Activity",
            "fields_searched": ["Title", "Narrative_Description"],
            "fields_NOT_searched": ["Staff_Comments", "Loan_Event_Description", "Location_Narrative",
                                    "Original_Agreement_Title"],
            "keyword_regex": "data cent(er|re)|datacent|artificial intelligence|\\bAI\\b (case-SENSITIVE after fix)|machine learning|cloud comput|supercomput|digital econom|5G|hyperscal|semiconductor",
            "languages": "English only",
        },
        "keyword_match_counts": kw_counts,
        "false_positives_found_and_fixed": [
            {"record_id": 34762, "cause": ("\\bAI\\b with re.I matched the person name 'Yan "
                                           "Ting'ai' (Chinese Ambassador, 2004)",),
             "fix": "AI token made case-sensitive via (?-i:...) — record excluded from hits"},
            {"record_id": 100460, "cause": ("'Myanmar Agricultural and Rural Statistics Project "
                                            "Data Center' matches 'data cent' but its subject is a "
                                            "statistics project, not commercial digital/AI infrastructure",),
             "fix": "kept in hits (keyword-level true positive) and documented as out-of-scope subject; not silently dropped"},
        ],
        "known_false_negative_risks": [
            "Non-English titles/narratives (dataset is English-only; nothing to scan).",
            "Variants not in the regex: 'AI factory', 'intelligent computing', 'colocation', 'server farm', 'digital infrastructure', 'IDC', 'compute'.",
            "Facilities described only in Staff_Comments or agreement titles (not scanned).",
            "Projects whose data-center relevance appears only in unlinked source documents.",
        ],
        "definitional_choices": [
            "5G/4G telecom rollouts are INCLUDED as digital-infrastructure adjacency (policy choice; inflates 'AI infra' counts if read narrowly).",
            "Google Maps/other 'Other'-type sources are not scanned.",
        ],
        "hit_count": {"before_ai_case_fix": 37, "after": 36},
        "limits": ("The scan identifies financing/announcement records, not facilities; absence of "
                   "hits is absence within this defined universe only — it does not establish the "
                   "absence of data-centre or procurement registries anywhere."),
    }

    (FINDINGS / "gds106768_dossier.json").write_text(json.dumps(dossier, ensure_ascii=False, indent=1))
    n_pass = sum(1 for s in dossier["sources"] if s["access"].get("status") == 200)
    print(f"dossier written: {len(dossier['sources'])} sources ({n_pass} fetched, "
          f"{len(dossier['disagreements'])} disagreements, {len(dossier['unknowns'])} unknowns); "
          f"GDS official page failure={gds_failed}")


if __name__ == "__main__":
    main()
