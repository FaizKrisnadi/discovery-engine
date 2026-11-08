"""Reusable evidence engine (vertical slice, integrity-repaired): versioned
sources tracked by RAW checksums, observations split into verbatim quotes vs
analyst synthesis, entities requiring stable identifiers or explicit
provisional status, and contradiction groups labelled possible/unproven with
date/unit/grain scope notes.

Design invariants (test-enforced in tests/test_engine.py):
1. Attribution: every claim points to an observation, which points to a
   specific source VERSION. Claims carry evidence_kind:
     verbatim          - quote is verbatim source text (test-verified against
                         the cached original bytes where available)
     paraphrase        - faithful restatement, labelled as such
     analyst_synthesis - this project's own inference/synthesis; attributed to
                         a recorded analysis artifact, never to a fetched
                         source, and phrased as a bounded-search finding
2. Raw fidelity: source versions hash the RAW bytes (file checksum), not
   derived annotations. Fetched files are snapshotted IMMUTABLY under
   data/evidence_snapshots/<checksum>/ so a later overwrite of the live file
   cannot make prior evidence irretrievable; retention is explicit
   (snapshot_retained | referenced_only | not_retained) and row/metadata
   hashes are labelled checksum_basis='metadata_row' - never implied to be
   raw-content checksums. Retrieval history is APPEND-ONLY
   (retrieval_events): attempts are never overwritten or lost.
   access_status distinguishes fetched | notice_page | missing | failed |
   not_fetched.
3. Determinism: primary keys are content hashes of canonical JSON.
4. Identity: entities with a stable identifier are globally keyed on it.
   Name-only mentions are SOURCE-SCOPED: the same name from two different
   sources yields two distinct entities until an explicit adjudication row
   declares them the same (or distinct). Homonyms therefore cannot silently
   merge. All identity decisions are recorded with their decider.
5. Uncertainty: certainty (documented|reported|inferred), review_status
   (machine_extracted|human_verified - never fabricated), time precision.
6. Contradictions: only single-valued predicates group; every group is
   labelled kind='possible' (unproven) with a scope_note recording date,
   unit and grain differences; same-subject claims at different dates are
   temporal sequence candidates, not confirmed conflicts.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ENGINE_VERSION = "0.7.0"

CERTAINTY = ("documented", "reported", "inferred")
REVIEW = ("machine_extracted", "human_verified")
EVIDENCE_KIND = ("verbatim", "paraphrase", "analyst_synthesis")
ENTITY_TYPES = ("organization", "project", "facility", "person", "asset", "event", "analysis_artifact")
ACCESS_STATUS = ("fetched", "notice_page", "missing", "failed", "not_fetched")
IDENTITY_STATUS = ("identified", "provisional_name_only", "adjudicated")

# Predicates for which two distinct values about the same subject MAY be a
# contradiction. Multi-valued predicates (e.g., financing participants) never group.
SINGLE_VALUED_PREDICATES = {
    "HAS_RECORD_STATUS", "HAS_TOTAL_FACILITY_AMOUNT", "HAS_CAPACITY_CLAIM",
    "HAS_OPERATION_STATUS", "RENEWABLE_PROCUREMENT_STATUS", "IS_PHYSICAL_SUPPLY_OF",
    "IS_AI_WORKLOAD", "LOCATED_IN", "HAS_USE_OF_PROCEEDS", "HAS_GREEN_LABEL",
}


def canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(obj) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  source_pk TEXT PRIMARY KEY,
  source_ref TEXT NOT NULL,
  version_index INTEGER NOT NULL,
  raw_checksum TEXT,                   -- sha256 of RAW bytes/dataset row, not annotations
  raw_bytes INTEGER,
  raw_path TEXT,
  publisher TEXT, license TEXT, source_type TEXT,
  document_date TEXT,
  access_status TEXT NOT NULL,         -- fetched|notice_page|missing|failed|not_fetched
  retrieval_attempts_json TEXT NOT NULL DEFAULT '[]',  -- DEPRECATED v0.2 field; kept for migration
  fetched_at_utc TEXT,
  snapshot_path TEXT,                  -- immutable content-addressed copy of raw bytes
  raw_retention TEXT NOT NULL DEFAULT 'not_retained',
  checksum_basis TEXT NOT NULL DEFAULT 'metadata_row',  -- file_bytes|inline_bytes|metadata_row
  details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS retrieval_events (
  event_pk TEXT PRIMARY KEY,           -- hash(source_ref, ts, outcome, details)
  source_ref TEXT NOT NULL,
  ts TEXT NOT NULL,
  outcome TEXT NOT NULL,               -- fetched|http_404|notice_page|error|generated|not_attempted
  details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
  obs_pk TEXT PRIMARY KEY,
  source_pk TEXT NOT NULL REFERENCES sources(source_pk),
  locator TEXT NOT NULL,
  field TEXT NOT NULL,
  quote TEXT NOT NULL,
  evidence_kind TEXT NOT NULL,         -- verbatim|paraphrase|analyst_synthesis
  verified_against_raw INTEGER,        -- 1 if verbatim quote substring-matched cached raw text
  extractor_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
  entity_pk TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  name TEXT NOT NULL,
  identifier TEXT,                     -- stable external id (LEI, registry no, dataset key) if known
  identity_status TEXT NOT NULL,       -- identified|provisional_name_only|provisional_scoped|adjudicated
  scope TEXT                           -- introducing source_ref for name-only mentions ('global' otherwise)
);
CREATE TABLE IF NOT EXISTS entity_aliases (
  alias TEXT NOT NULL, entity_pk TEXT NOT NULL REFERENCES entities(entity_pk),
  status TEXT NOT NULL,
  observation_pk TEXT REFERENCES observations(obs_pk),
  PRIMARY KEY (alias, entity_pk)
);
CREATE TABLE IF NOT EXISTS adjudications (
  adjudication_pk TEXT PRIMARY KEY,
  entity_pk_a TEXT NOT NULL, entity_pk_b TEXT NOT NULL,
  decision TEXT NOT NULL,              -- same_entity | distinct_entities | unadjudicated
  basis_observation_pk TEXT,
  decided_by TEXT NOT NULL,
  decided_at TEXT,                     -- ISO time (NULL for legacy rows: rowid order governs)
  sequence INTEGER                     -- append-only order; supersession = higher sequence
);
CREATE TABLE IF NOT EXISTS claims (
  claim_pk TEXT PRIMARY KEY,
  subject_pk TEXT NOT NULL REFERENCES entities(entity_pk),
  predicate TEXT NOT NULL,
  object_pk TEXT REFERENCES entities(entity_pk),
  object_literal TEXT,
  claim_time TEXT,
  time_precision TEXT,
  certainty TEXT NOT NULL,
  review_status TEXT NOT NULL,
  evidence_kind TEXT NOT NULL,
  unit TEXT,
  grain TEXT,
  observation_pk TEXT NOT NULL REFERENCES observations(obs_pk),
  ingested_run TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relations (
  rel_pk TEXT PRIMARY KEY,
  subject_pk TEXT NOT NULL, predicate TEXT NOT NULL, object_pk TEXT NOT NULL,
  claim_pk TEXT NOT NULL REFERENCES claims(claim_pk)
);
CREATE TABLE IF NOT EXISTS contradictions (
  group_pk TEXT NOT NULL, claim_pk TEXT NOT NULL REFERENCES claims(claim_pk),
  kind TEXT NOT NULL DEFAULT 'possible',
  scope_note TEXT,
  resolution_status TEXT NOT NULL DEFAULT 'unresolved',
  PRIMARY KEY (group_pk, claim_pk)
);
CREATE TABLE IF NOT EXISTS ingest_runs (
  run_id TEXT PRIMARY KEY,
  script TEXT, engine_version TEXT,
  started_at_utc TEXT,
  inputs_hash TEXT NOT NULL,
  sources_new INTEGER, sources_changed INTEGER, sources_not_present INTEGER,
  claims_ingested INTEGER, deterministic_hash TEXT
);
CREATE TABLE IF NOT EXISTS source_events (
  event_pk TEXT PRIMARY KEY, source_ref TEXT NOT NULL, event TEXT NOT NULL,
  run_id TEXT NOT NULL, details_json TEXT
);
CREATE TABLE IF NOT EXISTS supersessions (
  supersession_pk TEXT PRIMARY KEY,
  superseded_claim_pk TEXT NOT NULL REFERENCES claims(claim_pk),
  superseding_claim_pk TEXT NOT NULL REFERENCES claims(claim_pk),
  basis TEXT NOT NULL,                      -- why the new claim supersedes the old
  evidence_claim_pk TEXT REFERENCES claims(claim_pk),  -- e.g. the correction record claim
  recorded_at TEXT NOT NULL,
  recorded_by TEXT NOT NULL,                -- always disclosed (AI-generated unless stated)
  status TEXT NOT NULL DEFAULT 'active'     -- active | withdrawn
);
CREATE TABLE IF NOT EXISTS adjudication_conflicts (
  conflict_pk TEXT PRIMARY KEY, entity_pks_json TEXT NOT NULL,
  detected_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'unresolved'
);
"""


@dataclass
class SourceIn:
    """A source to record. `raw_path` (if given) is checksummed directly - the
    version identity is the RAW bytes, never derived annotations.
    `retrieval_attempts` documents each access try (status, error, ts)."""
    source_ref: str
    publisher: str = ""
    license: str = ""
    source_type: str = ""
    document_date: str | None = None
    access_status: str = "fetched"
    fetched_at_utc: str | None = None
    raw_path: Path | None = None
    raw_bytes_inline: bytes | None = None
    retrieval_attempts: list = field(default_factory=list)
    raw_row: dict | None = None          # for dataset records: the raw row values


@dataclass
class ClaimIn:
    subject_key: str
    subject_type: str
    predicate: str
    object_key: str | None = None
    object_type: str | None = None
    object_literal: str | None = None
    claim_time: str | None = None
    time_precision: str = "unknown"
    certainty: str = "documented"
    review_status: str = "machine_extracted"
    evidence_kind: str = "verbatim"      # verbatim|paraphrase|analyst_synthesis
    unit: str | None = None
    grain: str | None = None
    source_ref: str = ""
    locator: str = ""
    field: str = ""
    quote: str = ""


class Engine:
    """Opens (never recreates) the database. Schema upgrades run as in-place
    migrations guarded by PRAGMA user_version: existing rows, source versions,
    retrieval history and review decisions are preserved; destructive resets
    are not part of the upgrade path."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA)
        self.snap_dir = self.db_path.parent / "evidence_snapshots"
        self.snap_dir.mkdir(parents=True, exist_ok=True)
        self._global_keys: dict[str, str] = {}
        self._migrate()
        self.conn.commit()

    def register_global_key(self, key: str, entity_type: str, name: str,
                            identifier: str) -> str:
        """Declare a stable engine-case identifier for an entity that spans
        multiple sources (e.g., an investigation's working case key). The
        identifier must be disclosed as engine-assigned, not a registry id."""
        pk = self.ensure_entity(entity_type, name, identifier=identifier)
        self._global_keys[key] = pk
        return pk

    def _verify_snapshots(self):
        """Integrity pass: a snapshot whose bytes do not match its recorded
        checksum must never be presented as retained evidence. Mark such rows
        raw_retention='not_retained' (explicit unavailability); the mismatched
        file stays on disk (no deletions). Returns corrected count. This exists
        because the v2->v3 backfill snapshotted historical versions from the
        CURRENT live file, which had already moved on for regenerated
        artifacts — their original bytes were never captured."""
        corrected = 0
        for spk, ck, snap, details in self.conn.execute(
                "SELECT source_pk, raw_checksum, snapshot_path, details_json FROM sources "
                "WHERE snapshot_path IS NOT NULL").fetchall():
            if not snap or not Path(snap).exists():
                continue
            if file_sha256(Path(snap)) != ck:
                note = ("snapshot backfill mismatch: retained bytes do not match the recorded "
                        "version checksum; original bytes were not captured before the live "
                        "file changed. Marked not_retained (corrected "
                        f"{datetime.now(timezone.utc).isoformat()}).")
                self.conn.execute(
                    "UPDATE sources SET snapshot_path=NULL, raw_retention='not_retained', "
                    "details_json=? WHERE source_pk=?",
                    (canonical({**json.loads(details or "{}"), "snapshot_correction": note}), spk))
                corrected += 1
        if corrected:
            self.conn.commit()
        return corrected

    def _migrate(self):
        """Sequential in-place migration: v0/v0.1 -> v2 (integrity columns),
        then v2 -> v3 (scoping, snapshots, append-only retrieval events),
        then v3 -> v4 (snapshot verification pass). Existing rows are never
        deleted or rewritten destructively."""
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]

        if version < 2:
            # v0/v0.1 -> v0.2: add the integrity columns; legacy rows are
            # preserved as-is and re-verified by subsequent re-ingestion.
            cols = {r[1] for r in self.conn.execute("PRAGMA table_info(sources)")}
            if "raw_checksum" not in cols:
                self.conn.execute("ALTER TABLE sources ADD COLUMN raw_checksum TEXT")
            if "raw_bytes" not in cols:
                self.conn.execute("ALTER TABLE sources ADD COLUMN raw_bytes INTEGER")
            if "raw_path" not in cols:
                self.conn.execute("ALTER TABLE sources ADD COLUMN raw_path TEXT")
            if "retrieval_attempts_json" not in cols:
                self.conn.execute("ALTER TABLE sources ADD COLUMN retrieval_attempts_json "
                                  "TEXT NOT NULL DEFAULT '[]'")
            ocols = {r[1] for r in self.conn.execute("PRAGMA table_info(observations)")}
            if "evidence_kind" not in ocols:
                self.conn.execute("ALTER TABLE observations ADD COLUMN evidence_kind TEXT "
                                  "NOT NULL DEFAULT 'verbatim'")
            if "verified_against_raw" not in ocols:
                self.conn.execute("ALTER TABLE observations ADD COLUMN verified_against_raw INTEGER")
            ecols = {r[1] for r in self.conn.execute("PRAGMA table_info(entities)")}
            if "identifier" not in ecols:
                self.conn.execute("ALTER TABLE entities ADD COLUMN identifier TEXT")
            if "identity_status" not in ecols:
                self.conn.execute("ALTER TABLE entities ADD COLUMN identity_status TEXT "
                                  "NOT NULL DEFAULT 'provisional_name_only'")
            ccols = {r[1] for r in self.conn.execute("PRAGMA table_info(claims)")}
            if "evidence_kind" not in ccols:
                self.conn.execute("ALTER TABLE claims ADD COLUMN evidence_kind TEXT "
                                  "NOT NULL DEFAULT 'verbatim'")
            if "unit" not in ccols:
                self.conn.execute("ALTER TABLE claims ADD COLUMN unit TEXT")
            if "grain" not in ccols:
                self.conn.execute("ALTER TABLE claims ADD COLUMN grain TEXT")
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS adjudications ("
                "adjudication_pk TEXT PRIMARY KEY, entity_pk_a TEXT NOT NULL, "
                "entity_pk_b TEXT NOT NULL, decision TEXT NOT NULL, "
                "basis_observation_pk TEXT, decided_by TEXT NOT NULL)")
            self.conn.execute("UPDATE entities SET identity_status='provisional_name_only' "
                              "WHERE identity_status IS NULL")
            self.conn.execute("PRAGMA user_version = 2")
            self.conn.commit()
            version = 2

        if version < 3:
            # v2 -> v3: source-scoped identities, immutable snapshots,
            # append-only retrieval events
            ecols = {r[1] for r in self.conn.execute("PRAGMA table_info(entities)")}
            if "scope" not in ecols:
                self.conn.execute("ALTER TABLE entities ADD COLUMN scope TEXT")
            self.conn.execute("UPDATE entities SET scope='unscoped' WHERE scope IS NULL")
            scols = {r[1] for r in self.conn.execute("PRAGMA table_info(sources)")}
            if "snapshot_path" not in scols:
                self.conn.execute("ALTER TABLE sources ADD COLUMN snapshot_path TEXT")
            if "raw_retention" not in scols:
                self.conn.execute("ALTER TABLE sources ADD COLUMN raw_retention TEXT "
                                  "NOT NULL DEFAULT 'not_retained'")
            if "checksum_basis" not in scols:
                self.conn.execute("ALTER TABLE sources ADD COLUMN checksum_basis TEXT "
                                  "NOT NULL DEFAULT 'metadata_row'")
            for spk, path, ck, basis in self.conn.execute(
                    "SELECT source_pk, raw_path, raw_checksum, checksum_basis "
                    "FROM sources WHERE raw_path IS NOT NULL").fetchall():
                if basis in ("", "metadata_row", None):
                    self.conn.execute("UPDATE sources SET checksum_basis='file_bytes' "
                                      "WHERE source_pk=?", (spk,))
                snap, ret = self._snapshot(Path(path), ck)
                self.conn.execute("UPDATE sources SET snapshot_path=?, raw_retention=? "
                                  "WHERE source_pk=?", (snap, ret, spk))
            for ref, att_json in self.conn.execute(
                    "SELECT DISTINCT source_ref, retrieval_attempts_json FROM sources").fetchall():
                try:
                    atts = json.loads(att_json or "[]")
                except json.JSONDecodeError:
                    atts = []
                self.record_retrieval_events(ref, atts)
            self.conn.execute("PRAGMA user_version = 3")
            self.conn.commit()

        if version < 4:
            corrected = self._verify_snapshots()
            self.conn.execute("PRAGMA user_version = 4")
            self.conn.commit()
            self._last_snapshot_corrections = corrected

        if version < 5:
            # v4 -> v5: append-only adjudications. Existing rows keep their
            # authorship and basis; sequence is backfilled by rowid so the
            # latest-decision policy is unchanged for legacy history. Legacy
            # decided_at stays NULL and is disclosed as unknown.
            acols = {r[1] for r in self.conn.execute("PRAGMA table_info(adjudications)")}
            if "decided_at" not in acols:
                self.conn.execute("ALTER TABLE adjudications ADD COLUMN decided_at TEXT")
            if "sequence" not in acols:
                self.conn.execute("ALTER TABLE adjudications ADD COLUMN sequence INTEGER")
            for rowid in self.conn.execute(
                    "SELECT rowid FROM adjudications ORDER BY rowid").fetchall():
                pass  # rowids are stable; sequence assigned below in order
            rows = self.conn.execute(
                "SELECT rowid FROM adjudications ORDER BY rowid").fetchall()
            for i, (rid,) in enumerate(rows, start=1):
                self.conn.execute(
                    "UPDATE adjudications SET sequence=? WHERE rowid=?", (i, rid))
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_adjudications_pair "
                              "ON adjudications(entity_pk_a, entity_pk_b)")
            self.conn.execute("PRAGMA user_version = 5")
            self.conn.commit()

        if version < 6:
            # v5 -> v6: explicit, source-backed, append-only claim supersession.
            # Superseded claims are NEVER deleted; they stop being presented as
            # current and contradiction groups they resolve are labelled.
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS supersessions ("
                "supersession_pk TEXT PRIMARY KEY, "
                "superseded_claim_pk TEXT NOT NULL REFERENCES claims(claim_pk), "
                "superseding_claim_pk TEXT NOT NULL REFERENCES claims(claim_pk), "
                "basis TEXT NOT NULL, evidence_claim_pk TEXT REFERENCES claims(claim_pk), "
                "recorded_at TEXT NOT NULL, recorded_by TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'active')")
            self.conn.execute("PRAGMA user_version = 6")
            self.conn.commit()
        if version < 7:
            # v6 -> v7: supersession withdrawal (conservative repair) — a
            # supersession row is never deleted; an erroneous supersession is
            # marked withdrawn with a reason and remains fully inspectable.
            scols = {r[1] for r in self.conn.execute("PRAGMA table_info(supersessions)")}
            if "withdrawn_at" not in scols:
                self.conn.execute("ALTER TABLE supersessions ADD COLUMN withdrawn_at TEXT")
            if "withdrawn_reason" not in scols:
                self.conn.execute("ALTER TABLE supersessions ADD COLUMN withdrawn_reason TEXT")
            self.conn.execute("PRAGMA user_version = 7")
            self.conn.commit()

    # ---------- entities (homonym-safe: source-scoped until adjudicated) ----------
    def entity_pk(self, entity_type: str, name: str, identifier: str | None = None,
                  scope: str | None = None) -> str:
        """Identifier-bearing entities are globally keyed on the identifier.
        Name-only entities are keyed on (type, name, scope): the SAME name
        introduced by two different sources yields TWO entities until an
        explicit adjudication declares them the same."""
        if identifier:
            return content_hash({"t": entity_type, "id": identifier.strip().lower()})
        return content_hash({"t": entity_type, "n": name.strip().lower(),
                             "scope": scope or "unscoped"})

    def ensure_entity(self, entity_type: str, name: str, identifier: str | None = None,
                      scope: str | None = None, allow_unscoped: bool = False) -> str:
        """Create (or fetch) an entity. Name-only mentions REQUIRE a scope:
        two unscoped name-only calls must never silently merge homonyms, so
        scope-less creation raises unless allow_unscoped=True is passed
        explicitly (legacy/migration paths only)."""
        assert entity_type in ENTITY_TYPES, entity_type
        if not identifier and not scope and not allow_unscoped:
            raise ValueError(
                f"unscoped name-only entity '{name}' would silently merge homonyms; "
                "pass scope=<source_ref> or an identifier (or allow_unscoped=True "
                "for legacy/migration paths only)")
        if identifier:
            status, sc = "identified", "global"
        elif scope:
            status, sc = "provisional_scoped", scope
        else:
            status, sc = "provisional_name_only", "unscoped"
        pk = self.entity_pk(entity_type, name, identifier, scope)
        self.conn.execute(
            "INSERT OR IGNORE INTO entities(entity_pk, entity_type, name, identifier, "
            "identity_status, scope) VALUES (?,?,?,?,?,?)",
            (pk, entity_type, name, identifier, status, sc))
        return pk

    def _operative_adjudications(self) -> dict[frozenset, str]:
        """Latest decision per unordered pair — append-only supersession by
        sequence (legacy rows with NULL sequence fall back to rowid order).
        Read-only. All historical decisions remain in the table."""
        operative: dict[frozenset, str] = {}
        for seq, a, b, d in self.conn.execute(
                "SELECT COALESCE(sequence, -rowid), entity_pk_a, entity_pk_b, decision "
                "FROM adjudications ORDER BY COALESCE(sequence, -rowid)"):
            operative[frozenset((a, b))] = d
        return operative

    def adjudication_history(self, pk_a: str, pk_b: str) -> list[dict]:
        """Full append-only history for one pair, oldest first — nothing is
        hidden by supersession."""
        lo, hi = sorted([pk_a, pk_b])
        return [dict(zip(["decision", "decided_by", "decided_at", "sequence"], r))
                for r in self.conn.execute(
                    "SELECT decision, decided_by, decided_at, sequence FROM adjudications "
                    "WHERE entity_pk_a=? AND entity_pk_b=? "
                    "ORDER BY COALESCE(sequence, -rowid)", (lo, hi))]

    def identity_resolution(self, entity_pk: str) -> dict:
        """READ-ONLY identity resolution. Returns the transitive same_entity
        closure (latest-decision-per-pair, order-independent) plus any
        conflicts. Never writes: conflict recording is the caller's explicit
        decision via record_identity_conflicts(). Policy (conservative):
        superseded adjudications are interpreted latest-wins per pair; if the
        operative graph still asserts both same and distinct between reachable
        entities, NO merge is applied and the conflict is returned."""
        operative = self._operative_adjudications()
        same: dict[str, set[str]] = {}
        distinct: set[frozenset] = set()
        for pair, d in operative.items():
            a, b = tuple(pair)
            if d == "same_entity":
                same.setdefault(a, set()).add(b)
                same.setdefault(b, set()).add(a)
            elif d == "distinct_entities":
                distinct.add(pair)
        closure = {entity_pk}
        frontier = [entity_pk]
        while frontier:
            cur = frontier.pop()
            for nxt in same.get(cur, ()):
                if nxt not in closure:
                    closure.add(nxt)
                    frontier.append(nxt)
        conflicts = [sorted(p) for p in distinct if p <= closure]
        if conflicts:
            return {"closure": {entity_pk}, "conflicts": conflicts, "merged": False}
        return {"closure": closure, "conflicts": [], "merged": len(closure) > 1}

    def same_entity_pks(self, entity_pk: str) -> set[str]:
        """Read-only transitive same_entity closure (latest-decision-per-pair,
        order-independent). Conservative under conflict: no merge, and NO
        writes happen here — conflicts are available via identity_resolution()
        and may be recorded explicitly with record_identity_conflicts()."""
        res = self.identity_resolution(entity_pk)
        return set(res["closure"])

    def record_identity_conflicts(self, conflicts: list, entity_pk: str | None = None) -> int:
        """EXPLICIT conflict recording — the only writer. Callers decide when;
        resolution queries never commit caller transactions."""
        n = 0
        for c in conflicts or []:
            pk = content_hash({"pairs": canonical(sorted(c)), "closure_ref": entity_pk or ""})
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO adjudication_conflicts("
                "conflict_pk, entity_pks_json, detected_at, status) "
                "VALUES (?,?,?,'unresolved')", (pk, canonical(sorted(c)), now_iso()))
            n += cur.rowcount
        self.conn.commit()
        return n

    def add_alias(self, alias: str, entity_pk: str, status: str, obs_pk: str | None = None):
        assert status in ("canonical", "ambiguous", "rejected")
        self.conn.execute(
            "INSERT OR REPLACE INTO entity_aliases(alias, entity_pk, status, observation_pk) "
            "VALUES (?,?,?,?)", (alias.strip().lower(), entity_pk, status, obs_pk))

    def ambiguous_aliases(self) -> list[dict]:
        return [{"alias": a, "entity_pk": e} for a, e in self.conn.execute(
            "SELECT alias, entity_pk FROM entity_aliases WHERE status='ambiguous'")]

    def adjudicate(self, pk_a: str, pk_b: str, decision: str, decided_by: str,
                   basis_obs: str | None = None, decided_at: str | None = None) -> str:
        """EXPLICIT identity adjudication - the only path to merging homonyms.
        APPEND-ONLY: every decision, including a repeat or reversal, becomes a
        NEW row (prior authorship/basis is never overwritten). Supersession is
        by sequence (higher wins); no commit here - caller's transaction."""
        assert decision in ("same_entity", "distinct_entities", "unadjudicated")
        decided_at = decided_at or now_iso()
        seq = self.conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM adjudications").fetchone()[0]
        lo, hi = sorted([pk_a, pk_b])
        apk = content_hash({"a": lo, "b": hi, "d": decision, "by": decided_by,
                            "at": decided_at, "seq": seq})
        self.conn.execute(
            "INSERT INTO adjudications(adjudication_pk, entity_pk_a, entity_pk_b, "
            "decision, basis_observation_pk, decided_by, decided_at, sequence) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (apk, pk_a, pk_b, decision, basis_obs, decided_by, decided_at, seq))
        return apk

    # ---------- sources (raw-checksum versioning + immutable snapshots) ----------
    SNAPSHOT_DIR = None  # set by Engine.__init__ from db_path

    def record_retrieval_events(self, source_ref: str, attempts: list) -> int:
        """APPEND-ONLY retrieval history: each attempt becomes an immutable
        event; nothing is ever overwritten."""
        n = 0
        for att in attempts or []:
            ts = str(att.get("ts") or att.get("attempted_at") or "unknown")
            outcome = str(att.get("outcome") or att.get("status") or
                          att.get("note", "")[:40] or "unknown")
            ek = content_hash({"ref": source_ref, "ts": ts, "outcome": outcome,
                               "details": canonical(att)})
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO retrieval_events(event_pk, source_ref, ts, outcome, "
                "details_json) VALUES (?,?,?,?,?)",
                (ek, source_ref, ts, outcome, canonical(att)))
            n += cur.rowcount
        return n

    def _snapshot(self, raw_path: Path | None, checksum: str | None) -> tuple[str | None, str]:
        """Copy raw bytes into an immutable, content-addressed snapshot so a
        later overwrite of the live file cannot destroy prior evidence.
        Returns (snapshot_path, retention)."""
        if raw_path is None or checksum is None or not Path(raw_path).exists():
            return None, "not_retained"
        snap_dir = self.snap_dir / checksum[:16]
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap = snap_dir / Path(raw_path).name
        if not snap.exists():
            snap.write_bytes(Path(raw_path).read_bytes())
        elif file_sha256(snap) != checksum:
            # collision under truncated prefix: store full-hash directory
            snap = self.snap_dir / checksum / Path(raw_path).name
            snap.parent.mkdir(parents=True, exist_ok=True)
            if not snap.exists():
                snap.write_bytes(Path(raw_path).read_bytes())
        return self._repo_rel(snap), "snapshot_retained"

    def _repo_rel(self, p) -> str | None:
        """Store paths relative to the repo root (db_path's grandparent) so the
        committed database resolves on any machine, not just the checkout that
        produced it. Only applies when the DB actually lives inside a repo
        (marked by .git/pyproject.toml); throwaway DBs elsewhere keep absolute
        paths, so CWD-relative reads keep working unchanged. Paths outside the
        root are stored as given."""
        if p is None:
            return None
        q = Path(p).resolve()
        root = self.db_path.resolve().parents[2]
        if (root / ".git").exists() or (root / "pyproject.toml").exists():
            try:
                return str(q.relative_to(root))
            except ValueError:
                pass
        return str(q)

    def record_source(self, src: SourceIn, run_id: str) -> tuple[str, str]:
        if src.raw_path is not None and Path(src.raw_path).exists():
            checksum = file_sha256(src.raw_path)
            raw_bytes = Path(src.raw_path).stat().st_size
            basis = "file_bytes"
        elif src.raw_bytes_inline is not None:
            checksum = hashlib.sha256(src.raw_bytes_inline).hexdigest()
            raw_bytes = len(src.raw_bytes_inline)
            basis = "inline_bytes"
        elif src.raw_row is not None:
            # METADATA row hash - explicitly NOT a raw-content checksum
            checksum = content_hash(src.raw_row)
            raw_bytes = len(canonical(src.raw_row))
            basis = "metadata_row"
        else:
            checksum = None
            raw_bytes = None
            basis = "none"
        # append-only retrieval history (never overwritten)
        self.record_retrieval_events(src.source_ref, src.retrieval_attempts)

        prior = self.conn.execute(
            "SELECT source_pk, raw_checksum FROM sources WHERE source_ref=? "
            "ORDER BY version_index DESC LIMIT 1", (src.source_ref,)).fetchone()
        if prior and prior[1] == checksum:
            return prior[0], "unchanged"
        idx = 1 if not prior else self.conn.execute(
            "SELECT MAX(version_index) FROM sources WHERE source_ref=?",
            (src.source_ref,)).fetchone()[0] + 1
        pk = content_hash({"ref": src.source_ref, "hash": checksum or "", "idx": idx})
        snap_path, retention = self._snapshot(src.raw_path, checksum)
        if basis == "metadata_row":
            retention = "not_retained"  # no raw content exists to retain
        details = {"document_date": src.document_date, "source_type": src.source_type}
        self.conn.execute(
            "INSERT INTO sources(source_pk, source_ref, version_index, raw_checksum, raw_bytes, "
            "raw_path, publisher, license, source_type, document_date, access_status, "
            "retrieval_attempts_json, fetched_at_utc, snapshot_path, raw_retention, "
            "checksum_basis, details_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pk, src.source_ref, idx, checksum, raw_bytes,
             self._repo_rel(src.raw_path),
             src.publisher, src.license, src.source_type, src.document_date,
             src.access_status, canonical(src.retrieval_attempts),
             src.fetched_at_utc or now_iso(), snap_path, retention, basis,
             canonical(details)))
        event = "new" if not prior else "changed"
        self.conn.execute(
            "INSERT INTO source_events(event_pk, source_ref, event, run_id, details_json) "
            "VALUES (?,?,?,?,?)",
            (content_hash({"ref": src.source_ref, "event": event, "run": run_id,
                           "hash": checksum or "", "idx": idx}),
             src.source_ref, event, run_id,
             canonical({"raw_checksum": checksum, "prior_raw_checksum": prior[1] if prior else None,
                        "snapshot_path": snap_path})))
        return pk, event

    def latest_source_pk(self, source_ref: str) -> str | None:
        row = self.conn.execute(
            "SELECT source_pk FROM sources WHERE source_ref=? ORDER BY version_index DESC LIMIT 1",
            (source_ref,)).fetchone()
        return row[0] if row else None

    def not_present_sources(self, seen_refs: set[str]) -> list[str]:
        known = {r[0] for r in self.conn.execute("SELECT DISTINCT source_ref FROM sources")}
        return sorted(known - seen_refs)

    # ---------- observations & claims ----------
    def add_observation(self, source_pk: str, locator: str, field_: str, quote: str,
                        evidence_kind: str = "verbatim",
                        verified_against_raw: int | None = None) -> str:
        assert evidence_kind in EVIDENCE_KIND
        pk = content_hash({"s": source_pk, "l": locator, "f": field_, "q": quote,
                           "k": evidence_kind})
        self.conn.execute(
            "INSERT OR IGNORE INTO observations(obs_pk, source_pk, locator, field, quote, "
            "evidence_kind, verified_against_raw, extractor_version) VALUES (?,?,?,?,?,?,?,?)",
            (pk, source_pk, locator, field_, quote, evidence_kind, verified_against_raw,
             ENGINE_VERSION))
        return pk

    def add_claim(self, c: ClaimIn, run_id: str, obs_pk: str) -> str:
        assert c.certainty in CERTAINTY and c.review_status in REVIEW
        assert c.evidence_kind in EVIDENCE_KIND
        assert not (c.evidence_kind == "analyst_synthesis" and c.source_ref and
                    not c.source_ref.startswith("analysis:")), \
            "analyst_synthesis claims must cite an analysis artifact, not a fetched source"
        scope = c.source_ref  # name-only mentions are scoped to their source
        if c.subject_key in self._global_keys:
            subj = self._global_keys[c.subject_key]
        else:
            subj = self.ensure_entity(c.subject_type, c.subject_key.split(":", 1)[1],
                                      scope=scope)
        obj = None
        if c.object_key:
            obj = (self._global_keys.get(c.object_key) or
                   self.ensure_entity(c.object_type, c.object_key.split(":", 1)[1],
                                      scope=scope))
        pk = content_hash({"s": subj, "p": c.predicate, "o": c.object_key,
                           "ol": c.object_literal, "t": c.claim_time, "obs": obs_pk})
        self.conn.execute(
            "INSERT OR IGNORE INTO claims(claim_pk, subject_pk, predicate, object_pk, "
            "object_literal, claim_time, time_precision, certainty, review_status, "
            "evidence_kind, unit, grain, observation_pk, ingested_run) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pk, subj, c.predicate, obj, c.object_literal, c.claim_time, c.time_precision,
             c.certainty, c.review_status, c.evidence_kind, c.unit, c.grain, obs_pk, run_id))
        if obj:
            self.conn.execute(
                "INSERT OR IGNORE INTO relations(rel_pk, subject_pk, predicate, object_pk, claim_pk) "
                "VALUES (?,?,?,?,?)",
                (content_hash({"s": subj, "p": c.predicate, "o": obj, "c": pk}),
                 subj, c.predicate, obj, pk))
        return pk

    def ingest_claims(self, claims: list[ClaimIn], run_id: str,
                      quote_verification: dict[str, str] | None = None) -> int:
        """quote_verification: source_ref -> cached raw text; verbatim quotes are
        substring-checked against it and marked verified 1 or 0."""
        n = 0
        src_cache: dict[str, str] = {}
        for c in claims:
            if c.source_ref not in src_cache:
                pk = self.latest_source_pk(c.source_ref)
                assert pk, f"source not recorded: {c.source_ref}"
                src_cache[c.source_ref] = pk
            spk = src_cache[c.source_ref]
            verified = None
            if c.evidence_kind == "verbatim" and quote_verification and c.source_ref in quote_verification:
                # whitespace-normalized substring check (line breaks in PDF/HTML
                # extraction must not fail an otherwise-verbatim quote)
                norm = lambda t: re.sub(r"\s+", " ", t or "")
                verified = 1 if norm(c.quote) in norm(quote_verification[c.source_ref]) else 0
            obs = self.add_observation(spk, c.locator, c.field, c.quote,
                                       evidence_kind=c.evidence_kind,
                                       verified_against_raw=verified)
            self.add_claim(c, run_id, obs)
            n += 1
        return n

    # ---------- explicit supersession (append-only) ----------
    def record_supersession(self, superseded_pk: str, superseding_pk: str, basis: str,
                            recorded_by: str, evidence_claim_pk: str | None = None) -> str:
        """Record that one claim supersedes another, with a source-backed basis.
        APPEND-ONLY: the superseded claim row is preserved and remains
        inspectable; it simply stops being presented as current. No commit
        here - caller's transaction."""
        assert superseded_pk != superseding_pk
        for pk in (superseded_pk, superseding_pk):
            assert self.conn.execute("SELECT COUNT(*) FROM claims WHERE claim_pk=?",
                                     (pk,)).fetchone()[0] == 1, f"unknown claim {pk}"
        # deterministic PK: re-recording the same supersession (same pair, same
        # basis) is an idempotent reassertion, not a new event - so repeated
        # ingest runs never duplicate supersession rows
        spk = content_hash({"old": superseded_pk, "new": superseding_pk, "basis": basis})
        self.conn.execute(
            "INSERT OR IGNORE INTO supersessions(supersession_pk, superseded_claim_pk, "
            "superseding_claim_pk, basis, evidence_claim_pk, recorded_at, recorded_by, status) "
            "VALUES (?,?,?,?,?,?,?, 'active')",
            (spk, superseded_pk, superseding_pk, basis, evidence_claim_pk,
             now_iso(), recorded_by))
        return spk

    def withdraw_supersession(self, supersession_pk: str, reason: str, decided_by: str) -> None:
        """Conservative repair: mark an erroneous supersession withdrawn.
        The row (and its full audit content) is preserved; it simply stops
        taking effect. Withdrawal itself is recorded in-row."""
        self.conn.execute(
            "UPDATE supersessions SET status='withdrawn', withdrawn_at=?, "
            "withdrawn_reason=? WHERE supersession_pk=?",
            (now_iso(), canonical({"reason": reason, "decided_by": decided_by}),
             supersession_pk))

    def active_supersessions(self) -> dict[str, dict]:
        """claim_pk -> {superseded_by, basis, recorded_by, recorded_at} for
        actively superseded claims (read-only)."""
        out = {}
        for old, new, basis, by, at in self.conn.execute(
                "SELECT superseded_claim_pk, superseding_claim_pk, basis, recorded_by, "
                "recorded_at FROM supersessions WHERE status='active'"):
            out[old] = {"superseded_by": new, "basis": basis, "recorded_by": by,
                        "recorded_at": at}
        return out

    def find_claims(self, subject_pk: str, predicate: str,
                    literal_like: str | None = None) -> list[str]:
        """Claim pks for a subject/predicate (optionally literal LIKE)."""
        if literal_like:
            rows = self.conn.execute(
                "SELECT claim_pk FROM claims WHERE subject_pk=? AND predicate=? "
                "AND object_literal LIKE ?", (subject_pk, predicate, literal_like)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT claim_pk FROM claims WHERE subject_pk=? AND predicate=?",
                (subject_pk, predicate)).fetchall()
        return [r[0] for r in rows]

    def detect_contradictions(self) -> dict[str, list[str]]:
        """Group single-valued predicates; every group is kind='possible' with a
        scope_note recording date/unit/grain differences. Unproven conflicts stay
        possible; different claim_times are flagged as sequence candidates."""
        rows = self.conn.execute(
            "SELECT claim_pk, subject_pk, predicate, object_pk, object_literal, claim_time, "
            "time_precision, unit, grain FROM claims "
            f"WHERE predicate IN ({','.join('?' * len(SINGLE_VALUED_PREDICATES))})",
            tuple(SINGLE_VALUED_PREDICATES)).fetchall()
        groups: dict[tuple, list] = {}
        for r in rows:
            pk, subj, pred, obj, lit, t, prec, unit, grain = r
            val = obj or (lit or "").strip().lower() or None
            if val is None:
                continue
            groups.setdefault((subj, pred), []).append(
                {"claim_pk": pk, "value": val, "time": t, "unit": unit, "grain": grain})
        out = {}
        for (subj, pred), items in groups.items():
            byval: dict[str, list] = {}
            for it in items:
                byval.setdefault(it["value"], []).append(it)
            if len(byval) < 2:
                continue
            gpk = "contra:" + content_hash({"s": subj, "p": pred})[:24]
            times = sorted({it["time"] or "unknown" for it in items})
            units = sorted({it["unit"] or "unspecified" for it in items})
            grains = sorted({it["grain"] or "unspecified" for it in items})
            note = ("UNPROVEN: values differ but same-unit/same-grain/same-time equality has not "
                    "been adjudicated. "
                    + (f"claim_times differ ({', '.join(times)}) - may be sequence, not conflict. "
                       if len(times) > 1 else "")
                    + (f"units: {', '.join(units)}. " if len(set(units)) > 1 or units[0] != "unspecified" else "")
                    + (f"grains: {', '.join(grains)}." if len(set(grains)) > 1 or grains[0] != "unspecified" else ""))
            sup = self.active_supersessions()
            group_pks = {it["claim_pk"] for it in items}
            superseded_in_group = {c for c in group_pks
                                   if c in sup and sup[c]["superseded_by"] in group_pks}
            for it in items:
                res = ("resolved_by_supersession" if it["claim_pk"] in superseded_in_group
                       else "unresolved")
                self.conn.execute(
                    "INSERT INTO contradictions(group_pk, claim_pk, kind, scope_note, "
                    "resolution_status) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(group_pk, claim_pk) DO UPDATE SET resolution_status=excluded.resolution_status",
                    (gpk, it["claim_pk"], "possible", note, res))
            out[gpk] = [it["claim_pk"] for it in items]
        return out

    # ---------- runs ----------
    def finish_run(self, run_id: str, script: str, inputs_hash: str, sources_new: int,
                   sources_changed: int, sources_not_present: int, claims_ingested: int):
        dh = self.conn.execute(
            "SELECT group_concat(claim_pk, '') FROM (SELECT claim_pk FROM claims "
            "ORDER BY claim_pk)").fetchone()[0] or ""
        det = content_hash({"claims": dh})
        self.conn.execute(
            "INSERT OR REPLACE INTO ingest_runs(run_id, script, engine_version, started_at_utc, "
            "inputs_hash, sources_new, sources_changed, sources_not_present, claims_ingested, "
            "deterministic_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (run_id, script, ENGINE_VERSION, now_iso(), inputs_hash, sources_new,
             sources_changed, sources_not_present, claims_ingested, det))
        self.conn.commit()
        return det

    def commit(self):
        self.conn.commit()

    # ---------- investigation queries ----------
    def project_timeline(self, entity_pk: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT c.claim_pk, c.predicate, c.object_literal, c.object_pk, c.claim_time,
                      c.time_precision, c.certainty, c.review_status, c.evidence_kind,
                      c.unit, c.grain, o.quote, o.locator, o.verified_against_raw,
                      s.source_ref, s.version_index, s.publisher, s.access_status, e2.name
               FROM claims c
               JOIN observations o ON o.obs_pk = c.observation_pk
               JOIN sources s ON s.source_pk = o.source_pk
               LEFT JOIN entities e2 ON e2.entity_pk = c.object_pk
               WHERE c.subject_pk = ? OR c.object_pk = ?
               ORDER BY COALESCE(c.claim_time, '9999') ASC""",
            (entity_pk, entity_pk)).fetchall()
        sup = self.active_supersessions()
        out = []
        for r in rows:
            d = dict(zip([
                "claim_pk", "predicate", "object_literal", "object_pk", "claim_time",
                "time_precision", "certainty", "review_status", "evidence_kind", "unit",
                "grain", "quote", "locator", "verified_against_raw", "source_ref",
                "source_version", "publisher", "access_status", "object_name"], r))
            if d["claim_pk"] in sup:
                d["superseded_by"] = sup[d["claim_pk"]]["superseded_by"]
                d["supersession_basis"] = sup[d["claim_pk"]]["basis"]
                d["superseded_at"] = sup[d["claim_pk"]]["recorded_at"]
            else:
                d["superseded_by"] = None
                d["supersession_basis"] = None
                d["superseded_at"] = None
            out.append(d)
        return out

    def contradictions_for(self, entity_pk: str) -> list[dict]:
        return [dict(zip(["group_pk", "claim_pk", "kind", "scope_note"], r))
                for r in self.conn.execute(
            """SELECT DISTINCT co.group_pk, co.claim_pk, co.kind, co.scope_note
               FROM contradictions co JOIN claims c ON c.claim_pk = co.claim_pk
               WHERE c.subject_pk = ? OR c.object_pk = ?""", (entity_pk, entity_pk))]

    def unknowns_for(self, entity_pk: str, dimensions: dict) -> dict:
        out = {}
        for dim, preds in dimensions.items():
            found = self.conn.execute(
                f"SELECT COUNT(*) FROM claims WHERE subject_pk=? AND predicate IN "
                f"({','.join('?' * len(preds))})", (entity_pk, *preds)).fetchone()[0]
            out[dim] = "unknown" if found == 0 else f"{found} claim(s)"
        return out
