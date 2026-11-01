"""Fetch Indonesian assets from GEM's public Ownership Tracing API.

Two stages, both cached and logged (data/http_cache, data/processed/api_request_log.jsonl):
  1. Page through /assets?country=Indonesia  -> data/raw/gem_idn_assets.json
  2. For every Coal Plant location, /locations/{id} (unit details incl.
     start_year, owner, parent, captive, status) -> data/raw/gem_idn_coal_locations.json

API root: https://api.globalenergymonitor.org/ (documented, no auth).
GEM data license: Creative Commons Attribution 4.0 (verified 2026-10-30 at
https://globalenergymonitor.org/creative-commons-license/).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery.http import cached_get_json  # noqa: E402

API = "https://api.globalenergymonitor.org"
RAW = ROOT / "data" / "raw"


def fetch_asset_list() -> list[dict]:
    out, offset = [], 0
    while True:
        d = cached_get_json(f"{API}/assets", params={"country": "Indonesia", "limit": 500, "offset": offset})
        out += d["results"]
        print(f"  /assets offset={offset} -> {len(d['results'])} (total {d['total']})", flush=True)
        if offset + 500 >= d["total"]:
            break
        offset += 500
    return out


def fetch_coal_locations(assets: list[dict]) -> list[dict]:
    coal_loc_ids = sorted({a["location_id"] for a in assets if a["asset_type"] == "Coal Plant"})
    print(f"coal plant locations: {len(coal_loc_ids)}", flush=True)
    locs = []
    for i, lid in enumerate(coal_loc_ids):
        locs.append(cached_get_json(f"{API}/locations/{lid}"))
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(coal_loc_ids)} locations fetched", flush=True)
    return locs


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    meta = {"fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "api": API, "license": "CC BY 4.0 (globalenergymonitor.org/creative-commons-license/)"}

    assets = fetch_asset_list()
    (RAW / "gem_idn_assets.json").write_text(json.dumps({"meta": meta, "results": assets}, ensure_ascii=False, indent=1))
    print(f"wrote gem_idn_assets.json ({len(assets)} assets)")

    locs = fetch_coal_locations(assets)
    (RAW / "gem_idn_coal_locations.json").write_text(json.dumps({"meta": meta, "locations": locs}, ensure_ascii=False, indent=1))
    print(f"wrote gem_idn_coal_locations.json ({len(locs)} plant locations)")


if __name__ == "__main__":
    main()
