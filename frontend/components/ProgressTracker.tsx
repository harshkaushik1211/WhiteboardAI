"use client";

import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const STEPS = [
  { id: "script", label: "Script" },
  { id: "scenes", label: "Scenes" },
  { id: "svg", label: "SVG Assets" },
  { id: "voice", label: "Voice" },
  { id: "timeline", label: "Timeline" },
  { id: "render", label: "Render" },
  { id: "complete", label: "Complete" },
];

interface ProgressTrackerProps {
  currentStep: string;
  progress: number;
  message?: string;
}

export function ProgressTracker({
  currentStep,
  progress,
  message,
}: ProgressTrackerProps) {
  const currentIndex = STEPS.findIndex((s) => s.id === currentStep);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between text-sm">
        <span className="text-white/70">{message || "Processing..."}</span>
        <span className="font-mono text-brand-400">{Math.round(progress)}%</span>
      </div>
      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-brand-600 to-brand-400 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        {STEPS.map((step, i) => {
          const done = i < currentIndex || currentStep === "complete";
          const active = step.id === currentStep;
          return (
            <div
              key={step.id}
              className={cn(
                "flex flex-col items-center gap-2 p-3 rounded-lg text-center text-xs",
                active && "bg-brand-600/20 border border-brand-500/30",
                done && !active && "opacity-60"
              )}
            >
              {done ? (
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              ) : active ? (
                <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />
              ) : (
                <Circle className="w-5 h-5 text-white/30" />
              )}
              <span>{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
