"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Play, Image, Mic, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SceneCard } from "@/components/SceneCard";
import { TimelineView } from "@/components/TimelineView";
import {
  getProject,
  generateScenes,
  generateVoice,
  renderVideo,
  API_BASE,
} from "@/lib/api";
import type { VoiceResult } from "@/lib/api";
import type { Project } from "@/lib/types";
import { F5VoicePanel } from "@/components/F5VoicePanel";
import { AvatarPanel } from "@/components/AvatarPanel";
import type { AvatarResult } from "@/components/AvatarPanel";

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [stepLoading, setStepLoading] = useState("");

  // Derived voice provider state
  const isF5Mode =
    (project?.config?.voice_provider as string | undefined) === "f5tts";
  const f5AudioReady = project?.voice_generation_status === "completed";

  // Derived avatar provider state
  const isSadTalkerMode =
    (project?.config?.avatar_provider as string | undefined) === "sadtalker";
  const sadTalkerClipsReady = project?.avatar_generation_status === "completed";
  const sadTalkerFailed = project?.avatar_generation_status === "failed";
  const avatarPending = isSadTalkerMode && !sadTalkerClipsReady && !sadTalkerFailed;

  // Render is blocked until all required assets (voice + avatar pending) are ready.
  // P7: Avatar failure is non-blocking (graceful fallback).
  const renderBlocked = (isF5Mode && !f5AudioReady) || avatarPending;

  const refresh = async () => {
    const p = await getProject(projectId);
    setProject(p);
  };

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [projectId]);

  const runStep = async (
    name: string,
    fn: () => Promise<unknown>
  ) => {
    setStepLoading(name);
    try {
      await fn();
      await refresh();
    } finally {
      setStepLoading("");
    }
  };

  const handleRender = async () => {
    const { job_id } = await renderVideo(projectId);
    router.push(`/render/${projectId}?job=${job_id}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-white/50">Loading project...</div>
      </div>
    );
  }

  if (!project?.script) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p>Project not found</p>
      </div>
    );
  }

  const { script } = project;

  return (
    <main className="min-h-screen bg-slate-900">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-white/60 hover:text-white mb-8"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold">{script.title}</h1>
            <p className="text-white/50 mt-1">Topic: {project.topic}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={!!stepLoading}
              onClick={() =>
                runStep("scenes", () => generateScenes(projectId))
              }
            >
              <Image className="w-4 h-4 mr-1" />
              {stepLoading === "scenes" ? "..." : "Images"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!!stepLoading}
              onClick={() => runStep("voice", () => generateVoice(projectId))}
            >
              <Mic className="w-4 h-4 mr-1" />
              {stepLoading === "voice" ? "..." : isF5Mode ? "Export Narration" : "Voice"}
            </Button>
            <Button
              size="sm"
              onClick={handleRender}
              disabled={renderBlocked}
              title={
                renderBlocked
                  ? "Import F5-TTS audio first using the panel below"
                  : undefined
              }
            >
              <Play className="w-4 h-4 mr-1" /> Render Video
            </Button>
          </div>
        </div>

        <Card className="mb-8">
          <TimelineView scenes={script.scenes} totalDuration={script.total_duration} />
        </Card>

        {project.ai_image_audit && project.ai_image_audit.length > 0 && (
          <Card className="mb-8">
            <h3 className="font-semibold mb-4">AI whiteboard images (PNG)</h3>
            <p className="text-sm text-white/50 mb-4">
              Model: {project.ai_image_audit[0]?.model}
              {project.ai_image_audit[0]?.stroke_mode
                ? ` — ${project.ai_image_audit[0].stroke_mode}`
                : ""}
              {project.ai_image_audit[0]?.segmentation_backend
                ? ` (${project.ai_image_audit[0].segmentation_backend})`
                : ""}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {project.ai_image_audit.map((entry) => (
                <div
                  key={entry.scene_id}
                  className="rounded-lg border border-white/10 p-4 bg-white/5"
                >
                  <p className="font-medium text-brand-300 mb-2">
                    Scene {entry.scene_id}: {entry.headline}
                  </p>
                  {entry.object_labels && entry.object_labels.length > 0 && (
                    <p className="text-xs text-white/40 mb-2">
                      Objects: {entry.object_labels.join(", ")}
                      {entry.path_count != null ? ` · ${entry.path_count} paths` : ""}
                    </p>
                  )}
                  <img
                    src={`${API_BASE}/media/projects/${projectId}/${entry.image_path}`}
                    alt={entry.headline}
                    className="w-full rounded bg-white"
                  />
                </div>
              ))}
            </div>
          </Card>
        )}

        {project.voice_files && project.voice_files.length > 0 && (
          <Card className="mb-8">
            <h3 className="font-semibold mb-4">Audio Preview</h3>
            <div className="space-y-2">
              {project.voice_files.map((vf) => (
                <audio
                  key={vf}
                  controls
                  src={`${API_BASE}/media/projects/${projectId}/${vf}`}
                  className="w-full"
                />
              ))}
            </div>
          </Card>
        )}

        {/* F5-TTS workflow panel — shown when project uses F5 voice provider */}
        {isF5Mode && (
          <div className="mb-8">
            <F5VoicePanel
              projectId={projectId}
              voiceStatus={project.voice_generation_status}
              packageExported={project.f5_package_exported}
              audioImportedAt={project.audio_imported_at}
              onImportComplete={(_results: VoiceResult[]) => {
                refresh();
              }}
            />
          </div>
        )}

        {/* SadTalker Avatar panel — shown when project uses sadtalker avatar provider */}
        {isSadTalkerMode && (
          <div className="mb-8">
            <AvatarPanel
              projectId={projectId}
              avatarStatus={project.avatar_generation_status}
              packageExported={project.sadtalker_package_exported}
              avatarImportedAt={project.avatar_imported_at}
              onImportComplete={(_results: AvatarResult[]) => {
                refresh();
              }}
            />
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {script.scenes.map((scene, i) => (
            <SceneCard
              key={scene.scene_id}
              scene={scene}
              plan={project.scene_plans?.find((p) => p.scene_id === scene.scene_id)}
              projectId={projectId}
              index={i}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
