"""WAV audio merger for multi-chunk XTTS output.

XTTS generates one WAV per text chunk.  This module stitches those chunks
into a single output WAV with a short silence gap between them.

All chunks are resampled to 24 000 Hz (XTTS native sample rate) before
concatenation to prevent sample-rate mismatch artifacts.

Dependencies:
    soundfile  (already used in the benchmark — pure Python + libsndfile)
    numpy      (guaranteed by TTS / torch install)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import numpy as np
import soundfile as sf

# XTTS native sample rate
XTTS_SAMPLE_RATE = 24_000

# Gap inserted between chunks (seconds)
_INTER_CHUNK_GAP_S = 0.05   # 50 ms — barely perceptible, avoids hard glitch


def _silence(seconds: float, sample_rate: int = XTTS_SAMPLE_RATE) -> np.ndarray:
    """Return a mono silence array of the given duration."""
    n = int(seconds * sample_rate)
    return np.zeros(n, dtype=np.float32)


def _load_wav(path: Path) -> tuple[np.ndarray, int]:
    """Load a WAV file and return (mono_data, sample_rate)."""
    data, sr = sf.read(str(path), dtype="float32")
    # Convert to mono if stereo
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, sr


def merge_chunks(chunk_paths: List[Path], output_path: Path) -> float:
    """Concatenate *chunk_paths* WAVs into *output_path*.

    Args:
        chunk_paths:  Ordered list of per-chunk WAV files.
        output_path:  Destination WAV path (created or overwritten).

    Returns:
        Total audio duration in seconds.

    Raises:
        ValueError: If *chunk_paths* is empty.
        FileNotFoundError: If any chunk file does not exist.
    """
    if not chunk_paths:
        raise ValueError("merge_chunks: chunk_paths is empty")

    segments: List[np.ndarray] = []
    gap = _silence(_INTER_CHUNK_GAP_S)

    for i, path in enumerate(chunk_paths):
        if not path.exists():
            raise FileNotFoundError(f"Chunk file not found: {path}")

        data, sr = _load_wav(path)

        # Resample to XTTS native rate if needed (should never happen, but be safe)
        if sr != XTTS_SAMPLE_RATE:
            # Simple linear resample approximation via numpy
            target_len = int(len(data) * XTTS_SAMPLE_RATE / sr)
            data = np.interp(
                np.linspace(0, len(data), target_len),
                np.arange(len(data)),
                data,
            ).astype(np.float32)

        segments.append(data)
        if i < len(chunk_paths) - 1:
            segments.append(gap)

    merged = np.concatenate(segments)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), merged, XTTS_SAMPLE_RATE)

    return float(len(merged) / XTTS_SAMPLE_RATE)
