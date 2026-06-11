import React, { useEffect, useMemo, useState } from "react";
import { continueRender, delayRender, useCurrentFrame } from "remotion";
import {
  getDashOffset,
  getStrokeProgress,
  isStrokeComplete,
} from "../animations/strokeReveal";
import type { ContourPath, StrokeData } from "../types/stroke";
import { resolveImageSrc } from "../utils/resolveImageSrc";

interface ContourStrokeRevealProps {
  src: string;
  inkSrc?: string;
  strokeData: StrokeData;
  startFrame: number;
  endFrame: number;
  x: number;
  y: number;
  width: number;
  height: number;
  color?: string;
}

interface PathDrawState {
  path: ContourPath;
  status: "pending" | "drawing" | "done";
  localProgress: number;
}

/** Length-weighted sequential stroke reveal — one line after another. */
function computePathDrawStates(
  paths: ContourPath[],
  progress: number,
  strokePhaseEnd: number
): PathDrawState[] {
  if (!paths.length) return [];

  const totalLen = paths.reduce((s, p) => s + Math.max(p.length || 80, 8), 0);
  const strokeT = Math.min(1, progress / strokePhaseEnd);
  const drawnLen = strokeT * totalLen;

  let acc = 0;
  return paths.map((path) => {
    const len = Math.max(path.length || 80, 8);
    if (acc + len <= drawnLen) {
      acc += len;
      return { path, status: "done" as const, localProgress: 1 };
    }
    if (acc < drawnLen) {
      const localProgress = (drawnLen - acc) / len;
      acc += len;
      return { path, status: "drawing" as const, localProgress };
    }
    return { path, status: "pending" as const, localProgress: 0 };
  });
}

/**
 * Line-by-line whiteboard stroke reveal:
 *   Phase 1: SVG paths drawn sequentially with dash animation (brush-like)
 *   Phase 2: color image fades in when strokes complete
 */
export const ContourStrokeReveal: React.FC<ContourStrokeRevealProps> = ({
  src,
  strokeData,
  startFrame,
  endFrame,
  x,
  y,
  width,
  height,
  color = "#1a1a2e",
}) => {
  const frame = useCurrentFrame();
  const [colorReady, setColorReady] = useState(false);
  const [handle] = useState(() =>
    delayRender("Loading sketch for line stroke reveal")
  );

  const progress = getStrokeProgress(frame, startFrame, endFrame);
  const paths = strokeData.paths ?? [];
  const sw = strokeData.width;
  const sh = strokeData.height;

  const STROKE_PHASE_END = 0.9;
  const COLOR_FADE_START = 0.88;

  const pathStates = useMemo(
    () => computePathDrawStates(paths, progress, STROKE_PHASE_END),
    [paths, progress]
  );

  const colorAlpha =
    progress < COLOR_FADE_START
      ? 0
      : Math.min(1, (progress - COLOR_FADE_START) / (1 - COLOR_FADE_START));

  const showFullColor = isStrokeComplete(progress);

  useEffect(() => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = resolveImageSrc(src);
    img.onload = () => {
      setColorReady(true);
      continueRender(handle);
    };
    img.onerror = () => continueRender(handle);
  }, [src, handle]);

  if (!paths.length) {
    return null;
  }

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        height,
        background: "#ffffff",
      }}
    >
      {/* Stroke layer — viewBox matches stroke-data coords */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox={`0 0 ${sw} ${sh}`}
        width={width}
        height={height}
        preserveAspectRatio="xMidYMid meet"
        style={{ position: "absolute", inset: 0, overflow: "visible" }}
      >
        {pathStates.map(({ path, status, localProgress }, i) => {
          if (status === "pending") return null;

          const len = Math.max(path.length || 80, 8);

          if (status === "done") {
            return (
              <path
                key={i}
                d={path.d}
                stroke={color}
                strokeWidth={2.8}
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            );
          }

          const dashOffset = getDashOffset(len, localProgress);
          return (
            <path
              key={i}
              d={path.d}
              stroke={color}
              strokeWidth={2.8}
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
              strokeDasharray={`${len} ${len}`}
              strokeDashoffset={dashOffset}
            />
          );
        })}
      </svg>

      {/* Color image fades in after strokes finish */}
      {colorReady && colorAlpha > 0 && (
        <img
          src={resolveImageSrc(src)}
          alt=""
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "contain",
            opacity: showFullColor ? 1 : colorAlpha,
            pointerEvents: "none",
          }}
        />
      )}
    </div>
  );
};
