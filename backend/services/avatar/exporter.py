"""SadTalker Export Service — Phase-4 Architecture Review.

P1: Generates ONE avatar video per project (not per-scene).
    Packages ``combined.wav`` (the full narration audio) + source image.
    The Colab worker generates a single ``avatar.webm`` driven by the full audio.
    The renderer uses per-scene frame offsets to show the correct window.

P4: All manifests are versioned with ``manifest_version``, ``provider``,
    and ``provider_version`` fields.

P5: ``background_removal`` instructions are embedded in the manifest so the
    Colab worker knows which tool to use (BiRefNet → BRIA → RMBG-2.0 fallback).

P6: A SHA-256 cache key is computed from source_image + combined_audio bytes
    and embedded in the manifest.  The importer uses this to populate the cache.

P12: All log lines use structured ``[AVATAR_EXPORT]`` prefix.

Package layout:

    <project>/sadtalker_package/
        avatar_manifest.json    ← versioned, machine-readable spec
        combined.wav            ← full narration audio (all scenes concatenated)
        source_image.{ext}      ← reference portrait photo

ZIP returned from ``/export-sadtalker-package``.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from models.schemas import ScriptSchema
from utils.file_manager import load_json, project_dir, save_json

logger = logging.getLogger("sadtalker_export")

# Manifest schema version (increment when structure changes).
MANIFEST_VERSION = 1
PROVIDER = "sadtalker"
PROVIDER_VERSION = "sadtalker_v1"


class SadTalkerExportService:
    """Builds the combined-audio + source-image package for SadTalker processing.

    P1: Exports ONE combined audio track (not per-scene clips) so the Colab
    worker generates a single avatar video driven by the full narration.
    """

    def export(
        self,
        project_id: str,
        script: ScriptSchema,
        avatar_source: str,
    ) -> Path:
        """Create ``sadtalker_package/`` with combined audio + source image.

        Args:
            project_id: Unique project identifier.
            script: Full script (used for timeline metadata in the manifest).
            avatar_source: Relative path to the source image inside the project
                folder (e.g. ``"avatar/source.png"``).

        Returns:
            Path to the created ``sadtalker_package/`` directory.
        """
        proj = project_dir(project_id)
        pkg_dir = proj / "sadtalker_package"
        pkg_dir.mkdir(parents=True, exist_ok=True)

        now_str = datetime.now(timezone.utc).isoformat()

        # ── 1. Source image ───────────────────────────────────────────────────
        src_img_path = proj / avatar_source
        if src_img_path.exists():
            dest_img_name = f"source_image{src_img_path.suffix}"
            dest_img = pkg_dir / dest_img_name
            shutil.copy2(src_img_path, dest_img)
            logger.info(f"[AVATAR_EXPORT] Copied source image: {dest_img_name}")
        else:
            dest_img_name = "source_image.png"
            dest_img = pkg_dir / dest_img_name
            logger.warning(
                f"[AVATAR_EXPORT] Source image not found at {src_img_path}; "
                "continuing without it — worker must supply one."
            )

        # ── 2. Combined audio (P1 — single track instead of per-scene) ────────
        combined_audio_src = proj / "voices" / "combined.wav"
        combined_audio_dest: Path | None = None

        if combined_audio_src.exists():
            combined_audio_dest = pkg_dir / "combined.wav"
            shutil.copy2(combined_audio_src, combined_audio_dest)
            logger.info("[AVATAR_EXPORT] Copied combined.wav for single-video generation")
        else:
            # Fallback: try combined.mp3
            combined_mp3 = proj / "voices" / "combined.mp3"
            if combined_mp3.exists():
                combined_audio_dest = pkg_dir / "combined.mp3"
                shutil.copy2(combined_mp3, combined_audio_dest)
                logger.info("[AVATAR_EXPORT] Copied combined.mp3 (WAV not available)")
            else:
                logger.warning(
                    "[AVATAR_EXPORT] No combined audio found in voices/. "
                    "The worker must generate speech separately."
                )

        # Get provider version and quality settings from project config
        cfg = load_json(project_id, "config.json") or {}
        quality = cfg.get("avatar_quality", settings.avatar_quality)

        # ── 3. Compute SHA-256 cache key (P6 & Hardening 2) ───────────────────
        from services.avatar.cache import AvatarCacheService
        cache_key = AvatarCacheService.compute_key(
            PROVIDER_VERSION,
            quality,
            dest_img if dest_img.exists() else None,
            combined_audio_dest,
        )
        logger.info(f"[AVATAR_CACHE] Cache key: {cache_key}")

        # ── 4. Build scene timeline metadata for renderer sync ────────────────
        scene_timeline = []
        elapsed = 0.0
        for scene in script.scenes:
            scene_timeline.append({
                "scene_id": scene.scene_id,
                "start_sec": round(elapsed, 3),
                "end_sec": round(elapsed + scene.duration, 3),
                "duration_sec": round(scene.duration, 3),
                "narration": scene.narration,
            })
            elapsed += scene.duration

        # Map quality presets (Refinement D)
        sadtalker_config = {
            "still": True,
            "preprocess": "full",
            "result_dir": "results",
            "enhancer": None,
            "background_enhancer": None,
            "size": 256,
            "expression_scale": 1.0,
            "pose_style": 0,
        }
        if quality == "fast":
            sadtalker_config["preprocess"] = "resize"
            sadtalker_config["size"] = 256
        elif quality == "high":
            sadtalker_config["preprocess"] = "full"
            sadtalker_config["size"] = 512
            sadtalker_config["enhancer"] = "gfpgan"

        # ── 5. Write avatar_manifest.json (P4 versioned + Refinement A) ───────
        manifest = {
            # Refinement A: Schema & Versioning
            "avatar_schema_version": 1,
            "manifest_version": MANIFEST_VERSION,
            "provider": PROVIDER,
            "provider_version": PROVIDER_VERSION,
            "avatar_quality": quality,
            # Project metadata
            "project_id": project_id,
            "title": script.title,
            "created_at": now_str,
            "total_duration_sec": round(elapsed, 3),
            # Input files
            "source_image": dest_img_name,
            "audio_file": combined_audio_dest.name if combined_audio_dest else None,
            # P6: Cache key
            "cache_key": cache_key,
            # Scene timeline for renderer synchronization
            "scene_timeline": scene_timeline,
            # P5: Background removal instructions for Colab worker
            "background_removal": {
                "enabled": True,
                "priority": ["birefnet", "bria_rmbg", "rmbg_2"],
                "output_format": "webm_alpha",   # VP9 WebM with transparency
                "fallback_format": "mp4+mask",   # avatar.mp4 + avatar_mask.mp4
                "description": (
                    "Worker MUST remove the background and export transparent WebM. "
                    "Use BiRefNet as priority, fall back to BRIA RMBG or RMBG-2.0. "
                    "If alpha-channel export is unavailable, export avatar.mp4 + "
                    "avatar_mask.mp4 (grayscale matte)."
                ),
            },
            # SadTalker inference config mapped to quality
            "sadtalker_config": sadtalker_config,
        }

        manifest_path = pkg_dir / "avatar_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info(
            f"[AVATAR_EXPORT] Package created at {pkg_dir} "
            f"(v{MANIFEST_VERSION}, key={cache_key[:8]}…)"
        )

        # ── 6. Write processing_metadata.json (Refinement F & 4 retry structure) ──
        metadata = {
            "retry_count": 0,
            "last_retry_at": None,
        }
        meta_path = pkg_dir / "processing_metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # ── 7. Persist cache key in project config for importer ───────────────
        cfg["avatar_cache_key"] = cache_key
        cfg["avatar_manifest_version"] = MANIFEST_VERSION
        save_json(project_id, "config.json", cfg)

        return pkg_dir

    def build_zip(self, project_id: str) -> bytes:
        """Build a ZIP archive of the ``sadtalker_package/`` directory.

        Args:
            project_id: Unique project identifier.

        Returns:
            Raw ZIP bytes ready to stream as a download response.

        Raises:
            FileNotFoundError: If the package directory does not exist.
        """
        proj = project_dir(project_id)
        pkg_dir = proj / "sadtalker_package"
        if not pkg_dir.exists():
            raise FileNotFoundError(
                f"SadTalker package not found for project {project_id}. "
                "Run /generate-avatar first."
            )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in pkg_dir.iterdir():
                if file_path.is_file():
                    zf.write(file_path, arcname=file_path.name)
        logger.info(f"[AVATAR_EXPORT] ZIP built for project {project_id}")
        return buf.getvalue()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_cache_key(
        image_path: Path | None,
        audio_path: Path | None,
    ) -> str:
        """Compute SHA-256 cache key from source image + combined audio bytes.

        P6: The key uniquely identifies a (portrait, audio) pair so repeated
        generation with the same inputs reuses the cached avatar.webm.
        """
        h = hashlib.sha256()
        for p in (image_path, audio_path):
            if p and p.exists():
                h.update(p.read_bytes())
            else:
                h.update(b"\x00")  # stable placeholder for missing file
        return h.hexdigest()
