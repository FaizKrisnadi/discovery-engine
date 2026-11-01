# Source registry (verified 2026-10-30 unless noted)

Statuses are from live checks performed during this milestone. "Verified" means: accessed successfully from this machine on the date shown, with the access method and terms recorded. Nothing here was bypassed; no authentication, CAPTCHA, paywall or security control was circumvented.

## Used in the pipeline

| Source | What it provided | Access (verified) | License / terms (verified) | Coverage & limitations |
|---|---|---|---|---|
| AidData, China's Loans and Grants to Low- and Middle-Income Countries, v1.0 (2025-11-18) | 23,816 financing records, 175 fields; 72 Indonesia ENERGY records used | Direct zip: `https://docs.aiddata.org/ad4/datasets/AidDatas_CLG_LMIC_Dataset_v1.0.zip` (32 MB; sha256 `8d9dcfda…`) | ODC-By 1.0, stated in the workbook's `License` sheet (quoted in data/raw) | Compiled secondary dataset (TUFF methodology, source-based). Record status ≠ plant status; syndicate members are separate rows; announcement ≠ disbursement; title capacities are announced, not built. No hydro/solar/wind split from titles. |
| GEM Ownership Tracing API (`https://api.globalenergymonitor.org/`) | 1,516 Indonesian assets (assets list), 26 location details for the matched sample | Documented unauthenticated API; page limit 500; Cloudflare rejects non-browser UAs — we used a descriptive custom UA and a one-time paged fetch (174 requests, logged in `data/processed/api_request_log.jsonl`) | CC BY 4.0, verified at `https://globalenergymonitor.org/creative-commons-license/` | Asset types: coal plants/mines, oil&gas plants, pipelines, bioenergy, iron&steel, cement. NO hydro/solar/wind/geothermal in this API. Unit grain (`location_id` × unit); ownership fields are current-state (build 2026-10-29). Some plants "to be determined" owners. |
| GLEIF API v1 (`https://api.gleif.org/api/v1`) | 15 targeted legalName queries; 18 LEI candidates | Documented, unauthenticated; `filter[entity.legalName]` exact-ish search; 20 cached requests | GLEIF data CC BY 4.0 (per GLEIF terms page) | Only overseas branches of Chinese policy banks surfaced (no HQ LEIs); zero hits for PLN and most Indonesian SPVs; name-collision trap: "China Development Industrial Bank" (Taiwan) ≠ China Development Bank. Relationship data = accounting consolidation, NOT beneficial ownership. |

## Checked, not used

| Source | Finding (verified this session) | Reason not used |
|---|---|---|
| GEM xlsx downloads (`globalenergymonitor.org/download-data`) | Downloads are gated behind a JS form posting to a Supabase presign endpoint; no static file link | API above provides the same data more accessibly; form-gated bulk download not needed |
| AidData GCDF v3.0 / other AidData datasets | Listed on aiddata.org/datasets | CLG-LMIC v1.0 supersedes for this question |
| OCCRP Aleph, ICIJ Offshore Leaks, OpenCorporates, OpenSanctions | Reviewed via public documentation pages only | Not asset/infrastructure-oriented for this question; not stress-tested this session — characterized from docs, not probes |

## Access discipline

- Robots/terms respected; descriptive User-Agent; one-time paged fetches with on-disk cache (`data/http_cache/`); every network request logged with URL, status and duration.
- API request volume to date: 174 GEM + 20 GLEIF + one AidData zip download (see `data/processed/api_request_log.jsonl`).
- No personal-data collection; entities are corporate/institutional.
- Usage reporting honesty: GEM/GLEIF do not expose per-key quotas for anonymous use; we report our own request log, not server-side usage.
