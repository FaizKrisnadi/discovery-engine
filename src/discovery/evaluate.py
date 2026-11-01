"""Evaluation: entity-resolution metrics (provisional AI labels; leakage makes
score direction and magnitude unknown) and candidate-discovery audits with the
ordinary-search baseline transcripts (exact queries, retrieved references).

Language discipline:
- A GEM plant record does not independently verify an AidData-to-GEM identity
  or a finance relationship; matched pairs rest on provisional AI labels.
- Ambiguous/unadjudicated cases are counted in neither precision nor recall;
  denominators and exclusions are stated.
- Absence from one web search is limited search results, not proof of novelty.
- GEM ownership/parent fields are current-state (API build 2026-10-29) and
  cannot be assumed to hold at a loan's commitment year.
- AidData and GEM records are secondary compiled datasets, not primary
  documents; underlying agreements were not inspected in this milestone.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if __name__ == "__main__" else Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
LABELS = ROOT / "data" / "labels"
FINDINGS = ROOT / "findings"


def match_metrics() -> dict:
    cands = {r["record_id"]: r for r in json.loads((PROC / "match_candidates.json").read_text())}
    lab = {x["record_id"]: x for x in json.loads((LABELS / "match_labels.json").read_text())["labels"]}
    heldout = set(json.loads((LABELS / "heldout_sample.json").read_text())["record_ids"])

    THRESH = 0.55
    ambiguous = {rid for rid, x in lab.items() if x["label"] == "AMBIGUOUS"}
    evaluable = {rid: x for rid, x in lab.items()
                 if x["label"] in ("MATCH", "NOT_MATCH") and rid not in heldout}
    matched = {rid for rid, x in evaluable.items() if x["label"] == "MATCH"}
    proposed = {rid for rid, r in cands.items()
                if r["candidates"] and r["candidates"][0]["score"] >= THRESH
                and rid not in heldout and rid in evaluable}
    tp = {rid for rid in proposed if cands[rid]["candidates"][0]["gem_location_id"]
          == lab[rid]["gem_location_id"]}
    fp = proposed - tp
    recall3 = {rid for rid in matched if any(c["gem_location_id"] == lab[rid]["gem_location_id"]
                                             for c in cands[rid]["candidates"])}
    human_added = {rid for rid, x in lab.items() if x.get("human_added") and rid not in heldout}
    return {
        "status": ("PROVISIONAL DEVELOPMENT NUMBERS. Labels are AI-generated (same model family as the "
                   "matcher's author) and the matcher's normalization was tuned while inspecting these "
                   "records; leakage and label error make the direction and magnitude of any bias unknown. "
                   "These are NOT unbiased estimates and NOT human-verified results."),
        "threshold_top1": THRESH,
        "denominators": {
            "total_labeled_records": len(lab),
            "label_distribution": {k: sum(1 for x in lab.values() if x["label"] == k)
                                   for k in sorted({x["label"] for x in lab.values()})},
            "retrospective_sample_excluded_not_a_clean_heldout": sorted(heldout),
            "retrospective_sample_note": ("This 10-record sample was drawn AFTER the full candidate table "
                                          "had been inspected during development (see "
                                          "data/labels/heldout_sample.json). It is excluded from the "
                                          "metrics below only because its labels were written with "
                                          "knowledge of matcher output; it provides NO independent "
                                          "validation and never can, even with future adjudication."),
            "excluded_from_pr_ambiguous_unadjudicated": sorted(ambiguous),
            "excluded_from_pr_not_applicable_or_not_in_gem_or_not_found":
                sorted(rid for rid, x in lab.items() if x["label"] in ("NOT_APPLICABLE", "NOT_IN_GEM", "NOT_FOUND")),
            "evaluable_for_pr": len(evaluable),
            "matched_records_in_pr_denominator": len(matched),
        },
        "top1_proposed": len(proposed),
        "top1_agreeing_with_labels": len(tp),
        "top1_disagreeing_with_labels": len(fp),
        "top1_agreement_with_provisional_labels": round(len(tp) / len(proposed), 3) if proposed else None,
        "label_top3_coverage_of_matched": (f"{len(recall3)}/{len(matched)}"),
        "label_top3_coverage_rate_provisional": round(len(recall3) / len(matched), 3) if matched else None,
        "false_agreement_examples": [
            {"record_id": rid, "machine_top": cands[rid]["candidates"][0]["gem_plant_name"],
             "labeled": lab[rid]["gem_location_id"], "note": lab[rid]["note"]}
            for rid in sorted(fp)][:8],
        "machine_missed_or_human_added_records": sorted(human_added),
        "required_next_step": ("Draw a genuinely fresh sample from unexposed records via a different "
                               "process/agent and have it independently human-adjudicated before any "
                               "quality claim is repeated."),
    }


BASELINE_SEARCHES = [
    {
        "finding": "D2-shared-sponsor-groups (China Datang / DSSP Sumsel-5 + Kendari-3)",
        "query": 'China Datang "DSSP Power" Sumsel Kendari Indonesia power plant loans',
        "conducted": "2026-10-30, web-search tool available to the agent; one query, not a controlled or exhaustive search",
        "references_retrieved": [
            "https://www.businesstimes.com.sg (China Datang $394M majority stake in DSS thermal plants, Dec 2020)",
            "https://www.caixinglobal.com (same acquisition coverage)",
            "https://www.datang-dsspower.co.id (PT Datang DSSP Power Indonesia corporate site)",
        ],
        "found": ("Publicly reported 2020 acquisition of a majority stake in Dian Swastatika Sentosa thermal "
                  "plants by China Datang (~$394M)."),
        "not_surfaced": ("Per-plant loan records (AidData: CDB for Sumsel-5, 2012; CDB for Kendari-3, 2015) "
                         "and the explicit two-plants-one-name-group structure were not surfaced by this query."),
        "verdict": ("PARTIAL OVERLAP ONLY. The acquisition is public knowledge; that specific prior loan "
                    "records tie CDB to two plants now under one parent group was not surfaced here. This "
                    "is limited evidence from one search, not proof of novelty. TEMPORAL CAVEAT: the 2020 "
                    "acquisition postdates both loan commitments; the sponsor relationship at commitment "
                    "time (2012, 2015) is NOT established by any source consulted."),
    },
    {
        "finding": "D5-identity-conflicts (Parit Baru)",
        "query": '"Parit Baru" power plant Kalimantan Eximbank buyer\'s credit status',
        "conducted": "2026-10-30, web-search tool; one query",
        "references_retrieved": [
            "https://www.gem.wiki/Parit_Baru_power_station (2x50MW Bengkayang plant; revived ~2017; original units operational ~2020; expansion stalled 2021)",
            "https://www.liputan6.com/bisnis/read/2892663/pln-lanjutkan-pembangunan-3-pltu-di-kalbar-yang-mangkrak (PLN reviving stalled Kalbar plants)",
            "https://www.suarakalbar.co.id/2021/07/pln-selesaikan-lakukan-first-year-inspection-pada-unit-2-pltu-parit-baru-site-bengkayang (Unit 2 inspection 2021)",
        ],
        "found": ("A 2x50MW Parit Baru plant in Bengkayang, revived ~2017 and operational ~2020; GEM API "
                  "shows planned 100MW + cancelled 100MW units with construction start 2033."),
        "not_surfaced": "No source connecting this plant to the AidData record's $132.1M Eximbank credit.",
        "verdict": ("CONFLICT with the provisional merge: identity between the AidData 'Parit Baru' record "
                    "and the GEM plant is NOT established. Label downgraded MATCH->AMBIGUOUS. One search's "
                    "failure to find a credit record is limited search results, not proof that none exists."),
    },
    {
        "finding": "Banten Suralaya unit-grain resolution (Java 9 & 10 = GEM Units 09-10)",
        "query": '"Java 9" "Java 10" Banten Suralaya coal plant units financing',
        "conducted": "2026-10-30, web-search tool; one query",
        "references_retrieved": [
            "https://www.thejakartapost.com/business/2023/09/14/green-groups-slam-world-bank-for-backing-indonesian-coal-plants (Java 9-10 ownership context)",
            "https://www.thejakartapost.com/business/2023/10/31/indonesia-to-omit-private-coal-power-plants-from-its-jetp-investment-plan (JETP exclusion, Oct 2023)",
            "https://www.linkedin.com/posts/trend_asia_from-banten-and-jakarta-to-all-over-indonesia-activity-7246811056327516161-ddz- (Trend Asia: IRT = Barito Pacific x PLN Indonesia Power JV)",
        ],
        "found": ("Java 9-10 CFPP at Suralaya owned by PT Indo Raya Tenaga (Barito Pacific x PLN Indonesia "
                  "Power JV); 2023 JETP/World Bank coverage."),
        "not_surfaced": ("The GEM unit-level mapping (Units 09-10 = 2x1000MW consistent with the announced "
                         "2GW) and AidData record 92603 (Bank of China participation in the $2.6B syndicate "
                         "to PT Indo Raya Tenaga)."),
        "verdict": ("PARTIAL OVERLAP ONLY; limited evidence from one search, not proof of novelty. "
                    "OWNERSHIP CAVEAT: GEM's plant-level owner (PT Indonesia Power Suralaya 100%) reflects "
                    "the multi-decade site; unit-level ownership of Units 09-10 was not resolved here and "
                    "is NOT asserted."),
    },
]


def main() -> None:
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matching_metrics": match_metrics(),
        "baseline_searches": BASELINE_SEARCHES,
        "baseline_limitations": (
            "Searches were run by the agent with a web-search tool on 2026-10-30 (one query each). "
            "They establish what one ordinary search surfaces for these specific phrasings on that date; "
            "they do not bound what a persistent human investigator, a different engine, or Indonesian-"
            "language queries would find. 'Not surfaced' is not 'does not exist', and partial overlap is "
            "not a novelty proof."),
    }
    (FINDINGS / "evaluation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    m = out["matching_metrics"]
    print("top1 agreement with provisional labels:", m["top1_agreement_with_provisional_labels"],
          f"({m['top1_agreeing_with_labels']}/{m['top1_proposed']});",
          "top3 coverage of matched:", m["label_top3_coverage_of_matched"])
    print("wrote findings/evaluation.json")


if __name__ == "__main__":
    main()
