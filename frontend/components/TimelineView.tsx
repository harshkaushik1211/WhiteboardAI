"use client";

import type { Scene } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TimelineViewProps {
  scenes: Scene[];
  totalDuration: number;
}

export function TimelineView({ scenes, totalDuration }: TimelineViewProps) {
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-white/70">Timeline</h4>
      <div className="flex h-12 rounded-lg overflow-hidden border border-white/10">
        {scenes.map((scene, i) => {
          const width = (scene.duration / totalDuration) * 100;
          const colors = [
            "bg-brand-600",
            "bg-purple-600",
            "bg-emerald-600",
            "bg-amber-600",
            "bg-rose-600",
            "bg-cyan-600",
          ];
          return (
            <div
              key={scene.scene_id}
              className={cn(
                "flex items-center justify-center text-xs font-medium text-white/90 border-r border-white/10 last:border-0",
                colors[i % colors.length]
              )}
              style={{ width: `${width}%` }}
              title={scene.narration}
            >
              {i + 1}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-xs text-white/40">
        <span>0s</span>
        <span>{totalDuration}s</span>
      </div>
    </div>
  );
}
