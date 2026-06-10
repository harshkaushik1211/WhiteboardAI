import React, { useCallback, useEffect, useRef, useState } from "react";
import { continueRender, delayRender, useCurrentFrame } from "remotion";
import { getStrokeProgress } from "../animations/strokeReveal";
import type { StrokeData } from "../types/stroke";
import { strokeCellCount, strokeObjectSpans } from "../types/stroke";
import { resolveImageSrc } from "../utils/resolveImageSrc";
import { cellDestRect, computeSketchLayout } from "../utils/sketchLayout";

interface ObjectWiseSketchRevealProps {
  src: string;
  inkSrc?: string;
  strokeData: StrokeData;
  startFrame: number;
  endFrame: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Storyboard-ai style: black ink cells build up, then each cell is replaced
 * with color at the same position so drawing stays connected.
 */
export const ObjectWiseSketchReveal: React.FC<ObjectWiseSketchRevealProps> = ({
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
    delayRender("Loading sketch images for stroke reveal")
  );

  const progress = getStrokeProgress(frame, startFrame, endFrame);
  const visibleCells = strokeCellCount(progress, strokeData);
  const objects = strokeObjectSpans(strokeData);

  const paint = useCallback(() => {
    const canvas = canvasRef.current;
    const colorImg = colorRef.current;
    const inkImg = inkRef.current;
    if (!canvas || !colorImg?.complete || !inkImg?.complete) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const layout = computeSketchLayout(width, height, strokeData);
    const split = strokeData.split_len;

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);

    const drawCell = (
      row: number,
      col: number,
      img: HTMLImageElement
    ) => {
      const r = cellDestRect(row, col, split, layout);
      ctx.drawImage(img, r.sx, r.sy, r.sw, r.sh, r.dx, r.dy, r.dw, r.dh);
    };

    for (const obj of objects) {
      if (visibleCells >= obj.end) {
        for (let i = obj.start; i < obj.end; i++) {
          const [row, col] = strokeData.cells[i];
          drawCell(row, col, colorImg);
        }
        continue;
      }

      if (visibleCells > obj.start) {
        for (let i = obj.start; i < visibleCells && i < obj.end; i++) {
          const [row, col] = strokeData.cells[i];
          drawCell(row, col, inkImg);
        }
      }
      break;
    }
  }, [strokeData, visibleCells, objects, width, height]);

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
    color.onload = () => {
      colorRef.current = color;
      done();
    };
    color.onerror = done;

    const ink = new Image();
    ink.crossOrigin = "anonymous";
    ink.src = resolveImageSrc(inkSrc || src);
    ink.onload = () => {
      inkRef.current = ink;
      done();
    };
    ink.onerror = done;

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
