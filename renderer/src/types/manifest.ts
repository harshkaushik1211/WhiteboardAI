import type { StrokeData } from "./stroke";

export interface Position {
  x: number;
  y: number;
}

export interface Size {
  w: number;
  h: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface RenderElement {
  id: string;
  type: string;
  shape?: string;
  position?: Position;
  size?: Size;
  from?: Point;
  to?: Point;
  from_point?: Point;
  to_point?: Point;
  animation: string;
  start_frame: number;
  end_frame: number;
  label?: string;
  text?: string;
  color?: string;
  svg_content?: string;
  svg_path?: string;
  image_src?: string;
  stroke_data?: StrokeData;
  ink_image_src?: string;
  action?: string;
  animation_intent?: string;
  motion_profile?: string;
  target_id?: string;
}

export interface SubtitleEntry {
  text: string;
  start_frame: number;
  end_frame: number;
  highlight_words?: string[];
}

export interface RenderScene {
  scene_id: number;
  start_frame: number;
  duration_frames: number;
  audio?: string;
  narration: string;
  subtitles: SubtitleEntry[];
  elements: RenderElement[];
  camera?: { zoom?: number; focusX?: number; focusY?: number };
  // Phase-4 SadTalker avatar overlay (optional)
  avatar_clip_src?: string;   // Remotion staticFile() path to transparent WebM clip
  avatar_position?: "bottom_right" | "bottom_left" | "bottom_center";
  avatar_scale?: number;       // 0.0–1.0 relative to video height
  avatar_start_frame?: number; // P1: scene offset frame in combined avatar video
}

export interface RenderManifest {
  title: string;
  fps: number;
  width: number;
  height: number;
  total_frames: number;
  scenes: RenderScene[];
  // P1/P10: Single avatar video configuration
  avatar_clip_src?: string;
  avatar_position?: "bottom_right" | "bottom_left" | "bottom_center";
  avatar_scale?: number;
  avatar_layout?: "pip" | "teacher_mode" | "split_screen" | "full_avatar";
  avatar_duration_valid?: boolean;
  // Optional legacy / fallback global avatar config
  avatar?: {
    position?: "bottom_right" | "bottom_left" | "bottom_center";
    scale?: number;
  };
}
