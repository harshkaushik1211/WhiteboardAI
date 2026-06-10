import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useVideoConfig,
} from "remotion";
import type { RenderManifest } from "../types/manifest";
import { Scene } from "../components/Scene";
import { AvatarOverlay } from "../components/AvatarOverlay";

interface WhiteboardVideoProps {
  manifest?: RenderManifest;
}

export const WhiteboardVideo: React.FC<WhiteboardVideoProps> = ({ manifest }) => {
  const { fps } = useVideoConfig();

  if (!manifest) {
    return null;
  }

  // Global/Project-level avatar configuration (P1 / P10)
  const globalAvatarClip = manifest.avatar_clip_src;
  const globalAvatarPosition = manifest.avatar_position ?? manifest.avatar?.position ?? "bottom_right";
  const globalAvatarScale = manifest.avatar_scale ?? manifest.avatar?.scale ?? 0.25;
  const globalAvatarLayout = manifest.avatar_layout ?? "pip";

  return (
    <AbsoluteFill style={{ backgroundColor: "#ffffff" }}>
      {manifest.scenes.map((scene) => {
        // Use project-level clip if available, otherwise fall back to per-scene clip (backward compatible)
        const clipSrc = globalAvatarClip || scene.avatar_clip_src;
        const position = scene.avatar_position ?? globalAvatarPosition;
        const scale = scene.avatar_scale ?? globalAvatarScale;
        const startFrom = globalAvatarClip ? (scene.avatar_start_frame ?? 0) : 0;

        return (
          <Sequence
            key={scene.scene_id}
            from={scene.start_frame}
            durationInFrames={scene.duration_frames}
          >
            {/* ── Whiteboard canvas (always rendered) ── */}
            <Scene scene={scene} />

            {/* ── Avatar overlay (optional — only rendered when clip is present) ── */}
            <AvatarOverlay
              clipSrc={clipSrc}
              position={position}
              scale={scale}
              fadeInFrames={12}
              startFrom={startFrom}
              layout={globalAvatarLayout}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
