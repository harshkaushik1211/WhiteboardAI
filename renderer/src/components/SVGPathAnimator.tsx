import React, { useMemo } from "react";
import { useCurrentFrame } from "remotion";
import {
  getStrokeProgress,
  getDashOffset,
  isStrokeComplete,
  parsePathLengthFromTag,
  sequencePathDelays,
  DEFAULT_PATH_LENGTH,
} from "../animations/strokeReveal";

const DRAWABLE_TAGS = /<(path|circle|rect|ellipse|line|polyline|polygon)[^>]*>/gi;

interface SVGPathAnimatorProps {
  svgContent: string;
  startFrame: number;
  endFrame: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  color?: string;
}

export const SVGPathAnimator: React.FC<SVGPathAnimatorProps> = ({
  svgContent,
  startFrame,
  endFrame,
  x = 0,
  y = 0,
  width = 380,
  height = 320,
  color = "#1a1a2e",
}) => {
  const frame = useCurrentFrame();

  const { viewBox, paths, innerSvg } = useMemo(() => {
    const vbMatch = svgContent.match(/viewBox="([^"]+)"/i);
    const viewBox = vbMatch ? vbMatch[1] : `0 0 ${width} ${height}`;
    const innerMatch = svgContent.match(/<svg[^>]*>([\s\S]*)<\/svg>/i);
    const inner = innerMatch ? innerMatch[1] : svgContent;
    const paths = [...inner.matchAll(DRAWABLE_TAGS)].map((m) => m[0]);
    return { viewBox, paths, innerSvg: inner };
  }, [svgContent, width, height]);

  const delays = sequencePathDelays(paths.length, startFrame, endFrame);
  const overallProgress = getStrokeProgress(frame, startFrame, endFrame);

  if (isStrokeComplete(overallProgress)) {
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
          const { start, end } = delays[i] || { start: startFrame, end: endFrame };
          const progress = getStrokeProgress(frame, start, end);
          if (isStrokeComplete(progress)) {
            return (
              <g key={i} dangerouslySetInnerHTML={{ __html: tag }} />
            );
          }
          const pathLen = parsePathLengthFromTag(tag, DEFAULT_PATH_LENGTH);
          const dashOffset = getDashOffset(pathLen, progress);
          const opacity = progress > 0 ? 1 : 0;

          const animated = tag
            .replace(/stroke="[^"]*"/g, "")
            .replace(/stroke-width="[^"]*"/g, "")
            .replace(/fill="[^"]*"/g, 'fill="none"')
            .replace(/>\s*$/, ` stroke="${color}" stroke-width="2.5" fill="none" opacity="${opacity}" style="stroke-dasharray:${pathLen};stroke-dashoffset:${dashOffset}" />`);

          return (
            <g
              key={i}
              dangerouslySetInnerHTML={{ __html: animated }}
            />
          );
        })}
      </svg>
    </div>
  );
};
