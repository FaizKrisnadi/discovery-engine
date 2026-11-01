"""Targeted GLEIF enrichment for organizations central to the findings.

GLEIF relationship records capture accounting consolidation (reporting scopes),
NOT beneficial ownership. Every lookup is cached, logged, and keeps multiple
candidates; nothing is auto-merged.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if __name__ == "__main__" else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from discovery.http import cached_get_json  # noqa: E402

API = "https://api.gleif.org/api/v1"

# exact legal-name queries; names copied from AidData agency fields / GEM parents
QUERIES = {
    "Export-Import Bank of China (China Eximbank)": "Export-Import Bank of China",
    "China Development Bank (CDB)": "China Development Bank",
    "Industrial and Commercial Bank of China (ICBC)": "Industrial and Commercial Bank of China",
    "Bank of China (BOC)": "Bank of China Limited",
    "China Construction Bank Corporation (CCB)": "China Construction Bank Corporation",
    "China Shenhua Energy Co Ltd": "China Shenhua Energy Company Limited",
    "China Datang Overseas Investment Co Ltd": "China Datang Overseas Investment",
    "Power Construction Corporation of China Ltd": "Power Construction Corporation of China",
    "China Energy Engineering Corp Ltd": "China Energy Engineering Group",
    "Golden Concord Holdings Ltd": "Golden Concord Holdings",
    "PT Perusahaan Listrik Negara (Persero) (PLN)": "PT Perusahaan Listrik Negara",
    "PT Sumber Segara Primadaya": "PT Sumber Segara Primadaya",
    "PT DSSP Power Sumsel": "PT DSSP Power Sumsel",
    "PT Lion Power Energy": "PT Lion Power Energy",
    "PT Indo Raya Tenaga": "PT Indo Raya Tenaga",
}


def main() -> None:
    out = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
           "api": API,
           "license": "GLEIF data under CC BY 4.0 (gleif.org); relationship data = accounting consolidation, not beneficial ownership",
           "queries": {}}
    for key, q in QUERIES.items():
        d = cached_get_json(f"{API}/lei-records", params={"filter[entity.legalName]": q, "page[size]": 5})
        cands = []
        for rec in d.get("data", []):
            a = rec["attributes"]["entity"]
            cands.append({
                "lei": rec["id"],
                "legal_name": a["legalName"]["name"],
                "country": a["legalAddress"]["country"],
                "status": a.get("status"),
                "registration_status": rec["attributes"].get("registration", {}).get("status"),
            })
        out["queries"][key] = {"query": q, "candidates": cands}
        print(f"{key}: {len(cands)} candidates")
    (ROOT / "data/processed/gleif_enrichment.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("wrote data/processed/gleif_enrichment.json")


if __name__ == "__main__":
    main()
