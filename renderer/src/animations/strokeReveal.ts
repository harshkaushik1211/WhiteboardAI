import { Easing, interpolate } from "remotion";

export const DEFAULT_PATH_LENGTH = 400;
/** When progress reaches this, show the final crisp artwork (no dash overlay). */
export const STROKE_COMPLETE_PROGRESS = 0.995;

export function isStrokeComplete(progress: number): boolean {
  return progress >= STROKE_COMPLETE_PROGRESS;
}

export function getStrokeProgress(
  frame: number,
  startFrame: number,
  endFrame: number
): number {
  const span = Math.max(endFrame - startFrame, 1);
  return interpolate(frame, [startFrame, startFrame + span], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });
}

/** Slightly longer than true length so dashes fully clear before we snap to final art. */
export function effectivePathLength(pathLength: number): number {
  return Math.max(pathLength * 1.12, 40);
}

export function getDashOffset(pathLength: number, progress: number): number {
  return effectivePathLength(pathLength) * (1 - progress);
}

export function getFadeOpacity(progress: number): number {
  return progress;
}

export function getScale(progress: number): number {
  return 0.5 + progress * 0.5;
}

/** Stagger per-path reveal across total frame span */
export function sequencePathDelays(
  pathCount: number,
  startFrame: number,
  endFrame: number,
  staggerRatio: number = 0.15
): Array<{ start: number; end: number }> {
  if (pathCount <= 0) return [];
  const total = Math.max(endFrame - startFrame, 1);
  const each = Math.max(8, Math.floor(total / pathCount));
  const stagger = Math.floor(each * staggerRatio);
  return Array.from({ length: pathCount }, (_, i) => ({
    start: startFrame + i * stagger,
    end: Math.min(endFrame, startFrame + (i + 1) * each),
  }));
}

export function parsePathLengthFromTag(tag: string, fallback: number): number {
  const m = tag.match(/data-path-length="([\d.]+)"/);
  if (m) return parseFloat(m[1]);
  const d = tag.match(/\sd="([^"]*)"/i);
  if (d) return estimatePathLengthFromD(d[1]);
  return fallback;
}

/** Rough length when data-path-length is missing (filled diagram exports). */
export function estimatePathLengthFromD(d: string): number {
  const nums = d.match(/-?\d+\.?\d*/g) || [];
  return Math.max(120, Math.min(6000, nums.length * 14));
}

export function extractFillColor(tag: string, fallback: string): string {
  const m = tag.match(/fill="([^"]+)"/i);
  if (!m || m[1] === "none") return fallback;
  return m[1];
}

const DIAGRAM_BG_FILLS = new Set(["#eef5f9", "#ffffff", "#fff"]);

export function isDiagramBackgroundPath(tag: string, index: number): boolean {
  if (index === 0 && /M0\s+0\s+C316/i.test(tag)) return true;
  const fill = extractFillColor(tag, "").toLowerCase();
  return DIAGRAM_BG_FILLS.has(fill);
}
