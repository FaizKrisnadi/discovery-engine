# Assessment: connecting AI infrastructure with renewable energy in Indonesia/SEA

Date: 2026-10-30. Machine-readable results: [findings/ai_infra_re_scan.json](../findings/ai_infra_re_scan.json) (reproduce: `.venv/bin/python scripts/ai_infra_re_scan.py`). Everything below distinguishes what was verified live this session from what news or documentation reports.

## The five layers, kept strictly separate

| Layer | Meaning | Reproducible public data found? |
|---|---|---|
| Announcement | a vendor/government says it will build/invest | Yes (news; not license-clean structured data) |
| Financing | a recorded loan/equity event for the infrastructure | **Yes — AidData CLG-LMIC v1.0** (ODC-By 1.0, verified in-workbook) |
| Operating facility | the facility exists and runs | Partial — for power plants only (GEM API); **no permitted reproducible registry of SEA data centers found** |
| Power procurement | the facility buys/certificates renewable electricity | **No** — PLN's tradable REC program exists (news-verified since ~2020: Jakarta Post 2020-01-28; Indonesia Business Post 2024-10; SolarQuarter 2025-09) but no public per-customer registry or volumes surfaced; I-REC registries are account/fee-gated |
| Physical supply | which generator physically serves the facility | **No** — no dataset inspected connects a data center to a specific generator; grid-level context is derivable (below) |

## Source paths assessed (verified this session unless noted)

1. **AidData CLG-LMIC v1.0** — INGESTED. 2,632 SEA records scanned by keyword (titles + narratives): 37 hits, of which the only literal data-center project is **record 106768 — GDS Nusajaya Tech Park Data Center Phase 1 (Johor, Malaysia): $272.12M syndicated green-labeled loan, Dec 2023 (BoC Malaysia, UOB, OCBC, StanChart)**, status `Completion`, sector COMMUNICATIONS, narrative quoting the facility agreement. Indonesia contributes 4G/5G network-expansion records (95638, 100676 — status `Pipeline: Commitment`, i.e., announcements) and one agriculture-AI lab record for Myanmar (100460). License ODC-By 1.0 (verified in workbook License sheet). Limitations: no procurement/energy fields; syndicate members duplicate rows; statuses lag reality.
2. **GEM Ownership Tracing API** — INGESTED for supply context. `country=Malaysia` → 232 assets saved to `data/raw/gem_malaysia_assets.json`. **GEM-API-listed Peninsular operating subtotal (API build 2026-10-29, state spellings normalized, Labuan excluded as East Malaysia): ~15,034 MW oil & gas (34 units), 12,200 MW coal (17 units), 105.2 MW bioenergy (8 units), plus 77.8 MW of operating units whose API state field is missing — reported as an explicit unassigned bucket, never dropped or guessed.** This is an INCOMPLETE subtotal of listed units, NOT a generation mix, NOT a grid-emissions factor, and NOT evidence of electricity supplied to any specific data centre. Coverage gap stated plainly: the API asset list contains **no solar, wind or hydro assets at all** — bioenergy is the only renewable class present. That is an API coverage gap, **not** evidence about Malaysian renewable capacity. License CC BY 4.0 (verified at GEM's Creative Commons page).
3. **GEM Global Solar/Wind Power Tracker xlsx** — ASSESSED, NOT ACCESSED. Downloads are gated behind a JavaScript form posting to a presign endpoint; no static file link exists. The license is stated CC BY 4.0, but I did not automate the form (that would circumvent the intended access path). This is the single highest-value next step for the physical-supply side: one manual download with recorded checksum would make the RE side reproducible.
4. **PLN tradable renewable energy certificates (REC)** — ASSESSED VIA NEWS ONLY. The mechanism exists (news-verified), and data-center operators in Indonesia use RECs for renewable claims; however web.pln.co.id was unreachable this session and no public per-customer REC registry or volume data was found. Without a registry, procurement claims are not verifiable from public data. No PLN license terms could be inspected — another blocker.
5. **Vendor/government announcements** (Microsoft's $1.7B Indonesia cloud/AI pledge 2024, NVIDIA–Indosat Solo AI region, Oracle, AWS $5B) — ASSESSED, NOT INGESTED: newsroom text is copyrighted and unstructured; useful only as the announcement layer.
6. **I-REC / international certificate registries** — account/fee-gated; not publicly reproducible without paid access (which is out of scope).

Identifiers that exist: AidData `AidData_Record_ID` (e.g., 106768) and GEM `location_id`/`asset_id`/`entity_id` on the power side. **No stable public identifier system for SEA data centers was surfaced in our limited search** — not proof of absence; the identifier layer remains the practical blocker for reproducible joins.

## Primary-source dossier (record 106768)

The four sources AidData links for the GDS record were fetched and audited (`scripts/gds106768_dossier.py` → [findings/gds106768_dossier.json](../findings/gds106768_dossier.json)): IJGlobal deal-sheet PDF (fetched, 3 pp.), PR Newswire release (fetched; dateline 08 Dec 2023, "provided by GDS"), GDS official news page (**access failure in substance** — returns a site notice template, article no longer served), Google Maps (not fetched; coordinates recorded as stated in the URL). Cross-checks: BoC tranche USD 68.03M (IJGlobal) matches the AidData row amount; total MYR 1.27B / USD 272.12M consistent across IJGlobal and the release. Disagreements kept visible: capacity 69.9 MW (title; company-stated IT power) vs 54.00 MW (IJGlobal field), instrument "Green Bond" vs "green term loan", and status (IJGlobal "Pre-construction"/"Financial close" vs AidData "Completion"). Green use-of-proceeds: asserted by participants, proceeds stated as construction completion; **no Green Loan Framework or second-party opinion among the sources**. Renewable procurement: **only a quoted 2030 aspiration and marketing language — no REC/PPA/on-site evidence**. AI workloads: not inferable and not inferred.

## Exploratory example built (one, deliberately small)

GDS Nusajaya DC Phase 1: layer 1 = AidData financing record with the *green-labeled loan* quoted from the narrative; layer 2 = GEM-listed Peninsular operating capacity subtotal as grid context (incomplete by construction; explicitly not a mix, not an emissions factor, not supply evidence). The scan's `non_claims` block states explicitly: no claim that the DC procures renewables (the loan is GREEN-LABELLED FINANCING, a loan-market label — not renewable-procurement evidence); no claim of physical supply from any plant; no generation-mix or emissions interpretation of the subtotal; the GEM API's missing solar/wind is a coverage gap, not evidence about Malaysian renewables. This example demonstrates the *shape* of an evidence-linked connection without fabricating the missing middle layers.

## Honest conclusion

The original goal — connecting AI infrastructure with renewable energy — is **not yet supported end-to-end by permitted reproducible public data** for Indonesia/SEA. What exists: the financing/announcement layer (AidData) and the physical-generation context (GEM, minus solar/wind/hydro in its API). What is missing: a licensed data-center registry (operating facilities), public REC/procurement registries (claims), and any supply-linkage data (physical). Building "connections" from what exists today would require exactly the leaps this project is designed to refuse.

## Runnable next-step plan

1. **Manual GEM solar/wind tracker download** (form + recorded checksum + download date) → adds the RE supply side for Peninsular Malaysia/Johor and Indonesia; then extend `gem_supply_context()` to compute RE share of operating capacity with the same discipline.
2. **PLN REC desk research**: request/locate the REC scheme regulation (PLN/ESDM peraturan) and any published aggregate issuance statistics; quote terms; if a public registry emerges, ingest as the claims layer.
3. **Data-center registry candidates** (assess licenses before use): national investment-agency project lists (BKPM/EDB/MIDA), stock-exchange disclosures of listed operators (GDS 9660.HK filings; DCI Indonesia; Princeton Digital via notes), municipal permits — each likely partial; document coverage honestly.
4. **Re-run this scan** after each addition: `scripts/ai_infra_re_scan.py` is the fixed entry point; new layers slot into the same five-layer frame with the same non-claim discipline.
5. Only when two layers meet with shared identifiers (e.g., a DC operator with both a financing record and a REC position) may a connection finding be emitted — via the same evidence-graph and provisional-label machinery used in milestone 1.
