"""SadTalker avatar provider — Phase-4 Architecture Review.

P1: Exports a SINGLE combined audio + portrait package.
P6: Checks the avatar cache before triggering export/queue.
P12: Structured [AVATAR_EXPORT] / [AVATAR_CACHE] logging.

SadTalker is an external tool run via Google Colab.  This provider does NOT
generate video clips directly.  Instead, ``generate()`` triggers the export
workflow:

    generate-avatar (sadtalker mode)
        → P6: Check AvatarCacheService — if HIT, copy cached clip and mark complete
        → P6 MISS: SadTalkerExportService.export(project_id, script, avatar_source)
              → <project>/sadtalker_package/avatar_manifest.json  (P4 versioned)
              → <project>/sadtalker_package/combined.wav           (P1 single audio)
              → <project>/sadtalker_package/source_image.png
              → ZIP returned via /export-sadtalker-package
        → SadTalkerQueueService.enqueue_project(project_id)

The user (or Colab automation) then:
    1. Downloads the ZIP
    2. Runs SadTalker → background removal → exports avatar.webm (P5 transparent)
    3. Uploads via /import-sadtalker-clips

This pattern is IDENTICAL to the F5-TTS voice provider workflow.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from config import settings
from models.schemas import AvatarResult, AvatarProviderCapabilities
from services.avatar.exporter import SadTalkerExportService
from services.avatar.providers.base import AvatarProvider
from services.avatar.queue_service import SadTalkerQueueService
from services.avatar.metrics import AvatarMetricsService
from utils.file_manager import load_json, project_dir, save_json

logger = logging.getLogger("sadtalker_provider")


class SadTalkerProvider(AvatarProvider):
    """Avatar provider that exports a single-audio clip package for SadTalker.

    P1: Packages combined.wav (not per-scene clips).
    P6: Checks the avatar cache before triggering export.
    Clips are imported later via /import-sadtalker-clips.
    """

    name: str = "sadtalker"

    def get_capabilities(self) -> AvatarProviderCapabilities:
        """Get capabilities descriptor for SadTalker (Refinement I & Hardening 6)."""
        return AvatarProviderCapabilities(
            supports_transparency=True,
            supports_live_generation=False,
            supports_high_quality=True,
        )

    async def generate(
        self,
        project_id: str,
        script,  # ScriptSchema — avoid circular import at module level
        avatar_source: str,
    ) -> List[AvatarResult]:
        """Export avatar package for external SadTalker processing.

        P6: First checks whether a cached clip exists for the same
        (portrait, audio) pair.  If so, copies it and marks generation
        complete — no Colab run needed.
        """
        proj = project_dir(project_id)
        cfg = load_json(project_id, "config.json") or {}
        metrics_service = AvatarMetricsService()

        # ── P6: Cache check ───────────────────────────────────────────────────
        image_path = proj / avatar_source
        combined_wav = proj / "voices" / "combined.wav"
        if not combined_wav.exists():
            combined_wav = proj / "voices" / "combined.mp3"

        quality = cfg.get("avatar_quality", settings.avatar_quality)
        provider_version = "sadtalker_v1"

        from services.avatar.cache import AvatarCacheService
        cache = AvatarCacheService()
        cache_key = AvatarCacheService.compute_key(
            provider_version,
            quality,
            image_path if image_path.exists() else None,
            combined_wav if combined_wav.exists() else None,
        )

        avatars_dir = proj / "avatars"
        cached_clip = cache.copy_from_cache(cache_key, avatars_dir)

        if cached_clip is not None:
            logger.info(
                f"[AVATAR_CACHE] Cache HIT for project {project_id} "
                f"(key={cache_key[:8]}…). Skipping SadTalker export/queue."
            )
            # Record cache hit and GPU jobs saved (Refinement H & Hardening 10)
            metrics_service.update_metrics(cache_hits=1, gpu_jobs_saved=1)

            # Build and persist AvatarResult from cached clip
            from services.avatar.importer import SadTalkerImportService
            import io, zipfile
            # Build an in-memory ZIP so we can reuse the import path
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.write(cached_clip, arcname=cached_clip.name)
            # Run import (will validate durations and persist avatar_result.json)
            importer = SadTalkerImportService()
            result, _ = importer.import_clips(project_id, buf.getvalue(), cache_hit=True)

            cfg["avatar_generation_status"] = "completed"
            cfg["sadtalker_package_exported"] = False  # no Drive export needed
            cfg["avatar_cache_key"] = cache_key
            save_json(project_id, "config.json", cfg)
            return [result]

        # ── Queue size protection check (Refinement G & Hardening 3) ──────────
        # Bypassed on cache hit (Final Architecture Adjustment)
        queue_path = settings.sadtalker_queue_path
        processing_path = settings.sadtalker_processing_path

        queue_count = sum(1 for entry in queue_path.iterdir() if entry.is_dir()) if queue_path.exists() else 0
        processing_count = sum(1 for entry in processing_path.iterdir() if entry.is_dir()) if processing_path.exists() else 0

        if (queue_count + processing_count) >= settings.max_avatar_queue_size:
            logger.warning(
                f"[AVATAR_QUEUE] Generation rejected: queue+processing count "
                f"({queue_count + processing_count}) >= limit ({settings.max_avatar_queue_size})"
            )
            metrics_service.update_metrics(failed_avatar_generations=1)
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="Avatar queue is currently full. Please try again later."
            )

        # ── Export package ────────────────────────────────────────────────────
        logger.info(
            f"[AVATAR_EXPORT] Cache MISS for project {project_id}; "
            "building export package."
        )
        metrics_service.update_metrics(cache_misses=1, total_avatar_generations=1)

        exporter = SadTalkerExportService()
        exporter.export(project_id, script, avatar_source)

        # ── Enqueue to Google Drive ────────────────────────────────────────────
        queue_service = SadTalkerQueueService()
        queue_service.enqueue_project(project_id)

        # ── Update status flags ───────────────────────────────────────────────
        cfg["avatar_generation_status"] = "pending"
        cfg["sadtalker_package_exported"] = True
        cfg["avatar_cache_key"] = cache_key
        save_json(project_id, "config.json", cfg)

        logger.info(
            f"[AVATAR_EXPORT] Package exported and queued for project {project_id}."
        )
        return []
