"""Polite HTTP layer: descriptive UA, retries, on-disk cache, request log.

The request log (data/processed/api_request_log.jsonl) lets us report exact
API usage; GEM and GLEIF are public no-auth APIs and we keep volume tiny
(one-time paged fetches + a few dozen targeted lookups).
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "http_cache"
REQUEST_LOG = ROOT / "data" / "processed" / "api_request_log.jsonl"

UA = (
    "discovery-engine-m1/0.1 (non-commercial research prototype; "
    "single-run paged fetch with caching; no scraping of restricted content)"
)

_session = requests.Session()
_session.headers.update({"User-Agent": UA})


def _log(entry: dict) -> None:
    REQUEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with REQUEST_LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cached_get_json(url: str, *, params: dict | None = None, max_age_days: float = 365.0,
                    retries: int = 4, sleep: float = 1.0) -> dict:
    """GET url as JSON, cached on disk. Logs every network request."""
    key = hashlib.sha256(
        (url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))).encode()
    ).hexdigest()[:24]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        age_days = (time.time() - cache_file.stat().st_mtime) / 86400.0
        if age_days <= max_age_days:
            return json.loads(cache_file.read_text())

    last_err = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            r = _session.get(url, params=params, timeout=90)
            dt = time.time() - t0
            _log({"ts": datetime.now(timezone.utc).isoformat(), "url": r.url,
                  "status": r.status_code, "seconds": round(dt, 2),
                  "attempt": attempt + 1, "cached": False})
            if r.status_code == 200 and r.text.strip():
                obj = r.json()
                cache_file.write_text(json.dumps(obj, ensure_ascii=False))
                time.sleep(sleep)
                return obj
            last_err = f"status {r.status_code}: {r.text[:150]!r}"
        except Exception as e:  # noqa: BLE001 - retry any transport error
            last_err = repr(e)
            _log({"ts": datetime.now(timezone.utc).isoformat(), "url": url,
                  "error": last_err, "attempt": attempt + 1, "cached": False})
        time.sleep(sleep * (attempt + 1) * 2)
    raise RuntimeError(f"GET failed after {retries} attempts: {url} ({params}) -> {last_err}")
