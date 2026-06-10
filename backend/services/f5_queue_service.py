"""F5 Queue Service.

Handles enqueuing of F5-TTS projects by copying narration packages
to the configured Google Drive queue folder.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config import settings
from utils.file_manager import project_dir, load_json, save_json

logger = logging.getLogger("f5_queue")


class F5QueueService:
    """Service to automatically enqueue projects to the Google Drive queue folder."""

    def enqueue_project(self, project_id: str) -> None:
        """Enqueue the project narration package to the Google Drive queue directory.

        Args:
            project_id: The project identifier.

        Raises:
            ValueError: If the project_id is invalid or contains path traversal.
            FileNotFoundError: If the source narration package is missing.
            RuntimeError: If Google Drive folders cannot be accessed or written to.
        """
        logger.info(f"[F5_QUEUE] Enqueuing project {project_id}")

        # 1. Safe project ID validation (reliability enhancement #3)
        if not re.match(r"^[a-zA-Z0-9_-]+$", project_id):
            logger.error(f"[F5_QUEUE] Invalid project ID: {project_id}")
            raise ValueError(f"Invalid project_id: {project_id}")

        # 2. Locate source narration package directory
        source_dir = project_dir(project_id) / "f5_package"
        if not source_dir.exists():
            logger.error(f"[F5_QUEUE] Narration package directory does not exist at {source_dir}")
            raise FileNotFoundError(
                f"Narration package not found for project {project_id}. "
                "Ensure generate-voice was called first."
            )

        # 3. Resolve target directory under Google Drive queue path
        queue_path = settings.f5_queue_path
        try:
            queue_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[F5_QUEUE] Failed to access/create queue path {queue_path}: {e}")
            raise RuntimeError(f"Failed to access Google Drive queue folder: {e}")

        target_dir = queue_path / f"project_{project_id}"

        # Clean existing queue folder if duplicate exists to avoid stale files
        if target_dir.exists():
            logger.warning(f"[F5_QUEUE] Duplicate queue directory {target_dir} exists. Cleaning it first.")
            shutil.rmtree(target_dir)

        target_dir.mkdir(parents=True, exist_ok=True)

        # 4. Copy package files (narration_pack.json and scene_*.txt)
        copied_files = []
        for file_path in source_dir.iterdir():
            if file_path.is_file() and (
                file_path.name == "narration_pack.json" or file_path.name.startswith("scene_")
            ):
                dest = target_dir / file_path.name
                shutil.copy2(file_path, dest)
                copied_files.append(file_path.name)

        if not copied_files:
            logger.error(f"[F5_QUEUE] No narration pack or scene files found in {source_dir}")
            raise FileNotFoundError(f"No valid files to enqueue found in {source_dir}")

        # 5. Write queue_status.json (with version and timestamps - refinements #2, #6)
        status_path = target_dir / "queue_status.json"
        now_str = datetime.now(timezone.utc).isoformat()
        status_data = {
            "project_id": project_id,
            "status": "queued",
            "version": 1,
            "created_at": now_str,
        }

        try:
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            logger.error(f"[F5_QUEUE] Failed to write queue_status.json: {e}")
            raise RuntimeError(f"Failed to write queue status file: {e}")

        # 6. Update local project config
        cfg = load_json(project_id, "config.json") or {}
        cfg["f5_processing_status"] = "queued"
        cfg["f5_queued_at"] = now_str
        cfg["f5_last_update"] = now_str
        save_json(project_id, "config.json", cfg)

        logger.info(f"[F5_QUEUE] Project {project_id} queued successfully under {target_dir}")
