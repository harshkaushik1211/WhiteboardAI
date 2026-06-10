"""F5-TTS narration package exporter.

Creates the ``f5_package/`` directory structure under a project directory and
produces:

- ``narration_pack.json``  — machine-readable metadata for batch processing
- ``scene_N.txt``          — one plain-text file per scene containing only
                             the narration text that F5-TTS should synthesise

The export is deliberately minimal so it can be consumed by any TTS tool, not
just F5-TTS.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from models.schemas import ScriptSchema
from utils.file_manager import project_dir


class F5ExportService:
    """Creates the F5-TTS narration package for a project."""

    # Folder name inside the project directory.
    PACKAGE_DIR = "f5_package"

    def export(self, project_id: str, script: ScriptSchema) -> Path:
        """Export narration text files and ``narration_pack.json``.

        Args:
            project_id: Unique project identifier.
            script: Parsed script with scene narrations.

        Returns:
            Path to the ``f5_package/`` directory.
        """
        pkg_dir = project_dir(project_id) / self.PACKAGE_DIR
        pkg_dir.mkdir(parents=True, exist_ok=True)

        scene_entries: List[Dict[str, Any]] = []
        for scene in script.scenes:
            text_filename = f"scene_{scene.scene_id}.txt"
            text_path = pkg_dir / text_filename

            # Write narration-only text file (no metadata, clean for TTS).
            text_path.write_text(scene.narration.strip(), encoding="utf-8")

            scene_entries.append(
                {
                    "scene_id": scene.scene_id,
                    "title": scene.visual_description[:80] if scene.visual_description else "",
                    "estimated_duration": round(scene.duration, 2),
                    "text_file": text_filename,
                }
            )

        pack_meta: Dict[str, Any] = {
            "project_id": project_id,
            "voice_provider": "f5tts",
            "total_scenes": len(script.scenes),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scenes": scene_entries,
        }

        pack_path = pkg_dir / "narration_pack.json"
        pack_path.write_text(
            json.dumps(pack_meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return pkg_dir

    def build_zip(self, project_id: str) -> bytes:
        """Build an in-memory ZIP archive of the narration package.

        The ZIP contains:
        - ``narration_pack.json``
        - ``scene_1.txt``, ``scene_2.txt``, … etc.

        Args:
            project_id: Unique project identifier.

        Returns:
            Raw ZIP bytes suitable for returning as a file download.

        Raises:
            FileNotFoundError: If the package has not been exported yet.
        """
        pkg_dir = project_dir(project_id) / self.PACKAGE_DIR
        if not pkg_dir.exists():
            raise FileNotFoundError(
                f"F5 narration package not found for project {project_id}. "
                "Run /generate-voice with voice_provider='f5tts' first."
            )

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(pkg_dir.iterdir()):
                if file_path.is_file():
                    zf.write(file_path, arcname=file_path.name)
        return buf.getvalue()
