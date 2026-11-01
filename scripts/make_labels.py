"""Human-audited match labels for AidData<->GEM entity resolution.

Each label records the auditor's decision for one AidData record against the
matcher's top candidates. Labels are decisions, not algorithm output:
- MATCH: record's financed project corresponds to the named GEM plant.
- AMBIGUOUS: plausible candidate but evidence insufficient to merge.
- NOT_MATCH: all machine candidates judged wrong for this record.
- NOT_FOUND: the project plausibly has no representation in GEM's API data.
- NOT_APPLICABLE: not an asset (programme, facility line, metering project).

Every MATCH that the matcher itself did not rank first is marked
human_added=true with the reason; machine false positives are kept visible.
Capacity relationships are documented in notes; announced (title) capacity is
never treated as built capacity.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

L = {
    # --- precise matches (name + capacity coherent) ---
    62064: ("MATCH", "L100000102804", "Sumsel-1: 700MW announced = GEM operating 700MW."),
    69418: ("MATCH", "L100000102804", "Sumsel-1 syndicate member (same project as 62064)."),
    69419: ("MATCH", "L100000102804", "Sumsel-1 syndicate member (same project as 62064)."),
    61474: ("MATCH", "L100000102707", "Bengkulu: 200MW = GEM operating 200MW."),
    69306: ("MATCH", "L100000102707", "Bengkulu syndicate member."),
    62065: ("MATCH", "L100000102810", "Kendari-3: 100MW = GEM operating 100MW."),
    67236: ("MATCH", "L100000102708", "Adipala: 660MW = GEM operating 660MW."),
    105327: ("MATCH", "L100000102708", "Adipala syndicate member."),
    38610: ("MATCH", "L100000102726", "Pacitan: 630MW = GEM operating 630MW."),
    38611: ("MATCH", "L100000102732", "Tanjung Awar-Awar: 700MW = GEM operating 700MW."),
    62053: ("MATCH", "L100000102713", "Rembang: 630MW = GEM operating 630MW."),
    62206: ("MATCH", "L100000102782", "Tanjung Kasam: 130MW = GEM operating 130MW."),
    67699: ("MATCH", "L100000102823", "Kalbar-1 (coal): 200MW = GEM operating 200MW; gas namesake rejected."),
    62054: ("MATCH", "L100000102835", "Teluk Sirih: 224MW = GEM operating 224MW."),
    105325: ("MATCH", "L100000102835", "Teluk Sirih syndicate member."),
    39373: ("MATCH", "L100000102792", "Takalar: 200MW = GEM operating 200MW."),
    49810: ("MATCH", "L100000102691", "Celukan Bawang: announced 426MW = GEM operating bucket 426MW; GEM also lists 660MW cancelled units excluded from the match."),
    38600: ("MATCH", "L100000102819", "Pelabuhan Ratu 3x350MW = GEM operating 1050MW."),
    98549: ("MATCH", "L100000405286", "Palembang Timur: 150MW = GEM operating 150MW."),
    34992: ("AMBIGUOUS", None, "Parit Baru: name exact but ordinary-search baseline (2026-10-30) found NO public Eximbank buyer's credit for the GEM plant (gem.wiki/Parit_Baru_power_station: 2x50MW, revived ~2017, original units operational ~2020, expansion stalled; planned 100MW unit in GEM). AidData record (commit 2012, $132.1M, 'Completion') may refer to a different project/phase with the same name. Identity unresolved: no merge; both claims preserved."),
    88860: ("MATCH", "L100000407148", "Onur Sultan powership: name exact (Karadeniz); announced 250MW vs GEM 470MW fleet — flagged powership relocation/capacity ambiguity, kept at plant grain."),
    # --- matches with documented capacity revisions or phase/grain caveats ---
    38546: ("MATCH", "L100000102697", "Banten Lontar: announced 945MW (2005) vs GEM operating 1260MW (3x420); name exact; capacity revision documented, not asserted as built-from-title."),
    110270: ("MATCH", "L100000102697", "Banten Lontar syndicate member (Sichuan branch)."),
    62069: ("MATCH", "L100000102703", "Java-7: announced 2100MW vs GEM operating 1982MW (2x991); name exact."),
    39185: ("MATCH", "L100000102806", "Sumsel-5: announced 300MW vs GEM operating 300MW within a 650MW site (cancelled units 350MW); receiver PT DSSP Power Sumsel consistent."),
    39372: ("MATCH", "L100000102769", "Pangkalan Susu phase 1: announced 440MW; GEM site operating 840MW includes later non-Chinese expansion — phase-level caveat."),
    61681: ("MATCH", "L100000102767", "Labuan/Labuhan Angin spelling variant; announced 230MW = GEM operating 230MW (115MW cancelled unit excluded)."),
    34922: ("MATCH", "L100000102767", "Labuan/Labuhan Angin spelling variant; original 2003 tranche."),
    38606: ("MATCH", "L100000102815", "Jabar Indramayu phase 1: announced 990MW = GEM operating 990MW; 2000MW cancelled units at same site excluded."),
    100701: ("MATCH", "L100000102815", "Indramayu syndicate member."),
    100703: ("MATCH", "L100000102815", "Indramayu syndicate member."),
    100704: ("MATCH", "L100000102815", "Indramayu syndicate member."),
    100705: ("MATCH", "L100000102815", "Indramayu syndicate member."),
    # --- human-added matches where the machine's top candidate was wrong ---
    37864: ("MATCH", "L100000102699", "HUMAN-ADDED: 625MW Banten Suralaya project corresponds to GEM Unit 08 (625MW, operating) inside the 6025MW multi-decade site; plant-level sum must not be compared (machine top candidate compared totals)."),
    92603: ("MATCH", "L100000102699", "HUMAN-ADDED: 'Java 9 and Java 10' = GEM Banten Suralaya Units 09-10 (2x1000MW operating), announced 2GW; verified at unit grain from GEM unit list."),
    38604: ("MATCH", "L100000102730", "HUMAN-ADDED: 'Jatim Paiton Expansion' is the Paiton-3 project (announced 660MW; GEM operating 815MW = 2x407.5MW net); machine top candidate Pacitan was a false partial-token match."),
    34801: ("MATCH", "L100000102711", "HUMAN-ADDED: Cilacap Phase 1 — receiver 'PT Sumber Segara Primadaya (S2P)' and GEM plant name 'Cilacap Sumber'; announced 600MW phase vs 2260MW site total; capacity not asserted."),
    34748: ("MATCH", "L100000102711", "HUMAN-ADDED: Cilacap Phase 2 (S2P), same site; machine top Sulbagsel-2 was a unit-number false match."),
    61465: ("MATCH", "L100000102711", "HUMAN-ADDED: Cilacap Phase 3 (S2P); machine top Belawan was false."),
    69234: ("MATCH", "L100000102711", "HUMAN-ADDED: Cilacap Phase 3 syndicate member (BOC)."),
    # --- explicit negatives and non-merges ---
    61098: ("NOT_MATCH", None, "Batang Toru hydropower is outside GEM API plant types; machine top 'Perak power station' is a false capacity-driven match."),
    111094: ("NOT_MATCH", None, "Batang Toru syndicate member; see 61098."),
    95717: ("NOT_FOUND", None, "250MW Morowali captive plant has no same-name GEM plant; 'Bekasi'/'Riau 2' candidates false (IMIP captive possibly under different GEM naming — unverified)."),
    98823: ("NOT_FOUND", None, "Morowali syndicate member; see 95717."),
    62261: ("NOT_MATCH", None, "Sorik Marapi geothermal outside GEM API plant types; 'Riau 2' candidate false."),
    69599: ("NOT_MATCH", None, "Sorik Marapi geothermal; see 62261."),
    96237: ("NOT_IN_GEM", None, "Wayang Windu/Salak/Darajat geothermal equity acquisition — not GEM-API asset types."),
    62262: ("NOT_IN_GEM", None, "Star Energy Geothermal acquisition facility — not a GEM-API asset."),
    73327: ("NOT_IN_GEM", None, "Star Energy Geothermal acquisition facility."),
    109257: ("NOT_FOUND", None, "PT Medco E&P Malaka reserve-based lending; no corresponding GEM asset; also cancelled."),
    38601: ("AMBIGUOUS", None, "Meulaboh PP (220MW): GEM 'Nagan Raya power station' (670MW) is the same locality but capacity and naming do not align; not merged."),
    70718: ("NOT_FOUND", None, "Sinar Mas 2x150MW Musi Banyuasin mine-mouth plant: no corresponding GEM plant found."),
    105328: ("NOT_FOUND", None, "See 70718."),
    61533: ("NOT_FOUND", None, "East Lombok IPP 50MW: below GEM unit-threshold coverage; not present."),
    61675: ("NOT_FOUND", None, "Jeneponto 200MW (Bosowa): no corresponding GEM plant under this name."),
    105193: ("NOT_IN_GEM", None, "Asahan-1 hydro — outside GEM API plant types."),
    61152: ("NOT_IN_GEM", None, "Jenelata dam — outside GEM API plant types."),
    61153: ("NOT_IN_GEM", None, "Riam Kiwa dam — outside GEM API plant types."),
    61154: ("NOT_IN_GEM", None, "Pelosika dam — outside GEM API plant types."),
    67053: ("NOT_IN_GEM", None, "Bonehulu dam — outside GEM API plant types."),
    67055: ("NOT_IN_GEM", None, "Lompatan Harimau dam — outside GEM API plant types."),
    39375: ("NOT_IN_GEM", None, "Jatigede hydropower — outside GEM API plant types."),
    38861: ("NOT_IN_GEM", None, "Jatigede dam — outside GEM API plant types."),
    61050: ("NOT_APPLICABLE", None, "PLN 35,000MW programme facility line — not a single asset."),
    92462: ("NOT_APPLICABLE", None, "PLN 35,000MW programme facility line."),
    108809: ("NOT_APPLICABLE", None, "PLN 35,000MW programme facility line."),
    102646: ("NOT_APPLICABLE", None, "PLN $750M renewable-energy facility line — not a single asset."),
    102653: ("NOT_APPLICABLE", None, "PLN $750M renewable-energy facility line."),
    108276: ("NOT_APPLICABLE", None, "Advanced Smart Metering PPP — not a power plant."),
    108277: ("NOT_APPLICABLE", None, "Advanced Smart Metering PPP — not a power plant."),
}


def main() -> None:
    rows = json.loads((ROOT / "data/processed/match_candidates.json").read_text())
    machine_top = {r["record_id"]: (r["candidates"][0]["gem_location_id"] if r["candidates"] else None)
                   for r in rows}
    labels = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "auditor": "AI-generated provisional labels (lead agent, model-run). NOT human-verified, NOT independent ground truth; require human audit before any downstream use.",
        "label_status": "provisional",
        "leakage_note": ("Development-set leakage: matcher normalization was tuned while inspecting these same records; "
                         "these labels are development labels, not a held-out evaluation set. "
                         "The 10-record sample in data/labels/heldout_sample.json is RETROSPECTIVE "
                         "(drawn after the full candidate table was inspected) and provides no "
                         "independent validation; a fresh unexposed sample is required for that."),
        "labels": [],
    }
    for rec_id, (label, loc, note) in sorted(L.items()):
        mt = machine_top.get(rec_id)
        labels["labels"].append({
            "record_id": rec_id,
            "label": label,
            "gem_location_id": loc,
            "machine_top_location_id": mt,
            "human_added": bool(loc and loc != mt),
            "machine_top_wrong": bool(mt and loc and mt != loc) or bool(mt and not loc),
            "note": note,
        })
    (ROOT / "data/labels/match_labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1))
    from collections import Counter
    print(Counter(x["label"] for x in labels["labels"]))
    print("human-added matches:", sum(1 for x in labels["labels"] if x["human_added"]))
    print("machine-top-wrong:", sum(1 for x in labels["labels"] if x["machine_top_wrong"]))


if __name__ == "__main__":
    main()
