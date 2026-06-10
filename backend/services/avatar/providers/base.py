"""Abstract base class for all avatar providers.

Follows the EXACT same design pattern as
:class:`~services.voice.providers.base.VoiceProvider`.

Adding a new provider (e.g. HeyGen, D-ID, LivePortrait, MuseTalk) means:
1. Creating a new subclass of :class:`AvatarProvider` here.
2. Registering it in ``services/avatar/factory.py``.

Providers MUST NOT touch Remotion, FFmpeg compositing, or rendering.
They are responsible ONLY for:

1. Generating per-scene transparent avatar video clips (WebM with alpha)
   inside the project's ``avatar/`` folder.
2. Returning accurate per-scene result information.

If a provider cannot generate clips immediately (e.g. requires an external
Colab worker), ``generate()`` should export a package and return an empty
list.  Results are then supplied via an import workflow — identical to how
F5-TTS works for voice.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from models.schemas import AvatarSceneResult, ScriptSchema, AvatarProviderCapabilities


class AvatarProvider(ABC):
    """Pluggable avatar provider interface.

    Each provider is responsible for one thing: given a project and a
    script, produce a list of :class:`~models.schemas.AvatarSceneResult`
    objects that the renderer can overlay on the whiteboard canvas without
    any knowledge of *how* the clips were produced.

    Providers MUST NOT touch the rendering pipeline, Remotion, or FFmpeg
    compositing.  They are responsible only for:

    1. Producing transparent WebM video files on disk inside the project's
       ``avatar/`` folder.
    2. Returning accurate per-scene duration and clip path information.

    Adding a new provider (e.g. HeyGen, D-ID, LivePortrait) means
    creating a new subclass here and registering it in ``factory.py``.
    """

    # Human-readable name used in logs and metadata.
    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        project_id: str,
        script: ScriptSchema,
        avatar_source: str,
    ) -> List[AvatarSceneResult]:
        """Generate (or prepare) avatar clips for every scene in *script*.

        Args:
            project_id: Unique project identifier.
            script: Parsed script containing all scenes with narration text.
            avatar_source: Path or key for the reference image/video used
                as the talking-head source (e.g. path to uploaded photo).

        Returns:
            A list of :class:`AvatarSceneResult` — one per scene — containing
            the relative WebM clip path and duration.  For providers that do
            *not* produce clips immediately (e.g. SadTalker Colab queue),
            this method exports a package and returns an *empty* list; results
            will be supplied later via the import workflow.
        """
    @abstractmethod
    def get_capabilities(self) -> AvatarProviderCapabilities:
        """Return the capability model for this avatar provider.

        Hardening 6: Capabilities are typed via Pydantic model.
        """
        ...
