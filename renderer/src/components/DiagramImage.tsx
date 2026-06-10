import React from "react";
import { Img } from "remotion";
import { resolveImageSrc } from "../utils/resolveImageSrc";

interface DiagramImageProps {
  src: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export const DiagramImage: React.FC<DiagramImageProps> = ({
  src,
  x,
  y,
  width,
  height,
}) => {
  return (
    <Img
      src={resolveImageSrc(src)}
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        height,
        objectFit: "contain",
      }}
    />
  );
};
