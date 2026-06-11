import React, { useCallback, useEffect, useRef, useState } from "react";
import { continueRender, delayRender, useCurrentFrame } from "remotion";
import { getStrokeProgress } from "../animations/strokeReveal";
import type { StrokeData } from "../types/stroke";
import { resolveImageSrc } from "../utils/resolveImageSrc";
import { computeSketchLayout } from "../utils/sketchLayout";

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

/**
 * Whiteboard "ink sweep" reveal:
 *   Phase 1 (0 → 70%): ink image sweeps in top-to-bottom with a soft gradient brush edge
 *   Phase 2 (65% → 100%): color image fades in over the ink
 *
 * This replaces the old SVG-contour-path approach which produced tiny invisible
 * fragments and bbox-rectangle artifacts.
 */
export const ContourStrokeReveal: React.FC<ContourStrokeRevealProps> = ({
  src,
  inkSrc,
  strokeData,
  startFrame,
  endFrame,
  x,
  y,
  width,
  height,
}) => {
  const frame = useCurrentFrame();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const colorRef = useRef<HTMLImageElement | null>(null);
  const inkRef = useRef<HTMLImageElement | null>(null);
  const [handle] = useState(() =>
    delayRender("Loading images for ink sweep reveal")
  );

  const progress = getStrokeProgress(frame, startFrame, endFrame);
  const layout = computeSketchLayout(width, height, strokeData);
  const { scale, offsetX, offsetY, drawW, drawH } = layout;
  const sW = strokeData.width;
  const sH = strokeData.height;

  // Timing constants
  const INK_SWEEP_END = 0.72;    // ink sweep occupies first 72% of animation
  const COLOR_FADE_IN = 0.65;    // color starts fading in while ink is still sweeping
  const BRUSH_EDGE_PX = 80;      // soft gradient pixels at the sweep boundary

  const paint = useCallback(() => {
    const canvas = canvasRef.current;
    const colorImg = colorRef.current;
    if (!canvas || !colorImg?.complete) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);

    const inkImg = inkRef.current;

    // ── Phase 1: ink sweep ────────────────────────────────────────────────────
    const inkProgress = Math.min(1, progress / INK_SWEEP_END);
    // revealY is in stroke-data space (0..sH); at inkProgress=1 whole image visible
    const revealYInk = inkProgress * sH;

    const drawSource = (inkImg?.complete ? inkImg : null) ?? colorImg;
    if (revealYInk > 0) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(offsetX, offsetY, drawW, revealYInk * scale);
      ctx.clip();
      ctx.drawImage(drawSource, 0, 0, sW, sH, offsetX, offsetY, drawW, drawH);
      ctx.restore();

      // Soft gradient brush edge at the sweep boundary
      if (inkProgress < 1) {
        const edgeCanvasY = offsetY + revealYInk * scale;
        const edgeH = BRUSH_EDGE_PX * scale;
        const grad = ctx.createLinearGradient(
          0, edgeCanvasY - edgeH,
          0, edgeCanvasY + 4
        );
        grad.addColorStop(0, "rgba(255,255,255,0)");
        grad.addColorStop(1, "rgba(255,255,255,1)");
        ctx.fillStyle = grad;
        ctx.fillRect(0, edgeCanvasY - edgeH, width, edgeH + 4);
      }
    }

    // ── Phase 2: color fade-in ────────────────────────────────────────────────
    const colorAlpha =
      progress < COLOR_FADE_IN
        ? 0
        : Math.min(1, (progress - COLOR_FADE_IN) / (1 - COLOR_FADE_IN));

    if (colorAlpha > 0) {
      ctx.globalAlpha = colorAlpha;
      ctx.drawImage(colorImg, 0, 0, sW, sH, offsetX, offsetY, drawW, drawH);
      ctx.globalAlpha = 1;
    }
  }, [
    progress,
    strokeData,
    width,
    height,
    scale,
    offsetX,
    offsetY,
    drawW,
    drawH,
    sW,
    sH,
  ]);

  useEffect(() => {
    paint();
  }, [paint, frame]);

  useEffect(() => {
    let pending = 2;
    const done = () => {
      pending -= 1;
      if (pending <= 0) {
        paint();
        continueRender(handle);
      }
    };

    const color = new Image();
    color.crossOrigin = "anonymous";
    color.src = resolveImageSrc(src);
    color.onload = () => { colorRef.current = color; done(); };
    color.onerror = done;

    // inkSrc may be undefined if the ink image wasn't generated; fall back to color.
    const inkSrcResolved = inkSrc ? resolveImageSrc(inkSrc) : null;
    if (inkSrcResolved) {
      const ink = new Image();
      ink.crossOrigin = "anonymous";
      ink.src = inkSrcResolved;
      ink.onload = () => { inkRef.current = ink; done(); };
      ink.onerror = done;
    } else {
      done(); // no ink image — proceed with color only
    }

    return () => {
      colorRef.current = null;
      inkRef.current = null;
    };
  }, [src, inkSrc, handle, paint]);

  return (
    <canvas
      ref={canvasRef}
      width={Math.round(width)}
      height={Math.round(height)}
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        height,
      }}
    />
  );
};
