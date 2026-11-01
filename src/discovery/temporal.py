"""Temporal validity classification for ownership relationships.

Semantics (corrected after two supervisory reviews — these are the actual rules):

1. Evidence discipline. Only claims with an explicit date basis
   ("source_dated" or "reported_event"), a traceable locator, a valid ISO
   observation date, correctly typed year fields and internally consistent
   dates count as dated evidence. date_basis="none" claims have NO
   evidentiary dates even if date-like fields are populated. Invalid or
   unprovenanced claims fail closed: they are excluded with reasons and the
   classification degrades to UNKNOWN.
2. Open-ended intervals (positive or negative) stop at their attestation
   horizon: the year of observed_at, or an explicit valid_to. They are never
   extrapolated beyond it.
3. Absence of evidence is not evidence of absence. A start date after the
   query year, or an interval ending before it, yields UNKNOWN. CONTRADICTED
   is returned exclusively for explicit negative evidence: a negative=True
   claim (source_dated interval, or a reported divestment event) whose scope
   covers the query year.
4. Holders may be co-owners. Different positive holders covering one year are
   NOT conflicting unless a covering claim asserts exclusive ownership
   (exclusive=True). A positive claim and a negative claim about the SAME
   holder over the same period do conflict. Non-overlapping intervals are
   change over time, not conflict.
5. Year-only granularity is handled conservatively: boundary years
   (query == valid_from or == valid_to, or the event year of a reported
   event) return UNKNOWN; only strictly interior years can be SUPPORTED.
6. Reported events are point facts, not intervals. A reported acquisition
   never supports coverage of any year by itself (interval inference requires
   source-dated interval evidence). A reported divestment is likewise a point
   fact: it does NOT yield CONTRADICTED for later years, because reacquisition
   can occur — continuing non-ownership requires explicit continuing-negative
   evidence (a source-dated negative interval, not an event).

Matching elsewhere in this project remains provisional; nothing here
fabricates dates, holders or human review.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

SUPPORTED = "supported"
CONTRADICTED = "contradicted"
UNKNOWN = "unknown"
CONFLICTING = "conflicting"

DATE_BASES = ("none", "source_dated", "reported_event")
GRANULARITIES = ("year", "month", "day")


def _is_year(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_iso_date(x) -> bool:
    if not isinstance(x, str) or not x:
        return False
    try:
        datetime.fromisoformat(x.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class OwnershipClaim:
    """One ownership (or explicit non-ownership) assertion and its provenance.

    Dated use requires: explicit date_basis, traceable locator, valid ISO
    observed_at, integer year fields, and (for negative claims) an explicit
    holder. Reported events are point facts and must not carry valid_to.
    """
    source: str
    locator: str = ""                # traceable reference; required for dated claims
    observed_at: str | None = None   # ISO date(-time) the source attested the relationship
    valid_from: int | None = None    # source-dated interval or event year
    valid_to: int | None = None      # source-dated interval end; must be None for reported events
    date_basis: str = "none"         # none | source_dated | reported_event
    granularity: str = "year"        # year | month | day
    holder: str = ""                 # who holds (or, for negative claims, does not hold) ownership
    negative: bool = False           # explicit NON-ownership assertion
    exclusive: bool = False          # source asserts this holder is the SOLE owner of the interval

    def problems(self) -> list[str]:
        p: list[str] = []
        if not self.source:
            p.append("missing source attribution")
        if self.date_basis not in DATE_BASES:
            p.append(f"unknown date_basis {self.date_basis!r}")
        if self.granularity not in GRANULARITIES:
            p.append(f"unknown granularity {self.granularity!r}")
        if self.observed_at is not None and not _is_iso_date(self.observed_at):
            p.append("observed_at is not a valid ISO date")
        for nm, v in (("valid_from", self.valid_from), ("valid_to", self.valid_to)):
            if v is not None and not _is_year(v):
                p.append(f"{nm} must be an integer year")
        dated = self.valid_from is not None or self.valid_to is not None
        if self.date_basis == "none":
            if dated:
                p.append("dates supplied without an explicit date basis; they are not evidence")
            if self.negative:
                p.append("negative assertion requires a dated basis")
        else:  # source_dated or reported_event
            if not self.locator:
                p.append("dated claim without a traceable locator")
            if self.observed_at is None:
                p.append("dated claim without an observation date")
            if self.valid_from is None:
                p.append("dated claim requires valid_from")
            if (_is_year(self.valid_from) and _is_year(self.valid_to)
                    and self.valid_from > self.valid_to):
                p.append("inverted interval (valid_from > valid_to)")
            if self.date_basis == "reported_event" and self.valid_to is not None:
                p.append("a reported event is a point fact and cannot carry an interval end")
            if self.negative and not self.holder:
                p.append("negative assertion requires an explicit holder")
        return p

    def _horizon_year(self) -> int | None:
        """Year through which this claim attests its assertion (usable claims only)."""
        if self.valid_to is not None:
            return self.valid_to
        if self.observed_at and _is_iso_date(self.observed_at):
            return int(self.observed_at[:4])
        return None


def classify_at(claims: list[OwnershipClaim], year) -> dict:
    """Classify whether provenance-carrying dated evidence covers `year`.

    Fails closed: invalid query years, invalid claims and unprovenanced input
    degrade to UNKNOWN with an explanation rather than asserting anything.
    """
    if not _is_year(year):
        return {"status": UNKNOWN,
                "explanation": f"invalid query year {year!r}; refusing to classify"}

    usable, excluded = [], []
    for c in claims:
        pr = c.problems()
        (excluded.append((c, pr)) if pr else usable.append(c))

    def excluded_note() -> str:
        if not excluded:
            return ""
        parts = "; ".join(f"{c.source or 'unattributed'}: {'; '.join(pr)}" for c, pr in excluded)
        return f" excluded from reasoning: {parts}."

    positive_intervals = [c for c in usable if not c.negative and c.date_basis == "source_dated"]
    positive_events = [c for c in usable if not c.negative and c.date_basis == "reported_event"]
    negatives = [c for c in usable if c.negative]
    if not usable:
        return {"status": UNKNOWN,
                "explanation": ("no usable dated ownership evidence"
                                + (excluded_note() or " (no claims supplied)"))}

    covered: list[OwnershipClaim] = []       # interior of a source-dated interval
    boundary: list[OwnershipClaim] = []      # query on an interval/event edge (year granularity)
    beyond: list[OwnershipClaim] = []        # after interval end / attestation horizon
    before_start: list[OwnershipClaim] = []  # interval begins after the query year
    neg_covered: list[OwnershipClaim] = []   # interior of an explicit non-ownership scope
    undated: list[OwnershipClaim] = []       # usable but without any dates (e.g., snapshots)

    undated_usable = [c for c in usable
                      if not c.negative and c.date_basis == "none"]
    for c in positive_intervals:
        h = c._horizon_year()
        if year == c.valid_from or (c.valid_to is not None and year == c.valid_to):
            boundary.append(c)
        elif c.valid_from < year:
            if h is not None and year <= h:
                covered.append(c)
            else:
                beyond.append(c)
        else:
            before_start.append(c)

    for c in negatives:
        # explicit negative evidence must be a source-dated INTERVAL. A
        # reported divestment EVENT is a point fact: reacquisition can occur,
        # so it never supports continuing non-ownership by itself.
        if c.date_basis != "source_dated":
            continue
        h = c._horizon_year()
        # explicit negative scope: (valid_from, end] where end = valid_to or
        # attestation horizon; open-ended negatives never run past observation
        if c.valid_from < year and (h is not None and year <= h):
            neg_covered.append(c)
        elif year == c.valid_from:
            boundary.append(c)

    if covered:
        holders = {c.holder for c in covered if c.holder}
        same_subject_negatives = [c for c in neg_covered
                                  if c.holder and (not holders or c.holder in holders)]
        if len(holders) > 1 and any(c.exclusive for c in covered):
            return {"status": CONFLICTING,
                    "explanation": (f"an exclusive-ownership claim and a different holder are both "
                                    f"attested for {year} ({', '.join(sorted(holders))}); "
                                    "both claims preserved, no winner chosen" + excluded_note())}
        if same_subject_negatives:
            return {"status": CONFLICTING,
                    "explanation": (f"dated ownership and dated explicit non-ownership for the same "
                                    f"holder both cover {year}; both claims preserved, no winner chosen"
                                    + excluded_note())}
        holder_note = ""
        if len(holders) > 1:
            holder_note = (f"; holders {', '.join(sorted(holders))} may be co-owners — different "
                           "holders alone are not treated as conflict without explicit exclusivity")
        windows = "; ".join(f"{c.source} [{c.locator}]: {c.valid_from}-"
                            f"{'open' if c.valid_to is None else c.valid_to}" for c in covered)
        return {"status": SUPPORTED,
                "explanation": (f"source-dated ownership covers {year} ({windows})"
                                + holder_note + excluded_note())}

    if neg_covered:
        neg_desc = "; ".join(f"{c.source} [{c.locator}] holder {c.holder or 'unspecified'}"
                             for c in neg_covered)
        return {"status": CONTRADICTED,
                "explanation": (f"explicit continuing-negative evidence (a source-dated "
                                f"non-ownership interval) covers {year} "
                                f"({neg_desc})" + excluded_note())}

    if boundary:
        return {"status": UNKNOWN,
                "explanation": (f"{year} is a boundary year of source-dated interval(s)/event(s) at "
                                f"year-only granularity; within-year direction is unknown"
                                + excluded_note())}

    if positive_events:
        years = ", ".join(str(c.valid_from) for c in positive_events)
        return {"status": UNKNOWN,
                "explanation": (f"reported event(s) in {years} attest point facts, not validity "
                                f"intervals; interval coverage requires source-dated interval evidence"
                                + excluded_note())}

    if beyond:
        horizons = ", ".join(str(c._horizon_year()) for c in beyond)
        return {"status": UNKNOWN,
                "explanation": (f"ownership attested only through {horizons}; the interval is "
                                f"not extrapolated beyond its attestation period, so {year} is unknown"
                                + excluded_note())}

    if before_start:
        starts = ", ".join(str(c.valid_from) for c in before_start)
        return {"status": UNKNOWN,
                "explanation": (f"source-dated ownership begins {starts}, after {year}; a later start "
                                f"date alone is not evidence of non-ownership earlier"
                                + excluded_note())}

    if undated or undated_usable:
        undated = undated or undated_usable
        prov = "; ".join(f"{c.source} [{c.locator or 'no locator'}] as of "
                         f"{c.observed_at or 'unknown time'}" for c in undated)
        return {"status": UNKNOWN,
                "explanation": (f"{len(undated)} ownership assertion(s) without source-provided "
                                f"validity dates ({prov}); ownership at {year} is NOT established "
                                f"and is not inferred from the later snapshot" + excluded_note())}

    return {"status": UNKNOWN,
            "explanation": (f"no dated ownership evidence covers {year}; gaps between attested "
                            f"intervals are not evidence either way" + excluded_note())}
