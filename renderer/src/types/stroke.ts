export interface StrokeObjectSpan {
  start: number;
  end: number;
  area?: number;
  bbox?: [number, number, number, number];
  label?: string;
  path_start?: number;
  path_end?: number;
  path_count?: number;
  is_background?: boolean;
}

export interface ContourPath {
  d: string;
  length: number;
  label?: string;
  area?: number;
}

export interface StrokeData {
  width: number;
  height: number;
  split_len: number;
  stroke_mode?: "svg_contour" | "grid";
  segmentation_backend?: string;
  cells: [number, number][];
  paths?: ContourPath[];
  path_count?: number;
  objects?: StrokeObjectSpan[];
  cell_count?: number;
  object_count?: number;
  object_labels?: string[];
  ink_image?: string;
}

export function strokeCellCount(progress: number, strokeData: StrokeData): number {
  const cells = strokeData.cells;
  if (!cells.length) return 0;
  if (progress >= 1) return cells.length;
  return Math.floor(progress * cells.length);
}

export function strokePathCount(progress: number, strokeData: StrokeData): number {
  const total = strokeData.path_count ?? strokeData.paths?.length ?? 0;
  if (!total) return 0;
  if (progress >= 1) return total;
  return Math.floor(progress * total);
}

export function strokeObjectSpans(strokeData: StrokeData): StrokeObjectSpan[] {
  if (strokeData.objects?.length) return strokeData.objects;

  if (strokeData.stroke_mode === "svg_contour" && strokeData.paths?.length) {
    return [
      {
        start: 0,
        end: strokeData.paths.length,
        path_start: 0,
        path_end: strokeData.paths.length,
      },
    ];
  }

  return [{ start: 0, end: strokeData.cells.length }];
}
