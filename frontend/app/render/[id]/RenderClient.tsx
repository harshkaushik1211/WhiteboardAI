"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ProgressTracker } from "@/components/ProgressTracker";
import { VideoPreview } from "@/components/VideoPreview";
import { connectRenderProgress, getProject, API_BASE } from "@/lib/api";
import type { JobUpdate } from "@/lib/types";

interface RenderClientProps {
  projectId: string;
  jobId: string;
}

export function RenderClient({ projectId, jobId }: RenderClientProps) {
  const [job, setJob] = useState<JobUpdate | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [title, setTitle] = useState("");

  useEffect(() => {
    if (!jobId) return;

    const cleanup = connectRenderProgress(jobId, (data) => {
      setJob(data);
      if (data.step === "complete") {
        getProject(projectId).then((p) => {
          setTitle(p.script?.title || p.topic);
          setVideoUrl(
            p.video_url
              ? `${API_BASE}${p.video_url}`
              : `${API_BASE}/media/projects/${projectId}/videos/final_video.mp4`
          );
        });
      }
    });

    return cleanup;
  }, [jobId, projectId]);

  useEffect(() => {
    getProject(projectId).then((p) => {
      setTitle(p.script?.title || p.topic);
    });
  }, [projectId]);

  return (
    <>
      <Link
        href={`/project/${projectId}`}
        className="inline-flex items-center gap-2 text-white/60 hover:text-white mb-8"
      >
        <ArrowLeft className="w-4 h-4" /> Back to project
      </Link>

      <h1 className="text-3xl font-bold mb-2">Rendering Video</h1>
      <p className="text-white/50 mb-8">{title || "Your educational video"}</p>

      {job ? (
        <div className="glass rounded-xl p-8 mb-8">
          <ProgressTracker
            currentStep={job.step}
            progress={job.progress}
            message={job.message}
          />
          {job.error && (
            <p className="mt-4 text-red-400 text-sm">{job.error}</p>
          )}
        </div>
      ) : (
        <div className="glass rounded-xl p-8 mb-8 text-center text-white/50">
          Connecting to render pipeline...
        </div>
      )}

      {videoUrl && job?.step === "complete" && (
        <VideoPreview videoUrl={videoUrl} title={title} />
      )}
    </>
  );
}
