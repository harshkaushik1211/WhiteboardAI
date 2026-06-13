"""IndicXlit Transliteration Service.

Provides offline, CPU-friendly phonetic transliteration of Roman Hinglish to Devanagari Hinglish.
Utilizes the ai4bharat-transliteration package, with cache support and robust fallback mechanisms.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)

# ── Dataclasses Monkey-Patch (Required for Python 3.11+ / Fairseq / Windows) ────
_orig_get_field = dataclasses._get_field

def _patched_get_field(cls, name, type, kw_only):
    default = getattr(cls, name, dataclasses.MISSING)
    if default is not dataclasses.MISSING:
        if isinstance(default, dataclasses.Field):
            orig_val = default.default
            if (
                orig_val is not dataclasses.MISSING
                and getattr(orig_val, "__class__", None) is not None
                and getattr(orig_val.__class__, "__hash__", None) is None
            ):
                default.default = "MOCKED_HASHABLE"
                try:
                    f = _orig_get_field(cls, name, type, kw_only)
                    f.default = orig_val
                    return f
                finally:
                    default.default = orig_val
        else:
            orig_val = default
            if (
                getattr(orig_val, "__class__", None) is not None
                and getattr(orig_val.__class__, "__hash__", None) is None
            ):
                setattr(cls, name, "MOCKED_HASHABLE")
                try:
                    f = _orig_get_field(cls, name, type, kw_only)
                    f.default = orig_val
                    return f
                finally:
                    setattr(cls, name, orig_val)
    return _orig_get_field(cls, name, type, kw_only)

dataclasses._get_field = _patched_get_field


# ── Lazy Loaded Engine & Cache ────────────────────────────────────────────────
_engine = None
_transliteration_cache: Dict[str, str] = {}


def _get_engine():
    """Lazily load and return the XlitEngine for Hindi."""
    global _engine
    if _engine is None:
        logger.info("[IndicXlit] Initializing XlitEngine for Hindi...")
        from ai4bharat.transliteration import XlitEngine
        _engine = XlitEngine("hi", beam_width=10, rescore=True)
        logger.info("[IndicXlit] XlitEngine loaded successfully.")
    return _engine


def normalize_text(text: str) -> str:
    """Normalize camelCase and PascalCase technical terms (e.g. FastAPI -> Fast API)."""
    if not text:
        return text
    # Split camelCase / PascalCase words (e.g. FastAPI -> Fast API, MongoDB -> Mongo DB)
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", text)


# Unicode range for Devanagari script: U+0900 to U+097F
_DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")


def already_devanagari(text: str) -> bool:
    """Returns True if the text contains Devanagari characters."""
    if not text:
        return False
    return bool(_DEVANAGARI_PATTERN.search(text))


def transliterate_hinglish(text: str) -> str:
    """Transliterate Roman-script Hinglish text into Devanagari Hinglish.

    Args:
        text: The input Hinglish text in Roman script.

    Returns:
        The transliterated Hinglish text in Devanagari script.
        If any failure occurs, logs a warning and returns the original text.
    """
    if not text or not text.strip():
        return text

    # Bypass if already containing Devanagari characters
    if already_devanagari(text):
        logger.debug(f"[IndicXlit] Input already contains Devanagari; bypassing transliteration: '{text[:30]}...'")
        return text

    # Check cache with original input first
    if text in _transliteration_cache:
        logger.debug(f"[IndicXlit] Cache hit for original input: '{text[:30]}...'")
        return _transliteration_cache[text]

    try:
        # Normalize technical terms
        normalized = normalize_text(text)

        # Check cache again with normalized input
        if normalized in _transliteration_cache:
            logger.debug(f"[IndicXlit] Cache hit for normalized input: '{normalized[:30]}...'")
            return _transliteration_cache[normalized]

        engine = _get_engine()
        res = engine.translit_sentence(normalized)
        output_text = res.get("hi", "")

        # Save results in cache for future calls
        _transliteration_cache[text] = output_text
        _transliteration_cache[normalized] = output_text

        return output_text

    except Exception as e:
        logger.warning(
            f"[IndicXlit] Transliteration failed: {e}. Falling back to original narration.",
            exc_info=True,
        )
        return text
