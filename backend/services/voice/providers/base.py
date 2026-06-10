"""Abstract base class for all voice providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from models.schemas import SceneVoiceResult, ScriptSchema


class VoiceProvider(ABC):
    """Pluggable voice provider interface.

    Each provider is responsible for one thing: given a project and a script,
    produce a list of :class:`~models.schemas.SceneVoiceResult` objects that
    the rest of the pipeline (timeline sync, render manifest, FFmpeg) can
    consume without any knowledge of *how* the audio was produced.

    Providers must NOT touch the rendering pipeline, Remotion, or FFmpeg.
    They are responsible only for:

    1. Producing audio files on disk inside the project's ``voices/`` folder.
    2. Returning accurate per-scene duration information.

    Adding a new provider (e.g. ElevenLabs, Azure TTS, OpenAI TTS) means
    creating a new subclass here and registering it in ``factory.py``.
    """

    # Human-readable name used in logs and metadata.
    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        project_id: str,
        script: ScriptSchema,
        voice: str,
    ) -> List[SceneVoiceResult]:
        """Generate (or prepare) audio for every scene in *script*.

        Args:
            project_id: Unique project identifier.
            script: Parsed script containing all scenes with narration text.
            voice: Voice style key (e.g. ``"male"``, ``"female"``).

        Returns:
            A list of :class:`SceneVoiceResult` — one per scene — containing
            the relative audio path and duration.  For providers that do *not*
            produce audio immediately (e.g. F5-TTS), this method exports the
            narration package and returns an *empty* list; voice results will
            be supplied later via the import workflow.
        """
        ...
