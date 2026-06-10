"use client";

import { Card } from "./ui/card";
import type { Scene, ScenePlan } from "@/lib/types";
import { API_BASE } from "@/lib/api";

interface SceneCardProps {
  scene: Scene;
  plan?: ScenePlan;
  projectId: string;
  index: number;
}

export function SceneCard({ scene, plan, projectId, index }: SceneCardProps) {
  const firstSvg = plan?.elements?.[0]?.svg_path;
  const svgUrl = firstSvg
    ? `${API_BASE}/media/projects/${projectId}/${firstSvg}`
    : null;

  return (
    <Card className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs text-brand-400 font-mono">Scene {index + 1}</span>
          <h3 className="text-lg font-semibold mt-1">
            {plan?.elements?.find((e) => e.concept)?.concept ||
              scene.keywords?.[0] ||
              `Scene ${scene.scene_id}`}
          </h3>
        </div>
        <span className="px-2 py-1 text-xs rounded bg-white/10">
          {scene.duration}s
        </span>
      </div>

      {svgUrl && (
        <div className="bg-white rounded-lg p-4 h-40 flex items-center justify-center overflow-hidden">
          <img
            src={svgUrl}
            alt={`Scene ${scene.scene_id} preview`}
            className="max-h-full max-w-full object-contain"
          />
        </div>
      )}

      <p className="text-sm text-white/70 line-clamp-3">{scene.narration}</p>

      {scene.keywords.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {scene.keywords.map((kw) => (
            <span
              key={kw}
              className="px-2 py-0.5 text-xs rounded-full bg-brand-600/20 text-brand-300"
            >
              {kw}
            </span>
          ))}
        </div>
      )}

      {plan && (
        <p className="text-xs text-white/40">
          {plan.elements.length} visual elements
        </p>
      )}
    </Card>
  );
}
