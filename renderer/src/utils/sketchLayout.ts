import type { StrokeData } from "../types/stroke";

/** Map stroke grid coords → canvas pixels (letterboxed, centered). */
export interface SketchLayout {
  sw: number;
  sh: number;
  scale: number;
  offsetX: number;
  offsetY: number;
  drawW: number;
  drawH: number;
}

export function computeSketchLayout(
  canvasW: number,
  canvasH: number,
  strokeData: StrokeData
): SketchLayout {
  const sw = strokeData.width;
  const sh = strokeData.height;
  const scale = Math.min(canvasW / sw, canvasH / sh);
  const drawW = sw * scale;
  const drawH = sh * scale;
  return {
    sw,
    sh,
    scale,
    offsetX: (canvasW - drawW) / 2,
    offsetY: (canvasH - drawH) / 2,
    drawW,
    drawH,
  };
}

export function cellDestRect(
  row: number,
  col: number,
  split: number,
  layout: SketchLayout
): { sx: number; sy: number; sw: number; sh: number; dx: number; dy: number; dw: number; dh: number } {
  const sx = col * split;
  const sy = row * split;
  const sw = Math.min(split, layout.sw - sx);
  const sh = Math.min(split, layout.sh - sy);
  const { scale, offsetX, offsetY } = layout;
  return {
    sx,
    sy,
    sw,
    sh,
    dx: offsetX + sx * scale,
    dy: offsetY + sy * scale,
    dw: sw * scale,
    dh: sh * scale,
  };
}
