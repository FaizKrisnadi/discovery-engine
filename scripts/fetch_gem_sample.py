"""Fetch GEM location details ONLY for the human-labeled matched plants.

Explicit sample (n=24), checkpointed via the HTTP cache; every request is
logged. No bulk crawling beyond this sample.
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

LOCATIONS = [
    "L100000102804", "L100000102707", "L100000102810", "L100000102708",
    "L100000102726", "L100000102732", "L100000102713", "L100000102782",
    "L100000102823", "L100000102835", "L100000102827", "L100000102697",
    "L100000102703", "L100000102792", "L100000102691", "L100000102806",
    "L100000102769", "L100000102767", "L100000102815", "L100000102699",
    "L100000102730", "L100000102711", "L100000407148", "L100000405286",
    "L100000102819", "L100000102690",
]


def main() -> None:
    locs = []
    for i, lid in enumerate(LOCATIONS):
        d = cached_get_json(f"{API}/locations/{lid}")
        locs.append(d)
        print(f"{i+1}/{len(LOCATIONS)} {lid} {d.get('asset_name')}")
    out = {"meta": {"fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                    "api": API,
                    "sample": "locations matched to AidData Indonesia energy records (human-labeled)",
                    "license": "CC BY 4.0 (globalenergymonitor.org/creative-commons-license/)"},
           "locations": locs}
    (ROOT / "data/raw/gem_idn_matched_locations.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("wrote data/raw/gem_idn_matched_locations.json")


if __name__ == "__main__":
    main()
