/**
 * AvatarOverlay
 *
 * Renders a transparent talking-head avatar clip as a picture-in-picture
 * overlay on the whiteboard canvas.
 *
 * The clip is positioned at one of three preset anchors:
 *   - bottom_right  (default) — lower-right corner with a small margin
 *   - bottom_left            — lower-left corner with a small margin
 *   - bottom_center          — centred horizontally at the bottom
 *
 * Scale is expressed as a fraction of the video HEIGHT (0.0–1.0).
 * For example, scale=0.25 means the avatar will be 25% of the video height
 * tall, and width is derived from the clip's natural aspect ratio.
 *
 * The clip MUST be a transparent WebM (VP9/alpha) produced by SadTalker or
 * an equivalent talking-head pipeline.  It is loaded via Remotion's
 * `staticFile()` helper so it benefits from Remotion's media caching.
 *
 * IMPORTANT: This component is fully optional.  When `clipSrc` is undefined
 * or empty the component renders nothing, ensuring that existing whiteboard-
 * only renders are completely unaffected.
 */

import React from "react";
import {
  AbsoluteFill,
  Video,
  useVideoConfig,
  staticFile,
  useCurrentFrame,
} from "remotion";

import { avatarLayoutRegistry } from "./AvatarLayoutRegistry";

// ── Types ────────────────────────────────────────────────────────────────────

export type AvatarPosition = "bottom_right" | "bottom_left" | "bottom_center";
export type AvatarLayout = "pip" | "teacher_mode" | "split_screen" | "full_avatar";

export interface AvatarOverlayProps {
  /** Remotion staticFile() compatible path to the transparent WebM clip. */
  clipSrc?: string;
  /**
   * Anchor corner / alignment for the PiP window.
   * @default "bottom_right"
   */
  position?: AvatarPosition;
  /**
   * Clip height as a fraction of the video height (0.0–1.0).
   * @default 0.25
   */
  scale?: number;
  /**
   * Optional fade-in duration in frames (applied at the start of this scene).
   * @default 12
   */
  fadeInFrames?: number;
  /**
   * P1: Start frame offset into the combined avatar video.
   * @default 0
   */
  startFrom?: number;
  /**
   * P10: Layout style for the avatar overlay.
   * @default "pip"
   */
  layout?: AvatarLayout;
}

// ── Constants ────────────────────────────────────────────────────────────────

const MARGIN_PX = 24; // outer margin from video edge in pixels
const BORDER_RADIUS = 12; // cosmetic corner rounding
const BOX_SHADOW = "0 4px 32px rgba(0,0,0,0.35)"; // subtle drop shadow

// ── Component ────────────────────────────────────────────────────────────────

export const AvatarOverlay: React.FC<AvatarOverlayProps> = ({
  clipSrc,
  position = "bottom_right",
  scale = 0.25,
  fadeInFrames = 12,
  startFrom = 0,
  layout = "pip",
}) => {
  const { width, height } = useVideoConfig();
  const frame = useCurrentFrame();

  // Render nothing if no clip source is provided — backward compatible.
  if (!clipSrc) return null;

  // ── Layout Styling (P10 Layout Abstraction) ──
  const layoutStyle = avatarLayoutRegistry.resolve(layout, {
    width,
    height,
    frame,
    fadeInFrames,
    scale,
    position,
    marginPx: MARGIN_PX,
    borderRadius: BORDER_RADIUS,
    boxShadow: BOX_SHADOW,
  });

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <Video
        src={staticFile(clipSrc)}
        style={layoutStyle}
        // Mute the clip — audio comes from the separately mixed voice track.
        muted
        // P1: Start from the calculated offset in the combined avatar video.
        startFrom={startFrom}
      />
    </AbsoluteFill>
  );
};
