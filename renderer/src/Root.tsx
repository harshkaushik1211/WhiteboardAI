import React from "react";
import { Composition } from "remotion";
import { WhiteboardVideo } from "./compositions/WhiteboardVideo";
import type { RenderManifest } from "./types/manifest";

const defaultManifest: RenderManifest = {
  title: "Sample Educational Video",
  fps: 30,
  width: 1920,
  height: 1080,
  total_frames: 300,
  scenes: [
    {
      scene_id: 1,
      start_frame: 0,
      duration_frames: 150,
      narration: "Welcome to this lesson.",
      subtitles: [
        { text: "Welcome", start_frame: 0, end_frame: 60 },
        { text: "to this lesson", start_frame: 60, end_frame: 150 },
      ],
      elements: [
        {
          id: "bulb-1",
          type: "svg_shape",
          shape: "lightbulb",
          position: { x: 960, y: 400 },
          size: { w: 200, h: 200 },
          animation: "stroke_reveal",
          start_frame: 15,
          end_frame: 90,
          svg_content: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><path d="M100,30 Q60,30 60,80 Q60,120 80,130 L80,150 L120,150 L120,130 Q140,120 140,80 Q140,30 100,30" fill="none" stroke="#1a1a2e" stroke-width="2.5"/></svg>`,
        },
      ],
      camera: { zoom: 1.05, focusX: 960, focusY: 400 },
    },
    {
      scene_id: 2,
      start_frame: 150,
      duration_frames: 150,
      narration: "Let's explore the concept.",
      subtitles: [
        { text: "Let's explore", start_frame: 0, end_frame: 70 },
        { text: "the concept", start_frame: 70, end_frame: 150 },
      ],
      elements: [
        {
          id: "arrow-1",
          type: "arrow",
          animation: "stroke_reveal",
          start_frame: 15,
          end_frame: 90,
          position: { x: 600, y: 500 },
          svg_content: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60"><path d="M10,30 L160,30 M130,10 L160,30 L130,50" fill="none" stroke="#1a1a2e" stroke-width="2.5"/></svg>`,
        },
      ],
    },
  ],
};

export interface VideoProps {
  manifest?: RenderManifest;
}

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="WhiteboardVideo"
        component={WhiteboardVideo}
        durationInFrames={defaultManifest.total_frames}
        fps={defaultManifest.fps}
        width={defaultManifest.width}
        height={defaultManifest.height}
        defaultProps={{ manifest: defaultManifest }}
        calculateMetadata={async ({ props }) => {
          const m = (props as VideoProps).manifest || defaultManifest;
          return {
            durationInFrames: m.total_frames,
            fps: m.fps,
            width: m.width,
            height: m.height,
            props: { manifest: m },
          };
        }}
      />
    </>
  );
};
