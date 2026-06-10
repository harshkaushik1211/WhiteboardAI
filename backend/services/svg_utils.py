"""SVG utilities: load library assets, arrows, labels (no primitive concept shapes)."""
import math
import re
import shutil
from pathlib import Path
from typing import Optional

from config import settings
from utils.file_manager import save_text
from utils.timing import MIN_TEXT_W, TEXT_FONT_BASE

STROKE = "#1a1a2e"
SW = "2.5"


def load_library_svg(relative_path: str) -> str:
    path = settings.assets_path / relative_path
    if path.exists():
        return path.read_text(encoding="utf-8")
    fallback = settings.assets_path / "icons" / "unknown-concept.svg"
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")
    return _minimal_placeholder()


def copy_asset_to_project(
    project_id: str,
    element_id: str,
    library_path: str,
    *,
    preserve_colors: bool = False,
) -> str:
    content = load_library_svg(library_path)
    if not preserve_colors:
        content = normalize_svg_stroke(content)
    filename = f"svgs/{element_id}.svg"
    save_text(project_id, filename, content)
    return filename


def is_diagram_svg_path(library_path: str) -> bool:
    return "photosynthesis-diagram" in library_path.replace("\\", "/")


def copy_image_to_project(project_id: str, element_id: str, library_path: str) -> str:
    src = settings.assets_path / library_path
    if not src.exists():
        raise FileNotFoundError(f"Image asset not found: {src}")
    ext = src.suffix.lower() or ".png"
    from utils.file_manager import project_dir

    dest_dir = project_dir(project_id) / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{element_id}{ext}"
    shutil.copy2(src, dest)
    return f"assets/{element_id}{ext}"


def normalize_svg_stroke(content: str) -> str:
    content = re.sub(r'fill="(?!none)[^"]*"', 'fill="none"', content)
    if 'stroke="' not in content:
        content = content.replace("<svg ", f'<svg stroke="{STROKE}" stroke-width="{SW}" ', 1)
    return content


def _minimal_placeholder() -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none" stroke="{STROKE}" stroke-width="{SW}">
  <circle cx="50" cy="50" r="35" data-path-length="220"/>
</svg>'''


def _rough_line(x1: float, y1: float, x2: float, y2: float, segments: int = 4) -> str:
    import random
    points = []
    for i in range(segments + 1):
        t = i / segments
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        if 0 < i < segments:
            x += random.uniform(-1.5, 1.5)
            y += random.uniform(-1.5, 1.5)
        points.append(f"{x:.1f},{y:.1f}")
    return "M " + " L ".join(points)


def generate_arrow_svg(
    x1: float, y1: float, x2: float, y2: float, label: Optional[str] = None
) -> str:
    w = abs(x2 - x1) + 80
    h = abs(y2 - y1) + 80
    ox = min(x1, x2) - 40
    oy = min(y1, y2) - 40
    lx1, ly1 = x1 - ox, y1 - oy
    lx2, ly2 = x2 - ox, y2 - oy
    angle = math.atan2(ly2 - ly1, lx2 - lx1)
    ax = lx2 - 18 * math.cos(angle - 0.4)
    ay = ly2 - 18 * math.sin(angle - 0.4)
    bx = lx2 - 18 * math.cos(angle + 0.4)
    by = ly2 - 18 * math.sin(angle + 0.4)
    line = _rough_line(lx1, ly1, lx2, ly2)
    head = f"M {lx2:.1f},{ly2:.1f} L {ax:.1f},{ay:.1f} M {lx2:.1f},{ly2:.1f} L {bx:.1f},{by:.1f}"
    label_svg = ""
    if label:
        mx, my = (lx1 + lx2) / 2, (ly1 + ly2) / 2 - 18
        label_svg = f'<text x="{mx:.0f}" y="{my:.0f}" text-anchor="middle" font-size="20" font-weight="600" fill="{STROKE}" stroke="none">{_escape(label)}</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" fill="none" stroke="{STROKE}" stroke-width="{SW}" stroke-linecap="round">
  <path d="{line}" data-path-length="200"/>
  <path d="{head}" data-path-length="50"/>
  {label_svg}
</svg>'''


def generate_text_svg(text: str, width: float = 500, height: float = 80) -> str:
    width = max(MIN_TEXT_W, width)
    font_size = max(TEXT_FONT_BASE, min(52, int(width / max(len(text), 6) * 1.4)))
    y = height * 0.65
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <text x="{width/2}" y="{y}" text-anchor="middle" font-size="{font_size}" font-family="Comic Sans MS, Segoe Print, cursive" font-weight="600" fill="{STROKE}">{_escape(text)}</text>
</svg>'''


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
