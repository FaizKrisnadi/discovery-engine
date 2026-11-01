"""Entity resolution: AidData financing records <-> GEM power plants.

Deterministic, candidate-preserving, human-labeled:
- For each AidData record we generate candidate project-name variants.
- We score them against every GEM plant of a matchable asset type
  (Coal Plant, Oil & Gas Plant, Bioenergy Plant) in Indonesia.
- We keep the top candidates with component scores; a separate, human-audited
  label file (data/labels/match_labels.json) decides actual matches.
- The matcher never merges: it only proposes. Ambiguity is preserved.

Capacity from the AidData title (e.g. "510MW") is treated as a *project-level
announced capacity* signal, compared against GEM plant-level sums. Unit-level
capacities are never used as a direct record-level match key.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
LABELS = ROOT / "data" / "labels"

MATCHABLE_TYPES = {"Coal Plant", "Oil & Gas Plant", "Bioenergy Plant"}

STOP_TOKENS = {
    "power", "station", "plant", "coal", "fired", "gas", "construction",
    "project", "complex", "phase", "unit", "mw", "gw", "kw", "the", "and",
    "of", "in", "for", "infrastructure", "ppp", "program", "programme",
}

CAP_RE = re.compile(r"(?P<cap>\d+(?:\.\d+)?)\s*(?P<unit>MW|GW|kW)\b", re.I)


@dataclass
class Candidate:
    gem_location_id: str
    gem_plant_name: str
    asset_type: str
    score: float
    name_score: float
    capacity_score: float
    province_score: float
    capacity_mw_gem: float | None
    capacity_mw_aiddata: float | None
    state_province: str


def name_variants(aiddata_title: str) -> list[str]:
    """Candidate project-name strings from an AidData title (conservative).

    Two orderings exist in AidData titles: capacity-then-name ("510MW Batang
    Toru ... Project") and name-then-capacity ("Palembang Timur 150MW Gas-fired
    Power Plant"). We generate variants covering both, plus compound names.
    """
    t = re.sub(r"\s*\(Linked to Records? ID#[\d,# ]+\)\s*$", "", str(aiddata_title))
    # the project phrase follows the last " for " in financing-clause titles
    seg = t.rsplit(" for ", 1)[-1] if " for " in t else t
    variants = {seg.strip(), CAP_RE.sub(" ", seg).strip()}
    # name may also precede the capacity token: keep the capacity-stripped
    # segment and the from-capacity-onward cut of the full title
    m = CAP_RE.search(t)
    if m:
        variants.add(t[m.start():].strip())
    out = set()
    for v in variants:
        out.add(v)
        cm = re.match(r"^(?P<head>.+?)\s+and\s+(?P<tail>.+?)\s+(?P<kind>(?:Coal-Fired|Gas|Hydro|Geothermal|Solar|Wind|Diesel)"
                      r"?[\w\s-]*?(?:Power Plant|power station|Power Station).*)$", v)
        if cm:
            head, tail, kind = cm.group("head"), cm.group("tail"), cm.group("kind")
            out.add(f"{head} {kind}")
            out.add(f"{tail} {kind}")
    return [v for v in out if len(v) >= 6]


def tokens(name: str) -> set[str]:
    n = name.lower()
    n = re.sub(r"[^a-z0-9\s]", " ", n)
    n = re.sub(r"\b\d+(?:\.\d+)?\s*(?:mw|gw|kw)\b", " ", n)
    return {t for t in n.split() if t and t not in STOP_TOKENS} - {""}


def digit_tokens(name: str) -> set[str]:
    return {t for t in tokens(name) if t.isdigit()}


def title_capacity_mw(title: str) -> float | None:
    m = CAP_RE.search(str(title))
    if not m:
        return None
    v = float(m.group("cap"))
    u = m.group("unit").lower()
    return v * 1000 if u == "gw" else (v / 1000 if u == "kw" else v)


def name_score(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    da, db = digit_tokens(a), digit_tokens(b)
    base = max(
        len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0,
        0.35 * fuzz.partial_ratio(a.lower(), b.lower()) / 100.0,
    )
    # unit numbers ("Phase 2" vs "Sulbagsel-2") must not drive a match:
    # disjoint unit numbers penalize; shared numbers alone cannot carry a match
    if da and db and not (da & db):
        base *= 0.5
    return base


def capacity_score(cap_a: float | None, cap_b: float | None) -> float:
    if cap_a is None or cap_b is None or cap_b == 0:
        return 0.5  # unknown: neutral, never decisive
    r = cap_a / cap_b
    if 0.9 <= r <= 1.1:
        return 1.0
    if 0.75 <= r <= 1.33:
        return 0.8
    if 0.5 <= r <= 2.0:
        return 0.5
    return 0.1


def province_score(prov_aid: str | None, prov_gem: str | None) -> float:
    if not prov_aid or not prov_gem:
        return 0.5
    return 1.0 if prov_aid.strip().lower() in prov_gem.strip().lower() else 0.3


def candidates_for_record(rec: dict, gem_plants: list[dict], top_n: int = 3) -> list[Candidate]:
    best: dict[str, Candidate] = {}
    for var in name_variants(rec["title"]):
        for p in gem_plants:
            if p["asset_type"] not in MATCHABLE_TYPES:
                continue
            ns = name_score(var, p["plant_name"])
            if ns < 0.2:
                continue
            # announced capacity in a title may cover one phase of a multi-unit
            # plant: compare against operating, planned and total buckets and
            # keep the best (documented in the candidate record)
            caps = p.get("capacity_mw_by_status") or {}
            bucket_caps = [caps.get("operating"), caps.get("planned"), p["capacity_mw_sum"]]
            cs = max(capacity_score(title_capacity_mw(rec["title"]), c) for c in bucket_caps)
            ps = province_score(None, p["state_province"])
            score = 0.65 * ns + 0.25 * cs + 0.10 * ps
            cand = Candidate(p["location_id"], p["plant_name"], p["asset_type"],
                             round(score, 4), round(ns, 4), round(cs, 4), round(ps, 4),
                             p["capacity_mw_sum"], title_capacity_mw(rec["title"]),
                             p["state_province"])
            if cand.gem_location_id not in best or cand.score > best[cand.gem_location_id].score:
                best[cand.gem_location_id] = cand
    cands = sorted(best.values(), key=lambda c: -c.score)
    return cands[:top_n]


def build_candidates() -> list[dict]:
    recs = json.loads((PROC / "aiddata_idn_energy.json").read_text())
    plants = json.loads((PROC / "gem_idn_plants.json").read_text())
    rows = []
    for rec in recs:
        cands = candidates_for_record(rec, plants)
        rows.append({
            "record_id": rec["record_id"],
            "title": rec["title"],
            "commitment_year": rec["commitment_year"],
            "status": rec["status"],
            "amount_nominal_usd": rec["amount_nominal_usd"],
            "funding_agencies_parent": rec["funding_agencies_parent"],
            "direct_receiving_agencies": rec["direct_receiving_agencies"],
            "candidates": [asdict(c) for c in cands],
        })
    return rows


def main() -> None:
    rows = build_candidates()
    (PROC / "match_candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    n_with = sum(1 for r in rows if r["candidates"] and r["candidates"][0]["score"] >= 0.55)
    print(f"records: {len(rows)}; with a >=0.55 top candidate: {n_with}")
    for r in rows:
        if r["candidates"]:
            c = r["candidates"][0]
            print(f"{r['record_id']} {c['score']:.2f} {c['name_score']:.2f}/{c['capacity_score']:.2f} "
                  f"-> {c['gem_plant_name'][:45]} ({c['capacity_mw_gem']}MW vs {c['capacity_mw_aiddata']}MW)")


if __name__ == "__main__":
    main()
