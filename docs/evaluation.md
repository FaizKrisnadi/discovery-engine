# Evaluation & audit (milestone 1)

Machine-readable versions: `findings/evaluation.json` (metrics + baseline transcripts), `findings/findings.json` (all discovery output with claim statuses).

## 1. Entity resolution — what the numbers are and are not

- Labels are **AI-generated provisional labels** produced by the same agent that built the matcher. They are not human ground truth.
- The matcher's normalization was tuned while inspecting these same records: **development-set leakage**. Bias direction and magnitude are **unknown** — these are not "optimistic bounds".
- Denominators (from `evaluation.json.matching_metrics.denominators`):
  - 72 records labeled total (39 MATCH / 2 AMBIGUOUS / 4 NOT_MATCH / 7 NOT_FOUND / 11 NOT_IN_GEM / 7 NOT_APPLICABLE).
  - 10 records form a **retrospective sample that was exposed during development** (`data/labels/heldout_sample.json`): the full per-record candidate table for all 72 records was printed and read **before** the sample was drawn (an earlier version of this file falsely claimed otherwise; corrected after supervisory review, with the file's filesystem birth time 2026-10-30T06:09:08+0700 as the only verified timestamp). It is excluded from the metrics below only because its labels were written with knowledge of matcher output; **it provides no independent validation and cannot, even with future adjudication.**
  - AMBIGUOUS cases (Parit Baru, Meulaboh) are counted in **neither** precision nor recall.
- Provisional development numbers at top-1 threshold 0.55: 20 records proposed, 20/20 agreeing with labels; label-top3 coverage of matched 29/34. Unassessed: everything excluded above; no claim is made beyond these records, and none of these numbers is independent.

## 2. Candidate discoveries and audit

### D2-shared-sponsor-groups (headline candidate)

*Temporal handling (corrected semantics after two supervisory reviews):* `src/discovery/temporal.py` requires explicit date basis, traceable provenance, ISO-valid observation dates and integer year fields; `date_basis="none"` claims are excluded even if date-like fields are populated. Open intervals — positive and negative — stop at their attestation horizon; absence of evidence before a start or after an end is `unknown`; `contradicted` is reserved for explicit negative evidence with an explicit holder; co-ownership is not conflict without an `exclusive=True` claim; reported events are point facts, never intervals; invalid inputs and invalid query years fail closed; year-only boundary years are `unknown`. Every `OWNER_OF` edge carries `validity={observed_at: 2026-10-29, valid_from/to: null, status: unknown}` and D2 emits `temporal_support_per_loan` citing the locator — every current pairing classifies `unknown` (Datang–DSSP vs 2012/2016 commitments), the honest result. 28 adversarial tests cover the rules; recorded limits are listed in docs/evidence_schema.md.

### D1-shared-financiers
- Eximbank loans across 11 provisionally-matched plants, CDB 9, BOC 6, ICBC 6, CCB 3 — each row carrying GEM status/start-year and its match-basis caveat.
- Audit: the join itself is mechanical; value is the combined per-plant status/ownership view, which neither dataset provides. Baseline: not separately searched (limitation recorded); case-by-case search would likely surface individual links.

### D5-identity-conflicts (negative/ambiguous cases — kept visible)
- Parit Baru (rec 34992): machine candidate 0.82, initially labeled MATCH; baseline search found the GEM plant (2×50MW, operational ~2020, expansion stalled) with **no** Eximbank credit found in searched sources → **downgraded to AMBIGUOUS**, no merge, both claims preserved with sources. One search's absence is limited search results, not proof of non-existence.
- Meulaboh (rec 38601): GEM "Nagan Raya" is the same locality; capacity/naming do not align; not merged.

### D3-status-discrepancies
- Zero cases remain among accepted matches after the Parit Baru downgrade — reported honestly as an empty result. Status-lag nuance (AidData "Implementation" vs GEM operating for Sumsel-1, start 2025) is definitional, not a contradiction.

### D4-commitment-to-cod-gaps
- 37 dated pairs; largest coherent gaps: Sumsel-1 2017→2025 (8y), Adipala 2009→2015 (6y). Descriptive only; GEM start-year is unit-earliest; no causal claim.

## 3. Baseline comparison — what was actually done

Three targeted web searches (one per top finding) run by the agent on 2026-10-30 with the web-search tool, **not** a controlled human panel. Queries, retrieved references (clickable URLs), what was found/not surfaced, and verdicts are preserved verbatim in `findings/evaluation.json.baseline_searches`. Limitations statement (verbatim): one query each; does not bound what a persistent human investigator, a different engine, or Indonesian-language queries would find; "not surfaced" is not "does not exist"; partial overlap is not a novelty proof.

Single-dataset baselines: AidData alone lacks plant status/ownership; GEM alone lacks lending events; these are structural facts about the datasets, verified by field inspection.

## 4. Failures and weaknesses (recorded)

- Machine false positives in top-1 position on dev labels: e.g., Batang Toru→Perak (capacity-driven), Cilacap phases→Belawan/Jambi-1 (digit-token issue, since fixed), Jeneponto→Barru. All preserved in candidates file; fixes were developed **on** these records (leakage).
- GLEIF coverage for this population is poor (no HQ LEIs for Chinese policy banks; no LEIs for most Indonesian SPVs) plus a name-collision trap.
- GEM API excludes hydro/solar/wind/geo → 25 of 72 records structurally unmatchable.
- "machine-top-wrong: 26" in label stats includes syndicate siblings of the same wrong project (shared titles), so it overcounts distinct errors; denominators in evaluation.json are per-record.
