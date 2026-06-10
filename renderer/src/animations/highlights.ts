import { interpolate } from "remotion";

export function getHighlightWidth(
  frame: number,
  startFrame: number,
  endFrame: number,
  fullWidth: number
): number {
  const progress = interpolate(
    frame,
    [startFrame, endFrame],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return fullWidth * progress;
}

export const HIGHLIGHT_COLOR = "rgba(255, 235, 59, 0.5)";
