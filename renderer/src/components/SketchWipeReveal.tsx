import React from "react";
import { Img, useCurrentFrame } from "remotion";
import { getStrokeProgress, isStrokeComplete } from "../animations/strokeReveal";
import { resolveImageSrc } from "../utils/resolveImageSrc";

interface SketchWipeRevealProps {
  src: string;
  startFrame: number;
  endFrame: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Storyboard-style reveal: image appears as if drawn left-to-right (clip-path wipe).
 */
export const SketchWipeReveal: React.FC<SketchWipeRevealProps> = ({
  src,
  startFrame,
  endFrame,
  x,
  y,
  width,
  height,
}) => {
  const frame = useCurrentFrame();
  const progress = getStrokeProgress(frame, startFrame, endFrame);

  if (isStrokeComplete(progress)) {
    return (
      <Img
        src={resolveImageSrc(src)}
        style={{
          position: "absolute",
          left: x,
          top: y,
          width,
          height,
          objectFit: "contain",
        }}
      />
    );
  }

  const clipRight = Math.max(0, 100 - progress * 100);

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        height,
        overflow: "hidden",
        clipPath: `inset(0 ${clipRight}% 0 0)`,
      }}
    >
      <Img
        src={resolveImageSrc(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
        }}
      />
    </div>
  );
};
