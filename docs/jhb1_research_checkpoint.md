# Research checkpoint: AirTrunk JHB1 (Johor, Malaysia) — 2026-10-31

## CORRECTION (2026-10-31, after supervisor source audit — supersedes parts of the original findings below)

The bounded search missed five accessible company-attributed documents. After fetching and inspecting them (all 200; snapshots retained and checksummed), the following findings CHANGE:

| Question | Original finding | Corrected finding (company-attributed, dated) |
|---|---|---|
| Who finances JHB1? | NOT ESTABLISHED | **Financed under AirTrunk's sustainability linked loan framework** (company statement, 7 Mar 2024: "JHB1 was financed under AirTrunk's sustainability linked loan framework"). Terms/lenders/amounts NOT stated. |
| Status | no dated primary source | **Operations commenced / official opening 30 Jul 2024** ("AirTrunk has commenced operations in Malaysia, following the official opening of its flagship Malaysian 150 megawatt (MW) hyperscale data centre in Johor Bahru, named AirTrunk JHB1"; initial phases over 50MW). |
| Who supplies energy? | NOT ESTABLISHED | **Partially established**: "AirTrunk worked with Malaysian utility company Tenaga Nasional Berhad (TNB) to connect JHB1" (30 Jul 2024) — TNB connected JHB1 per the company (connection ≠ supply-contract terms). Plus a **PLANNED 1MW rooftop-solar agreement** with Pekat Solar (20 Nov 2024: "will deliver 1 megawatt") — planned, not operational. |
| VPPA ↔ JHB1 link | "no accessible passage connects them" | **Superseded**: the FY24 Sustainability Report states the 30MW VPPA was signed "**to support JHB1's energy consumption**" / "for our JHB1 campus". This supports a *procurement-to-consumption* link. It does **NOT** establish direct physical supply from the solar farm to JHB1 (a VPPA is financial; no supply path is stated). The 30MW vs 29.99MW difference is rounding of the same farm. |
| Control | (Blackstone release not retrievable) | **Primary document retrieved**: Blackstone announced a **definitive agreement** (4 Sep 2024; buyer funds + CPP Investments named; sellers Macquarie Asset Management and the Public Sector Pension Investment Board; implied EV over A$24B) **subject to FIRB approval** — an agreement, **not a closing announcement**; completion remains secondary (deal tracker). |

**Unchanged:** no AI-workload evidence exists — "AI-ready" (design claim), "pivotal step in the adoption of AI" (CEO marketing) and "AI boom" (market narrative) are not workload evidence, and the IS_AI_WORKLOAD = NOT INFERABLE claim is re-affirmed. Physical supply from the solar farm remains unproven. The US$2.3B green loan still funds JHB2, not JHB1.

**Bookkeeping:** all five sources are ingested with snapshots and checksums; the correction is recorded in the engine as a `SUPERSEDES_PRIOR_FINDING` claim plus superseding claims; the earlier NOT-ESTABLISHED claims remain in the database (append-only history). The earlier ingest-run search history is preserved.

**Policy refinement (2026-10-31, after supersession audit):** supersessions are classified into three categories. (a) *Conclusion correction*: a newly-found source (the SLL statement) legitimately supersedes the earlier 'NOT ESTABLISHED' financing finding — kept. (b) *Refinement*: the physical-supply finding's basis was enriched (TNB connection, FY24 consumption-support wording) while the conclusion is unchanged — kept. (c) *Event evolution*: the Blackstone **agreement** (primary, 2024-09-04, subject to FIRB approval) and the later **reported closing** (secondary, deal tracker) are DIFFERENT DATED EVENTS THAT COEXIST — the 22 supersessions conflating them were **WITHDRAWN** (rows preserved with reason; both claims restored to current, each carrying its own date and source). Also made explicit: the JHB2 loan reporting **contradicts only** the claim that the US$2.3B loan finances JHB1; it does **not** contradict JHB1 financing in general — 'not established' and 'contradicted' are different statuses, and JHB1 financing is now positively established by the SLL statement.

**Supersession presentation (engine v0.6–v0.7):** supersession is now an explicit, source-backed, append-only mechanism (`supersessions` table: superseded claim → superseding claim, basis, recorded-by, recorded-at). Reader-facing surfaces (case pages, CLI walkthrough, claim detail) split claims into CURRENT vs SUPERSEDED — superseded variants are labelled "SUPERSEDED — historical claims, NOT current", link to their superseding claim and remain fully inspectable; contradiction rows they resolve are marked `resolved_by_supersession` instead of unresolved. For JHB1 this is live: HAS_FINANCING shows 1 current claim (SLL framework) + 9 superseded NOT-ESTABLISHED variants; IS_PHYSICAL_SUPPLY_OF shows 1 current claim (TNB-aware) + superseded variants; HAS_OWNER_REPORTED shows the corrected definitive-agreement framing. All presentation is AI-generated and unreviewed.

---

Question: **who finances, operates and supplies energy to this data-centre project; what is known about control or dependency; which links cannot be established?** Full dossier: [findings/jhb1_investigation.json](../findings/jhb1_investigation.json) (build: `scripts/jhb1_investigation.py`; 14 claims ingested as run `run-7b423d1c…`; view: `/case/airtrunk-jhb1`, `/case/airtrunk-jhb2`, `/case/airtrunk-ibvogt-solar-farm`).

## Answers (with status)

**Who finances it?** **JHB1-specific financing: NOT ESTABLISHED.** No accessible source records financing for JHB1 as an asset. The Jul 2026 **US$2.3B green loan** (30-lender syndicate; coordinated by 10 banks incl. Crédit Agricole, DBS, HSBC, SMBC, UOB — *ICD Nova, 2026-07-30, quoting a company statement that was not retrieved*) explicitly funds **JHB2** — a different building. Status: financing fact for JHB2 = reported (secondary quoting company statement); JHB1 financing = unknown.

**Who operates it?** **AirTrunk** — company statement: "our 150MW AirTrunk JHB1 data centre" (CTO quote, ib vogt release, 2024-03-05). Status: reported (company statement; no independent registry record consulted).

**Who supplies its energy?** **NOT ESTABLISHED.** (a) *Procurement*: AirTrunk announced a **VPPA** with ib vogt (29.99 MW solar farm, Malaysia's CGPP) — a **financial** instrument; the accessible passages never name JHB1 as the supplied facility. (b) *Physical supply*: no accessible source names JHB1's electricity supplier; grid connection is plausible but unevidenced here. (c) The green designation on the JHB2 loan is **efficiency-based** (targeted PUE 1.37), not a renewable-supply statement. (d) GEM's API contains no solar/wind assets — the 29.99 MW farm cannot be independently located there (coverage gap, not absence).

**Control or dependency?** **Ownership of the operator is reported**: a Blackstone-led consortium incl. CPP Investments (~12%) acquired AirTrunk (announced 2024-09-04; ~A$24B; reported closed late 2024 — secondary reporting + search transcript; **Blackstone's own release was not retrievable**: reconstructed URL 404). **Control is NOT established**: no accessible governance/decision-rights documentation. Dependency: the same corporate group sits on both facility and offtake sides — group-internal linkage, not third-party dependency.

**Which links cannot be established?** JHB1↔solar-farm supply; JHB1↔specific lenders; operator-ownership→energy-decision control; JHB1's grid supplier; JHB1's operational status from a dated primary source; any AI workload (market "AI boom" narrative in secondary reporting is not workload evidence).

## Falsification attempts (recorded in the engine as analyst-synthesis claims)

1. *"The VPPA supplies JHB1"* — **FAILED TO CONFIRM**: no accessible passage connects them; verdict NOT ESTABLISHED, strong claim rejected as unproven.
2. *"The US$2.3B green loan finances JHB1"* — **FALSIFIED** by the source's own wording ("to fund its JHB2 hyperscale facility").
3. *"Blackstone ownership = control over JHB1's energy arrangements"* — no evidence either way; NOT ESTABLISHED.
4. *"The 30-lender syndicate influences the VPPA/JHB1 operations"* — no accessible evidence; NOT ESTABLISHED (financing ≠ control).

## What a human must still review

1. Adjudicate all scoped identity pairs (AI provisional labels throughout; e.g., the two `bank-of-china-malaysia` scopes; AirTrunk entity scopes).
2. Retrieve Blackstone's 2024-09-04 release or the acquisition filing from a primary location before treating ownership as more than *reported*.
3. Fetch the Asian Power Jul 2026 article before repeating the solar-farm "started" claim (currently an unfetched headline).
4. Locate AirTrunk's Green Financing Framework and the JHB2 facility statement (primary) to check use-of-proceeds wording.
5. Independently confirm JHB1's operational status from a dated primary source (the company page is JS-rendered; no text extractable).

## Access failures preserved

AirTrunk newsroom VPPA announcement: HTTP 404 (guessed slug; JS-paginated index) · Blackstone release: 404 on reconstructed slug (variants not iterated per search rules) · The Asset ESG: SSL failure · airtrunk.com/jhb1/: 200 but JS-rendered, no extractable text · both 2026 search-transcript items: unfetched, no URLs.

## Limitations of this checkpoint

AI-generated throughout (nothing human-verified); English-language sources only; ICD Nova is secondary reporting quoting an unretrieved company statement; the investigation covers what a bounded search + four retrievals could reach — absence findings do not extend beyond that; entity resolution across scopes is provisional until human adjudication.
