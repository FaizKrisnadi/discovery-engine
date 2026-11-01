# Evidence schema (implemented in `data/processed/evidence_graph.json`)

Design rule: every assertion carries ≥1 evidence id; every evidence id resolves to a record quoting the exact source value, locator, license, source version and retrieval time. Test-enforced (`tests/test_pipeline.py::test_graph_evidence_integrity`).

## Entities (`entities[]`)

| type | id shape | fields | source |
|---|---|---|---|
| `financing_event` | `AID::<record_id>` | name (title), record_id | AidData CLG-LMIC v1.0 |
| `power_plant` | `GEM::<location_id>` | name, asset_type, state, wiki_url | GEM API |
| `organization` | `ORG::<normalized_name>` | name_origin ∈ {aiddata_financier, aiddata_receiver, gem_owner, aiddata_or_gem} | AidData / GEM (kept separate by origin; no auto-merge across sources) |
| `lei_record` | `LEI::<lei>` | legal_name, country | GLEIF |

Deliberate non-features: no fuzzy entity merging across sources; `ORG::` ids are normalized-name keys, so identical strings collapse only within a source's own vocabulary (documented aliasing risk: GEM "China Shenhua Energy Co Ltd" vs AidData "China Shenhua Overseas Development and Investment Co Ltd" stay distinct).

## Edges (`edges[]`)

| edge_type | meaning | claim_status | evidence |
|---|---|---|---|
| `FINANCING_EVENT` | self-edge carrying status, commitment year, amount, linked record ids, source URLs | documented | AidData row quote |
| `LENDER` | financier org → event | documented | AidData `Funding_Agencies_Parent` |
| `RECEIVER` | event → receiving org | documented | AidData `Direct_Receiving_Agencies` |
| `HAS_CAPACITY` | plant self-edge; capacity **by status bucket** (operating/planned/cancelled/retired) at unit grain | documented | GEM units quote |
| `PLANT_ATTRIBUTES` | plant self-edge; start_year (min + all units), status, owner, parent strings | documented | GEM `/locations/{id}` unit fields |
| `OWNER_OF` | org → plant, max unit-level share %, HQ country; carries a `validity` block | documented | GEM owners field |
| `OWNERSHIP_EVENT_REPORTED` | org → org, dated press-reported ownership event (e.g., Dec-2020 Datang–DSSP acquisition) | reported (portfolio-level; never plant-level validity evidence) | baseline-search references |
| `SAME_PLANT_AS` | event ↔ plant | **inferred (provisional AI label)** | both-side record quotes + label note |
| `HAS_LEI_CANDIDATE` | org → LEI candidate (multiple kept) | reported | GLEIF record quote |
| `GLEIF_QUERY` | org self-edge recording the query made | documented | query string |

## Evidence records (`evidence[]`)

`{evidence_id, source, source_version, license, locator, field, value, quote, url, retrieved_at}` — `quote` holds the exact text/JSON excerpt used; `locator` names the dataset record or API path; `url` links out where available.

## Interpretation layers (enforced vocabulary)

- **documented** — the value is stated by the cited dataset record (a secondary compiled dataset, not a primary document).
- **reported** — third-party identifier data (GLEIF candidates).
- **inferred** — produced by this system's matching; carries the provisional-label note; never auto-promoted.
- **unknown / unresolved** — explicit statuses in findings (`D5-identity-conflicts`); no silent winner when sources conflict (Parit Baru).

## What this schema deliberately does NOT claim

- GLEIF consolidation ≠ beneficial ownership (recorded on the GLEIF evidence license field).
- GEM parent/owner strings describe the API build date's state; they are not valid at earlier loan commitment dates without separate evidence.
- Announced title capacity ≠ built capacity; plant-level capacity sums ≠ project/phase capacity (unit buckets are kept separately for exactly this reason).

## Temporal validity (implemented in `src/discovery/temporal.py`, tested in `tests/test_temporal.py`)

Every `OWNER_OF` edge carries a `validity` block distinguishing observation from validity:

| field | meaning | value for GEM-snapshot edges |
|---|---|---|
| `observed_at` | when the source recorded/attested the relationship | `2026-10-29` (API build; preserved, ISO-validated) |
| `valid_from` / `valid_to` | source-dated interval | `null` — GEM supplies no ownership dates |
| `status` | `unknown` until source-dated evidence exists | `unknown` |
| `date_basis` | `none` / `source_dated` / `reported_event` | `none` |

`classify_at(claims, year)` actual semantics (each enforced by adversarial tests):

1. **Evidence discipline, fail closed** — dated use requires explicit `date_basis`, a traceable `locator`, a genuinely ISO-valid `observed_at` (not merely a four-digit prefix), integer year fields, and consistent intervals. `date_basis="none"` claims are excluded even if date-like fields are populated. Invalid claims (bad ISO, non-integer years, `valid_from=None` with `valid_to` set, inverted intervals, unattributed) are excluded with reasons; the result degrades to `unknown`, never an assertion. An invalid query year fails closed with `unknown`.
2. **Attestation horizon, both directions** — open-ended intervals, positive AND negative, are attested only through the year of `observed_at` (or `valid_to`); later years return `unknown` ("not extrapolated"). A stale observation (e.g., attested 2011) limits support accordingly.
3. **Absence ≠ negative evidence** — a start date after the query year or an interval ending before it returns `unknown`. `contradicted` requires explicit negative evidence: a `negative=True` claim with an **explicit holder**, whose scope covers the query year (source-dated interval, or a reported divestment event through its horizon). Boundary years of negative scopes are `unknown`.
4. **Co-ownership ≠ conflict** — different positive holders covering one year return `supported` with a co-ownership note; `conflicting` requires an `exclusive=True` claim contradicted by a different holder, or a positive and a negative claim about the SAME holder. Both claims preserved, no winner chosen.
5. **Reported events are point facts** — a reported acquisition never supports coverage of any year (interval inference would need source-dated interval evidence); a reported event carrying `valid_to` is rejected as malformed; a reported divestment (`negative=True`) likewise never yields `contradicted`: reacquisition can occur, so continuing non-ownership requires explicit continuing-negative evidence — a source-dated negative interval (which is still horizon-bounded).
6. **Year-only granularity** — boundary years (`year == valid_from`/`== valid_to`, or a reported-event year) return `unknown`; only strictly interior years can be `supported`.

D2 emits `temporal_support_per_loan` citing the traceable locator; on current data every pairing classifies `unknown` (e.g., Datang–DSSP vs the 2012 and 2016 commitments) — the honest result, not a gap.

**Recorded limits of the temporal model:** all year-level reasoning (month/day granularity parsed but not exploited); the horizon equals the observation year, which may under-claim for registry records that update continuously; exclusivity is per-claim and no source in this milestone asserts it; absolute ("no entity owned") negatives are out of scope — negative claims require a holder; re-acquisition after a reported divestment surfaces as same-subject conflict rather than being resolved; claims are reasoned over individually with no cross-claim aggregation or weighting; no date, holder or human review is fabricated anywhere on this path.
