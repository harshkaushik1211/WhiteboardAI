import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";

interface CameraMotionProps {
  children: React.ReactNode;
  sceneStartFrame: number;
  focusX?: number;
  focusY?: number;
  zoom?: number;
}

export const CameraMotion: React.FC<CameraMotionProps> = ({
  children,
  sceneStartFrame,
  focusX = 960,
  focusY = 540,
  zoom = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - sceneStartFrame,
    fps,
    config: { damping: 200, stiffness: 80 },
  });

  const currentZoom = 1 + (zoom - 1) * progress;
  const panStrength = zoom > 1.2 ? 0.42 : 0.15;
  const offsetX = (960 - focusX) * panStrength * progress;
  const offsetY = (540 - focusY) * panStrength * progress;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        transform: `scale(${currentZoom}) translate(${offsetX}px, ${offsetY}px)`,
        transformOrigin: "center center",
        transition: "transform 0.1s ease-out",
      }}
    >
      {children}
    </div>
  );
};
