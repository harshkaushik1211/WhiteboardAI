import React from "react";
import { useCurrentFrame } from "remotion";
import type { RenderElement } from "../types/manifest";
import { SVGAnimator } from "./SVGAnimator";
import { DiagramImage } from "./DiagramImage";
import { ContourStrokeReveal } from "./ContourStrokeReveal";
import { ObjectWiseSketchReveal } from "./ObjectWiseSketchReveal";
import { SketchWipeReveal } from "./SketchWipeReveal";

interface WhiteboardCanvasProps {
  elements: RenderElement[];
  sceneStartFrame: number;
}

function getMotionStyle(
  el: RenderElement,
  frame: number,
  elements: RenderElement[]
): React.CSSProperties {
  const startFrame = el.start_frame;
  const endFrame = el.end_frame;
  const profile = el.motion_profile;

  const defaultStyle: React.CSSProperties = {
    transition: "none",
  };

  if (!profile || profile === "stroke_reveal") {
    return defaultStyle;
  }

  const f = frame; // local frame relative to scene (Remotion sequence resets frame to 0 at sequence start)
  const d = endFrame - startFrame;
  const t = Math.max(0, Math.min(1, (f - startFrame) / (d || 1)));

  let dx = 0;
  let dy = 0;
  let rotation = 0;
  let opacity = 1;

  if (profile === "translate") {
    dx = 350 * t;
  } else if (profile === "translate_accelerate") {
    // Starts slow, ends fast
    dx = 400 * t * t * t;
  } else if (profile === "translate_decelerate") {
    // Starts fast, ends slow
    dx = 350 * (1 - Math.pow(1 - t, 3));
  } else if (profile === "roll_motion") {
    // Translate and rotate
    dx = 450 * t;
    rotation = t * 360;
  } else if (profile === "force_push") {
    // Arrow advances/pushes: 0% - 40% draws; 40% - 70% advances; 70% - 100% pushes forward
    if (t < 0.4) {
      dx = 0;
    } else if (t < 0.7) {
      const p = (t - 0.4) / 0.3;
      dx = 150 * p;
    } else {
      const p = (t - 0.7) / 0.3;
      dx = 150 + 200 * p;
    }
  } else if (profile === "constraint_hold") {
    // Moves -> constraint stops motion
    // 0% - 60% moves; 60% - 80% hard stop with bounce; 80% - 100% stopped
    if (t < 0.6) {
      dx = 400 * (t / 0.6);
    } else if (t < 0.8) {
      const p = (t - 0.6) / 0.2;
      dx = 400 - 30 * Math.sin(p * Math.PI);
    } else {
      dx = 370;
    }
  } else if (profile === "particle_flow") {
    // Continuous looping flow
    if (f >= startFrame) {
      dx = ((f - startFrame) * 4) % 300;
    }
  }

  // Check if this element is being pushed by another force_push element (Component 5 choreography)
  const pusher = elements.find(
    (other) => other.motion_profile === "force_push" && other.target_id === el.id
  );
  if (pusher) {
    const pf = f;
    const pd = pusher.end_frame - pusher.start_frame;
    const pt = Math.max(0, Math.min(1, (pf - pusher.start_frame) / (pd || 1)));
    if (pt >= 0.7) {
      const p = (pt - 0.7) / 0.3;
      dx = 200 * p;
    } else {
      dx = 0;
    }
  }

  const transformParts = [];
  if (dx !== 0 || dy !== 0) {
    transformParts.push(`translate(${dx}px, ${dy}px)`);
  }
  if (rotation !== 0) {
    transformParts.push(`rotate(${rotation}deg)`);
  }

  return {
    ...defaultStyle,
    transform: transformParts.length ? transformParts.join(" ") : undefined,
    opacity,
  };
}

export const WhiteboardCanvas: React.FC<WhiteboardCanvasProps> = ({
  elements,
  sceneStartFrame,
}) => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        position: "relative",
        width: 1920,
        height: 1080,
        backgroundColor: "#ffffff",
        overflow: "hidden",
      }}
    >
      {/* Subtle grid */}
      <svg
        width={1920}
        height={1080}
        style={{ position: "absolute", opacity: 0.03 }}
      >
        {Array.from({ length: 20 }).map((_, i) => (
          <line
            key={`v${i}`}
            x1={i * 96}
            y1={0}
            x2={i * 96}
            y2={1080}
            stroke="#000"
            strokeWidth={1}
          />
        ))}
        {Array.from({ length: 12 }).map((_, i) => (
          <line
            key={`h${i}`}
            x1={0}
            y1={i * 90}
            x2={1920}
            y2={i * 90}
            stroke="#000"
            strokeWidth={1}
          />
        ))}
      </svg>

      {elements.map((el) => {
        const fromPt = el.from ?? el.from_point;
        const toPt = el.to ?? el.to_point;
        const w = el.size?.w ?? 380;
        const h = el.size?.h ?? 320;
        const svgContent = el.svg_content || getPlaceholderSvg(el);

        let left: number;
        let top: number;
        if (el.type === "arrow" && fromPt && toPt) {
          left = Math.min(fromPt.x, toPt.x) - 30;
          top = Math.min(fromPt.y, toPt.y) - 30;
        } else {
          const cx = el.position?.x ?? (fromPt?.x ?? 960);
          const cy = el.position?.y ?? (fromPt?.y ?? 540);
          left = cx - w / 2;
          top = cy - h / 2;
        }

        const motionStyle = getMotionStyle(el, frame, elements);

        const renderChild = () => {
          if (el.type === "image" && el.image_src) {
            if (
              el.animation === "sketch_reveal" ||
              (el.id && el.id.endsWith("-sketch"))
            ) {
              if (el.stroke_data?.stroke_mode === "svg_contour") {
                return (
                  <ContourStrokeReveal
                    key={el.id}
                    src={el.image_src}
                    inkSrc={el.ink_image_src}
                    strokeData={el.stroke_data}
                    startFrame={el.start_frame}
                    endFrame={el.end_frame}
                    x={0}
                    y={0}
                    width={w}
                    height={h}
                    color={el.color}
                  />
                );
              }
              if (el.stroke_data?.cells?.length) {
                return (
                  <ObjectWiseSketchReveal
                    key={el.id}
                    src={el.image_src}
                    inkSrc={el.ink_image_src}
                    strokeData={el.stroke_data}
                    startFrame={el.start_frame}
                    endFrame={el.end_frame}
                    x={0}
                    y={0}
                    width={w}
                    height={h}
                  />
                );
              }
              return (
                <SketchWipeReveal
                  key={el.id}
                  src={el.image_src}
                  startFrame={el.start_frame}
                  endFrame={el.end_frame}
                  x={0}
                  y={0}
                  width={w}
                  height={h}
                />
              );
            }
            return (
              <DiagramImage
                key={el.id}
                src={el.image_src}
                x={0}
                y={0}
                width={w}
                height={h}
              />
            );
          }

          return (
            <SVGAnimator
              key={el.id}
              svgContent={svgContent}
              startFrame={el.start_frame}
              endFrame={el.end_frame}
              animation={el.animation}
              elementType={el.type}
              x={0}
              y={0}
              width={w}
              height={h}
              color={el.color}
              elementId={el.id}
            />
          );
        };

        return (
          <div
            key={el.id}
            style={{
              position: "absolute",
              left: left,
              top: top,
              width: w,
              height: h,
              ...motionStyle,
            }}
          >
            {renderChild()}
          </div>
        );
      })}
    </div>
  );
};

function getPlaceholderSvg(el: RenderElement): string {
  const text = el.text || el.label || el.shape || "•";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
    <circle cx="100" cy="100" r="60" fill="none" stroke="#1a1a2e" stroke-width="2.5" data-path-length="380"/>
    <text x="100" y="110" text-anchor="middle" font-size="20" fill="#1a1a2e">${text}</text>
  </svg>`;
}
