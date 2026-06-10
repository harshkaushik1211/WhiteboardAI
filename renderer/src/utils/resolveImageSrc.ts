import { staticFile } from "remotion";

/**
 * Remotion can only load images from public/ via staticFile(), data URLs, or http(s).
 * Backend stages project PNGs under public/render-assets/{projectId}/.
 */
export function resolveImageSrc(src: string): string {
  if (
    src.startsWith("data:") ||
    src.startsWith("http://") ||
    src.startsWith("https://")
  ) {
    return src;
  }

  const marker = "render-assets/";
  const idx = src.indexOf(marker);
  if (idx >= 0) {
    return staticFile(src.slice(idx));
  }

  if (src.startsWith("/") || src.includes("://")) {
    const name = src.split("/").pop();
    if (name) {
      return staticFile(`render-assets/${name}`);
    }
  }

  return staticFile(src.replace(/^\/+/, ""));
}
