"""Edge-TTS voice provider.

Wraps the existing ``voice_service`` logic so it is accessible through the
:class:`~services.voice.providers.base.VoiceProvider` interface.  All
behaviour is *identical* to the previous direct call of
``generate_voices_for_script()`` — this is purely an adapter.
"""

from __future__ import annotations

from typing import List

from models.schemas import SceneVoiceResult, ScriptSchema
from services.voice.providers.base import VoiceProvider

# Re-use the proven Edge-TTS implementation without duplicating any logic.
from services.voice_service import generate_voices_for_script


class EdgeTTSProvider(VoiceProvider):
    """Voice provider backed by Microsoft Edge-TTS (free, runs locally).

    This is the default provider and preserves 100 % of the existing
    pipeline behaviour.  Existing projects that were generated before the
    provider architecture was introduced will automatically use this provider.
    """

    name: str = "edge"

    async def generate(
        self,
        project_id: str,
        script: ScriptSchema,
        voice: str,
    ) -> List[SceneVoiceResult]:
        """Generate MP3 narration for every scene using Edge-TTS.

        Delegates to the canonical ``generate_voices_for_script`` function
        from ``voice_service``.  The function writes per-scene MP3 files into
        ``<project>/voices/`` and saves ``voice_results.json``.

        This implementation additionally stamps every result with
        ``provider="edge"`` so downstream tooling can trace audio origin.
        """
        results: List[SceneVoiceResult] = await generate_voices_for_script(
            project_id, script, voice
        )

        # Stamp provider metadata onto each result.
        for r in results:
            r.provider = "edge"

        return results
