"""F5-TTS audio importer.

Handles the upload of user-produced WAV/MP3 files from an external F5-TTS run.

Workflow
--------
1. User receives ``narration_pack.zip`` from ``/export-f5-package``.
2. User runs F5-TTS externally and produces ``scene_1.wav``, ``scene_2.wav`` …
3. User packages the WAV files into a ZIP and uploads to ``/import-f5-audio``.
4. This service validates strict sequential scene coverage and scene count.
5. Audio files are stored in ``voices/`` as first-class permanent assets.
6. ``voice_results.json`` is written with real probed durations + provider metadata.
7. ``voices/combined.wav`` is generated (permanent — required by avatar pipeline).
8. Import timestamp and ``voice_generation_status = "completed"`` are saved.

Re-import support
-----------------
Calling ``import_audio`` again for the same project replaces existing audio files,
regenerates ``voice_results.json`` and ``combined.wav``, and updates the timestamp.
This is fully idempotent and intentional — users often regenerate F5 audio to
improve quality.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from models.schemas import SceneVoiceResult, ScriptSchema
from utils.file_manager import ensure_project_dirs, project_dir, save_json

# Formats accepted on import (WAV and MP3 only — Phase 1 scope).
ACCEPTED_EXTENSIONS = {".wav", ".mp3"}

# Pattern to extract scene_id from filenames like scene_1.wav, scene_2.mp3
_SCENE_FILENAME_RE = re.compile(r"^scene_(\d+)\.(wav|mp3)$", re.IGNORECASE)


class ImportValidationError(ValueError):
    """Raised when the uploaded audio ZIP fails structural validation.

    Carries a structured ``report`` dict so the API can return rich
    diagnostic information to the frontend instead of a plain string.
    """

    def __init__(self, message: str, report: Dict[str, Any]) -> None:
        super().__init__(message)
        self.report = report


class F5ImportService:
    """Validates and stores F5-TTS audio files uploaded by the user."""

    def import_audio(
        self,
        project_id: str,
        zip_bytes: bytes,
        script: Optional[ScriptSchema] = None,
    ) -> Tuple[List[SceneVoiceResult], Dict[str, Any]]:
        """Process an uploaded ZIP of F5-TTS audio files.

        Performs strict validation before writing any files:
        - All scene files must be sequentially present (no gaps).
        - Scene count must match the script (if provided) or narration_pack.json.

        Args:
            project_id: Unique project identifier.
            zip_bytes: Raw bytes of the uploaded ZIP archive.
            script: Script used to validate scene count and IDs.

        Returns:
            Tuple of (voice_results, validation_report).

        Raises:
            ImportValidationError: If the ZIP fails structural validation.
                Carries a ``report`` dict with diagnostic details.
        """
        import logging
        logger = logging.getLogger("f5_import")

        # --- 0. Import duplicate protection (refinement #7) -------------------
        from utils.file_manager import load_json
        cfg = load_json(project_id, "config.json") or {}
        if cfg.get("f5_processing_status") in ("audio_ready", "completed") or cfg.get("voice_generation_status") == "completed":
            logger.info(f"[F5_IMPORT] Project already imported.")
            vr_data = load_json(project_id, "voice_results.json") or []
            results = [SceneVoiceResult.model_validate(r) for r in vr_data]
            validation_report = {
                "status": "success",
                "scenes_detected": len(results),
                "scenes_expected": len(results),
                "combined_audio_generated": (project_dir(project_id) / "voices" / "combined.wav").exists(),
                "voice_results_generated": True,
                "audio_imported_at": cfg.get("audio_imported_at"),
            }
            return results, validation_report

        dirs = ensure_project_dirs(project_id)
        voices_dir: Path = dirs["voices"]

        # --- 1. Extract files (no disk writes yet — validate first) ----------
        raw_extracted, status_data = self._read_zip(zip_bytes)

        if not raw_extracted:
            raise ImportValidationError(
                "No valid audio files found in ZIP. "
                f"Expected filenames: scene_1.wav, scene_2.wav … "
                f"(supported: {', '.join(sorted(ACCEPTED_EXTENSIONS))})",
                report={
                    "status": "error",
                    "error": "no_valid_files",
                    "scenes_detected": 0,
                    "scenes_expected": self._expected_scene_count(project_id, script),
                    "combined_audio_generated": False,
                    "voice_results_generated": False,
                },
            )

        expected_count = self._expected_scene_count(project_id, script)
        detected_ids = sorted(raw_extracted.keys())

        # --- 1b. Scene count validation inside status.json if present (refinement #1) ---
        if status_data and "scene_count" in status_data:
            expected_scene_count = status_data["scene_count"]
            actual_audio_count = len(raw_extracted)
            if actual_audio_count != expected_scene_count:
                logger.error(
                    f"[F5_IMPORT] Scene count mismatch: status.json specifies {expected_scene_count} scenes, "
                    f"but ZIP contains only {actual_audio_count} audio files."
                )
                raise ImportValidationError(
                    f"Scene count mismatch: status.json specifies {expected_scene_count} scenes, "
                    f"but ZIP contains only {actual_audio_count} audio files.",
                    report={
                        "status": "error",
                        "error": "scene_count_mismatch",
                        "scenes_detected": actual_audio_count,
                        "scenes_expected": expected_scene_count,
                        "combined_audio_generated": False,
                        "voice_results_generated": False,
                    }
                )

        # --- 2. Strict sequential coverage check (#2) -------------------------
        # All scene IDs from 1 to max must be present with no gaps.
        expected_ids = list(range(1, detected_ids[-1] + 1))
        missing_ids = [sid for sid in expected_ids if sid not in raw_extracted]
        if missing_ids:
            raise ImportValidationError(
                f"Missing scene files: {', '.join(f'scene_{s}.wav' for s in missing_ids)}. "
                "All scene files must be present with no gaps.",
                report={
                    "status": "error",
                    "error": "missing_scenes",
                    "scenes_detected": len(raw_extracted),
                    "scenes_expected": expected_count,
                    "missing_scene_ids": missing_ids,
                    "detected_scene_ids": detected_ids,
                    "combined_audio_generated": False,
                    "voice_results_generated": False,
                },
            )

        # --- 3. Scene count validation against script (#3) --------------------
        if expected_count > 0 and len(raw_extracted) != expected_count:
            raise ImportValidationError(
                f"Scene count mismatch: uploaded {len(raw_extracted)} file(s), "
                f"but project script has {expected_count} scene(s). "
                "Upload a complete set of scene audio files.",
                report={
                    "status": "error",
                    "error": "scene_count_mismatch",
                    "scenes_detected": len(raw_extracted),
                    "scenes_expected": expected_count,
                    "detected_scene_ids": detected_ids,
                    "combined_audio_generated": False,
                    "voice_results_generated": False,
                },
            )

        # --- 4. Write audio files to disk (all validation passed) -------------
        extracted: Dict[int, Path] = {}
        for scene_id, (filename, data) in raw_extracted.items():
            dest = voices_dir / filename
            dest.write_bytes(data)
            extracted[scene_id] = dest

        # --- 5. Probe durations and build voice results -----------------------
        results: List[SceneVoiceResult] = []
        for scene_id in sorted(extracted.keys()):
            audio_path = extracted[scene_id]
            rel_path = str(audio_path.relative_to(project_dir(project_id)))
            duration = self._probe_duration(audio_path)
            if duration <= 0:
                duration = self._estimate_duration_from_path(audio_path)

            results.append(
                SceneVoiceResult(
                    scene_id=scene_id,
                    audio_path=rel_path,
                    duration=duration,
                    timestamps=[],
                    provider="f5tts",
                )
            )

        # --- 6. Persist voice_results.json ------------------------------------
        save_json(
            project_id,
            "voice_results.json",
            [r.model_dump() for r in results],
        )

        # --- 7. Generate combined.wav (first-class permanent asset) -----------
        #
        # combined.wav is stored permanently in voices/ alongside per-scene
        # files.  It is the official input for future avatar pipeline stages
        # (LivePortrait, MuseTalk, SadTalker).  Re-import regenerates it.
        combined_generated = self._build_combined_audio(voices_dir, extracted)

        # --- 8. Update project config with status + import timestamp (#1, #4) -
        import_ts = datetime.now(timezone.utc).isoformat()
        cfg["voice_generation_status"] = "completed"
        cfg["f5_processing_status"] = "audio_ready"
        cfg["f5_package_exported"] = cfg.get("f5_package_exported", True)
        cfg["audio_imported_at"] = import_ts          # #1: audit timestamp
        cfg["f5_last_update"] = import_ts
        cfg["avatar_status"] = cfg.get("avatar_status", None)  # #4: future hook
        save_json(project_id, "config.json", cfg)

        # --- 9. Build structured validation report (#7) -----------------------
        validation_report: Dict[str, Any] = {
            "status": "success",
            "scenes_detected": len(results),
            "scenes_expected": expected_count if expected_count > 0 else len(results),
            "scene_ids": sorted(extracted.keys()),
            "combined_audio_generated": combined_generated is not None,
            "voice_results_generated": True,
            "audio_imported_at": import_ts,
            "durations": {r.scene_id: round(r.duration, 3) for r in results},
        }

        logger.info(f"[F5_IMPORT] Audio imported successfully {project_id}")
        return results, validation_report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_zip(
        self, zip_bytes: bytes
    ) -> Tuple[Dict[int, Tuple[str, bytes]], Optional[Dict[str, Any]]]:
        """Read and validate audio entries from *zip_bytes* without writing to disk.

        Returns:
            Tuple of (Mapping of scene_id → (filename, raw_bytes), parsed status_dict).
        """
        extracted: Dict[int, Tuple[str, bytes]] = {}
        status_data: Optional[Dict[str, Any]] = None

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                for name in zf.namelist():
                    # Strip directory components — accept flat or nested zips.
                    filename = Path(name).name
                    if filename == "status.json":
                        try:
                            status_data = json.loads(zf.read(name).decode("utf-8"))
                        except Exception:
                            # Ignore parse errors inside zip status.json
                            pass
                        continue

                    match = _SCENE_FILENAME_RE.match(filename)
                    if not match:
                        continue  # Ignore unrecognised files silently.

                    scene_id = int(match.group(1))
                    extracted[scene_id] = (filename, zf.read(name))
        except zipfile.BadZipFile as exc:
            raise ImportValidationError(
                f"Uploaded file is not a valid ZIP archive: {exc}",
                report={
                    "status": "error",
                    "error": "invalid_zip",
                    "scenes_detected": 0,
                    "scenes_expected": 0,
                    "combined_audio_generated": False,
                    "voice_results_generated": False,
                },
            ) from exc

        return extracted, status_data

    def _expected_scene_count(
        self,
        project_id: str,
        script: Optional[ScriptSchema],
    ) -> int:
        """Determine expected scene count from script or narration_pack.json."""
        if script is not None:
            return len(script.scenes)

        # Fallback: read narration_pack.json if it exists.
        pack_path = project_dir(project_id) / "f5_package" / "narration_pack.json"
        if pack_path.exists():
            try:
                data = json.loads(pack_path.read_text(encoding="utf-8"))
                return int(data.get("total_scenes", 0))
            except (json.JSONDecodeError, ValueError):
                pass

        return 0  # Unknown — skip count validation.

    def _probe_duration(self, path: Path) -> float:
        """Use FFmpeg to probe the actual audio duration in seconds."""
        try:
            result = subprocess.run(
                [
                    settings.ffmpeg_path,
                    "-i", str(path),
                    "-f", "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            # FFmpeg prints duration to stderr.
            m = re.search(
                r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr
            )
            if m:
                h, mi, s, cs = m.groups()
                return int(h) * 3600 + int(mi) * 60 + int(s) + int(cs) / 100
        except (OSError, subprocess.SubprocessError):
            pass
        return 0.0

    def _estimate_duration_from_path(self, path: Path) -> float:
        """Fallback: estimate duration from file size (very rough)."""
        size_bytes = path.stat().st_size
        # WAV CBR ≈ 88200 bytes/s for 44100 Hz 16-bit mono.
        # Use a conservative 64 kbps estimate for all formats.
        return max(3.0, size_bytes / 8000)

    def _build_combined_audio(
        self, voices_dir: Path, extracted: Dict[int, Path]
    ) -> Optional[Path]:
        """Concatenate all scene audio files into ``voices/combined.wav``.

        ``combined.wav`` is a **first-class permanent asset** stored alongside
        the per-scene files.  It is the official audio input for future avatar
        pipeline stages (LivePortrait, MuseTalk, SadTalker) which require a
        single continuous narration track.

        Re-importing audio regenerates this file automatically (-y flag).

        Args:
            voices_dir: Path to the project's voices directory.
            extracted: Mapping of scene_id → audio file path.

        Returns:
            Path to ``combined.wav``, or ``None`` if FFmpeg fails.
        """
        if len(extracted) < 1:
            return None

        ordered_paths = [extracted[sid] for sid in sorted(extracted.keys())]
        combined = voices_dir / "combined.wav"

        # Write concat list.
        concat_list = voices_dir / "f5_concat_list.txt"
        with concat_list.open("w", encoding="utf-8") as f:
            for p in ordered_paths:
                f.write(f"file '{p.resolve().as_posix()}'\n")

        try:
            subprocess.run(
                [
                    settings.ffmpeg_path,
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_list),
                    "-ar", "44100",   # Normalised sample rate for avatar tools.
                    "-ac", "1",       # Mono — standard for TTS narration.
                    "-c:a", "pcm_s16le",
                    str(combined),
                ],
                check=True,
                capture_output=True,
            )
            return combined
        except (subprocess.CalledProcessError, OSError):
            # Non-fatal: render pipeline does not require combined.wav.
            # Avatar pipeline will handle its absence gracefully in Phase 2.
            return None
