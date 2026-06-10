"""Avatar Cleanup Service — Phase-4 P9.

Removes avatar-related files that are no longer needed after a completed
render, respecting the configurable ``avatar_retention_days`` window.

Cleanup targets:

1. ``<project>/avatars/``  — project avatar clip directory.
   Only cleaned when:
   - ``avatar_generation_status == "completed"``
   - ``render_status == "complete"``
   - The import was completed more than ``avatar_retention_days`` ago.

2. ``WhiteboardAI_Avatar/completed/project_{id}/``  — Google Drive completed folder.
   Cleaned after the same conditions as above.

Usage (call from a background scheduler):

    cleanup = AvatarCleanupService()
    summary = cleanup.run()
    # → {"projects_cleaned": [...], "bytes_freed": 12345678}
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from config import settings
from utils.file_manager import load_json, project_dir

logger = logging.getLogger("sadtalker_cleanup")

# Prefix for log messages (P12 structured logging)
_LOG_TAG = "[AVATAR_CLEANUP]"


class AvatarCleanupService:
    """Removes expired avatar assets to control storage consumption.

    P9: Only deletes after both import AND render are confirmed complete and
    the retention window has elapsed.
    """

    def run(self) -> dict:
        """Scan all projects and remove eligible avatar assets.

        Returns:
            Summary dict with ``projects_cleaned`` list and ``bytes_freed`` count.
        """
        generated_root = settings.generated_path / "projects"
        if not generated_root.exists():
            logger.debug(f"{_LOG_TAG} Generated projects dir not found; nothing to clean.")
            return {"projects_cleaned": [], "bytes_freed": 0}

        retention = timedelta(days=settings.avatar_retention_days)
        now = datetime.now(timezone.utc)

        cleaned: list[str] = []
        bytes_freed: int = 0

        for project_path in generated_root.iterdir():
            if not project_path.is_dir():
                continue

            project_id = project_path.name
            cfg = load_json(project_id, "config.json") or {}
            status_data = load_json(project_id, "status.json") or {}

            # ── Eligibility checks ──
            avatar_status = cfg.get("avatar_generation_status")
            render_status = status_data.get("step")
            avatar_imported_at_str = cfg.get("avatar_imported_at")

            if avatar_status != "completed":
                continue

            if render_status != "complete":
                logger.debug(
                    f"{_LOG_TAG} Skipping {project_id}: render not complete yet."
                )
                continue

            if not avatar_imported_at_str:
                continue

            imported_at = self._parse_iso(avatar_imported_at_str)
            if imported_at is None:
                continue

            age = now - imported_at
            if age < retention:
                logger.debug(
                    f"{_LOG_TAG} Skipping {project_id}: "
                    f"age {age} < retention {retention}."
                )
                continue

            # ── Perform cleanup ──
            project_bytes = 0

            # 1. Remove project avatars/ directory
            avatars_dir = project_path / "avatars"
            if avatars_dir.exists():
                project_bytes += self._dir_size(avatars_dir)
                shutil.rmtree(avatars_dir)
                logger.info(
                    f"{_LOG_TAG} Removed {project_id}/avatars/ "
                    f"({project_bytes // 1024} KB freed)"
                )

            # 2. Remove sadtalker_package/ (export artefacts)
            pkg_dir = project_path / "sadtalker_package"
            if pkg_dir.exists():
                pkg_bytes = self._dir_size(pkg_dir)
                shutil.rmtree(pkg_dir)
                project_bytes += pkg_bytes
                logger.info(
                    f"{_LOG_TAG} Removed {project_id}/sadtalker_package/ "
                    f"({pkg_bytes // 1024} KB freed)"
                )

            # 3. Remove Drive completed folder
            completed_dir = settings.sadtalker_completed_path / f"project_{project_id}"
            if completed_dir.exists():
                drive_bytes = self._dir_size(completed_dir)
                shutil.rmtree(completed_dir)
                project_bytes += drive_bytes
                logger.info(
                    f"{_LOG_TAG} Removed Drive completed/{project_id}/ "
                    f"({drive_bytes // 1024} KB freed)"
                )

            if project_bytes > 0:
                bytes_freed += project_bytes
                cleaned.append(project_id)

        # Enforce Cache Retention Policy (Refinement E & 7)
        cache_summary = {"orphans": 0, "expired": 0, "lru": 0, "bytes_freed": 0}
        try:
            from services.avatar.cache import AvatarCacheService
            cache_service = AvatarCacheService()
            cache_summary = cache_service.cleanup_cache()
            bytes_freed += cache_summary.get("bytes_freed", 0)
        except Exception as exc:
            logger.error(f"{_LOG_TAG} Failed to run cache cleanup: {exc}", exc_info=True)

        if cleaned or cache_summary.get("bytes_freed", 0) > 0:
            logger.info(
                f"{_LOG_TAG} Cleanup complete: {len(cleaned)} project(s) cleaned. "
                f"Cache purged: orphans={cache_summary['orphans']}, expired={cache_summary['expired']}, lru={cache_summary['lru']}. "
                f"{bytes_freed // 1024} KB total freed across workspace."
            )
        else:
            logger.debug(f"{_LOG_TAG} Cleanup complete: nothing to remove.")

        return {"projects_cleaned": cleaned, "bytes_freed": bytes_freed}

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _dir_size(path: Path) -> int:
        """Return the total size of *path* (recursive) in bytes."""
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

    @staticmethod
    def _parse_iso(s: str) -> Optional[datetime]:
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
