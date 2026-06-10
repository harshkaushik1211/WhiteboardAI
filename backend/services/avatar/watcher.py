"""Avatar Processing Watcher — Phase-4 P3 + P11.

P3: Timeout Recovery
    Scans the ``sadtalker_processing/`` Google Drive folder for projects that
    have been stuck in processing longer than ``avatar_processing_timeout_hours``
    (default 12 hours).

    When a timeout is detected:
    1. The project directory is moved from ``processing/`` to ``failed/``.
    2. A ``failure_report.json`` is written explaining the reason.
    3. The local project ``config.json`` is updated with status="failed".
    4. A structured ``[AVATAR_RECOVERY]`` log is emitted.

P11: Heartbeat Tracking
    The Colab worker is expected to write a ``worker.json`` file inside the
    processing directory:

        {
            "worker": "sadtalker_colab",
            "started_at": "...",
            "last_heartbeat": "..."
        }

    If ``last_heartbeat`` is absent or stale beyond the timeout, the project
    is moved to ``failed/``.

Usage (call from a background scheduler or on every status poll):

    watcher = AvatarProcessingWatcher()
    watcher.check_timeouts()
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from config import settings
from utils.file_manager import load_json, save_json

logger = logging.getLogger("sadtalker_watcher")


class AvatarProcessingWatcher:
    """Detects and recovers stale SadTalker processing jobs.

    P3: Moves timed-out projects from ``processing/`` to ``failed/`` and
    updates local config so the render pipeline can fall back gracefully.

    P11: Uses ``worker.json::last_heartbeat`` as the primary signal. Falls
    back to ``queue_status.json::created_at`` (enqueue time) when heartbeat
    is absent.
    """

    def check_timeouts(self) -> list[str]:
        """Scan processing folder and move stale projects to failed.

        Returns:
            List of project IDs that were timed out in this run.
        """
        processing_root = settings.sadtalker_processing_path
        failed_root = settings.sadtalker_failed_path
        timeout_delta = timedelta(hours=settings.avatar_processing_timeout_hours)
        now = datetime.now(timezone.utc)

        timed_out: list[str] = []

        if not processing_root.exists():
            logger.debug("[AVATAR_RECOVERY] Processing folder does not exist; nothing to check.")
            return timed_out

        for entry in processing_root.iterdir():
            if not entry.is_dir():
                continue

            # Extract project_id from directory name (e.g. "project_abc123" → "abc123")
            project_id = self._extract_project_id(entry.name)
            if not project_id:
                logger.warning(
                    f"[AVATAR_RECOVERY] Unexpected directory in processing: {entry.name}"
                )
                continue

            # Determine reference timestamp (heartbeat > enqueue time)
            ref_time = self._get_reference_time(entry)

            if ref_time is None:
                # Can't determine age — use directory mtime as fallback
                mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
                ref_time = mtime
                logger.debug(
                    f"[AVATAR_RECOVERY] No timestamp for {project_id}; using mtime {mtime}"
                )

            age = now - ref_time
            if age < timeout_delta:
                logger.debug(
                    f"[AVATAR_RECOVERY] {project_id} age {age} < timeout {timeout_delta}; OK"
                )
                continue

            # ── TIMEOUT DETECTED ──────────────────────────────────────────────
            # Refinement F & 4: Retry validation
            meta_file = entry / "processing_metadata.json"
            retry_count = 0
            
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    retry_count = meta.get("retry_count", 0)
                except Exception:
                    pass

            if retry_count < settings.avatar_max_retries:
                retry_count += 1
                now_str = datetime.now(timezone.utc).isoformat()
                meta = {
                    "retry_count": retry_count,
                    "last_retry_at": now_str
                }
                try:
                    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                except Exception:
                    pass

                # Move folder back to queue
                queue_root = settings.sadtalker_queue_path
                queue_root.mkdir(parents=True, exist_ok=True)
                dest = queue_root / entry.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(entry), str(dest))

                # Update local config
                try:
                    cfg = load_json(project_id, "config.json") or {}
                    cfg["sadtalker_processing_status"] = "queued"
                    cfg["sadtalker_queued_at"] = now_str
                    cfg["sadtalker_last_update"] = now_str
                    save_json(project_id, "config.json", cfg)
                except Exception:
                    pass

                logger.info(
                    f"[AVATAR_RECOVERY] Requeuing project {project_id} (retry {retry_count}/{settings.avatar_max_retries}) due to timeout."
                )
            else:
                logger.warning(
                    f"[AVATAR_RECOVERY] Project {project_id} timed out after {age} and exhausted retries. "
                    f"Timeout threshold: {timeout_delta}. Moving to failed."
                )
                self._move_to_failed(entry, project_id, age, failed_root)
                self._update_local_config(project_id, reason="timeout", age_str=str(age))
                
                # Record failed metrics
                try:
                    from services.avatar.metrics import AvatarMetricsService
                    AvatarMetricsService().update_metrics(failed_avatar_generations=1)
                except Exception:
                    pass

                timed_out.append(project_id)

        if timed_out:
            logger.info(
                f"[AVATAR_RECOVERY] Timeout sweep complete: {len(timed_out)} project(s) moved to failed: "
                + ", ".join(timed_out)
            )
        else:
            logger.debug("[AVATAR_RECOVERY] Timeout sweep complete: no stale projects found.")

        return timed_out

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_project_id(dir_name: str) -> Optional[str]:
        """Return the project_id from a directory named ``project_{id}``."""
        m = re.match(r"^project_([a-zA-Z0-9_-]+)$", dir_name)
        return m.group(1) if m else None

    @staticmethod
    def _get_reference_time(entry: Path) -> Optional[datetime]:
        """Read the best available timestamp from worker.json or queue_status.json.

        P11: Prefers ``worker.json::last_heartbeat`` (set by the live worker),
        then falls back to ``worker.json::started_at`` and finally
        ``queue_status.json::created_at``.
        """
        def parse_iso(s: str) -> Optional[datetime]:
            try:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                return None

        # P11: worker.json
        worker_file = entry / "worker.json"
        if worker_file.exists():
            try:
                data = json.loads(worker_file.read_text(encoding="utf-8"))
                for key in ("last_heartbeat", "started_at"):
                    t = parse_iso(data.get(key, ""))
                    if t:
                        return t
            except Exception:
                pass

        # Fallback: queue_status.json
        status_file = entry / "queue_status.json"
        if status_file.exists():
            try:
                data = json.loads(status_file.read_text(encoding="utf-8"))
                t = parse_iso(data.get("created_at", ""))
                if t:
                    return t
            except Exception:
                pass

        return None

    @staticmethod
    def _move_to_failed(
        entry: Path,
        project_id: str,
        age: timedelta,
        failed_root: Path,
    ) -> None:
        """Move the stale processing directory to the failed folder."""
        failed_root.mkdir(parents=True, exist_ok=True)
        dest = failed_root / entry.name

        # Clean previous failed entry if it exists
        if dest.exists():
            shutil.rmtree(dest)

        shutil.move(str(entry), str(dest))

        # Write failure_report.json into the moved directory
        report = {
            "reason": "processing_timeout",
            "project_id": project_id,
            "age_seconds": age.total_seconds(),
            "timeout_hours": settings.avatar_processing_timeout_hours,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        (dest / "failure_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        logger.info(
            f"[AVATAR_RECOVERY] Moved {entry.name} → failed/; "
            f"failure_report.json written."
        )

    @staticmethod
    def _update_local_config(project_id: str, reason: str, age_str: str) -> None:
        """Update the local project config.json with failure status."""
        try:
            cfg = load_json(project_id, "config.json") or {}
            cfg["sadtalker_processing_status"] = "failed"
            cfg["avatar_generation_status"] = "failed"
            cfg["sadtalker_last_update"] = datetime.now(timezone.utc).isoformat()
            cfg["sadtalker_failure_reason"] = reason
            save_json(project_id, "config.json", cfg)
            logger.info(
                f"[AVATAR_RECOVERY] Updated local config for {project_id}: "
                f"status=failed reason={reason} age={age_str}"
            )
        except Exception as exc:
            logger.error(
                f"[AVATAR_RECOVERY] Failed to update local config for {project_id}: {exc}"
            )
