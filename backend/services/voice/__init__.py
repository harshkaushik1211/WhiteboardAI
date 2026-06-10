"""Voice provider package for the AI Whiteboard system.

Provides a pluggable architecture for voice generation:
- EdgeTTSProvider  : local Edge-TTS (default, existing behaviour)
- F5TTSProvider    : export narration pack for external F5-TTS processing

Usage::

    from services.voice.factory import get_voice_provider

    provider = get_voice_provider(project_id)
    voice_results = await provider.generate(project_id, script, voice)
"""

from services.voice.factory import get_voice_provider  # noqa: F401

__all__ = ["get_voice_provider"]
