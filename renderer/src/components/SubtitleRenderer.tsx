import React from "react";
import { useCurrentFrame } from "remotion";
import type { SubtitleEntry } from "../types/manifest";

interface SubtitleRendererProps {
  subtitles: SubtitleEntry[];
  globalStartFrame: number;
}

export const SubtitleRenderer: React.FC<SubtitleRendererProps> = ({
  subtitles,
  globalStartFrame: _globalStartFrame,
}) => {
  const frame = useCurrentFrame();

  const active = subtitles.find(
    (s) =>
      frame >= s.start_frame &&
      frame < s.end_frame
  );

  if (!active) return null;

  const isHighlight = active.highlight_words?.some((w) =>
    active.text.toLowerCase().includes(w.toLowerCase())
  );

  return (
    <div
      style={{
        position: "absolute",
        bottom: 80,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        padding: "0 60px",
        zIndex: 100,
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(0,0,0,0.75)",
          color: "#fff",
          padding: "16px 32px",
          borderRadius: 12,
          fontSize: 28,
          fontFamily: "Comic Sans MS, cursive, sans-serif",
          fontWeight: 600,
          textAlign: "center",
          maxWidth: "80%",
          boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
          borderBottom: isHighlight ? "4px solid #ffeb3b" : "none",
        }}
      >
        {active.text}
      </div>
    </div>
  );
};
