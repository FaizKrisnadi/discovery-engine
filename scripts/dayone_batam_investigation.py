"""DayOne Batam investigation dossier (Indonesian case).

Research question: who finances, operates and supplies energy to DayOne's Batam
data-centre infrastructure; what is known about control or dependency; which
links cannot be established?

GRAIN DISCIPLINE — distinct assets and entities, never conflated:
  A. DayOne Nongsa Digital Park (NDP) campus, Batam — ~72MW IT load, three
     data centres, financed by the IDR 6.7T (~US$412.1M) DBS/UOB loan (2025-06)
  B. DayOne Kabil Industrial Tech Park (KITP) campus, Batam — under
     development; PPA signed 2026-04-17 with PT PLN Batam (~511 MVA ≈ ~450 MW
     of GRID capacity; phases 2026-2027)
  Entities: DayOne (PT Digitalland Service One per Indonesian coverage), PLN
  Batam, BP Batam, DBS, UOB, INA (Indonesia Investment Authority), GDS
  Holdings (spun out the international unit that became DayOne).

Layer discipline: primary company statements (dayonedc.com release) /
secondary trade press (DCD, quoting company statements and a LinkedIn image) /
search transcripts (unfetched) are recorded separately with per-source status.
No AI-workload, physical-renewable-supply, ownership-control or causal-impact
inference is made. 'AI-ready platform' and 'supports AI workloads growth' are
company marketing framings.
"""
from __future__ import annotations

import json
import re
import html as H
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery.engine import ClaimIn, Engine, SourceIn, canonical, content_hash, file_sha256

RAW = ROOT / "data/raw"
FINDINGS = ROOT / "findings"
DB = ROOT / "data" / "processed" / "engine.sqlite3"

DCD_LOAN_REF = "https://www.datacenterdynamics.com/en/news/dayone-secures-412m-loan-for-batam-data-center-campus-in-indonesia"
DCD_PPA_REF = "https://www.datacenterdynamics.com/en/news/dayone-inks-450mw-ppa-with-pln-batam-to-power-planned-data-center-in-batam-indonesia"
DAYONE_PPA_REF = "https://dayonedc.com/markets/dayone-signs-indonesias-largest-511mva-450mw-ppa-to-expand-hyperscale-data-center-platform-in-batam"
NEWSROOM_REF = "https://www.dayone.com/newsroom"
ANALYSIS = "analysis:this-project:dayone-batam-investigation"
UOB_REF = "https://www.uobgroup.com/uobgroup/newsroom/news-releases/2025/dbs-uob-arrange-loan-for-data-centre-development-project-by-dayone.page"

DCD_LICENSE = "Data Center Dynamics article; quoted for research attribution only (copyright DCD)"
UOB_LICENSE = "UOB Group newsroom release; quoted for research attribution only (copyright UOB; page offers a PDF download)"
DAYONE_LICENSE = "DayOne website release; quoted for research attribution only"
SEARCH_LICENSE = "web-search transcript; underlying articles not fetched; summary only"
ANALYST_BYLINE = "this project (deterministic scripts; AI-generated, unreviewed)"


def _text(path: str) -> str:
    h = (ROOT / path).read_text(errors="ignore")
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h)))


def _attempts(log_name: str, name: str) -> list:
    d = json.loads((RAW / log_name).read_text())
    e = d.get(name)
    if not e:
        return []
    att = dict(e)
    att.setdefault("ts", e.get("attempted_at"))
    if e.get("status") is not None:
        att["outcome"] = f"http_{e['status']}"
    elif e.get("error"):
        att["outcome"] = "error"
    return [att]


def quote_texts() -> dict[str, str]:
    return {
        DCD_LOAN_REF: _text("data/raw/dayone_dcd_loan_article.html"),
        UOB_REF: _text("data/raw/dayone_uob_release.html"),
        DCD_PPA_REF: _text("data/raw/dayone_dcd_ppa_article.html"),
        DAYONE_PPA_REF: _text("data/raw/dayone_dayone_ppa_release.html"),
        ANALYSIS: "",
    }


def build_dossier() -> dict:
    fetch = json.loads((RAW / "dayone_fetch_log.json").read_text())
    d = {
        "research_question": ("Who finances, operates and supplies energy to DayOne's Batam "
                              "data-centre infrastructure; what is known about control or "
                              "dependency; which links cannot be established?"),
        "grain_discipline": {
            "A_ndp": "DayOne Nongsa Digital Park (NDP) campus, Batam — ~72MW IT load across three data centres; financed by the IDR 6.7 trillion (~US$412.1M) DBS/UOB loan (June 2025)",
            "B_kabil": "DayOne Kabil Industrial Tech Park (KITP) campus, Batam — under development; PPA signed 2026-04-17 with PT PLN Batam (~511 MVA ≈ ~450 MW of grid capacity; supply in phases 2026-2027)",
            "rule": ("NDP and Kabil are two different campuses of the same operator; the DBS/UOB "
                     "loan funds NDP (per source wording) and must not be attributed to Kabil; "
                     "the PLN Batam PPA is grid capacity with no stated energy mix and must not "
                     "be presented as renewable supply"),
        },
        "sources": [],
        "per_question": {},
        "falsification_attempts": [],
        "unknowns": [],
        "human_review_required": [],
    }

    d["sources"].append({
        "name": "DayOne release — PPA signing (company primary statement)",
        "url": DAYONE_PPA_REF, "layer": "company statements (primary)",
        "document_date": "2026-04-17 (dateline on page)",
        "access": fetch["dayone_ppa_release"],
        "license": DAYONE_LICENSE,
        "exact_passages": [
            {"topic": "PPA + counterparties + asset",
             "quote": "DayOne today announced the signing of a landmark set of agreements with PT PLN Batam, marking a major expansion of its digital infrastructure platform in Indonesia. The agreements include the largest long-term power purchase agreement (PPA) in Indonesia, at approximately 511 MVA, equivalent to around 450 MW of grid capacity, as well as memoranda of understanding covering connectivity and electrical infrastructure services for DayOne Kabil Industrial Tech Park (KITP), its new data center campus located in Kabil Integrated Industrial Estate (KIIE), Batam."},
            {"topic": "supply schedule",
             "quote": "Power supply will be delivered in phases between 2026 and 2027 to support the project."},
            {"topic": "second campus (grain: NDP precedes Kabil)",
             "quote": "The development represents DayOne\u2019s second hyperscale data center campus in Batam, following its flagship campus in Nongsa Digital Park (NDP)"},
            {"topic": "AI marketing framing (not workload evidence)",
             "quote": "The DayOne Kabil campus is being developed as a high-performance, AI-ready platform designed to support advanced computing workloads."},
            {"topic": "institutional context (BP Batam)",
             "quote": "strong government support, including the role of BP Batam in facilitating investment, streamlining regulatory processes, and infrastructure development."},
        ],
        "supports": {
            "kabil_ppa": "yes (2026-04-17; ~511 MVA \u2248 ~450 MW of GRID capacity; PLN Batam counterparty; KITP named)",
            "supply_schedule": "phases 2026-2027 (future commitment at signing; not operational supply)",
            "energy_mix": "NOT STATED anywhere in the release \u2014 'grid capacity' only; no renewable claim may be inferred",
            "ai_workload": "NO \u2014 'AI-ready platform' is a design/marketing framing",
        },
    })
    d["sources"].append({
        "name": "Data Center Dynamics — $412m loan article (secondary, quoting company statements and a LinkedIn image)",
        "url": DCD_LOAN_REF, "layer": "secondary reporting",
        "document_date": "2025-06-08 (byline 'June 08, 2025 By Dan Swinhoe')",
        "access": fetch["dcd_loan_article"],
        "license": DCD_LICENSE,
        "exact_passages": [
            {"topic": "NDP financing (NOT Kabil)",
             "quote": "Singapore banks DBS and UOB this week announced they have jointly provided an IDR 6.7 trillion ($412.1m) loan facility to DayOne to finance the development of a new data center campus in Batam, Indonesia."},
            {"topic": "NDP grain + schedule + capacity",
             "quote": "Proceeds of the loan will be used to develop and operate three data centers located in the Nongsa Digital Park (NDP). The first phase is due live by the end of 2025. The campus will have a combined IT load capacity of around 72MW."},
            {"topic": "land",
             "quote": "GDS spin-out DayOne acquired land in Batam in November 2021 ."},
            {"topic": "development partner (state-owned)",
             "quote": "The project, jointly developed by DayOne and the Indonesia Investment Authority (INA), is backed by the largest rupiah-denominated financing agreement ever secured for such a development. INA is Indonesia\u2019s sovereign wealth fund, wholly owned by the Government of Indonesia, and partnered with DayOne for the development in 2023 ."},
            {"topic": "CEO statement",
             "quote": "This landmark financing \u2014 the largest rupiah-denominated facility ever secured for a data centre development \u2014 is a strong endorsement of DayOne\u2019s proven ability to deliver digital infrastructure at speed and scale. (Jamie Khoo, CEO of DayOne)"},
            {"topic": "GDS relationship framing (as of 2025-06)",
             "quote": "DayOne is the international unit of Chinese data center operator GDS. The company rebranded its Singapore-based international unit at the beginning of this year and has secured outside investment from the likes of SoftBank Vision Fund, Citadel CEO Kenneth Griffin, Coatue Management, and Baupost Group."},
        ],
        "supports": {
            "ndp_financing": "yes (IDR 6.7T / $412.1M, DBS + UOB, for the three NDP data centres)",
            "ndp_schedule_capacity": "yes (first phase end-2025; ~72MW combined)",
            "ina_partnership": "yes as reported (jointly developed with INA; partnered 2023)",
            "gds_relationship": "mixed/evolving: 'GDS spin-out', 'international unit of GDS', rebranded Jan 2025, outside investors named \u2014 the exact current equity relationship is NOT established by this article",
            "kabil_financing": "NO \u2014 the loan funds NDP; nothing in the article links it to Kabil",
        },
    })
    d["sources"].append({
        "name": "Data Center Dynamics — PPA article (secondary)",
        "url": DCD_PPA_REF, "layer": "secondary reporting",
        "document_date": "~2026-04-20",
        "access": fetch["dcd_ppa_article"],
        "license": DCD_LICENSE,
        "exact_passages": [
            {"topic": "PPA grain + delivery",
             "quote": "The company signed a 450MW PPA with state-run utility PLN Batam to power its under-development data center campus in Kabil, Batam. The PPA will be delivered via the grid, with power supply delivered in phases between 2026 and 2027."},
            {"topic": "capacity unstated",
             "quote": "The data center is expected to have a similar capacity to the PPA signed, however exact details on its capacity were not shared. DCD has reached out for further information."},
            {"topic": "MoU status",
             "quote": "In addition to the PPA, the two firms inked a non-binding memorandum of understanding (MoU) covering con..."},
        ],
        "supports": {
            "kabil_ppa": "yes (corroborates the company release; adds 'delivered via the grid' and 'non-binding MoU')",
            "kabil_capacity": "NOT shared (expected similar to PPA \u2014 explicitly unstated)",
        },
    })
    d["sources"].append({
        "name": "DayOne newsroom — ACCESS FAILURE",
        "url": NEWSROOM_REF, "layer": "company statements (not retrieved)",
        "document_date": None,
        "access": {**fetch["dayone_site_news"],
                   "observation": "HTTP 404 (guessed path); no static newsroom index found"},
        "license": "n/a (not retrieved)",
        "exact_passages": [{"topic": "access failure", "quote": "HTTP 404"}],
        "supports": {},
    })
    d["sources"].append({
        "name": "WebSearch transcript — PLN Batam / PJBTL signing (Indonesian media)",
        "url": "websearch:transcript-2026-10-31:pln-batam-pjbtl",
        "layer": "secondary reporting (transcript; articles not fetched)",
        "document_date": "2026-04-24 to 2026-04-28 (per transcript)",
        "access": {"status": "not_fetched"},
        "license": SEARCH_LICENSE,
        "exact_passages": [
            {"topic": "signing entity + instrument",
             "quote": "PLN Batam (Indonesian state utility's Batam unit) and DayOne (PT Digitalland Service One) signed the PJBTL (electricity purchase agreement) of 511 MVA \u2014 reportedly the largest power purchase for a data center in Indonesia \u2014 plus an MoU covering fiber-optic infrastructure development and related services, to support DayOne's data center development in Batam."},
        ],
        "supports": {
            "signing_entity": "reported: PT Digitalland Service One (DayOne) \u2014 the Indonesian contracting entity; transcript-only",
            "instrument": "PJBTL (electricity sale-purchase agreement) + fiber MoU",
        },
    })
    d["sources"].append({
        "name": "WebSearch transcript — DayOne/GDS rebrand, Series C, Kabil 'AI-ready'",
        "url": "websearch:transcript-2026-10-31:dayone-gds-seriesc",
        "layer": "secondary reporting (transcript; articles not fetched)",
        "document_date": "transcript dated 2026-10-31",
        "access": {"status": "not_fetched"},
        "license": SEARCH_LICENSE,
        "exact_passages": [
            {"topic": "rebrand + independence (as summarised)",
             "quote": "DayOne is the rebranded international unit of GDS Holdings. GDS set up GDS International in Singapore in 2022. On January 1, 2025, GDSI was officially rebranded as DayOne, launching as an independent company (though GDS Holdings retains a stake/backing)."},
            {"topic": "Series C",
             "quote": "In January 2026, DayOne announced a US$2.0+ billion Series C raise, and it's reportedly pursuing a US listing (IPO valued around $5 billion)."},
        ],
        "supports": {
            "rebrand": "reported (transcript): GDSI \u2192 DayOne on 2025-01-01; 'independent company' with retained GDS stake/backing \u2014 exact equity relationship NOT established",
            "series_c": "reported (transcript, unfetched)",
        },
    })

    d["per_question"] = {
        "who_finances": {
            "ndp": ("CORRECTED 2026-10-31: PRIMARY bank release (UOB, 5 Jun 2025) \u2014 IDR 6.7 "
                    "trillion (SGD 530M) jointly provided by DBS and UOB; proceeds to three NDP "
                    "data centres; completion by end-2025 targeted; DayOne/INA joint venture "
                    "stated. DCD article is secondary corroboration."),
            "kabil": ("NOT ESTABLISHED (re-affirmed by the primary bank release: zero Kabil "
                      "mentions; proceeds allocated to NDP data centres). Non-mention within one "
                      "document is a bounded observation, not an explicit exclusion."),
            "company_level": "Series C US$2.0+B reported (Jan 2026, transcript, unfetched); outside investors incl. SoftBank Vision Fund, Kenneth Griffin, Coatue, Baupost (DCD)",
        },
        "who_operates": {
            "batam_campuses": "DayOne (company statements: 'its flagship campus in Nongsa Digital Park (NDP)'; KITP 'its new data center campus')",
            "contracting_entity": "PT Digitalland Service One reported as the PPA signing entity (transcript only)",
            "gds_relationship": ("EVOLVING/CONTESTED characterisations coexist: 'GDS spin-out' (DCD), "
                                 "'international unit of GDS' (DCD, Jun 2025), rebranded 2025-01-01 "
                                 "'independent company' with 'GDS Holdings retains a stake/backing' "
                                 "(transcript). The current equity/control relationship is NOT "
                                 "established by accessible sources."),
        },
        "who_supplies_energy": {
            "kabil": "PT PLN Batam under the ~511 MVA (\u2248450 MW) PPA — GRID capacity, supply in phases 2026-2027 (future commitment at signing). Energy mix NOT stated; no renewable claim may be inferred.",
            "ndp": "NOT ESTABLISHED from accessible sources (supplier/PPA for NDP not found; grid supply plausible but unevidenced here).",
        },
        "control_or_dependency": {
            "known": ("PLN Batam (state utility unit) is the PPA counterparty for Kabil; INA "
                      "(Indonesia's sovereign wealth fund) is the reported NDP co-development "
                      "partner; DBS/UOB are the reported NDP lenders; BP Batam participates in "
                      "investment facilitation (company statement)"),
            "not_known": ("GDS Holdings' current equity stake in or control over DayOne; DayOne "
                          "corporate structure between the Singapore unit and PT Digitalland Service "
                          "One; any security/covenant links between lenders and operations; whether "
                          "the Kabil PPA is exclusive or portfolio-wide"),
        },
    }

    d["falsification_attempts"] = [
        {"hypothesis": "The PLN Batam PPA is a renewable-energy supply agreement.",
         "attempts": "Searched the company release and the DCD article for any energy-mix or renewable wording.",
         "result": ("FAILED TO CONFIRM: both sources describe only 'grid capacity' delivered in "
                    "phases; neither states an energy mix. No renewable claim may be inferred."),
         "verdict": "NOT ESTABLISHED \u2014 the PPA is grid capacity; energy mix unknown."},
        {"hypothesis": "The DBS/UOB $412M loan finances the Kabil campus.",
         "attempts": "Checked the loan article's proceeds wording.",
         "result": ("CORRECTED 2026-10-31 with the primary bank release (UOB, 2025-06-05): proceeds "
                    "are allocated to 'three data centres located in the Nongsa Digital Park (NDP)' "
                    "and the release contains ZERO Kabil mentions. No source allocates loan proceeds "
                    "to Kabil. DISTINCTION preserved: absence of a Kabil mention within the "
                    "release is a bounded observation, not an explicit exclusion \u2014 Kabil "
                    "financing remains NOT ESTABLISHED."),
         "verdict": ("NOT SUPPORTED (corrected 2026-10-31: was overstated as FALSIFIED): the primary "
                     "bank release allocates proceeds to three NDP data centres and does not mention "
                     "Kabil; no source allocates loan proceeds to Kabil. This is non-establishment, "
                     "not affirmative exclusion — Kabil financing status remains NOT ESTABLISHED.")},
        {"hypothesis": "DayOne is fully independent of GDS Holdings (no current links).",
         "attempts": "Compared characterizations: 'GDS spin-out'/'international unit of GDS' (DCD, Jun 2025) vs 'independent company' with 'GDS retains a stake/backing' (transcript, 2026).",
         "result": ("CONTESTED/EVOLVING: the rebrand (2025-01-01) and outside investors are "
                    "reported, but no accessible source states the current GDS equity stake. Both "
                    "characterizations are kept as dated claims from different sources."),
         "verdict": "NOT ESTABLISHED \u2014 the current GDS\u2013DayOne equity/control relationship is unknown."},
        {"hypothesis": "The Kabil PPA signing means power is already being delivered.",
         "attempts": "Checked supply-schedule wording in both sources.",
         "result": ("FALSIFIED for the present-supply reading: 'Power supply will be delivered in "
                    "phases between 2026 and 2027' \u2014 a future commitment at signing."),
         "verdict": ("DOWNGRADED (corrected 2026-10-31): 'planned at announcement' is the supported "
                     "statement; whether a 2026-27 phase has begun delivering by the current date "
                     "(2026-10-31) is UNVERIFIED — a phased plan does not falsify present "
                     "delivery, which is simply not sourced.")},
    ]

    d["unknowns"] = [
        "Kabil campus financing (if any separate from company-level funding).",
        "NDP's electricity supplier and any PPA/contract for the NDP campus.",
        "Energy mix of the 511 MVA PPA (no renewable or fossil claim stated).",
        "Exact KITP IT-load capacity (DCD: 'not shared').",
        "GDS Holdings' current equity stake in, and governance rights over, DayOne.",
        "The corporate relationship between DayOne (Singapore) and PT Digitalland Service One (the reported Indonesian PPA signatory).",
        "Operational status of NDP's first phase (due end-2025 per DCD; no operational confirmation retrieved).",
        "Any AI workload at either campus ('AI-ready platform' is a design/marketing framing).",
    ]
    d["human_review_required"] = [
        "Retrieve and read the Indonesian-language PLN Batam statements and the PJBTL document (or excerpts) to confirm instrument, counterparty entity and capacity.",
        "Locate DayOne's own newsroom release for the PPA signing beyond the dayonedc.com markets page (newsroom 404).",
        "Confirm the GDS Holdings\u2013DayOne equity relationship from filings (GDS annual report / DayOne disclosures) before any control statement.",
        "Verify NDP first-phase operational status from a dated source.",
        "Adjudicate the scoped DayOne/GDS entity pairings in the engine.",
    ]
    return d


def dossier_claims(d: dict) -> list[ClaimIn]:
    NDP = "project:dayone-ndp-batam"
    KAB = "project:dayone-kabil-batam"
    a = lambda **kw: ClaimIn(subject_key=kw.pop("subject"), subject_type="project", **kw)
    C = [
        # ---- Kabil (B): PPA, counterparties, schedule ----
        a(subject=KAB, predicate="HAS_PPA_SIGNED",
          object_literal="PT PLN Batam \u2014 largest long-term PPA in Indonesia, ~511 MVA \u2248 ~450 MW of GRID capacity, for KITP (Kabil Integrated Industrial Estate, Batam); plus connectivity/electrical-infrastructure MoUs",
          claim_time="2026-04-17", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=DAYONE_PPA_REF, locator="release body", field="ppa",
          quote="The agreements include the largest long-term power purchase agreement (PPA) in Indonesia, at approximately 511 MVA, equivalent to around 450 MW of grid capacity, as well as memoranda of understanding covering connectivity and electrical infrastructure services for DayOne Kabil Industrial Tech Park (KITP), its new data center campus located in Kabil Integrated Industrial Estate (KIIE), Batam."),
        a(subject=KAB, predicate="HAS_PPA_COUNTERPARTY", object_key="org:pln-batam", object_type="organization",
          object_literal="PT PLN Batam (state utility unit)", claim_time="2026-04-17", time_precision="day",
          certainty="reported", evidence_kind="verbatim",
          source_ref=DAYONE_PPA_REF, locator="release body", field="counterparty",
          quote="a landmark set of agreements with PT PLN Batam"),
        a(subject=KAB, predicate="HAS_SUPPLY_SCHEDULE", object_literal="grid-delivered, in phases between 2026 and 2027 (future commitment at signing)",
          claim_time="2026-04-20", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref="https://www.datacenterdynamics.com/en/news/dayone-inks-450mw-ppa-with-pln-batam-to-power-planned-data-center-in-batam-indonesia",
          locator="article body", field="supply schedule",
          quote="The PPA will be delivered via the grid, with power supply delivered in phases between 2026 and 2027."),
        a(subject=KAB, predicate="IS_RENEWABLE_SUPPLY", object_literal="NOT ESTABLISHED: both sources describe only 'grid capacity'; no energy mix is stated anywhere",
          claim_time=None, time_precision="unknown", certainty="inferred", evidence_kind="analyst_synthesis",
          source_ref=ANALYSIS, locator="falsification_attempts[0]", field="energy mix",
          quote="FAILED TO CONFIRM: both sources describe only 'grid capacity'; neither states an energy mix."),
        a(subject=KAB, predicate="HAS_CAPACITY_CLAIM", object_literal="KITP IT-load capacity NOT shared (DCD: 'expected to have a similar capacity to the PPA signed, however exact details on its capacity were not shared')",
          claim_time="2026-04-20", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref="https://www.datacenterdynamics.com/en/news/dayone-inks-450mw-ppa-with-pln-batam-to-power-planned-data-center-in-batam-indonesia",
          locator="article body", field="capacity",
          quote="The data center is expected to have a similar capacity to the PPA signed, however exact details on its capacity were not shared."),
        a(subject=KAB, predicate="IS_AI_WORKLOAD", object_literal="NOT INFERABLE: 'AI-ready platform designed to support advanced computing workloads' is a design/marketing framing; no tenant or workload evidence",
          claim_time=None, time_precision="unknown", certainty="inferred", evidence_kind="analyst_synthesis",
          source_ref=ANALYSIS, locator="sources: DayOne release passages", field="ai workload",
          quote="The DayOne Kabil campus is being developed as a high-performance, AI-ready platform designed to support advanced computing workloads."),
        a(subject=KAB, predicate="HAS_INSTITUTIONAL_CONTEXT", object_literal="BP Batam role in investment facilitation, regulatory processes, infrastructure development (company statement)",
          claim_time="2026-04-17", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=DAYONE_PPA_REF, locator="release body", field="institutional context",
          quote="strong government support, including the role of BP Batam in facilitating investment, streamlining regulatory processes, and infrastructure development."),
        # ---- NDP (A): financing, partner, schedule, capacity ----
        a(subject=NDP, predicate="HAS_FINANCING", object_literal="IDR 6.7 trillion (~US$412.1M) loan facility from DBS and UOB (announced June 2025) for the three NDP data centres",
          claim_time="2025-06-08", time_precision="day", certainty="reported", evidence_kind="verbatim",
          unit="USD", grain="campus-level financing (NDP, named by source)",
          source_ref=DCD_LOAN_REF, locator="article body", field="financing",
          quote="Singapore banks DBS and UOB this week announced they have jointly provided an IDR 6.7 trillion ($412.1m) loan facility to DayOne to finance the development of a new data center campus in Batam, Indonesia."),
        a(subject=NDP, predicate="HAS_FINANCING_PARTICIPANT", object_key="org:dbs", object_type="organization",
          object_literal="joint lender", claim_time="2025-06-08", time_precision="day",
          certainty="reported", evidence_kind="verbatim",
          source_ref=DCD_LOAN_REF, locator="article body", field="lender",
          quote="Singapore banks DBS and UOB this week announced they have jointly provided an IDR 6.7 trillion ($412.1m) loan facility to DayOne"),
        a(subject=NDP, predicate="HAS_FINANCING_PARTICIPANT", object_key="org:uob", object_type="organization",
          object_literal="joint lender", claim_time="2025-06-08", time_precision="day",
          certainty="reported", evidence_kind="verbatim",
          source_ref=DCD_LOAN_REF, locator="article body", field="lender",
          quote="Singapore banks DBS and UOB this week announced they have jointly provided an IDR 6.7 trillion ($412.1m) loan facility to DayOne"),
        a(subject=NDP, predicate="HAS_DEVELOPMENT_PARTNER", object_key="org:ina", object_type="organization",
          object_literal="Indonesia Investment Authority (INA) \u2014 Indonesia's sovereign wealth fund, wholly owned by the Government of Indonesia; partnered with DayOne in 2023; jointly developed",
          claim_time="2025-06-08", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=DCD_LOAN_REF, locator="article body", field="development partner",
          quote="The project, jointly developed by DayOne and the Indonesia Investment Authority (INA), is backed by the largest rupiah-denominated financing agreement ever secured for such a development."),
        a(subject=NDP, predicate="HAS_CAPACITY_CLAIM", object_literal="~72MW combined IT load across three data centres (first phase due live end-2025)",
          claim_time="2025-06-08", time_precision="day", certainty="reported", evidence_kind="verbatim",
          unit="MW", grain="campus combined IT load (company-stated via DCD)",
          source_ref=DCD_LOAN_REF, locator="article body", field="capacity",
          quote="The campus will have a combined IT load capacity of around 72MW."),
        a(subject=NDP, predicate="HAS_SUPPLY_SCHEDULE", object_literal="first phase due live by end of 2025 (no operational confirmation retrieved)",
          claim_time="2025-06-08", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=DCD_LOAN_REF, locator="article body", field="schedule",
          quote="The first phase is due live by the end of 2025."),
        a(subject=NDP, predicate="HAS_OPERATOR", object_key="org:dayone", object_type="organization",
          object_literal="DayOne ('following its flagship campus in Nongsa Digital Park (NDP)' — company statement)",
          claim_time="2026-04-17", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=DAYONE_PPA_REF, locator="release body", field="operator",
          quote="The development represents DayOne\u2019s second hyperscale data center campus in Batam, following its flagship campus in Nongsa Digital Park (NDP)"),
        a(subject=NDP, predicate="IS_RENEWABLE_SUPPLY", object_literal="NOT ESTABLISHED: no NDP energy-mix or supplier document retrieved",
          claim_time=None, time_precision="unknown", certainty="inferred", evidence_kind="analyst_synthesis",
          source_ref=ANALYSIS, locator="per_question.who_supplies_energy.ndp", field="energy mix",
          quote="NOT ESTABLISHED from accessible sources (supplier/PPA for NDP not found; grid supply plausible but unevidenced here)."),
        # ---- UOB primary bank release claims (supervisor correction 2026-10-31) ----
        a(subject=NDP, predicate="HAS_FINANCING",
          object_literal="IDR 6.7 trillion (SGD 530 million) loan facility jointly provided by DBS and UOB — PRIMARY BANK RELEASE (2025-06-05); DCD article is secondary corroboration",
          claim_time="2025-06-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          unit="IDR", grain="campus-level financing (NDP, bank-attributed)",
          source_ref=UOB_REF, locator="release body", field="financing",
          quote="DBS and UOB have jointly provided a landmark IDR 6.7 trillion (SGD 530 million) loan 1 facility to finance the development of a new data centre campus in Batam, Indonesia."),
        a(subject=NDP, predicate="HAS_PROCEEDS_ALLOCATION",
          object_literal="three data centres located in the Nongsa Digital Park (NDP) — bank-attributed proceeds allocation; the release does not mention Kabil (0 occurrences)",
          claim_time="2025-06-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=UOB_REF, locator="release body", field="proceeds",
          quote="Proceeds of the loan will be used to develop and operate three data centres located in the Nongsa Digital Park (NDP) in Batam."),
        a(subject=NDP, predicate="HAS_SUPPLY_SCHEDULE",
          object_literal="Upon completion by end-2025 (bank-attributed, June 2025); operational status as of 2026-10-31 UNVERIFIED — a passed target date is not evidence of completion or failure",
          claim_time="2025-06-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=UOB_REF, locator="release body", field="schedule",
          quote="Upon completion by end-2025, the DayOne Nongsa Digital Park Data Centre campus will have a combined IT load capacity of around 72MW."),
        a(subject=NDP, predicate="HAS_CAPACITY_CLAIM",
          object_literal="~72MW combined IT load; bank adds context: ~5% of Indonesia's projected 1.41GW DC capacity by 2029 (BCG-cited demand up to 6.5GW by 2030)",
          claim_time="2025-06-05", time_precision="day", certainty="reported", evidence_kind="verbatim",
          unit="MW", grain="campus combined IT load (bank-attributed)",
          source_ref=UOB_REF, locator="release body", field="capacity",
          quote="the DayOne Nongsa Digital Park Data Centre campus will have a combined IT load capacity of around 72MW"),
        ClaimIn(subject_key="org:dayone", subject_type="organization",
                predicate="HAS_JOINT_VENTURE_CLAIM",
                object_literal="DayOne and INA have established a joint venture (bank-attributed statement, 2025-06-05); JV structure/ownership split NOT stated",
                claim_time="2025-06-05", time_precision="day", certainty="reported",
                evidence_kind="verbatim", source_ref=UOB_REF, locator="release body",
                field="joint venture",
                quote="DayOne and INA have established a joint venture to propel the growth and advancement of the data centre landscape in Indonesia."),
        ClaimIn(subject_key="org:ina", subject_type="organization",
                predicate="HAS_INSTITUTIONAL_CONTEXT",
                object_literal="INA's first investment in the sector (bank-attributed); INA is Indonesia's sovereign wealth fund, wholly owned by the Government of Indonesia",
                claim_time="2025-06-05", time_precision="day", certainty="reported",
                evidence_kind="verbatim", source_ref=UOB_REF, locator="release body",
                field="institutional context",
                quote="represents INA\u2019s first investment in the sector"),
        # NDP company-reported AI deployment claim (exact qualified wording)
        a(subject=NDP, predicate="HAS_COMPANY_AI_DEPLOYMENT_CLAIM",
          object_literal="company-reported: NDP 'already supports advanced AI infrastructure deployments in the region' — a company marketing/positioning claim about the campus; NOT verified specific workloads; distinct from Kabil's 'AI-ready' design framing",
          claim_time="2026-04-17", time_precision="day", certainty="reported", evidence_kind="verbatim",
          source_ref=DAYONE_PPA_REF, locator="release body", field="ai deployment claim",
          quote="Building on the foundation established in Nongsa, which already supports advanced AI infrastructure deployments in the region, KITP advances both scale and capability."),
        # correction record
        ClaimIn(subject_key="project:dayone-kabil-batam", subject_type="project",
                predicate="CORRECTION_RECORD",
                object_literal=("Supervisor source audit 2026-10-31: UOB primary bank release added "
                                "(proceeds allocated to three NDP data centres; no Kabil mention); "
                                "present-Kabil-power-delivery 'FALSIFIED' verdict DOWNGRADED to "
                                "'planned at announcement; actual delivery unverified' (a 2026-27 "
                                "phase may have begun by now); NDP 'already supports advanced AI "
                                "infrastructure deployments' recorded as a company-reported claim "
                                "without workload inference. Prior claims preserved."),
                certainty="inferred", review_status="machine_extracted",
                evidence_kind="analyst_synthesis",
                source_ref=ANALYSIS, locator="supervisor_correction", field="correction record",
                quote="The assertion that present Kabil power delivery is FALSIFIED by a phased 2026-27 plan is invalid: at the current date a phase might have begun; say planned at announcement, actual delivery unverified unless sourced."),
    ]
    # ---- operator + GDS relationship (evolving characterisations coexist) ----
    C += [
        ClaimIn(subject_key="project:dayone-kabil-batam", subject_type="project",
                predicate="HAS_OPERATOR", object_key="org:dayone", object_type="organization",
                object_literal="DayOne ('its new data center campus' \u2014 company release; 'DayOne is currently developing a data center at the Kabil Industrial Tech Park' \u2014 DCD)",
                claim_time="2026-04-17", time_precision="day", certainty="reported",
                evidence_kind="verbatim",
                source_ref=DAYONE_PPA_REF, locator="release body", field="operator",
                quote="for DayOne Kabil Industrial Tech Park (KITP), its new data center campus located in Kabil Integrated Industrial Estate (KIIE), Batam"),
        ClaimIn(subject_key="org:dayone", subject_type="organization",
                predicate="HAS_GDS_RELATIONSHIP_CLAIM",
                object_literal="EVOLVING/CONTESTED characterisations coexist as dated claims: 'GDS spin-out' / 'the international unit of Chinese data center operator GDS' (DCD, Jun 2025) vs rebranded 'independent company' with outside investors (SoftBank Vision Fund, Kenneth Griffin, Coatue, Baupost) and 'GDS Holdings retains a stake/backing' (transcript, 2026). Current equity/control relationship NOT established.",
                claim_time="2025-06-08", time_precision="day", certainty="reported",
                evidence_kind="verbatim",
                source_ref=DCD_LOAN_REF, locator="article body", field="gds relationship",
                quote="DayOne is the international unit of Chinese data center operator GDS. The company rebranded its Singapore-based international unit at the beginning of this year and has secured outside investment from the likes of SoftBank Vision Fund, Citadel CEO Kenneth Griffin, Coatue Management, and Baupost Group."),
        ClaimIn(subject_key="org:dayone", subject_type="organization",
                predicate="HAS_IDENTITY_LIMITATION",
                object_literal=("PT Digitalland Service One is reported (transcript only) as the "
                                "Indonesian PPA signatory; the corporate chain between DayOne "
                                "(Singapore) and PT Digitalland Service One is NOT established"),
                certainty="inferred", review_status="machine_extracted", evidence_kind="analyst_synthesis",
                source_ref=ANALYSIS, locator="sources: PLN Batam transcript", field="identity",
                quote="PLN Batam ... and DayOne (PT Digitalland Service One) signed the PJBTL of 511 MVA"),
        ClaimIn(subject_key="org:dayone", subject_type="organization",
                predicate="HAS_INVESTMENT", object_literal="Series C US$2.0+B reported (Jan 2026, transcript, unfetched); outside investors incl. SoftBank Vision Fund, Kenneth Griffin, Coatue, Baupost (DCD)",
                claim_time="2026-01", time_precision="month", certainty="reported",
                evidence_kind="paraphrase", source_ref=ANALYSIS,
                locator="sources: DayOne/GDS rebrand transcript", field="investment",
                quote="In January 2026, DayOne announced a US$2.0+ billion Series C raise, and it's reportedly pursuing a US listing (IPO valued around $5 billion)."),
        ClaimIn(subject_key="project:dayone-kabil-batam", subject_type="project",
                predicate="IS_AI_WORKLOAD", object_literal="NOT INFERABLE: 'AI-ready platform' and 'supports the rapid growth of cloud and AI workloads' are company design/positioning framings; no tenant or workload evidence",
                certainty="inferred", review_status="machine_extracted", evidence_kind="analyst_synthesis",
                source_ref=ANALYSIS, locator="sources: DayOne release passages", field="ai workload",
                quote="high-performance, AI-ready platform designed to support advanced computing workloads"),
        ClaimIn(subject_key="project:dayone-ndp-batam", subject_type="project",
                predicate="IS_AI_WORKLOAD", object_literal="NOT INFERABLE: no workload evidence for NDP; DBS executive's 'AI, cloud services' remark is market framing",
                certainty="inferred", review_status="machine_extracted", evidence_kind="analyst_synthesis",
                source_ref=ANALYSIS, locator="sources: DCD loan article DBS quote", field="ai workload",
                quote="solutions such as artificial intelligence, cloud services, and real-time processing"),
    ]
    return C


def main() -> None:
    d = build_dossier()
    (FINDINGS / "dayone_batam_investigation.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))

    eng = Engine(DB)
    eng.register_global_key("project:dayone-ndp-batam", "project", "dayone-ndp-batam",
                            identifier="engine-case:dayone-ndp-batam")
    eng.register_global_key("project:dayone-kabil-batam", "project", "dayone-kabil-batam",
                            identifier="engine-case:dayone-kabil-batam")

    inputs = content_hash({
        "dossier": canonical(d),
        "fetch_log": (RAW / "dayone_fetch_log.json").read_text(),
        "dcd_loan": file_sha256(RAW / "dayone_dcd_loan_article.html"),
        "dcd_ppa": file_sha256(RAW / "dayone_dcd_ppa_article.html"),
        "dayone_ppa": file_sha256(RAW / "dayone_dayone_ppa_release.html"),
    })
    run_id = "run-" + inputs[:16]

    gfl = json.loads((RAW / "dayone_fetch_log.json").read_text())
    sources = [
        SourceIn(source_ref=DAYONE_PPA_REF, publisher="DayOne (dayonedc.com)",
                 license=DAYONE_LICENSE, source_type="company press release (primary)",
                 document_date="2026-04-17", access_status="fetched",
                 fetched_at_utc=gfl["dayone_ppa_release"]["attempted_at"],
                 raw_path=RAW / "dayone_dayone_ppa_release.html",
                 retrieval_attempts=_attempts("dayone_fetch_log.json", "dayone_ppa_release")),
        SourceIn(source_ref=UOB_REF, publisher="UOB Group (with DBS)", license=UOB_LICENSE,
                 source_type="bank newsroom release (primary, lender-attributed)",
                 document_date="2025-06-05", access_status="fetched",
                 fetched_at_utc=gfl["uob_release"]["attempted_at"],
                 raw_path=RAW / "dayone_uob_release.html",
                 retrieval_attempts=_attempts("dayone_fetch_log.json", "uob_release")),
        SourceIn(source_ref=DCD_LOAN_REF, publisher="Data Center Dynamics", license=DCD_LICENSE,
                 source_type="secondary reporting (quotes company statements)",
                 document_date="2025-06-08", access_status="fetched",
                 fetched_at_utc=gfl["dcd_loan_article"]["attempted_at"],
                 raw_path=RAW / "dayone_dcd_loan_article.html",
                 retrieval_attempts=_attempts("dayone_fetch_log.json", "dcd_loan_article")),
        SourceIn(source_ref="https://www.datacenterdynamics.com/en/news/dayone-inks-450mw-ppa-with-pln-batam-to-power-planned-data-center-in-batam-indonesia",
                 publisher="Data Center Dynamics", license=DCD_LICENSE,
                 source_type="secondary reporting", document_date="~2026-04-20",
                 access_status="fetched", fetched_at_utc=gfl["dcd_ppa_article"]["attempted_at"],
                 raw_path=RAW / "dayone_dcd_ppa_article.html",
                 retrieval_attempts=_attempts("dayone_fetch_log.json", "dcd_ppa_article")),
        SourceIn(source_ref=NEWSROOM_REF, publisher="DayOne", license="n/a (not retrieved)",
                 source_type="company newsroom (guessed path)", access_status="missing",
                 fetched_at_utc=gfl["dayone_site_news"]["attempted_at"],
                 raw_path=RAW / "dayone_dayone_site_news.html",
                 retrieval_attempts=_attempts("dayone_fetch_log.json", "dayone_site_news")),
        SourceIn(source_ref="https://www.prnewswire.com/news/dayone/",
                 publisher="PR Newswire (DayOne room)", license="n/a (not retrieved)",
                 source_type="newsroom index (guessed path)", access_status="missing",
                 fetched_at_utc=gfl["dayone_prnews_index"]["attempted_at"],
                 raw_path=RAW / "dayone_dayone_prnews_index.html",
                 retrieval_attempts=_attempts("dayone_fetch_log.json", "dayone_prnews_index")),
        SourceIn(source_ref="websearch:transcript-2026-10-31:pln-batam-pjbtl",
                 publisher="Indonesian media (via WebSearch transcript)",
                 license=SEARCH_LICENSE, source_type="search transcript (unfetched)",
                 document_date="2026-04-24 to 2026-04-28 (per transcript)",
                 access_status="not_fetched",
                 raw_row={"summary": "PLN Batam and DayOne (PT Digitalland Service One) signed the 511 MVA PJBTL plus fiber MoU; Indonesian-language coverage; articles not fetched"}),
        SourceIn(source_ref="websearch:transcript-2026-10-31:dayone-gds-seriesc",
                 publisher="various (via WebSearch transcript)", license=SEARCH_LICENSE,
                 source_type="search transcript (unfetched)", document_date="2026-10-31",
                 access_status="not_fetched",
                 raw_row={"summary": "GDSI rebranded DayOne 2025-01-01; independent company; GDS retains stake/backing; Series C US$2.0+B Jan 2026; US listing pursuit"}),
        SourceIn(source_ref=ANALYSIS, publisher=ANALYST_BYLINE,
                 license="internal artifact (this project)", source_type="analysis artifact",
                 document_date="2026-10-31", access_status="fetched",
                 raw_path=FINDINGS / "dayone_batam_investigation.json",
                 retrieval_attempts=[{"ts": "2026-10-31", "outcome": "generated",
                                      "note": "generated by scripts/dayone_batam_investigation.py"}]),
    ]
    events = {}
    for src in sources:
        _, ev = eng.record_source(src, run_id)
        events[src.source_ref] = ev
    # not_present scoped to THIS script's prior source refs: other cases'
    # sources belong to their own ingests and must not be flagged as absent
    prior_own = {r[0] for r in eng.conn.execute(
        "SELECT DISTINCT se.source_ref FROM source_events se "
        "JOIN ingest_runs ir ON ir.run_id = se.run_id "
        "WHERE ir.script = ?", ("scripts/dayone_batam_investigation.py",))}
    not_present = sorted(prior_own - set(events))

    qv = quote_texts()
    qv[ANALYSIS] = json.dumps(d, ensure_ascii=False)
    n = eng.ingest_claims(dossier_claims(d), run_id, quote_verification=qv)

    # scoped orgs + identity limits
    eng.ensure_entity("organization", "dayone", scope=DCD_LOAN_REF)
    eng.ensure_entity("organization", "pln-batam", scope=DAYONE_PPA_REF)
    eng.ensure_entity("organization", "dbs", scope=DCD_LOAN_REF)
    eng.ensure_entity("organization", "uob", scope=DCD_LOAN_REF)
    eng.ensure_entity("organization", "ina", scope=DCD_LOAN_REF)
    # GDS relationship: the scoped gds-holdings entity from the GDS case stays
    # distinct from any DayOne-side mention (no merge without adjudication)
    contradictions = eng.detect_contradictions()
    det = eng.finish_run(run_id, script="scripts/dayone_batam_investigation.py",
                         inputs_hash=inputs,
                         sources_new=sum(1 for e in events.values() if e == "new"),
                         sources_changed=sum(1 for e in events.values() if e == "changed"),
                         sources_not_present=len(not_present), claims_ingested=n)
    eng.commit()
    print(json.dumps({"run_id": run_id, "claims": n,
                      "sources": {k[:52]: v for k, v in sorted(events.items())},
                      "not_present": not_present, "contradiction_groups": len(contradictions),
                      "deterministic_hash": det}, indent=1))


if __name__ == "__main__":
    main()
