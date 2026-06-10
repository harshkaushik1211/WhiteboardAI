import React, { useMemo } from "react";
import { useCurrentFrame } from "remotion";
import {
  getStrokeProgress,
  getDashOffset,
  isStrokeComplete,
  parsePathLengthFromTag,
  DEFAULT_PATH_LENGTH,
} from "../animations/strokeReveal";

const DRAWABLE_TAGS = /<(path|circle|rect|ellipse|line|polyline|polygon)[^>]*>/gi;

function applySharedStroke(
  tag: string,
  color: string,
  pathLen: number,
  progress: number
): string {
  if (isStrokeComplete(progress)) return tag;

  const dashOffset = getDashOffset(pathLen, progress);
  const opacity = progress > 0 ? 1 : 0;
  let out = tag
    .replace(/\s*stroke="[^"]*"/gi, "")
    .replace(/\s*stroke-width="[^"]*"/gi, "");
  if (!/fill="/i.test(out)) {
    out = out.replace(/>$/, ' fill="none">');
  }
  const selfClose = out.trimEnd().endsWith("/>");
  out = selfClose ? out.trimEnd().slice(0, -2) : out.trimEnd().replace(/>$/, "");
  return `${out} stroke="${color}" stroke-width="2.5" fill="none" opacity="${opacity}" vector-effect="non-scaling-stroke" style="stroke-dasharray:${pathLen};stroke-dashoffset:${dashOffset}"${selfClose ? " />" : ">"}`;
}

interface SharedStrokeSceneAnimatorProps {
  svgContent: string;
  startFrame: number;
  endFrame: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  color?: string;
}

/** All paths in a scene sketch reveal together (one shared progress). */
export const SharedStrokeSceneAnimator: React.FC<SharedStrokeSceneAnimatorProps> = ({
  svgContent,
  startFrame,
  endFrame,
  x = 0,
  y = 0,
  width = 1920,
  height = 1080,
  color = "#1a1a2e",
}) => {
  const frame = useCurrentFrame();
  const progress = getStrokeProgress(frame, startFrame, endFrame);

  const { viewBox, paths, textMarkup, innerSvg } = useMemo(() => {
    const vbMatch = svgContent.match(/viewBox="([^"]+)"/i);
    const viewBox = vbMatch ? vbMatch[1] : `0 0 ${width} ${height}`;
    const innerMatch = svgContent.match(/<svg[^>]*>([\s\S]*)<\/svg>/i);
    const inner = innerMatch ? innerMatch[1] : svgContent;
    const paths = [...inner.matchAll(DRAWABLE_TAGS)].map((m) => m[0]);
    const texts = [...inner.matchAll(/<text[\s\S]*?<\/text>/gi)].map((m) => m[0]);
    return { viewBox, paths, textMarkup: texts.join(""), innerSvg: inner };
  }, [svgContent, width, height]);

  const complete = isStrokeComplete(progress);

  if (complete) {
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
          const pathLen = parsePathLengthFromTag(tag, DEFAULT_PATH_LENGTH);
          const html = applySharedStroke(tag, color, pathLen, progress);
          return <g key={i} dangerouslySetInnerHTML={{ __html: html }} />;
        })}
        {textMarkup ? (
          <g
            style={{ opacity: progress > 0.65 ? 1 : 0 }}
            dangerouslySetInnerHTML={{ __html: textMarkup }}
          />
        ) : null}
      </svg>
    </div>
  );
};
