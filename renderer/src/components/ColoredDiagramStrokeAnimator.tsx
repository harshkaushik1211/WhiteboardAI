import React, { useMemo } from "react";
import { useCurrentFrame } from "remotion";
import {
  getStrokeProgress,
  getDashOffset,
  isStrokeComplete,
  parsePathLengthFromTag,
  extractFillColor,
  isDiagramBackgroundPath,
  DEFAULT_PATH_LENGTH,
} from "../animations/strokeReveal";

const DRAWABLE_TAGS = /<(path|circle|rect|ellipse|line|polyline|polygon)[^>]*>/gi;

function applyColoredStroke(
  tag: string,
  strokeColor: string,
  pathLen: number,
  progress: number
): string {
  if (isStrokeComplete(progress)) return tag;

  const dashOffset = getDashOffset(pathLen, progress);
  let out = tag
    .replace(/\s*stroke="[^"]*"/gi, "")
    .replace(/\s*stroke-width="[^"]*"/gi, "")
    .replace(/\s*fill="[^"]*"/gi, ' fill="none"');
  const selfClose = out.trimEnd().endsWith("/>");
  out = selfClose ? out.trimEnd().slice(0, -2) : out.trimEnd().replace(/>$/, "");
  return `${out} stroke="${strokeColor}" stroke-width="1.4" fill="none" vector-effect="non-scaling-stroke" style="stroke-dasharray:${pathLen};stroke-dashoffset:${dashOffset}"${selfClose ? " />" : ">"}`;
}

interface ColoredDiagramStrokeAnimatorProps {
  svgContent: string;
  startFrame: number;
  endFrame: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
}

/** Stroke-reveal for filled diagrams: each path draws in its own fill color, then fills in. */
export const ColoredDiagramStrokeAnimator: React.FC<ColoredDiagramStrokeAnimatorProps> = ({
  svgContent,
  startFrame,
  endFrame,
  x = 0,
  y = 0,
  width = 380,
  height = 320,
}) => {
  const frame = useCurrentFrame();
  const progress = getStrokeProgress(frame, startFrame, endFrame);

  const { viewBox, paths, innerSvg } = useMemo(() => {
    const vbMatch = svgContent.match(/viewBox="([^"]+)"/i);
    const viewBox = vbMatch ? vbMatch[1] : `0 0 ${width} ${height}`;
    const innerMatch = svgContent.match(/<svg[^>]*>([\s\S]*)<\/svg>/i);
    const inner = innerMatch ? innerMatch[1] : svgContent;
    const paths = [...inner.matchAll(DRAWABLE_TAGS)].map((m) => m[0]);
    return { viewBox, paths, innerSvg: inner };
  }, [svgContent, width, height]);

  if (isStrokeComplete(progress)) {
    return (
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          width,
          height,
        }}
        dangerouslySetInnerHTML={{
          __html: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}" width="${width}" height="${height}">${innerSvg}</svg>`,
        }}
      />
    );
  }

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        height,
      }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox={viewBox}
        width={width}
        height={height}
        style={{ overflow: "visible" }}
      >
        {paths.map((tag, i) => {
          const pathProgress = isDiagramBackgroundPath(tag, i) ? 1 : progress;
          const pathLen = parsePathLengthFromTag(tag, DEFAULT_PATH_LENGTH);
          const strokeColor = extractFillColor(tag, "#1a1a2e");
          const html = applyColoredStroke(tag, strokeColor, pathLen, pathProgress);
          return <g key={i} dangerouslySetInnerHTML={{ __html: html }} />;
        })}
      </svg>
    </div>
  );
};
