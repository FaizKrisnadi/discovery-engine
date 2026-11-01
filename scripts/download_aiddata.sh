#!/usr/bin/env bash
# Download + verify the AidData CLG-LMIC v1.0 zip (idempotent).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw
if [ ! -f data/raw/AidDatas_CLG_LMIC_Dataset_v1.0.zip ]; then
  curl -sL -o data/raw/AidDatas_CLG_LMIC_Dataset_v1.0.zip \
    "https://docs.aiddata.org/ad4/datasets/AidDatas_CLG_LMIC_Dataset_v1.0.zip"
fi
echo "sha256: $(shasum -a 256 data/raw/AidDatas_CLG_LMIC_Dataset_v1.0.zip | cut -d' ' -f1)"
echo "expected: 8d9dcfdaf2db9bc56e0587795e85264358d188cfbcf80ece9c2a66a66327af6e (2026-10-30 download)"
cd data/raw && unzip -o -q AidDatas_CLG_LMIC_Dataset_v1.0.zip -x "__MACOSX/*"
