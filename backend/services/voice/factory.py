"""Voice provider factory.

Resolves the correct :class:`~services.voice.providers.base.VoiceProvider`
for a given project based on ``config.json::voice_provider``.

Old projects that were created before the provider architecture was introduced
will not have a ``voice_provider`` key in their config.  These projects
default to Edge-TTS so that backward compatibility is fully preserved.
"""

from __future__ import annotations

from services.voice.providers.base import VoiceProvider
from utils.file_manager import load_json

# Avoid circular imports: providers import from factory indirectly.
_PROVIDERS: dict[str, str] = {
    "edge": "services.voice.providers.edge.EdgeTTSProvider",
    "f5tts": "services.voice.providers.f5.F5TTSProvider",
}

_DEFAULT_PROVIDER = "edge"


def get_voice_provider(project_id: str) -> VoiceProvider:
    """Return the correct :class:`VoiceProvider` for *project_id*.

    Reads ``config.json`` from the project directory.  If the
    ``voice_provider`` key is absent (legacy project) or unknown, the
    Edge-TTS provider is returned so rendering is never broken.

    Args:
        project_id: The project whose config should be inspected.

    Returns:
        A fully initialised :class:`VoiceProvider` instance ready to call
        ``await provider.generate(...)``.
    """
    config = load_json(project_id, "config.json") or {}
    provider_key = config.get("voice_provider", _DEFAULT_PROVIDER)

    if provider_key not in _PROVIDERS:
        provider_key = _DEFAULT_PROVIDER

    # Lazy import to avoid circular deps at module load time.
    module_path, class_name = _PROVIDERS[provider_key].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


def get_provider_key(project_id: str) -> str:
    """Return the provider key string for *project_id* (e.g. ``"edge"``).

    Useful for conditional logic that does not need a full provider instance.
    """
    config = load_json(project_id, "config.json") or {}
    key = config.get("voice_provider", _DEFAULT_PROVIDER)
    return key if key in _PROVIDERS else _DEFAULT_PROVIDER
