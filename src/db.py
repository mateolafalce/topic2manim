"""Supabase database persistence layer for jobs.

Falls back to file-based JSON persistence if Supabase is not configured.
Uses httpx (already a transitive dependency) to avoid heavy supabase-py builds.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

_SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
_ENABLED = bool(_SUPABASE_URL and _SUPABASE_KEY)

_TABLE = "jobs"
_REST_BASE = f"{_SUPABASE_URL}/rest/v1/{_TABLE}" if _ENABLED else ""
_HEADERS = {
    "apikey": _SUPABASE_KEY,
    "Authorization": f"Bearer {_SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Local fallback directory (same as video_generator.py uses)
_JOBS_DIR = Path(__file__).parent.parent / "content" / "jobs"
_JOBS_DIR.mkdir(parents=True, exist_ok=True)


def is_enabled() -> bool:
    return _ENABLED


def _job_record_path(job_id: str) -> Path:
    return _JOBS_DIR / f"{job_id}.json"


def _iso_now() -> str:
    return datetime.now().isoformat()


def _sanitize_for_json(value: Any) -> Any:
    """Remove non-serializable values (e.g., Locks, Threads)."""
    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [_sanitize_for_json(v) for v in value]
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return str(value)


def _job_to_db_row(job: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a job dict into a Supabase table row."""
    row = {
        "id": job.get("job_id"),
        "created_at": job.get("created_at") or _iso_now(),
        "updated_at": _iso_now(),
        "status": job.get("status", "queued"),
        "topic": job.get("topic", ""),
        "progress": int(job.get("progress", 0)),
        "current_step": job.get("current_step", ""),
        "message": job.get("message", ""),
        "error": job.get("error"),
        "video_url": job.get("video_url"),
        "html_url": job.get("html_url"),
        "cancel_requested": bool(job.get("cancel_requested", False)),
        "config": {},
        "script": None,
        "render_checkpoint": None,
        "scene_results": None,
    }
    # Pack volatile nested fields into JSONB columns
    config_keys = [
        "enable_tts",
        "llm_provider",
        "llm_model",
        "tts_provider",
        "tts_voice",
        "video_settings",
        "input_mode",
    ]
    row["config"] = {k: job.get(k) for k in config_keys if k in job}
    if "script" in job:
        row["script"] = _sanitize_for_json(job["script"])
    if "render_checkpoint" in job:
        row["render_checkpoint"] = _sanitize_for_json(job["render_checkpoint"])
    if "scene_results" in job:
        row["scene_results"] = _sanitize_for_json(job["scene_results"])
    return row


def _db_row_to_job(row: Dict[str, Any]) -> Dict[str, Any]:
    """Reconstruct a job dict from a Supabase row."""
    job = dict(row)
    job["job_id"] = job.pop("id", None)
    # Unpack config
    config = job.pop("config", {}) or {}
    job.update(config)
    # Promote JSONB fields
    for key in ("script", "render_checkpoint", "scene_results"):
        if job.get(key) is None:
            job.pop(key, None)
    return job


def _write_local(job_id: str, data: Dict[str, Any]) -> None:
    path = _job_record_path(job_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        print(f"[WARN] Could not persist job {job_id} locally: {exc}")


def _read_local(job_id: str) -> Optional[Dict[str, Any]]:
    path = _job_record_path(job_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API (mirrors the existing _persist_job / _load_job_from_disk interface)
# ---------------------------------------------------------------------------

def persist_job(job_id: str, job: Dict[str, Any]) -> None:
    """Write job to Supabase (if configured) and always to local disk."""
    clean = _sanitize_for_json(job)
    _write_local(job_id, clean)
    if not _ENABLED:
        return
    try:
        row = _job_to_db_row(clean)
        with httpx.Client(timeout=15.0) as client:
            # Upsert via POST with merge-duplicates preference
            resp = client.post(
                _REST_BASE,
                headers={**_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"},
                json=row,
            )
            if resp.status_code not in (200, 201):
                print(f"[WARN] Supabase persist failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as exc:
        print(f"[WARN] Supabase persist error: {exc}")


def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Load job from Supabase (if configured), else local disk."""
    if _ENABLED:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    _REST_BASE,
                    headers=_HEADERS,
                    params={"id": f"eq.{job_id}", "select": "*"},
                )
                if resp.status_code == 200:
                    rows = resp.json()
                    if rows:
                        return _db_row_to_job(rows[0])
        except Exception as exc:
            print(f"[WARN] Supabase load error: {exc}")
    return _read_local(job_id)


def list_recent_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    """List recent jobs from Supabase (if configured), else local disk."""
    if _ENABLED:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    _REST_BASE,
                    headers=_HEADERS,
                    params={
                        "select": "*",
                        "order": "updated_at.desc",
                        "limit": limit,
                    },
                )
                if resp.status_code == 200:
                    return [_db_row_to_job(r) for r in resp.json()]
        except Exception as exc:
            print(f"[WARN] Supabase list error: {exc}")
    # Fallback: scan local JSON files
    jobs = []
    for path in sorted(_JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                jobs.append(json.load(f))
        except Exception:
            continue
    return jobs[:limit]


def delete_job(job_id: str) -> bool:
    """Delete job from Supabase (if configured) and local disk."""
    path = _job_record_path(job_id)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass
    if _ENABLED:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.delete(
                    _REST_BASE,
                    headers=_HEADERS,
                    params={"id": f"eq.{job_id}"},
                )
                return resp.status_code in (200, 204)
        except Exception as exc:
            print(f"[WARN] Supabase delete error: {exc}")
    return True


# ---------------------------------------------------------------------------
# Adapter helpers for video_generator.py
# ---------------------------------------------------------------------------

def make_persist_fn() -> Callable[[str, Optional[Dict[str, Any]]], None]:
    """Return a persist function compatible with render_pipeline's persist_fn signature."""

    def _persist(job_id: str, checkpoint: Optional[Dict[str, Any]] = None) -> None:
        from video_generator import jobs, jobs_lock

        with jobs_lock:
            data = dict(jobs.get(job_id, {}))
        if checkpoint is not None:
            data["render_checkpoint"] = checkpoint
        persist_job(job_id, data)

    return _persist


def sync_jobs_dict_on_startup(jobs_dict: Dict[str, Any], jobs_lock: Any) -> None:
    """On startup, load recent jobs from Supabase/local into the in-memory dict."""
    recent = list_recent_jobs(limit=100)
    with jobs_lock:
        for job in recent:
            jid = job.get("job_id")
            if jid and jid not in jobs_dict:
                jobs_dict[jid] = job
