"""Avatar provider factory.

Resolves the correct :class:`~services.avatar.providers.base.AvatarProvider`
for a given project based on ``config.json::avatar_provider``.

Follows the EXACT same pattern as
:mod:`services.voice.factory`.

Old projects that were created before avatar support was introduced will not
have an ``avatar_provider`` key in their config.  These projects default to
``None`` (no avatar) so that backward compatibility is fully preserved.
"""

from __future__ import annotations

import importlib
from typing import Optional

from services.avatar.providers.base import AvatarProvider
from utils.file_manager import load_json

# Lazy import map: key → dotted.path.ClassName
_PROVIDERS: dict[str, str] = {
    "sadtalker": "services.avatar.providers.sadtalker.SadTalkerProvider",
    # Future providers:
    # "liveportrait": "services.avatar.providers.liveportrait.LivePortraitProvider",
    # "musetalk":     "services.avatar.providers.musetalk.MuseTalkProvider",
    # "heygen":       "services.avatar.providers.heygen.HeyGenProvider",
}

_NO_AVATAR = None  # sentinel: avatar pipeline disabled


def get_avatar_provider(project_id: str) -> Optional[AvatarProvider]:
    """Return the correct :class:`AvatarProvider` for *project_id*, or None.

    Reads ``config.json`` from the project directory.  If the
    ``avatar_provider`` key is absent (legacy project or whiteboard-only),
    ``None`` is returned so the render pipeline skips avatar generation
    cleanly.

    Args:
        project_id: The project whose config should be inspected.

    Returns:
        A fully initialised :class:`AvatarProvider` instance, or ``None``
        when avatar generation is disabled for this project.
    """
    config = load_json(project_id, "config.json") or {}
    provider_key = config.get("avatar_provider", None)

    if not provider_key or provider_key not in _PROVIDERS:
        return _NO_AVATAR

    # Lazy import to avoid circular deps at module load time.
    module_path, class_name = _PROVIDERS[provider_key].rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


def get_avatar_provider_key(project_id: str) -> Optional[str]:
    """Return the avatar provider key string for *project_id*, or None.

    Useful for conditional logic that does not need a full provider instance.
    """
    config = load_json(project_id, "config.json") or {}
    key = config.get("avatar_provider", None)
    return key if key in _PROVIDERS else None
