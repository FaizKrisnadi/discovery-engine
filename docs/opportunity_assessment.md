# Opportunity assessment (milestone 1)

Date: 2026-10-30. Scope of evidence: live API/download checks on this date; documented-tool review via public pages. All claims below distinguish what was verified here from what is reported by others.

## Candidate problems examined

### A. Cross-dataset relationship discovery (chosen)

**Question:** do combined datasets reveal financing↔asset relationships (and sponsor-group structure) that neither dataset nor a single ordinary search exposes?

**Verified foundations (this session):**
- AidData "China's Loans and Grants to Low- and Middle-Income Countries" v1.0 (2025-11-18): 23,816 records, 175 fields, direct zip download, ODC-By 1.0 license stated in the workbook's License sheet (verified). 72 Indonesia ENERGY records, with financier/receiver agency fields and per-record source URLs.
- GEM Ownership Tracing API (documented, unauthenticated, `https://api.globalenergymonitor.org/`): 58,051 assets, 26,943 entities, 54,761 asset-ownership links; 1,516 Indonesian assets incl. 548 coal-plant units; per-unit owner/parent/`start_year`/`status` fields; CC BY 4.0 (verified at globalenergymonitor.org/creative-commons-license/).
- GLEIF API v1: unauthenticated LEI records (verified); relationship data = accounting consolidation, NOT beneficial ownership.

**Limitation honestly stated:** GEM's API asset types exclude hydro, solar, wind and geothermal — a large share of Chinese-financed Indonesian power (Batang Toru, Sorik Marapi, Wayang Windu, dams) is out of scope for matching. The matchable universe here is coal/oil&gas/bioenergy plants (174 coal plants in Indonesia).

### B. Institutional dependency discovery (deferred)

Agreements, permits and offtake chains behind an investment. Rejected for this milestone: requires primary documents (contracts, PPAs, PPA amendments) which were not accessible at the needed depth within the milestone window; AidData/GEM are secondary compiled datasets and cannot establish dependency structure alone.

### C. Temporal and contradictory-evidence discovery (partially adopted)

Status/date conflicts between datasets were adopted as a *discovery query* (D3/D5) rather than the headline product. A standalone "contradiction engine" was rejected for now: with two datasets the contradiction surface is thin (one resolved case: Parit Baru identity conflict; several benign status-lag cases) and both sources are updated on different schedules with different definitions.

## Why A: evidence

- The full pipeline ran on real data: 72 financing records, 1,009 GEM plant locations, 40 provisionally matched records (24 plants) with a candidate-preserving matcher, and five discovery queries producing auditable output.
- The strongest candidate finding (D2) — CDB loan records to two plants (Sumsel-5 2012; Kendari-3 2015) whose GEM-recorded current owner name is the same group (China Datang Overseas Investment / DSSP) — required joining equity-parent strings to loan rows; one ordinary web search surfaced the 2020 Datang–DSSP acquisition but not the loan-record structure. Limited evidence, reported as such (see docs/evaluation.md).
- Negative results are part of the case: GLEIF lookups showed HQ entities of Chinese policy banks are absent (only overseas branches have LEIs) and surfaced a dangerous name collision (China Development Industrial Bank, Taiwan ≠ China Development Bank); the Parit Baru candidate match was downgraded after a baseline search contradicted it.

## Existing tools considered (summary; details in source_registry.md)

| Tool | Does well | Gap exploited here |
|---|---|---|
| AidData CLG-LMIC | Chinese official finance events with agencies, amounts, source URLs | no asset-level status/ownership; no join to plant registries |
| GEM trackers/API | asset inventory with unit-level ownership/current status | no Chinese lending records; no event history |
| GLEIF | legal-entity identifiers, consolidation scopes | no coverage of Chinese bank HQs/Indonesian SPVs here; consolidation ≠ ownership |
| OCCRP Aleph / ICIJ Offshore Leaks | leaked/registered offshore structures, document search | not asset/infrastructure-oriented; no lending-to-asset join |
| OpenSanctions / OpenCorporates | screening, corporate registries | sanctions/registry focus; no infrastructure project linkage |

Full landscape verification was limited to what could be tested live in this session; platform capabilities are characterized from their documentation, not stress-tested.
