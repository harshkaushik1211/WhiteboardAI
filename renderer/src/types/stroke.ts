export interface StrokeObjectSpan {
  start: number;
  end: number;
  area?: number;
  /** Pixel bbox [x, y, w, h] for color fill when object finishes drawing */
  bbox?: [number, number, number, number];
}

export interface StrokeData {
  width: number;
  height: number;
  split_len: number;
  cells: [number, number][];
  objects?: StrokeObjectSpan[];
  cell_count?: number;
  object_count?: number;
  ink_image?: string;
}

/** Continuous grid reveal (matches storyboard-ai cell cadence). */
export function strokeCellCount(progress: number, strokeData: StrokeData): number {
  const cells = strokeData.cells;
  if (!cells.length) return 0;
  if (progress >= 1) return cells.length;
  return Math.floor(progress * cells.length);
}

export function strokeObjectSpans(
  strokeData: StrokeData
): StrokeObjectSpan[] {
  if (strokeData.objects?.length) return strokeData.objects;
  return [{ start: 0, end: strokeData.cells.length }];
}
