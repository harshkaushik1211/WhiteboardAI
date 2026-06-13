"""XTTS Hindi Voice Provider.

Handles Hindi and Hinglish narration using the XTTS-v2 model
(Coqui TTS community fork, multilingual/multi-dataset/xtts_v2).

Architecture:
    Hindi   → Devanagari text → XTTS (lang="hi") → WAV chunks → merged WAV
    Hinglish → Roman text → transliterate() → Devanagari → XTTS (lang="hi")
               → WAV chunks → merged WAV

English narration is NEVER routed here — this provider only handles
language_mode in ("hindi", "hinglish").

Voice cloning:
    Uses teacher_short.wav from assets/teacher_voice/ as the reference
    speaker.  The reference audio is embedded in the repo so no runtime
    download is required.

Threading:
    XTTS model is loaded lazily on first call and cached as a module
    singleton.  The VoiceProvider.generate() method is async (required
    by the base class) but XTTS inference is synchronous.  We run it
    in an executor to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import List

from models.schemas import SceneSchema, SceneVoiceResult, ScriptSchema, LanguageMode
from services.voice.providers.base import VoiceProvider
from services.voice.providers.xtts.text_chunker import chunk_text
from services.voice.providers.xtts.audio_merger import merge_chunks
from services.transliteration import transliterate_hinglish
from services.voice.providers.xtts.model_loader import get_xtts_model
from utils.file_manager import ensure_project_dirs

logger = logging.getLogger(__name__)

# Reference voice used for speaker cloning
_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "teacher_voice"
_REFERENCE_WAV = _ASSETS_DIR / "teacher_short.wav"

# XTTS language code for Hindi/Hinglish
_XTTS_LANG = "hi"


def _get_reference_wav() -> str:
    """Return the path to the reference WAV, raising if missing."""
    if not _REFERENCE_WAV.exists():
        raise FileNotFoundError(
            f"[XTTS Hindi Provider] Reference voice file not found: {_REFERENCE_WAV}\n"
            "Please ensure 'teacher_short.wav' exists in 'backend/assets/teacher_voice/'.\n"
            "Copy it from 'xtts_benchmark/reference/teacher_short.wav'."
        )
    return str(_REFERENCE_WAV)


def _prepare_text(narration: str, language_mode: LanguageMode | str | None) -> str:
    """Apply transliteration for Hinglish; return Devanagari text for Hindi."""
    mode = str(language_mode).lower() if language_mode else ""
    if "hinglish" in mode:
        return transliterate_hinglish(narration)
    # Hindi Devanagari text is used as-is
    return narration


def _generate_scene_sync(
    tts,
    narration: str,
    language_mode: LanguageMode | str | None,
    output_path: Path,
) -> float:
    """Synchronous XTTS generation for a single scene.

    1. Prepare text (transliterate if Hinglish).
    2. Chunk into XTTS-safe segments.
    3. Generate WAV for each chunk into a temp directory.
    4. Merge chunks into output_path.
    5. Return duration in seconds.
    """
    ref_wav = _get_reference_wav()
    prepared_text = _prepare_text(narration, language_mode)
    chunks = chunk_text(prepared_text)

    if not chunks:
        logger.warning("[XTTS] No chunks produced for narration; skipping generation.")
        return 0.0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(chunks) == 1:
        # Single chunk — write directly to output path
        tts.tts_to_file(
            text=chunks[0],
            speaker_wav=ref_wav,
            language=_XTTS_LANG,
            file_path=str(output_path),
        )
        import soundfile as sf
        data, sr = sf.read(str(output_path))
        return float(len(data) / sr)
    else:
        # Multiple chunks — write to temp files, then merge
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            chunk_paths: List[Path] = []

            for i, chunk in enumerate(chunks):
                chunk_path = tmp / f"chunk_{i:03d}.wav"
                logger.debug(f"[XTTS] Chunk {i+1}/{len(chunks)}: {len(chunk)} chars")
                tts.tts_to_file(
                    text=chunk,
                    speaker_wav=ref_wav,
                    language=_XTTS_LANG,
                    file_path=str(chunk_path),
                )
                chunk_paths.append(chunk_path)

            duration = merge_chunks(chunk_paths, output_path)
            return duration


class XTTSHindiProvider(VoiceProvider):
    """Voice provider for Hindi and Hinglish narration using XTTS-v2.

    Only handles language_mode in ("hindi", "hinglish").
    Falls back to Edge-TTS for English — this should never happen as
    the factory routes English exclusively to Edge-TTS / F5-TTS.
    """

    name: str = "xtts_hindi"

    async def generate(
        self,
        project_id: str,
        script: ScriptSchema,
        voice: str,
    ) -> List[SceneVoiceResult]:
        """Generate WAV narration for every scene using XTTS-v2.

        Args:
            project_id: Unique project identifier.
            script:     Parsed script containing scenes with narration text.
            voice:      Voice style key (ignored — XTTS uses reference cloning).

        Returns:
            List of SceneVoiceResult — one per scene — with WAV audio paths
            and probed durations.
        """
        dirs = ensure_project_dirs(project_id)
        language_mode = script.language_mode  # LanguageMode enum or None
        mode_str = str(language_mode).lower() if language_mode else ""

        logger.info(
            f"[XTTS Hindi Provider] Generating {len(script.scenes)} scenes "
            f"(language_mode={language_mode}, project={project_id})"
        )

        # Save original and transliterated scripts for debugging if Hinglish
        if "hinglish" in mode_str:
            try:
                original_lines = [s.narration.strip() for s in script.scenes]
                transliterated_lines = [transliterate_hinglish(line) for line in original_lines]
                
                from utils.file_manager import save_text
                save_text(project_id, "original_script.txt", "\n".join(original_lines))
                save_text(project_id, "transliterated_script.txt", "\n".join(transliterated_lines))
                logger.info(f"[XTTS] Saved original and transliterated scripts for project {project_id}")
            except Exception as script_err:
                logger.warning(f"[XTTS] Failed to save debug script files: {script_err}", exc_info=True)

        # Load model once — subsequent calls use the cached singleton
        loop = asyncio.get_event_loop()
        tts = await loop.run_in_executor(None, get_xtts_model)

        results: List[SceneVoiceResult] = []

        for scene in script.scenes:
            output_path = dirs["voices"] / f"scene_{scene.scene_id}.wav"
            narration = scene.narration.strip()

            logger.info(f"[XTTS] Scene {scene.scene_id}: {len(narration)} chars")

            try:
                duration = await loop.run_in_executor(
                    None,
                    _generate_scene_sync,
                    tts,
                    narration,
                    language_mode,
                    output_path,
                )
            except Exception as e:
                logger.error(
                    f"[XTTS] Scene {scene.scene_id} generation failed: {e}",
                    exc_info=True,
                )
                raise RuntimeError(
                    f"[XTTS Hindi Provider] Failed to generate audio for "
                    f"scene {scene.scene_id}: {e}"
                ) from e

            if duration <= 0:
                duration = scene.duration

            results.append(
                SceneVoiceResult(
                    scene_id=scene.scene_id,
                    audio_path=f"voices/scene_{scene.scene_id}.wav",
                    duration=duration,
                    timestamps=[],   # XTTS does not provide word timestamps
                    provider="xtts_hindi",
                )
            )
            logger.info(f"[XTTS] Scene {scene.scene_id}: {duration:.2f}s generated OK")

        # Persist voice results
        from utils.file_manager import save_json
        save_json(project_id, "voice_results.json", [r.model_dump() for r in results])

        return results
