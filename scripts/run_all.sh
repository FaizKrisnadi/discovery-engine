#!/usr/bin/env bash
# Reproduce the milestone-1 pipeline end to end.
# Raw downloads are cached: re-running hits the network only for cache misses.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH=src
PY=".venv/bin/python"

echo "== 1. raw data =="
if [ ! -f data/raw/AidDatas_CLG_LMIC_Dataset_v1.0.xlsx ]; then
  bash scripts/download_aiddata.sh
fi
if [ ! -f data/raw/gem_idn_assets.json ]; then
  .venv/bin/python scripts/fetch_gem.py
fi
if [ ! -f data/raw/gem_idn_matched_locations.json ]; then
  .venv/bin/python scripts/fetch_gem_sample.py
fi

echo "== 2. normalize =="
$PY -m discovery.normalize
echo "== 3. match =="
$PY -m discovery.matching
echo "== 4. labels =="
.venv/bin/python scripts/make_labels.py
.venv/bin/python scripts/make_heldout.py
echo "== 5. GLEIF =="
$PY -m discovery.gleif
echo "== 6. graph =="
$PY -m discovery.graph
echo "== 7. discover =="
$PY -m discovery.discover
echo "== 7b. AI-infra / RE scan (bounded next step) =="
.venv/bin/python scripts/ai_infra_re_scan.py
echo "== 7c. GDS 106768 primary-source dossier =="
.venv/bin/python scripts/gds106768_dossier.py
echo "== 7d. evidence engine ingest (two SEA DC cases + grid context) =="
.venv/bin/python scripts/engine_ingest.py
echo "== 7e. JHB1 source-grounded investigation =="
.venv/bin/python scripts/jhb1_investigation.py
echo "== 7f. DayOne Batam investigation (Indonesian case) =="
.venv/bin/python scripts/dayone_batam_investigation.py
echo "== 8. evaluate =="
$PY -m discovery.evaluate
echo "== 9. tests =="
$PY -m pytest tests -q

echo "DONE: findings/findings.json, findings/evaluation.json, data/processed/evidence_graph.json"
