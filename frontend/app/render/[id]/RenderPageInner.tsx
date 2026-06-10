"use client";

import { useParams, useSearchParams } from "next/navigation";
import { RenderClient } from "./RenderClient";

export function RenderPageInner() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const jobId = searchParams.get("job") || "";

  return <RenderClient projectId={projectId} jobId={jobId} />;
}
