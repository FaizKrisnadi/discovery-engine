"""Temporal validity tests (adversarial). Semantics under test:

- date_basis="none" never turns supplied dates into evidence
- open-ended intervals stop at their attestation horizon (no extrapolation)
- absence of evidence before a start / after an end is UNKNOWN, never
  CONTRADICTED; only explicit negative evidence yields CONTRADICTED
- distinct non-overlapping intervals are change over time, not conflict
- year-only granularity makes boundary years UNKNOWN
- invalid dates and missing provenance exclude a claim from reasoning
"""
from __future__ import annotations

import json
from pathlib import Path

from discovery.temporal import (OwnershipClaim, classify_at, SUPPORTED,
                                CONTRADICTED, UNKNOWN, CONFLICTING)

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / "findings"
PROC = ROOT / "data" / "processed"


def dated(valid_from=None, valid_to=None, observed="2026-06-01", holder="Holder A",
          source="registry X", locator="EVTEST1", granularity="year", negative=False,
          exclusive=False):
    return OwnershipClaim(source=source, locator=locator, observed_at=observed,
                          valid_from=valid_from, valid_to=valid_to,
                          date_basis="source_dated", granularity=granularity,
                          holder=holder, negative=negative, exclusive=exclusive)


# ---------- evidence discipline ----------

def test_basis_none_with_supplied_dates_is_not_evidence():
    c = OwnershipClaim(source="GEM", locator="EV1", observed_at="2026-10-29",
                       date_basis="none", valid_from=2010, valid_to=2020)
    assert any("not evidence" in p for p in c.problems())
    res = classify_at([c], 2015)
    assert res["status"] == UNKNOWN
    assert "excluded" in res["explanation"]


def test_dated_claim_requires_provenance():
    no_locator = dated(valid_from=2010, locator="")
    no_observed = dated(valid_from=2010, observed=None)
    for c in (no_locator, no_observed):
        assert c.problems(), "dated claim without provenance must be flagged"
        res = classify_at([c], 2015)
        assert res["status"] == UNKNOWN and "excluded" in res["explanation"]


def test_inverted_interval_is_invalid_and_excluded():
    c = dated(valid_from=2020, valid_to=2010)
    assert any("inverted" in p for p in c.problems())
    res = classify_at([c], 2015)
    assert res["status"] == UNKNOWN
    assert "inverted" in res["explanation"]


def test_unattributed_claim_is_excluded():
    c = dated(valid_from=2010, source="")
    assert any("source" in p for p in c.problems())
    assert classify_at([c], 2015)["status"] == UNKNOWN


# ---------- attestation horizon / open-ended intervals ----------

def test_open_interval_not_extrapolated_beyond_observation():
    c = dated(valid_from=2010, observed="2026-06-01")  # open end
    assert classify_at([c], 2015)["status"] == SUPPORTED      # interior, within horizon
    assert classify_at([c], 2026)["status"] == SUPPORTED      # horizon year itself is attested
    res = classify_at([c], 2030)
    assert res["status"] == UNKNOWN
    assert "not extrapolated" in res["explanation"]


def test_closed_interval_ends_at_stated_end_not_indefinitely():
    c = dated(valid_from=2010, valid_to=2020)
    assert classify_at([c], 2015)["status"] == SUPPORTED
    res = classify_at([c], 2025)
    assert res["status"] == UNKNOWN
    assert "not extrapolated" in res["explanation"]


def test_unparseable_observation_date_fails_closed():
    c = dated(valid_from=2010, observed="unknown date")
    res = classify_at([c], 2015)
    assert res["status"] == UNKNOWN
    assert "excluded" in res["explanation"] and "ISO" in res["explanation"]


def test_stale_observation_limits_open_ended_support():
    # attested in 2011 only: open interval may not be stretched to 2015
    c = dated(valid_from=2010, observed="2011-01-01")
    assert classify_at([c], 2011)["status"] == SUPPORTED
    res = classify_at([c], 2015)
    assert res["status"] == UNKNOWN
    assert "not extrapolated" in res["explanation"]


# ---------- absence of evidence vs explicit negatives ----------

def test_start_after_query_is_unknown_not_contradicted():
    res = classify_at([dated(valid_from=2021)], 2015)
    assert res["status"] == UNKNOWN
    assert "not evidence of non-ownership" in res["explanation"]


def test_interval_ending_before_query_is_unknown_not_contradicted():
    res = classify_at([dated(valid_from=2005, valid_to=2012)], 2015)
    assert res["status"] == UNKNOWN
    assert "not extrapolated" in res["explanation"]


def test_explicit_negative_interval_yields_contradicted():
    neg = dated(valid_from=2016, valid_to=2020, holder="Holder A", negative=True)
    assert classify_at([neg], 2018)["status"] == CONTRADICTED
    # boundary years of a negative interval are also conservative
    assert classify_at([neg], 2016)["status"] == UNKNOWN
    # before the negative interval there is no evidence either way
    assert classify_at([neg], 2015)["status"] == UNKNOWN


def test_negative_open_ended_respects_attestation_horizon():
    neg = dated(valid_from=2016, valid_to=None, observed="2026-06-01",
                holder="Holder A", negative=True)
    assert classify_at([neg], 2018)["status"] == CONTRADICTED
    assert classify_at([neg], 2026)["status"] == CONTRADICTED   # horizon year attested
    res = classify_at([neg], 2030)
    assert res["status"] == UNKNOWN                              # never past the horizon
    assert "boundary year" in classify_at([neg], 2016)["explanation"]


def test_negative_requires_explicit_holder():
    c = dated(valid_from=2016, valid_to=2020, holder="", negative=True)
    assert any("explicit holder" in p for p in c.problems())
    assert classify_at([c], 2018)["status"] == UNKNOWN


def test_negative_requires_dated_basis():
    c = OwnershipClaim(source="X", locator="EV2", observed_at="2020-01-01",
                       date_basis="none", negative=True)
    assert c.problems()
    assert classify_at([c], 2018)["status"] == UNKNOWN


# ---------- sequence vs conflict ----------

def test_sequential_intervals_are_change_not_conflict():
    a = dated(valid_from=2005, valid_to=2012, holder="Co A", locator="EV3")
    b = dated(valid_from=2014, valid_to=2020, holder="Co B", locator="EV4")
    assert classify_at([a, b], 2010)["status"] == SUPPORTED
    assert classify_at([a, b], 2019)["status"] == SUPPORTED
    # 2013 sits in the gap: after A's attested end, before B's start
    res = classify_at([a, b], 2013)
    assert res["status"] == UNKNOWN
    assert ("not extrapolated" in res["explanation"]) or \
           ("not evidence of non-ownership" in res["explanation"])
    # the same gap seen from only one side keeps the corresponding message
    assert "not extrapolated" in classify_at([a], 2013)["explanation"]
    assert "not evidence of non-ownership" in classify_at([b], 2013)["explanation"]
    assert CONFLICTING not in (classify_at([a, b], y)["status"] for y in (2010, 2013, 2019))


def test_co_ownership_is_not_conflict_without_exclusivity():
    a = dated(valid_from=2010, valid_to=2020, holder="Co A", locator="EV5")
    b = dated(valid_from=2010, valid_to=2020, holder="Co B", locator="EV6")
    res = classify_at([a, b], 2015)
    assert res["status"] == SUPPORTED
    assert "co-owners" in res["explanation"]
    # an exclusive-ownership claim plus a different holder DOES conflict
    ax = dated(valid_from=2010, valid_to=2020, holder="Co A", locator="EV7", exclusive=True)
    res2 = classify_at([ax, b], 2015)
    assert res2["status"] == CONFLICTING
    assert "no winner" in res2["explanation"]
    # two exclusive claims naming the same holder are consistent
    ax2 = dated(valid_from=2010, valid_to=2020, holder="Co A", locator="EV8", exclusive=True)
    assert classify_at([ax, ax2], 2015)["status"] == SUPPORTED


def test_positive_negative_overlap_depends_on_subject():
    pos = dated(valid_from=2010, valid_to=2020, holder="Co A", locator="EV9")
    neg_same = dated(valid_from=2010, valid_to=2020, holder="Co A", negative=True, locator="EV10")
    neg_other = dated(valid_from=2010, valid_to=2020, holder="Co B", negative=True, locator="EV11")
    assert classify_at([pos, neg_same], 2015)["status"] == CONFLICTING   # same holder
    res = classify_at([pos, neg_other], 2015)                            # different holder: consistent
    assert res["status"] == SUPPORTED


# ---------- reported events are point facts ----------

def test_reported_event_is_point_not_interval():
    ev = OwnershipClaim(source="press", locator="EV12", observed_at="2026-06-01",
                        valid_from=2020, date_basis="reported_event", holder="Co A")
    assert not ev.problems()
    for y in (2015, 2020, 2021, 2025):
        res = classify_at([ev], y)
        assert res["status"] == UNKNOWN, (y, res)
    assert "point facts, not validity intervals" in classify_at([ev], 2025)["explanation"]


def test_reported_divestment_is_not_continuing_negative_evidence():
    div = OwnershipClaim(source="press", locator="EV13", observed_at="2026-06-01",
                         valid_from=2020, date_basis="reported_event",
                         holder="Co A", negative=True)
    # a divestment EVENT never yields CONTRADICTED: reacquisition can occur;
    # continuing non-ownership needs explicit continuing-negative evidence
    for y in (2020, 2022, 2026, 2030):
        res = classify_at([div], y)
        assert res["status"] == UNKNOWN, (y, res)
        assert res["status"] != CONTRADICTED


def test_divestment_plus_explicit_interval_is_required_for_contradiction():
    div = OwnershipClaim(source="press", locator="EV13", observed_at="2026-06-01",
                         valid_from=2020, date_basis="reported_event",
                         holder="Co A", negative=True)
    interval = dated(valid_from=2020, valid_to=None, observed="2026-06-01",
                     holder="Co A", negative=True, locator="EV15")
    # only the source-dated negative INTERVAL carries the contradiction
    assert classify_at([interval], 2022)["status"] == CONTRADICTED
    assert classify_at([interval], 2030)["status"] == UNKNOWN   # still horizon-bounded
    # event alone stays unknown even alongside nothing else
    assert classify_at([div], 2022)["status"] == UNKNOWN


def test_reported_event_with_interval_end_is_rejected():
    ev = OwnershipClaim(source="press", locator="EV14", observed_at="2026-06-01",
                        valid_from=2020, valid_to=2024, date_basis="reported_event", holder="Co A")
    assert any("point fact" in p for p in ev.problems())
    assert classify_at([ev], 2022)["status"] == UNKNOWN


# ---------- fail-closed input validation ----------

def test_missing_valid_from_with_valid_to_does_not_crash():
    c = dated(valid_from=None, valid_to=2010)
    assert any("requires valid_from" in p for p in c.problems())
    res = classify_at([c], 2015)
    assert res["status"] == UNKNOWN
    assert "excluded" in res["explanation"]


def test_observed_at_must_be_valid_iso():
    for bad in (2026, "2026-13-45", "not a date", 20261029):
        c = dated(valid_from=2010, observed=bad)
        assert any("ISO" in p for p in c.problems()), bad
        assert classify_at([c], 2015)["status"] == UNKNOWN
    for good in ("2026-06-01", "2026-10-29T18:38:09+00:00", "2026-10-29T18:38:09Z"):
        assert not any("ISO" in p for p in dated(valid_from=2010, observed=good).problems()), good


def test_year_fields_must_be_integers():
    for bad in ("2010", 2010.5, True):
        c = dated(valid_from=bad)
        assert any("integer year" in p for p in c.problems()), bad
    c2 = dated(valid_from=2010, valid_to="2020")
    assert any("integer year" in p for p in c2.problems())


def test_invalid_query_year_fails_closed():
    claims = [dated(valid_from=2010, valid_to=2020)]
    for bad_year in ("2015", None, 2015.0, True):
        res = classify_at(claims, bad_year)
        assert res["status"] == UNKNOWN
        assert "invalid query year" in res["explanation"]


# ---------- year-only granularity ----------

def test_boundary_years_unknown_interior_supported():
    c = dated(valid_from=2010, valid_to=2020)
    assert classify_at([c], 2010)["status"] == UNKNOWN   # start boundary
    assert classify_at([c], 2020)["status"] == UNKNOWN   # end boundary
    assert classify_at([c], 2015)["status"] == SUPPORTED
    assert "boundary year" in classify_at([c], 2010)["explanation"]


# ---------- no evidence at all ----------

def test_empty_and_undated_inputs_are_unknown():
    assert classify_at([], 2015)["status"] == UNKNOWN
    snap = OwnershipClaim(source="GEM", locator="EV9", observed_at="2026-10-29", date_basis="none")
    res = classify_at([snap], 2015)
    assert res["status"] == UNKNOWN
    assert "not inferred" in res["explanation"] or "no usable" in res["explanation"]


# ---------- integration with the graph and D2 ----------

def test_graph_ownership_edges_carry_unknown_validity():
    g = json.loads((PROC / "evidence_graph.json").read_text())
    owners = [e for e in g["edges"] if e["edge_type"] == "OWNER_OF"]
    assert owners
    for e in owners:
        v = e["attributes"]["validity"]
        assert v["status"] == "unknown" and v["valid_from"] is None and v["valid_to"] is None
        assert v["observed_at"] == "2026-10-29" and v["date_basis"] == "none"
    assert "unknown" in owners[0]["statement"]


def test_d2_temporal_support_all_unknown_with_provenance():
    findings = json.loads((FINDINGS / "findings.json").read_text())
    d2 = next(f for f in findings if f["finding_id"] == "D2-shared-sponsor-groups")
    n = 0
    for group in d2["results"]:
        for plant in group["aiddata_financed"]:
            for pair in plant["temporal_support_per_loan"]:
                n += 1
                assert pair["ownership_at_commitment"] == UNKNOWN, pair
                assert "OWNER_OF edges" in pair["explanation"]  # traceable locator cited
    datang = next(g for g in d2["results"] if "Datang" in g["parent_name_as_recorded_by_gem"])
    recs = {pair["record_id"] for plant in datang["aiddata_financed"]
            for pair in plant["temporal_support_per_loan"]}
    assert {"39185", "62065"} <= recs
    assert n > 0
