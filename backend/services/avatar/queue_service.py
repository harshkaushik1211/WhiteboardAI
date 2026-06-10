"""SadTalker Queue Service — Phase-4 Architecture Review.

P4: All status files include ``manifest_version``, ``provider``, ``provider_version``.

P11: Writes a ``worker.json`` heartbeat scaffold into the queue folder so
     the watcher (P3) can detect dead workers.

P12: All log lines use structured ``[AVATAR_QUEUE]`` prefix.

Handles enqueuing of SadTalker projects by copying the avatar package
to the configured Google Drive queue folder for Colab worker pickup.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config import settings
from utils.file_manager import load_json, project_dir, save_json

logger = logging.getLogger("sadtalker_queue")

# P4 manifest version constants
MANIFEST_VERSION = 1
PROVIDER = "sadtalker"
PROVIDER_VERSION = "sadtalker_v1"


class SadTalkerQueueService:
    """Service to automatically enqueue projects to the SadTalker Drive queue folder."""

    def enqueue_project(self, project_id: str) -> None:
        """Enqueue the project avatar package to the Google Drive queue directory.

        Args:
            project_id: The project identifier.

        Raises:
            ValueError: If the project_id is invalid or contains path traversal.
            FileNotFoundError: If the source avatar package is missing.
            RuntimeError: If Google Drive folders cannot be accessed or written to.
        """
        logger.info(f"[AVATAR_QUEUE] Enqueuing project {project_id}")

        # ── 1. Validate project ID ────────────────────────────────────────────
        if not re.match(r"^[a-zA-Z0-9_-]+$", project_id):
            logger.error(f"[AVATAR_QUEUE] Invalid project ID: {project_id}")
            raise ValueError(f"Invalid project_id: {project_id}")

        # ── 2. Locate source avatar package ───────────────────────────────────
        source_dir = project_dir(project_id) / "sadtalker_package"
        if not source_dir.exists():
            logger.error(
                f"[AVATAR_QUEUE] Package directory missing: {source_dir}"
            )
            raise FileNotFoundError(
                f"Avatar package not found for project {project_id}. "
                "Ensure /generate-avatar was called first."
            )

        # ── 3. Prepare target queue directory ─────────────────────────────────
        queue_path = settings.sadtalker_queue_path
        try:
            queue_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(
                f"[AVATAR_QUEUE] Cannot access/create queue path {queue_path}: {e}"
            )
            raise RuntimeError(f"Failed to access SadTalker Google Drive queue folder: {e}")

        target_dir = queue_path / f"project_{project_id}"

        # Clean stale entry if present to avoid file conflicts
        if target_dir.exists():
            logger.warning(
                f"[AVATAR_QUEUE] Stale queue directory {target_dir} found; cleaning."
            )
            shutil.rmtree(target_dir)

        target_dir.mkdir(parents=True, exist_ok=True)

        # ── 4. Copy package files ─────────────────────────────────────────────
        copied_files = []
        for file_path in source_dir.iterdir():
            if file_path.is_file():
                dest = target_dir / file_path.name
                shutil.copy2(file_path, dest)
                copied_files.append(file_path.name)

        if not copied_files:
            logger.error(f"[AVATAR_QUEUE] No files to copy in {source_dir}")
            raise FileNotFoundError(f"No valid files to enqueue found in {source_dir}")

        now_str = datetime.now(timezone.utc).isoformat()

        # ── 5. Write queue_status.json (P4 versioned) ─────────────────────────
        status_data = {
            "manifest_version": MANIFEST_VERSION,      # P4
            "provider": PROVIDER,                       # P4
            "provider_version": PROVIDER_VERSION,       # P4
            "project_id": project_id,
            "status": "queued",
            "created_at": now_str,
            "files": copied_files,
        }
        try:
            (target_dir / "queue_status.json").write_text(
                json.dumps(status_data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"[AVATAR_QUEUE] Failed to write queue_status.json: {e}")
            raise RuntimeError(f"Failed to write queue status file: {e}")

        # ── 6. Write worker.json heartbeat scaffold (P11) ─────────────────────
        # The Colab worker updates this file during processing.
        # The watcher (P3) reads last_heartbeat to detect dead workers.
        worker_scaffold = {
            "worker": None,           # Colab worker fills this in ("sadtalker_colab")
            "started_at": None,       # Worker fills on job start
            "last_heartbeat": None,   # Worker updates periodically (every ~30s)
            "progress_pct": 0,        # Worker updates during generation
            "current_scene": None,    # Worker fills with current scene being processed
        }
        try:
            (target_dir / "worker.json").write_text(
                json.dumps(worker_scaffold, indent=2), encoding="utf-8"
            )
        except Exception as e:
            # Non-fatal; watcher falls back to queue_status.json::created_at
            logger.warning(f"[AVATAR_QUEUE] Could not write worker.json: {e}")

        # ── 7. Update local project config ────────────────────────────────────
        cfg = load_json(project_id, "config.json") or {}
        cfg["sadtalker_processing_status"] = "queued"
        cfg["sadtalker_queued_at"] = now_str
        cfg["sadtalker_last_update"] = now_str
        save_json(project_id, "config.json", cfg)

        logger.info(
            f"[AVATAR_QUEUE] Project {project_id} queued successfully → {target_dir} "
            f"({len(copied_files)} file(s))"
        )
