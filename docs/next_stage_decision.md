# Next-stage decision (milestone 1)

Date: 2026-10-30. Decision: **PIVOT-NARROW before EXPAND** — one bounded second milestone, with human adjudication as the gate.

## What the experiment showed

1. The end-to-end loop works on real data: two heterogeneous public datasets + one identifier registry → evidence-linked, typed, dated relationships → five discovery queries → auditable output with negative cases. 12 integrity tests pass.
2. There is a real combined view that single datasets and one-shot search do not provide (financier↔plant↔sponsor-name structure with per-plant status). The headline candidate (D2) is plausible but rests on **name-string co-occurrence** and a **current-state ownership snapshot** — it is not yet a verified finding, and the temporal problem (2020 acquisition vs 2012/2015 loans) means the discovery logic must become time-aware before it can be trusted.
3. Quality is the binding constraint, not data volume: 25 of 72 records are structurally out of GEM's scope; the matcher needed human-in-the-loop additions for exactly the hard cases (unit-grain Suralaya, spelling variants, same-name different-phase Parit Baru); AI provisional labels cannot certify precision. Among the cases examined this session, no misleading connection is known to have survived unflagged — this is an observation about the examined cases, **not** an exhaustive audit of all 2,258 edges.

## Decision

- **Expand collection?** Not yet. More datasets before a human-adjudicated match-quality gate would scale unverified joins.
- **Pivot?** Narrow, not abandon: the defensible near-term product is a *time-aware cross-dataset link verifier* for Indonesian power assets — (a) independent human adjudication on a **fresh, unexposed sample**, (b) temporal scoping of ownership claims (as-of dating), (c) the five discovery queries re-run only on adjudicated matches.
- **Stop?** No: the failure modes found (grain, spelling, name collisions, status definitions) are exactly the ones an evidence-linked design is built to expose; no misleading connection is *known* to have survived its checks unflagged among the examined cases (qualified as above).

## Gate criteria for milestone 2 (pre-registered)

1. Draw a fresh sample from records whose matcher output has not been inspected, via a different process/agent, and have it independently human-adjudicated → top-1 precision ≥ 0.8 on adjudicated labels before any "discovery" claim is repeated. (The existing 10-record sample is development-exposed and cannot serve this purpose.)
2. Time-aware ownership: every sponsor/owner assertion carries a validity window or is marked unknown-at-time; D2 re-run must not use post-commitment acquisitions as commitment-time facts.
3. At least one finding from the adjudicated set that an ordinary-search baseline fails to surface, documented with the search transcript, before expanding beyond Indonesian power.
4. Expansion targets only if (1)-(3) pass: GEM xlsx trackers (hydro/geo/solar coverage), PLN/CPSE procurement documents, JPP/KEK licensing documents.

## Token & cost discipline (actuals)

- Model tokens: this milestone ran inside the session's own budget; no separate model-call metering was exposed by the harness (reported honestly as unknown; no bulk LLM extraction was used — all extraction is deterministic field parsing).
- Network: 174 GEM API requests, 20 GLEIF requests, 1 zip download, 3 web searches — all logged (`data/processed/api_request_log.jsonl`).
- No paid services used.
