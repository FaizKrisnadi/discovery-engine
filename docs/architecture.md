# Architecture: from vertical slice to a public-interest intelligence platform

Date: 2026-10-30 (evening session). This document describes the long-term target and what the current vertical slice (`src/discovery/engine.py`, `scripts/engine_ingest.py`, `src/discovery/investigate.py`) already delivers, aligned with HANDOVER.md's mission: an evidence-driven discovery engine for institutional, commercial and infrastructure networks — now pointed at **the political economy of AI infrastructure in Southeast Asia**.

## Target platform (three planes)

1. **Evidence plane (this slice, runnable).** Versioned sources → observations (locator + verbatim quote) → dated claims (certainty, review status, time precision) → typed relations between entities. Content-addressed PKs; every assertion reversible to a source *version*. Contradictions grouped, never winner-picked. Identity via entities + alias table with explicit ambiguity (no silent merges). Temporal validity for ownership (from milestone 1) folds in as a claim attribute.
2. **Analysis plane (partially exists).** The milestone-1 matching/contradiction/discovery machinery (D1–D5) and the GEM/AidData/GLEIF pipelines become *engines over the same store*: matching emits `inferred` claims with review_status=machine_extracted; discovery queries read claims, not ad-hoc JSON.
3. **Interface plane (now runnable).** `investigate` CLI and a local read-only web interface (`scripts/serve_investigation.py`, 127.0.0.1 only, GET only, SQLite mode=ro) browse cases/organizations/sources, follow finance-energy-status links, render dated claims with exact provenance and review status, and surface unresolved identity candidates, unproven contradictions and explicit unknowns with accessible empty/error states. Next: cross-project views (sponsor groups, financiers, energy programmes), watch-mode diffs, then dashboards.

## What the vertical slice already does (demonstrable)

- `scripts/engine_ingest.py`: deterministic ingestion of **two independently sourced SEA data-centre cases** plus grid context into `data/processed/engine.sqlite3`:
  - **Case 1 — GDS Nusajaya NTP1 (Malaysia)**: AidData record 106768 + IJGlobal deal sheet + PR Newswire release + GDS official page (access failure preserved) + Google Maps URL (not fetched).
  - **Case 2 — AirTrunk JHB1 VPPA (Malaysia)**: ib vogt co-announcement (fetched), AirTrunk's own announcement (404/JS-index — access limit preserved), a July 2026 "project started" item (reported, unfetched, no URL).
  - **Grid context**: GEM-listed Peninsular operating subtotal with the `what_this_is_not` block carried into claims.
- 26 claims, 9 source refs, 2 unresolved contradiction groups (GDS status; GDS capacity 69.9 vs 54.00), explicit unknowns (renewable procurement not evidenced; physical supply not established; AI workloads not inferable).
- `investigate` CLI renders both projects' timelines with per-claim certainty/review/source-version/quote.

## Comparison with existing tools (why this is not a duplicate)

| Tool | Strength | Gap this engine addresses |
|---|---|---|
| OCCRP Aleph | document archive + entity extraction across leaks/filings | no claim-level temporality, no contradiction surfacing, no review-status lifecycle |
| ICIJ Offshore Leaks | curated leaked-network exploration | static snapshots; no source versioning or re-verification |
| OpenSanctions / OpenCorporates | entity screening / registry coverage | no project-level infra claims; no energy-claim modelling |
| AidData / GEM portals | authoritative datasets | portal views; no cross-dataset claims store; no per-claim provenance to *versions* |
| This engine | claim-level provenance, versioned sources, contradiction visibility, identity ambiguity, temporal validity | deliberately small evidence base so far — the niche is method, not yet coverage |

## Evidence-integrity rules (engine v0.3, supervisor-audited twice)

- **Quote fidelity**: `verbatim` observations are substring-verified against the cached original (raw bytes / extracted text / dataset row, whitespace-normalized) and store the verification result; `paraphrase` and `analyst_synthesis` are labelled as such.
- **Inference separation**: analyst inferences cite recorded analysis artifacts (`analysis:this-project:...`, themselves checksummed) — never a fetched source — and phrase absence as bounded-search findings ("not surfaced within the documented search; absence not established beyond it").
- **Raw versioning**: source versions hash RAW bytes (file sha256 or raw dataset rows), not derived annotations; retrieval attempts are recorded per source; `record_source` refreshes non-identity metadata (attempts, access status) without bumping versions when raw content is unchanged.
- **Access statuses**: `fetched | notice_page | missing | failed | not_fetched` — HTTP-200-but-wrong-content is `notice_page`, 404 is `missing`, error is `failed`.
- **Identity (v0.3)**: identifier-bearing entities are globally keyed on the identifier. Name-only mentions are **source-scoped**: the same name introduced by two sources yields two entities (identity_status='provisional_scoped'), so homonyms cannot silently merge. Merging is only ever additive via an explicit `adjudications` row (`same_entity`/`distinct_entities`/`unadjudicated`) with a disclosed decider; `same_entity_pks()` follows adjudications at query time without rewriting rows. Investigation projects carry disclosed engine-case identifiers (`engine-case:...`) — working keys, not registry ids.
- **Immutable snapshots (v0.3, serving hardened v0.5)**: every file-backed source version is copied at ingest into `data/evidence_snapshots/<checksum>/` (root confinement ENFORCED on serve: the resolved path must sit inside that root — symlink escapes and outside paths are refused 403 without reading); identical content shares one content-addressed snapshot. Retention is explicit: `snapshot_retained | referenced_only | not_retained`. Row/metadata hashes are labelled `checksum_basis='metadata_row'` — never presented as raw-content checksums. `/raw/<source_pk>` serves every snapshot as `application/octet-stream` (download, never same-origin HTML execution) and the server sends `X-Content-Type-Options: nosniff`; a v0.4 verification migration marked 9 regenerated-artifact versions honestly `not_retained` after finding their backfilled snapshots held another version's bytes.
- **Append-only retrieval history (v0.3)**: every fetch attempt is an immutable `retrieval_events` row (ts, outcome, details); attempts are never overwritten. The v0.2 `retrieval_attempts_json` column is deprecated and preserved only as migration backfill.
- **Contradictions**: single-valued predicates only; every group is `kind='possible'` (unproven) with a scope note recording date/unit/grain differences; differing claim_times are flagged as sequence candidates.
- **Adjudication policy (conservative, v0.5)**: adjudications are an **append-only event log** — every decision, including repeats and reversals, becomes a new row with its own author, basis, timestamp (or honest NULL for legacy rows) and sequence; `INSERT OR REPLACE` is gone, so prior authorship/basis is never overwritten. Supersession is latest-sequence-wins per unordered pair; all history remains queryable (`adjudication_history`) and the UI shows the full per-pair log. If the operative graph still asserts both `same_entity` and `distinct_entities` between reachable entities, NO merge is applied anywhere and the conflict stays unresolved. Resolution queries are strictly READ-ONLY — conflict recording is an explicit caller action (`record_identity_conflicts`), never a side effect of a query, and never commits caller transactions.
- **Snapshot correction (v0.4 migration)**: the v2→v3 backfill snapshotted historical versions from the CURRENT live file, which had already moved on for regenerated analysis artifacts; 9 rows falsely claimed retention. A verification pass compares every snapshot against its recorded checksum and marks mismatches `raw_retention='not_retained'` (explicit unavailability; the mismatched files remain on disk — no deletions). `/raw/<source_pk>` serves snapshot bytes only after re-verifying the checksum, and answers 404 with an honest explanation for unretained content.
- **Migration policy**: upgrades run in place via a sequential `PRAGMA user_version` chain (v0/v0.1→v2→v3) of `ALTER TABLE`/backfill steps; existing rows, source versions, snapshots, retrieval history and adjudications are preserved, and cross-run superseded claim variants are kept (the CLI deduplicates for display while counting them). Destructive resets are not part of the upgrade path — and none has occurred since the policy was adopted (the pre-policy losses are documented in PROGRESS.md).

## Data-access principles (unchanged)

Permitted access only (public APIs/downloads; form-gated downloads noted, not automated); descriptive UA; request log; licenses recorded per source (ODC-By, CC BY 4.0, copyright-with-attribution for press content); no publication; no contact; no paid services.

## Next milestones

1. **M2-A (coverage)**: ingest GEM solar/wind tracker xlsx after one manual form download (checksummed) → RE supply side as claims; ingest a second financier dimension (HKEX filings for listed operators — GDS 9698.HK disclosures are public regulatory documents) to test the filing adapter.
2. **M2-B (identity)**: sponsor-group resolution with the provisional-label discipline from milestone 1 (DayOne/GDS ambiguity is the worked example); GLEIF lookups as identifier claims.
3. **M2-C (monitoring)**: scheduled re-fetch of the 9 known source refs; version diffs surface `changed`/`not_present` events as watch findings (schema already supports it).
4. **M3 (analysis)**: port D1–D5 discovery queries to run over claims; emit findings only from adjudicated labels (gate: independent human review of a fresh sample, per docs/next_stage_decision.md).
5. **M4 (interface)**: cross-project views + watch dashboard only after M3 passes its gate.

Explicit non-goals until the evidence base earns them: no AI-workload inference from data-centre announcements; no physical-supply inference from green loans or VPPAs; no ownership claims from consolidation data; no universal-absence claims from limited searches.
