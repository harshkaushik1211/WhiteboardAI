import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import type { RenderScene } from "../types/manifest";
import { WhiteboardCanvas } from "./WhiteboardCanvas";
import { SubtitleRenderer } from "./SubtitleRenderer";
import { CameraMotion } from "./CameraMotion";
import { useSceneTransition } from "../animations/transitions";

interface SceneProps {
  scene: RenderScene;
}

export const Scene: React.FC<SceneProps> = ({ scene }) => {
  const { opacity } = useSceneTransition(
    0,
    scene.duration_frames,
    30
  );

  return (
    <AbsoluteFill style={{ opacity }}>
      <CameraMotion
        sceneStartFrame={0}
        focusX={scene.camera?.focusX ?? 960}
        focusY={scene.camera?.focusY ?? 540}
        zoom={scene.camera?.zoom ?? 1}
      >
        <WhiteboardCanvas
          elements={scene.elements}
          sceneStartFrame={0}
        />
      </CameraMotion>
      <SubtitleRenderer
        subtitles={scene.subtitles}
        globalStartFrame={scene.start_frame}
      />
    </AbsoluteFill>
  );
};
