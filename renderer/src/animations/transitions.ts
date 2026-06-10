import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export function useSceneTransition(
  sceneStartFrame: number,
  sceneDurationFrames: number,
  transitionFrames: number = 24
) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = interpolate(
    frame,
    [sceneStartFrame, sceneStartFrame + transitionFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const fadeOut = interpolate(
    frame,
    [
      sceneStartFrame + sceneDurationFrames - transitionFrames,
      sceneStartFrame + sceneDurationFrames,
    ],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const opacity = Math.min(fadeIn, fadeOut);

  const scale = spring({
    frame: frame - sceneStartFrame,
    fps,
    config: { damping: 200, stiffness: 100 },
  });

  return { opacity, scale: 0.95 + scale * 0.05 };
}

export function useZoomPan(
  focusX: number,
  focusY: number,
  zoom: number,
  sceneStartFrame: number
) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - sceneStartFrame,
    fps,
    config: { damping: 200 },
  });

  const currentZoom = 1 + (zoom - 1) * progress;
  const offsetX = (960 - focusX) * progress * 0.1;
  const offsetY = (540 - focusY) * progress * 0.1;

  return {
    transform: `scale(${currentZoom}) translate(${offsetX}px, ${offsetY}px)`,
  };
}
