import React, { useMemo } from "react";
import { useCurrentFrame } from "remotion";
import {
  getStrokeProgress,
  getFadeOpacity,
  getScale,
} from "../animations/strokeReveal";
import { getHighlightWidth, HIGHLIGHT_COLOR } from "../animations/highlights";
import { SVGPathAnimator } from "./SVGPathAnimator";
import { ColoredDiagramStrokeAnimator } from "./ColoredDiagramStrokeAnimator";
import { SharedStrokeSceneAnimator } from "./SharedStrokeSceneAnimator";

interface SVGAnimatorProps {
  svgContent: string;
  startFrame: number;
  endFrame: number;
  animation: string;
  elementType?: string;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  color?: string;
  elementId?: string;
}

export const SVGAnimator: React.FC<SVGAnimatorProps> = ({
  svgContent,
  startFrame,
  endFrame,
  animation,
  elementType = "svg",
  x = 0,
  y = 0,
  width = 380,
  height = 320,
  color = "#1a1a2e",
  elementId = "",
}) => {
  const frame = useCurrentFrame();
  const progress = getStrokeProgress(frame, startFrame, endFrame);

  const sharedSceneSketch = useMemo(() => {
    if (animation !== "stroke_reveal") return false;
    if (elementId.endsWith("-sketch") || /-layer-\d+$/.test(elementId)) return true;
    return width >= 1600 && height >= 900;
  }, [animation, elementId, width, height]);

  const diagramStroke = useMemo(() => {
    if (animation !== "stroke_reveal") return false;
    const inner = svgContent.match(/<svg[^>]*>([\s\S]*)<\/svg>/i)?.[1] ?? svgContent;
    const paths = [...inner.matchAll(/<path[^>]*>/gi)];
    const filled = paths.filter((m) => /fill="(?!none)/i.test(m[0])).length;
    return paths.length >= 40 && filled >= 20;
  }, [svgContent, animation]);

  if (animation === "static" || elementType === "diagram") {
    const innerSvg = useMemo(() => {
      const match = svgContent.match(/<svg[^>]*>([\s\S]*)<\/svg>/i);
      return match ? match[1] : svgContent;
    }, [svgContent]);

    const vbMatch = svgContent.match(/viewBox="([^"]+)"/i);
    const viewBox = vbMatch ? vbMatch[1] : `0 0 ${width} ${height}`;

    return (
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          width,
          height,
          opacity: 1,
        }}
        dangerouslySetInnerHTML={{
          __html: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}" width="${width}" height="${height}">${innerSvg}</svg>`,
        }}
      />
    );
  }

  if (animation === "fade_in" || elementType === "text" || elementType === "label") {
    const opacity = getFadeOpacity(progress);
    const innerSvg = useMemo(() => {
      const match = svgContent.match(/<svg[^>]*>([\s\S]*)<\/svg>/i);
      return match ? match[1] : svgContent;
    }, [svgContent]);

    return (
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          width,
          height,
          opacity,
          transform: `scale(${getScale(progress)})`,
        }}
        dangerouslySetInnerHTML={{
          __html: `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">${innerSvg}</svg>`,
        }}
      />
    );
  }

  if (animation === "highlight") {
    const w = getHighlightWidth(frame, startFrame, endFrame, width);
    return (
      <div
        style={{
          position: "absolute",
          left: x,
          top: y + height * 0.4,
          width: w,
          height: 10,
          backgroundColor: HIGHLIGHT_COLOR,
          borderRadius: 4,
        }}
      />
    );
  }

  if (sharedSceneSketch) {
    return (
      <SharedStrokeSceneAnimator
        svgContent={svgContent}
        startFrame={startFrame}
        endFrame={endFrame}
        x={x}
        y={y}
        width={width}
        height={height}
        color={color}
      />
    );
  }

  if (diagramStroke) {
    return (
      <ColoredDiagramStrokeAnimator
        svgContent={svgContent}
        startFrame={startFrame}
        endFrame={endFrame}
        x={x}
        y={y}
        width={width}
        height={height}
      />
    );
  }

  // stroke_reveal, scale_in — per-path animator for outline icons
  return (
    <SVGPathAnimator
      svgContent={svgContent}
      startFrame={startFrame}
      endFrame={endFrame}
      x={x}
      y={y}
      width={width}
      height={height}
      color={color}
    />
  );
};
