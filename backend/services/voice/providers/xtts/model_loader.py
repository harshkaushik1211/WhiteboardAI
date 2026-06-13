"""XTTS-v2 model loader — singleton with Windows compatibility patches.

Loads the XTTS-v2 model once and caches it as a module-level singleton.
Applies all Windows-specific patches discovered during the benchmark phase:

    1. transformers version-check patch — prevents TTS from detecting
       PyTorch >= 2.9 and requiring torchcodec.
    2. torchaudio load/save patch — replaces the FFmpeg-backed backend
       with soundfile to bypass missing torchcodec DLL on Windows.

These patches are applied BEFORE the TTS library is imported so they
take effect for all subsequent model loading calls.

Usage:
    from services.voice.providers.xtts.model_loader import get_xtts_model
    tts = get_xtts_model()   # loads on first call, cached thereafter
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level singleton
_xtts_model: Optional[object] = None
_xtts_load_error: Optional[Exception] = None
_patches_applied: bool = False


def _apply_windows_patches() -> None:
    """Apply runtime patches required on Windows with PyTorch >= 2.9."""
    global _patches_applied
    if _patches_applied:
        return
    _patches_applied = True

    # Patch 1: transformers version check
    try:
        import transformers.utils.import_utils as iu
        _orig = iu.is_torch_greater_or_equal

        def _patched_version_check(library_version: str, accept_dev: bool = False) -> bool:
            if library_version == "2.9":
                return False
            return _orig(library_version, accept_dev)

        iu.is_torch_greater_or_equal = _patched_version_check
        logger.debug("[XTTS] transformers version-check patch applied.")
    except Exception as e:
        logger.warning(f"[XTTS] Failed to apply transformers patch: {e}")

    # Patch 2: torchaudio load/save via soundfile
    try:
        import torchaudio
        import soundfile as sf
        import torch

        def _patched_load(
            uri: str,
            frame_offset: int = 0,
            num_frames: int = -1,
            normalize: bool = True,
            channels_first: bool = True,
            **kwargs,
        ):
            data, sr = sf.read(uri, dtype="float32")
            tensor = torch.from_numpy(data)
            if tensor.ndim == 1:
                tensor = tensor.unsqueeze(0)
            elif channels_first:
                tensor = tensor.T
            return tensor, sr

        def _patched_save(
            filepath: str,
            src,
            sample_rate: int,
            channels_first: bool = True,
            **kwargs,
        ) -> None:
            data = src.detach().cpu().numpy()
            if channels_first and data.ndim > 1:
                data = data.T
            sf.write(filepath, data, sample_rate)

        torchaudio.load = _patched_load
        torchaudio.save = _patched_save
        logger.debug("[XTTS] torchaudio load/save patched with soundfile backend.")
    except Exception as e:
        logger.warning(f"[XTTS] Failed to patch torchaudio: {e}")


def get_xtts_model():
    """Return the cached XTTS-v2 model, loading it if necessary.

    Returns:
        A ``TTS`` instance from the Coqui TTS library, ready to call
        ``tts_to_file(...)``.

    Raises:
        ImportError:  If the Coqui TTS library is not installed.
        RuntimeError: If the model fails to download or load.
    """
    global _xtts_model, _xtts_load_error

    if _xtts_model is not None:
        return _xtts_model

    if _xtts_load_error is not None:
        # Re-raise stored error — no point retrying a failed load
        raise _xtts_load_error

    _apply_windows_patches()

    try:
        from TTS.api import TTS  # type: ignore
    except ImportError as e:
        err = ImportError(
            "[XTTS Hindi Provider] Coqui TTS library not installed.\n"
            "Install it with:\n"
            "  pip install coqui-tts\n"
            f"Original error: {e}"
        )
        _xtts_load_error = err
        raise err from e

    try:
        logger.info("[XTTS] Loading tts_models/multilingual/multi-dataset/xtts_v2 on CPU …")
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
        _xtts_model = tts
        logger.info("[XTTS] Model loaded successfully.")
        return tts
    except Exception as e:
        import traceback
        err = RuntimeError(
            f"[XTTS Hindi Provider] Failed to load XTTS-v2 model.\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
        _xtts_load_error = err
        raise err from e
