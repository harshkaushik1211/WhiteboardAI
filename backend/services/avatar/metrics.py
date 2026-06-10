"""Avatar Metrics Service — Phase-4 Hardening & Observability.

Refinement H: Operational Metrics
    Tracks total_avatar_generations, successful_avatar_generations,
    failed_avatar_generations, cache_hits, cache_misses, and average_generation_time.

Hardening 1: Writes must be atomic and thread-safe / process-safe (uses mkdir lock).
Hardening 8: Metric endpoint must expose only aggregate stats (no project IDs/paths).
Hardening 10: Track gpu_jobs_saved metric (cache hits).
"""

from __future__ import annotations

import json
import logging
import time
import shutil
from pathlib import Path
from typing import Dict, Any

from config import settings

logger = logging.getLogger("avatar_metrics")


class MetricsLock:
    """Folder-creation-based cross-process file lock.
    
    mkdir() is atomic across POSIX and Windows platforms.
    """
    def __init__(self, lock_path: Path, timeout: float = 5.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.acquired = False

    def __enter__(self):
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                self.lock_path.mkdir(exist_ok=False)
                self.acquired = True
                return self
            except FileExistsError:
                time.sleep(0.02)
        logger.warning("[AVATAR_METRICS] Failed to acquire metrics write lock; timeout exceeded.")
        raise TimeoutError("Timeout acquiring metrics file lock")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            try:
                self.lock_path.rmdir()
            except FileNotFoundError:
                pass


class AvatarMetricsService:
    """Tracks and persists avatar generation performance indicators."""

    def __init__(self):
        self.metrics_path = settings.generated_path / "avatar_metrics.json"
        self.lock_path = settings.generated_path / "avatar_metrics.lock"

    def _read_metrics(self) -> Dict[str, Any]:
        """Read metrics from disk or initialize if missing/corrupt."""
        if not self.metrics_path.exists():
            return self._init_metrics()
        try:
            return json.loads(self.metrics_path.read_text(encoding="utf-8"))
        except Exception:
            return self._init_metrics()

    def _init_metrics(self) -> Dict[str, Any]:
        return {
            "total_avatar_generations": 0,
            "successful_avatar_generations": 0,
            "failed_avatar_generations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "gpu_jobs_saved": 0,
            "total_generation_time": 0.0,
            "average_generation_time": 0.0,
        }

    def _write_metrics(self, data: Dict[str, Any]) -> None:
        """Write metrics data to disk atomically."""
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        # Compute dynamic average
        success_count = data.get("successful_avatar_generations", 0)
        total_time = data.get("total_generation_time", 0.0)
        data["average_generation_time"] = round(total_time / success_count, 2) if success_count > 0 else 0.0

        temp_file = self.metrics_path.with_suffix(".tmp")
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            temp_file.replace(self.metrics_path)
        except Exception:
            shutil.move(str(temp_file), str(self.metrics_path))

    def update_metrics(self, **increments) -> None:
        """Atomic increase of specific metrics."""
        try:
            with MetricsLock(self.lock_path):
                data = self._read_metrics()
                for key, val in increments.items():
                    if key in data:
                        data[key] += val
                self._write_metrics(data)
        except Exception as e:
            logger.error(f"[AVATAR_METRICS] Failed to update metrics: {e}")

    def record_generation_time(self, duration: float) -> None:
        """Add a successful generation and accumulate its runtime."""
        try:
            with MetricsLock(self.lock_path):
                data = self._read_metrics()
                data["successful_avatar_generations"] += 1
                data["total_generation_time"] += duration
                self._write_metrics(data)
        except Exception as e:
            logger.error(f"[AVATAR_METRICS] Failed to record generation time: {e}")

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Expose only safe, private-data-free metrics."""
        data = self._read_metrics()
        return {
            "total_avatar_generations": data.get("total_avatar_generations", 0),
            "successful_avatar_generations": data.get("successful_avatar_generations", 0),
            "failed_avatar_generations": data.get("failed_avatar_generations", 0),
            "cache_hits": data.get("cache_hits", 0),
            "cache_misses": data.get("cache_misses", 0),
            "gpu_jobs_saved": data.get("gpu_jobs_saved", 0),
            "average_generation_time": data.get("average_generation_time", 0.0),
        }
