import React from "react";

export interface LayoutStyleProps {
  width: number;
  height: number;
  frame: number;
  fadeInFrames: number;
  scale: number;
  position: "bottom_right" | "bottom_left" | "bottom_center";
  marginPx: number;
  borderRadius: number;
  boxShadow: string;
}

export type LayoutStyleResolver = (props: LayoutStyleProps) => React.CSSProperties;

/**
 * Registry of display layouts for transparent head avatars.
 *
 * Refinement J: Layout selector is isolated, permitting future additions
 * (e.g. customized overlays, virtual background splits) without altering
 * renderer core code.
 */
class AvatarLayoutRegistry {
  private resolvers: Map<string, LayoutStyleResolver> = new Map();

  constructor() {
    // Register default layouts
    this.register("pip", (props) => {
      const clipHeight = Math.round(props.height * Math.min(1, Math.max(0, props.scale)));
      const baseStyle: React.CSSProperties = {
        position: "absolute",
        bottom: props.marginPx,
        height: clipHeight,
        width: "auto",
        borderRadius: props.borderRadius,
        boxShadow: props.boxShadow,
        overflow: "hidden",
        opacity: Math.min(1, props.frame / Math.max(1, props.fadeInFrames)),
        background: "transparent",
      };

      let positionStyle: React.CSSProperties = {};
      switch (props.position) {
        case "bottom_left":
          positionStyle = { left: props.marginPx };
          break;
        case "bottom_center":
          positionStyle = {
            left: "50%",
            transform: "translateX(-50%)",
          };
          break;
        case "bottom_right":
        default:
          positionStyle = { right: props.marginPx };
          break;
      }
      return { ...baseStyle, ...positionStyle };
    });

    this.register("teacher_mode", (props) => {
      const teacherHeight = Math.round(props.height * 0.5);
      return {
        position: "absolute",
        bottom: 0,
        left: "50%",
        transform: "translateX(-50%)",
        height: teacherHeight,
        width: "auto",
        boxShadow: props.boxShadow,
        borderRadius: `${props.borderRadius}px ${props.borderRadius}px 0 0`,
        opacity: Math.min(1, props.frame / Math.max(1, props.fadeInFrames)),
        background: "transparent",
      };
    });

    this.register("split_screen", (props) => {
      return {
        position: "absolute",
        top: 0,
        right: 0,
        width: "50%",
        height: "100%",
        opacity: Math.min(1, props.frame / Math.max(1, props.fadeInFrames)),
        background: "transparent",
        objectFit: "cover",
      };
    });

    this.register("full_avatar", (props) => {
      return {
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        opacity: Math.min(1, props.frame / Math.max(1, props.fadeInFrames)),
        background: "transparent",
        objectFit: "cover",
      };
    });
  }

  public register(name: string, resolver: LayoutStyleResolver) {
    this.resolvers.set(name.toLowerCase(), resolver);
  }

  public resolve(name: string, props: LayoutStyleProps): React.CSSProperties {
    const resolver = this.resolvers.get(name.toLowerCase()) || this.resolvers.get("pip");
    if (!resolver) return {};
    return resolver(props);
  }
}

export const avatarLayoutRegistry = new AvatarLayoutRegistry();
