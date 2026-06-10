"""SadTalker Import Service — Phase-4 Architecture Review.

P1: Accepts a single ``avatar.webm`` (or ``avatar.mp4`` + ``avatar_mask.mp4``
    fallback) instead of per-scene clips.  The single video is driven by the
    full combined audio.

P2: Duration validation — probes both ``combined.wav`` and ``avatar.webm``
    with ffprobe.  If ``abs(audio - video) > tolerance``, marks the result as
    duration_valid=False and stores a validation report.  Import succeeds
    (not an error) so the render pipeline can proceed without the avatar (P7).

P6: After a successful import the clip is stored in the avatar cache under its
    SHA-256 key so subsequent identical requests skip SadTalker entirely.

P12: All log lines use structured ``[AVATAR_IMPORT]`` / ``[AVATAR_CACHE]`` prefixes.

Expected ZIP layout from Colab worker:

    avatar.webm              ← transparent VP9/alpha WebM  (preferred)
    avatar.mp4               ← fallback when alpha unsupported
    avatar_mask.mp4          ← greyscale matte (pair with avatar.mp4)
    status.json              ← optional worker metadata / heartbeat info

After import:

    <project>/avatars/avatar.webm   (or .mp4)
    <project>/avatar_result.json    ← project-level AvatarResult
    config.json                     ← updated avatar_generation_status
"""

from __future__ import annotations

import io
import json
import logging
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from config import settings
from models.schemas import AvatarResult
from utils.file_manager import load_json, project_dir, save_json

logger = logging.getLogger("sadtalker_import")

# Accepted primary clip filenames (in preference order).
_PRIMARY_CLIP_NAMES = ("avatar.webm", "avatar.mp4")
_FALLBACK_MASK_NAME = "avatar_mask.mp4"


class ImportValidationError(Exception):
    """Raised when the imported archive has a critical structural failure."""

    def __init__(self, message: str, report: dict):
        super().__init__(message)
        self.report = report


class SadTalkerImportService:
    """Validates and imports a SadTalker avatar clip into a project.

    P1: Handles a single project-level video (not per-scene clips).
    P2: Validates duration drift against ``settings.avatar_duration_tolerance``.
    P6: Stores imported clip in the avatar cache after successful validation.
    """

    def import_clips(
        self,
        project_id: str,
        zip_bytes: bytes,
        script=None,  # kept for API compatibility; unused in single-video flow
        cache_hit: bool = False,
    ) -> Tuple[AvatarResult, dict]:
        """Import SadTalker avatar ZIP into the project.

        Args:
            project_id: Unique project identifier.
            zip_bytes: Raw bytes of the uploaded ZIP archive.
            script: Unused; kept for API backward compatibility.
            cache_hit: True if this result is restored from cache (skips timing).

        Returns:
            Tuple of:
            - :class:`AvatarResult` with clip path, duration, and validation info.
            - Validation report dict for the API response.

        Raises:
            ImportValidationError: On structural failures (no clip found, bad ZIP).
        """
        proj = project_dir(project_id)
        avatars_dir = proj / "avatars"
        avatars_dir.mkdir(parents=True, exist_ok=True)

        now_str = datetime.now(timezone.utc).isoformat()
        cfg = load_json(project_id, "config.json") or {}

        # ── Report scaffold ───────────────────────────────────────────────────
        report: dict = {
            "status": "pending",
            "clip_imported": None,
            "has_mask": False,
            "avatar_duration_sec": None,
            "audio_duration_sec": None,
            "duration_drift_sec": None,
            "duration_valid": None,
            "duration_tolerance_sec": settings.avatar_duration_tolerance,
            "avatar_result_generated": False,
            "avatar_imported_at": None,
            "cache_stored": False,
        }

        # ── Extract ZIP ───────────────────────────────────────────────────────
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
        except zipfile.BadZipFile as exc:
            raise ImportValidationError("Uploaded file is not a valid ZIP.", report) from exc

        names_in_zip = {Path(n).name.lower(): n for n in zf.namelist()}

        # ── 1. Locate and extract clips (Refinement B — store original output) ──
        clip_dest: Optional[Path] = None

        # Extract original output if present in the ZIP
        if "avatar_original.mp4" in names_in_zip:
            orig_dest = avatars_dir / "avatar_original.mp4"
            orig_dest.write_bytes(zf.read(names_in_zip["avatar_original.mp4"]))
            logger.info("[AVATAR_IMPORT] Extracted original clip: avatar_original.mp4")
        elif "avatar.mp4" in names_in_zip and "avatar.webm" in names_in_zip:
            orig_dest = avatars_dir / "avatar_original.mp4"
            orig_dest.write_bytes(zf.read(names_in_zip["avatar.mp4"]))
            logger.info("[AVATAR_IMPORT] Saved avatar.mp4 as avatar_original.mp4")

        # Extract primary visual clip (webm preferred)
        for candidate in _PRIMARY_CLIP_NAMES:
            if candidate in names_in_zip:
                clip_dest = avatars_dir / candidate
                clip_dest.write_bytes(zf.read(names_in_zip[candidate]))
                logger.info(f"[AVATAR_IMPORT] Extracted primary clip: {candidate}")
                break

        if clip_dest is None:
            raise ImportValidationError(
                "No avatar clip found in ZIP. Expected 'avatar.webm' or 'avatar.mp4'.",
                report,
            )

        report["clip_imported"] = str(clip_dest.relative_to(proj))

        # ── 2. Extract mask if present (P5 fallback) ──────────────────────────
        if _FALLBACK_MASK_NAME in names_in_zip:
            mask_dest = avatars_dir / _FALLBACK_MASK_NAME
            mask_dest.write_bytes(zf.read(names_in_zip[_FALLBACK_MASK_NAME]))
            report["has_mask"] = True
            logger.info("[AVATAR_IMPORT] Extracted avatar_mask.mp4 (fallback matte)")

        # ── 3. Extract worker status.json if present ──────────────────────────
        if "status.json" in names_in_zip:
            status_data = json.loads(zf.read(names_in_zip["status.json"]).decode("utf-8"))
            logger.info(f"[AVATAR_IMPORT] Worker status: {status_data.get('status')}")

        # ── 4. Duration validation (P2) ───────────────────────────────────────
        avatar_dur = self._probe_duration(clip_dest)
        report["avatar_duration_sec"] = avatar_dur

        # Probe combined audio from voices/
        audio_path = proj / "voices" / "combined.wav"
        if not audio_path.exists():
            audio_path = proj / "voices" / "combined.mp3"

        audio_dur = self._probe_duration(audio_path) if audio_path.exists() else 0.0
        report["audio_duration_sec"] = audio_dur

        drift = abs(avatar_dur - audio_dur)
        report["duration_drift_sec"] = round(drift, 4)

        duration_valid = drift <= settings.avatar_duration_tolerance
        report["duration_valid"] = duration_valid

        if not duration_valid:
            logger.warning(
                f"[AVATAR_IMPORT] Duration mismatch for project {project_id}: "
                f"audio={audio_dur:.3f}s avatar={avatar_dur:.3f}s "
                f"drift={drift:.4f}s > tolerance={settings.avatar_duration_tolerance}s. "
                "Marking duration_valid=False — render will fall back to whiteboard+audio."
            )
        else:
            logger.info(
                f"[AVATAR_IMPORT] Duration OK: audio={audio_dur:.3f}s "
                f"avatar={avatar_dur:.3f}s drift={drift:.4f}s"
            )

        # Compute generation time (Refinement C)
        generation_time = None
        if cache_hit:
            generation_time = 0.0
        else:
            # Parse timing from zipped status.json
            if "status.json" in names_in_zip:
                try:
                    status_data = json.loads(zf.read(names_in_zip["status.json"]).decode("utf-8"))
                    started_str = status_data.get("started_at")
                    completed_str = status_data.get("completed_at")
                    if started_str and completed_str:
                        generation_time = (datetime.fromisoformat(completed_str) - datetime.fromisoformat(started_str)).total_seconds()
                except Exception:
                    pass

            if generation_time is None:
                # Fallback: check config for queued_at
                queued_at_str = cfg.get("sadtalker_queued_at")
                if queued_at_str:
                    try:
                        queued_at = datetime.fromisoformat(queued_at_str)
                        generation_time = (datetime.now(timezone.utc) - queued_at).total_seconds()
                    except Exception:
                        pass

        # Update metrics (Refinement H & Hardening 10)
        try:
            from services.avatar.metrics import AvatarMetricsService
            metrics_service = AvatarMetricsService()
            if duration_valid:
                if not cache_hit:
                    if generation_time is not None:
                        metrics_service.record_generation_time(generation_time)
                    else:
                        metrics_service.update_metrics(successful_avatar_generations=1)
            else:
                metrics_service.update_metrics(failed_avatar_generations=1)
        except Exception as exc:
            logger.warning(f"[AVATAR_IMPORT] Metrics update failed: {exc}")

        # ── 5. Load cache key from config (set by exporter) ───────────────────
        cache_key = cfg.get("avatar_cache_key")

        # ── 6. Store in avatar cache (P6) ─────────────────────────────────────
        cache_stored = False
        if cache_key and duration_valid and not cache_hit:
            try:
                from services.avatar.cache import AvatarCacheService
                AvatarCacheService().store_cache(cache_key, clip_dest)
                cache_stored = True
                logger.info(f"[AVATAR_CACHE] Clip cached under key {cache_key[:8]}…")
            except Exception as exc:
                logger.warning(f"[AVATAR_CACHE] Cache store failed (non-fatal): {exc}")

        report["cache_stored"] = cache_stored

        # ── 7. Build AvatarResult (Refinement A & C) ──────────────────────────
        manifest_version = cfg.get("avatar_manifest_version", 1)
        rel_path = str(clip_dest.relative_to(proj))

        result = AvatarResult(
            avatar_schema_version=1,
            clip_path=rel_path,
            total_duration=avatar_dur,
            audio_duration=audio_dur,
            duration_valid=duration_valid,
            duration_drift=round(drift, 4),
            provider="sadtalker",
            provider_version="sadtalker_v1",
            manifest_version=manifest_version,
            cache_key=cache_key,
            layout=cfg.get("avatar_layout", "pip"),
            # Diagnostic report (Refinement C)
            background_removed=bool(clip_dest and clip_dest.suffix.lower() == ".webm"),
            cache_hit=cache_hit,
            generation_time_seconds=generation_time,
            validation_passed=duration_valid,
        )

        # ── 8. Persist avatar_result.json ─────────────────────────────────────
        save_json(project_id, "avatar_result.json", result.model_dump())

        # ── 9. Update project config ──────────────────────────────────────────
        # P7: If duration invalid, mark as "failed" so render can proceed without avatar
        if duration_valid:
            cfg["avatar_generation_status"] = "completed"
            cfg["sadtalker_processing_status"] = "completed"
        else:
            cfg["avatar_generation_status"] = "failed"
            cfg["sadtalker_processing_status"] = "failed_duration_mismatch"

        cfg["avatar_imported_at"] = now_str
        cfg["sadtalker_last_update"] = now_str
        save_json(project_id, "config.json", cfg)

        save_json(project_id, "status.json", {"step": "avatar_imported"})

        report["status"] = "completed" if duration_valid else "failed_duration_mismatch"
        report["avatar_result_generated"] = True
        report["avatar_imported_at"] = now_str

        logger.info(
            f"[AVATAR_IMPORT] Import {'complete' if duration_valid else 'FAILED (duration)'} "
            f"for project {project_id}: {rel_path}"
        )
        return result, report

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _probe_duration(self, path: Path) -> float:
        """Probe media file duration using ffprobe (P2)."""
        ffmpeg_path = Path(settings.ffmpeg_path)
        ffprobe_name = (
            ffmpeg_path.name
            .replace("ffmpeg", "ffprobe")
            .replace("FFMPEG", "FFPROBE")
        )
        ffprobe = str(ffmpeg_path.parent / ffprobe_name)
        if not Path(ffprobe).exists():
            import shutil as sh
            resolved = sh.which("ffprobe")
            ffprobe = resolved or "ffprobe"
        try:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            logger.warning(f"[AVATAR_IMPORT] ffprobe failed for {path}; returning 0.0")
            return 0.0
