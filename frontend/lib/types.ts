export interface Scene {
  scene_id: number;
  narration: string;
  visual_description: string;
  keywords: string[];
  duration: number;
}

export interface Script {
  title: string;
  total_duration: number;
  scenes: Scene[];
}

export interface SceneElement {
  id: string;
  type: string;
  concept?: string;
  asset_id?: string;
  asset_library_path?: string;
  shape?: string;
  position?: { x: number; y: number };
  size?: { w: number; h: number };
  animation: string;
  delay: number;
  duration: number;
  label?: string;
  text?: string;
  svg_path?: string;
}

export interface ScenePlan {
  scene_id: number;
  background: string;
  elements: SceneElement[];
  camera?: { zoom?: number; focusX?: number; focusY?: number };
}

export interface Project {
  project_id: string;
  topic: string;
  status: string;
  script?: Script;
  scene_plans?: ScenePlan[];
  voice_files?: string[];
  video_url?: string;
  config?: Record<string, unknown>;
  ai_sketch_audit?: AiSketchAuditEntry[];
  ai_image_audit?: AiImageAuditEntry[];
  // Voice provider status
  voice_generation_status?: string;     // "pending" | "completed"
  f5_package_exported?: boolean;
  f5_processing_status?: string;
  // F5 import audit
  audio_imported_at?: string | null;
  // Avatar pipeline — Phase-4 SadTalker
  avatar_provider?: string | null;      // null | "sadtalker" | "liveportrait" | "musetalk"
  avatar_source?: string | null;        // relative path to source portrait image
  avatar_status?: string | null;        // legacy field
  avatar_generation_status?: string;    // "pending" | "completed"
  sadtalker_package_exported?: boolean;
  sadtalker_processing_status?: string; // "queued" | "processing" | "clips_ready" | "completed" | "failed"
  avatar_imported_at?: string | null;
  avatar_position?: string;             // "bottom_right" | "bottom_left" | "bottom_center"
  avatar_scale?: number;                // 0.0–1.0
}

export interface AiImageAuditEntry {
  scene_id: number;
  headline: string;
  image_path: string;
  image_prompt: string;
  model: string;
  visual_mode: string;
}

export type VisualMode = "library" | "ai_line_art" | "ai_image";
export type VoiceProvider = "edge" | "f5tts";

export type AvatarProvider = "liveportrait" | "musetalk" | "sadtalker" | null;

export interface GenerateConfig {
  topic: string;
  duration: number;
  style: string;
  voice: string;
  language: string;
  visual_mode?: VisualMode;
  voice_provider?: VoiceProvider;
  avatar_provider?: AvatarProvider;
}

export interface AiSketchLayerAudit {
  layer_index: number;
  label: string;
  svg_path: string;
  path_count: number;
}

export interface AiSketchAuditEntry {
  scene_id: number;
  headline: string;
  layers: AiSketchLayerAudit[];
  layer_count: number;
  model: string;
  visual_mode: string;
  /** @deprecated single-layer audit */
  svg_path?: string;
  path_count?: number;
}

export interface JobUpdate {
  job_id: string;
  project_id: string;
  step: string;
  progress: number;
  message: string;
  error?: string;
}
