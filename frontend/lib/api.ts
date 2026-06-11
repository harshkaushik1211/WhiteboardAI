const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

import type { GenerateConfig, JobUpdate, Project, Script, ScenePlan } from "./types";

export interface VoiceResult {
  scene_id: number;
  audio_path: string;
  duration: number;
  provider: string;
}

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `API error ${res.status}`);
  }
  return res.json();
}

export async function generateScript(config: GenerateConfig) {
  return fetchApi<{ project_id: string; script: Script }>("/generate-script", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function generateScenes(projectId: string) {
  return fetchApi<{ project_id: string; scene_plans: ScenePlan[] }>(
    "/generate-scenes",
    { method: "POST", body: JSON.stringify({ project_id: projectId }) }
  );
}

export async function generateVoice(projectId: string) {
  return fetchApi<{ project_id: string; voice_files: string[] }>(
    "/generate-voice",
    { method: "POST", body: JSON.stringify({ project_id: projectId }) }
  );
}

export async function renderVideo(projectId: string) {
  return fetchApi<{ job_id: string; project_id: string }>("/render-video", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

/**
 * Download the F5-TTS narration package as a ZIP file.
 * The ZIP contains narration_pack.json and one scene_N.txt per scene.
 */
export async function exportF5Package(projectId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/export-f5-package`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Export failed: ${res.status}`);
  }
  return res.blob();
}

/**
 * Upload a ZIP of F5-TTS WAV/MP3 files and generate voice_results.json.
 * The ZIP must contain files named scene_1.wav, scene_2.wav …
 */
export async function importF5Audio(
  projectId: string,
  zipFile: File
): Promise<{
  voice_generation_status: string;
  voice_results: VoiceResult[];
  combined_wav: string;
  validation_report?: Record<string, unknown>;
}> {
  const form = new FormData();
  form.append("audio_zip", zipFile);

  const res = await fetch(
    `${API_BASE}/import-f5-audio?project_id=${encodeURIComponent(projectId)}`,
    { method: "POST", body: form }
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Import failed: ${res.status}`);
  }
  return res.json();
}

export async function getProject(projectId: string): Promise<Project> {
  return fetchApi<Project>(`/project/${projectId}`);
}

export function getMediaUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path.startsWith("/") ? path : `/media/projects/${path}`}`;
}

export function connectRenderProgress(
  jobId: string,
  onUpdate: (data: JobUpdate) => void,
  onError?: (err: Event) => void
): () => void {
  const ws = new WebSocket(`${WS_BASE}/ws/${jobId}`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type !== "ping") {
        onUpdate(data as JobUpdate);
      }
    } catch {
      // ignore parse errors
    }
  };

  ws.onerror = (e) => onError?.(e);

  return () => ws.close();
}

export interface F5StatusResponse {
  status: string;
  audio_ready: boolean;
  queued_at?: string;
  last_update?: string;
}

export async function getF5Status(projectId: string): Promise<F5StatusResponse> {
  return fetchApi<F5StatusResponse>(`/project/${encodeURIComponent(projectId)}/f5-status`);
}

// =============================================================================
// PHASE-4: SADTALKER AVATAR API
// =============================================================================

export interface AvatarResult {
  scene_id: number;
  clip_path: string;
  duration: number;
  provider: string;
}

export interface SadTalkerStatusResponse {
  status: string;
  clips_ready: boolean;
  queued_at?: string;
  last_update?: string;
}

/**
 * Upload a portrait photo to use as the talking-head source for SadTalker.
 * Stored as <project>/avatar/source.<ext>.
 */
export async function uploadAvatarSource(
  projectId: string,
  imageFile: File
): Promise<{ project_id: string; avatar_source: string; message: string }> {
  const form = new FormData();
  form.append("image", imageFile);

  const res = await fetch(
    `${API_BASE}/upload-avatar-source?project_id=${encodeURIComponent(projectId)}`,
    { method: "POST", body: form }
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Upload failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Trigger SadTalker avatar package export (calls /generate-avatar).
 * Returns export status message.
 */
export async function generateAvatar(
  projectId: string,
  avatarSource?: string
): Promise<{ project_id: string; avatar_provider: string; status: string; message: string }> {
  return fetchApi(`/generate-avatar`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, avatar_source: avatarSource }),
  });
}

/**
 * Download the SadTalker avatar package as a ZIP file.
 * The ZIP contains avatar_pack.json, source_image, and per-scene audio.
 */
export async function exportSadTalkerPackage(projectId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/export-sadtalker-package`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Export failed: ${res.status}`);
  }
  return res.blob();
}

/**
 * Upload a ZIP of SadTalker WebM clips and generate avatar_results.json.
 * The ZIP must contain files named scene_1.webm, scene_2.webm …
 */
export async function importSadTalkerClips(
  projectId: string,
  zipFile: File
): Promise<{
  avatar_generation_status: string;
  avatar_results: AvatarResult[];
  validation_report?: Record<string, unknown>;
}> {
  const form = new FormData();
  form.append("clips_zip", zipFile);

  const res = await fetch(
    `${API_BASE}/import-sadtalker-clips?project_id=${encodeURIComponent(projectId)}`,
    { method: "POST", body: form }
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Import failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Poll the SadTalker queue status (mirrors getF5Status).
 */
export async function getSadTalkerStatus(
  projectId: string
): Promise<SadTalkerStatusResponse> {
  return fetchApi<SadTalkerStatusResponse>(
    `/project/${encodeURIComponent(projectId)}/sadtalker-status`
  );
}

export interface PipelineStatusResponse {
  voice: {
    status: string;
    audio_ready: boolean;
    queued_at?: string;
  };
  avatar: {
    status: string;
    clips_ready: boolean;
    queued_at?: string;
  };
  render: {
    status: string;
    video_url?: string;
  };
}

/**
 * Poll the unified pipeline status for voice, avatar, and render (P8).
 */
export async function getPipelineStatus(
  projectId: string
): Promise<PipelineStatusResponse> {
  return fetchApi<PipelineStatusResponse>(
    `/project/${encodeURIComponent(projectId)}/pipeline-status`
  );
}

export { API_BASE };
