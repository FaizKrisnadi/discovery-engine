# Research checkpoint: DayOne Batam campuses (Indonesia) — 2026-10-31

Question: **who finances, operates and supplies energy to DayOne's Batam data-centre infrastructure; what is known about control or dependency; which links cannot be established?** Dossier: [findings/dayone_batam_investigation.json](../findings/dayone_batam_investigation.json) (build: `scripts/dayone_batam_investigation.py`; 20 claims ingested; view: `/case/dayone-ndp-batam`, `/case/dayone-kabil-batam`). Full suite at time of writing: 152/152.

## CORRECTION (2026-10-31, after supervisor source audit — UOB primary release added)

The supervisor supplied the **original UOB bank release** (uobgroup.com, 5 June 2025, Singapore/Jakarta dateline) — a primary, lender-attributed document that the bounded search missed. Verified exact passages (snapshot retained, checksummed, quotes raw-verified):

- "DBS and UOB have jointly provided a landmark IDR 6.7 trillion (SGD 530 million) loan facility to finance the development of a new data centre campus in Batam, Indonesia."
- "The data centre project, jointly developed by Singapore-based data centre developer and operator DayOne and the Indonesia Investment Authority (INA)…"
- "Proceeds of the loan will be used to develop and operate **three data centres located in the Nongsa Digital Park (NDP)** in Batam." — the release contains **zero Kabil mentions**.
- "**Upon completion by end-2025**, the DayOne Nongsa Digital Park Data Centre campus will have a combined IT load capacity of around 72MW" (with market context: ~5% of projected 1.41GW national capacity by 2029).
- "**DayOne and INA have established a joint venture** to propel the growth and advancement of the data centre landscape in Indonesia." (JV structure/ownership split NOT stated.)
- "represents **INA's first investment in the sector**."

Effects on the findings: (1) the NDP financing claim is upgraded from secondary (DCD) to **primary bank-attributed** (DCD kept as corroboration); (2) Kabil financing remains **NOT ESTABLISHED** — re-affirmed by zero Kabil mentions in the release, with the explicit caveat that non-mention within one document is a bounded observation, not an exclusion; (3) the NDP supply schedule now distinguishes the **end-2025 completion target (bank-attributed)** from **operational status as of 2026-10-31 (UNVERIFIED)**; (4) NDP's "already supports advanced AI infrastructure deployments" is recorded as a **company-reported claim** — distinct from verified specific workloads and from Kabil's "AI-ready" design framing; (5) the two "FALSIFIED" verdicts were downgraded per the conservative policy — the Kabil-financing verdict to **NOT SUPPORTED** (proceeds allocated to NDP; no source allocates them to Kabil) and the present-supply verdict to **UNVERIFIED** (a 2026–27 phase may have begun delivering; the phased plan does not falsify present delivery). A `CORRECTION_RECORD` claim is ingested; all prior claims remain in the database.

---


- **A. DayOne Nongsa Digital Park (NDP) campus, Batam** — ~72MW combined IT load across three data centres; financed by the IDR 6.7 trillion (~US$412.1M) DBS/UOB loan (announced June 2025); first phase due live end-2025.
- **B. DayOne Kabil Industrial Tech Park (KITP) campus, Batam** — under development; PPA signed 2026-04-17 with PT PLN Batam (~511 MVA ≈ ~450 MW of **grid** capacity); supply in phases 2026–2027.
- These are the company's **first and second** Batam campuses per its own release ("its second hyperscale data center campus in Batam, following its flagship campus in Nongsa Digital Park").

## Answers (with status)

**Who finances it?** **NDP**: IDR 6.7 trillion (~US$412.1M) loan facility jointly provided by DBS and UOB (DCD, 2025-06-08, quoting the banks' announcement) — status: reported. **Kabil**: NOT ESTABLISHED — no Kabil-specific financing document retrieved; the DBS/UOB loan funds NDP per the source's own wording. **Company level**: Series C US$2.0+B reported (Jan 2026, transcript, unfetched); outside investors incl. SoftBank Vision Fund, Kenneth Griffin, Coatue, Baupost (DCD).

**Who operates it?** **DayOne** — company release ("its new data center campus", "its flagship campus"); DCD ("DayOne is currently developing a data center at the Kabil Industrial Tech Park"). The reported Indonesian contracting entity for the PPA is **PT Digitalland Service One** (transcript only). Status: reported.

**Who supplies energy?** **Kabil**: PT PLN Batam under the PPA — **~511 MVA ≈ ~450 MW of grid capacity, delivered via the grid in phases 2026–2027** (company release + DCD). Energy mix: **NOT STATED** in any source — no renewable claim may be inferred; supply is a future commitment, not current delivery. **NDP**: NOT ESTABLISHED — no NDP supplier/PPA document retrieved.

**Control or dependency?** DayOne is characterized in accessible sources as a **"GDS spin-out" / "the international unit of Chinese data center operator GDS"** (DCD, Jun 2025) that was **rebranded from GDS International on 2025-01-01** as an "independent company" with outside investors (SoftBank Vision Fund, Kenneth Griffin, Coatue, Baupost) and, per transcript, "GDS Holdings retains a stake/backing". These characterizations **coexist as dated claims and CONTEST each other on the current equity relationship** — NOT ESTABLISHED. Dependency facts: PLN Batam (state utility unit) is the Kabil PPA counterparty; **INA (Indonesia's sovereign wealth fund, wholly government-owned) is the reported NDP co-development partner (partnered 2023)**; BP Batam's facilitation role is company-stated. What is NOT known: GDS's current equity stake or governance rights over DayOne; the corporate chain between DayOne (Singapore) and PT Digitalland Service One; any lender security links.

## Falsification attempts (recorded as analyst-synthesis claims)

1. *"The PLN Batam PPA is renewable-energy supply"* — **FAILED TO CONFIRM**: both sources describe only "grid capacity"; no energy mix stated. VERDICT: NOT ESTABLISHED.
2. *"The DBS/UOB $412M loan finances the Kabil campus"* — **FALSIFIED for the specific attribution** (proceeds fund the three NDP data centres); with the explicit distinction that this does NOT exclude other Kabil financing — which remains NOT ESTABLISHED.
3. *"DayOne is fully independent of GDS Holdings"* — **CONTESTED/EVOLVING**: both characterizations kept as dated claims; current equity relationship unknown.
4. *"PPA signing means power is already flowing"* — **FALSIFIED**: "Power supply will be delivered in phases between 2026 and 2027".

## What a human must still review

1. Retrieve the Indonesian-language PLN Batam statements and, ideally, the PJBTL document to confirm instrument, counterparty entity (PT Digitalland Service One) and capacity.
2. Confirm the GDS Holdings–DayOne equity relationship from filings (GDS annual report / DayOne disclosures) before any control statement.
3. Verify NDP first-phase operational status from a dated source (due end-2025 per DCD; nothing retrieved).
4. Locate DayOne's own newsroom (dayonedc.com newsroom path; dayone.com 404) for the PPA release cross-check.
5. Adjudicate the scoped DayOne/GDS entity pairings in the engine (AI provisional).

## Access failures preserved

dayone.com/news (404) · PR Newswire DayOne room (404) · dayonedc.com newsroom path not found (only markets pages) · Indonesian PPA-signing coverage unfetched (no URLs in transcript).

## Limitations

AI-generated throughout (nothing human-verified); the DCD loan article is secondary reporting (now corroborated by the primary UOB release); the PPA rests on the company release plus DCD secondary reporting — the PJBTL document itself was not retrieved; English-language sources only, with Indonesian-language coverage known to exist unfetched; the bounded search does not establish absence beyond its universe; Kabil power delivery as of the current date is unverified rather than excluded.
