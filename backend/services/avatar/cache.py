"""Avatar Cache Service — Phase-4 P6.

SHA-256 content-addressed cache for avatar WebM clips.

Cache key is computed as:

    SHA256(source_image_bytes + combined_audio_bytes)

This guarantees that the SAME portrait photo + SAME audio always map to
the same key.  If both inputs are identical to a previous run, the cached
``avatar.webm`` is reused instead of re-running SadTalker.

Cache layout:

    <ROOT>/avatar_cache/
        <hex_key_64_chars>/
            avatar.webm          ← the cached transparent WebM
            cached_at.json       ← timestamp + provenance metadata

Usage (exporter checks before building package):

    cache = AvatarCacheService()
    key = cache.compute_key(image_path, audio_path)
    if (hit := cache.check_cache(key)) is not None:
        # skip SadTalker; copy hit to project avatars/
        ...
    else:
        # run export; after import:
        cache.store_cache(key, result_clip_path)
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger("sadtalker_cache")


class AvatarCacheService:
    """Content-addressed cache for transparent avatar WebM clips.

    P6: Avoids re-running SadTalker when the same (portrait, audio) pair
    has already been processed.
    """

    @property
    def _cache_root(self) -> Path:
        root = settings.avatar_cache_path
        root.mkdir(parents=True, exist_ok=True)
        return root

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def compute_key(
        provider_version: str,
        avatar_quality: str,
        image_path: Optional[Path],
        audio_path: Optional[Path],
    ) -> str:
        """Compute a SHA-256 cache key from input metadata + file bytes.

        Hardening 2 & 9: Cache key includes provider version, quality preset,
        source portrait bytes, and narrative audio bytes.
        """
        h = hashlib.sha256()
        h.update(provider_version.encode("utf-8"))
        h.update(avatar_quality.encode("utf-8"))
        for p in (image_path, audio_path):
            if p and p.exists():
                h.update(p.read_bytes())
            else:
                h.update(b"\x00")
        return h.hexdigest()

    def check_cache(self, key: str) -> Optional[Path]:
        """Return the cached clip path if a valid entry exists, else None.

        Args:
            key: 64-character SHA-256 hex digest.

        Returns:
            Absolute path to the cached ``avatar.webm`` / ``avatar.mp4``,
            or ``None`` if not cached.
        """
        entry_dir = self._cache_root / key
        for name in ("avatar.webm", "avatar.mp4"):
            candidate = entry_dir / name
            if candidate.exists():
                logger.info(f"[AVATAR_CACHE] Cache HIT for key {key[:8]}…: {name}")
                return candidate
        logger.debug(f"[AVATAR_CACHE] Cache MISS for key {key[:8]}…")
        return None

    def store_cache(self, key: str, clip_path: Path) -> Path:
        """Copy a clip into the cache under the given key.

        Args:
            key: 64-character SHA-256 hex digest.
            clip_path: Absolute path to the clip file to cache.

        Returns:
            Path to the newly stored cache entry.
        """
        entry_dir = self._cache_root / key
        entry_dir.mkdir(parents=True, exist_ok=True)
        dest = entry_dir / clip_path.name
        shutil.copy2(clip_path, dest)

        # Write provenance metadata alongside the clip.
        meta = {
            "cache_key": key,
            "source_clip": str(clip_path),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        (entry_dir / "cached_at.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        logger.info(f"[AVATAR_CACHE] Stored clip under key {key[:8]}… → {dest}")
        return dest

    def copy_from_cache(self, key: str, dest_dir: Path) -> Optional[Path]:
        """Copy a cached clip to *dest_dir*, returning the destination path.

        Useful for restoring a cached clip into a project's ``avatars/`` folder.

        Args:
            key: 64-character SHA-256 hex digest.
            dest_dir: Directory to copy the cached clip into.

        Returns:
            Destination path, or ``None`` if the key is not cached.
        """
        cached = self.check_cache(key)
        if cached is None:
            return None
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / cached.name
        shutil.copy2(cached, dest)
        logger.info(f"[AVATAR_CACHE] Restored from cache to {dest}")
        return dest

    def evict(self, key: str) -> bool:
        """Remove a cache entry.

        Args:
            key: 64-character SHA-256 hex digest.

        Returns:
            True if the entry existed and was removed, False otherwise.
        """
        import shutil as sh
        entry_dir = self._cache_root / key
        if entry_dir.exists():
            sh.rmtree(entry_dir)
            logger.info(f"[AVATAR_CACHE] Evicted cache key {key[:8]}…")
            return True
        return False

    def cleanup_cache(self) -> dict:
        """Enforce sequentially ordered cache retention policy.

        Hardening 7: Enforces cleanup order:
        1. Orphans (missing required files or json metadata).
        2. Expired (older than avatar_cache_retention_days).
        3. LRU pruning (removes oldest valid entries if cache exceeds max GB).
        """
        now = datetime.now(timezone.utc)
        retention_days = settings.avatar_cache_retention_days
        retention_delta = timedelta(days=retention_days)
        max_bytes = int(settings.avatar_cache_max_gb * 1024 * 1024 * 1024)

        orphans_removed = 0
        expired_removed = 0
        lru_removed = 0
        total_bytes_freed = 0

        # Scan for cache folders
        valid_entries = []

        if not self._cache_root.exists():
            return {"orphans": 0, "expired": 0, "lru": 0, "bytes_freed": 0}

        for entry in self._cache_root.iterdir():
            if not entry.is_dir():
                continue

            key = entry.name
            meta_file = entry / "cached_at.json"

            # ── 1. Orphan check ──
            has_media = (entry / "avatar.webm").exists() or (entry / "avatar.mp4").exists()
            if not meta_file.exists() or not has_media:
                entry_size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                shutil.rmtree(entry)
                orphans_removed += 1
                total_bytes_freed += entry_size
                logger.info(f"[AVATAR_CACHE_CLEANUP] Evicted orphan cache entry: {key[:8]}… ({entry_size // 1024} KB freed)")
                continue

            # Load metadata
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                cached_at_str = meta.get("cached_at")
                cached_at = datetime.fromisoformat(cached_at_str)
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
            except Exception:
                entry_size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                shutil.rmtree(entry)
                orphans_removed += 1
                total_bytes_freed += entry_size
                logger.info(f"[AVATAR_CACHE_CLEANUP] Evicted corrupt cache entry metadata: {key[:8]}…")
                continue

            # ── 2. Expiry check ──
            if now - cached_at > retention_delta:
                entry_size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                shutil.rmtree(entry)
                expired_removed += 1
                total_bytes_freed += entry_size
                logger.info(
                    f"[AVATAR_CACHE_CLEANUP] Evicted expired cache entry: {key[:8]}… "
                    f"(age: {(now - cached_at).days} days, {entry_size // 1024} KB freed)"
                )
                continue

            # Accumulate info for LRU check
            entry_size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
            valid_entries.append({
                "path": entry,
                "key": key,
                "cached_at": cached_at,
                "size": entry_size
            })

        # ── 3. LRU pruning ──
        total_cache_size = sum(e["size"] for e in valid_entries)
        if total_cache_size > max_bytes:
            # Sort valid entries by cached_at ascending (oldest first)
            valid_entries.sort(key=lambda x: x["cached_at"])
            for e in valid_entries:
                if total_cache_size <= max_bytes:
                    break
                shutil.rmtree(e["path"])
                lru_removed += 1
                total_bytes_freed += e["size"]
                total_cache_size -= e["size"]
                logger.info(f"[AVATAR_CACHE_CLEANUP] Evicted LRU cache entry: {e['key'][:8]}… to satisfy max size limit.")

        return {
            "orphans": orphans_removed,
            "expired": expired_removed,
            "lru": lru_removed,
            "bytes_freed": total_bytes_freed,
        }
