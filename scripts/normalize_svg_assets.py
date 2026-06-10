#!/usr/bin/env python3
"""Normalize curated SVGs: outline-only, unified stroke, no raster."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "assets"
STROKE = "#1a1a2e"
SKIP_DIRS = {"index", "svg-templates"}


def normalize_svg(content: str) -> str:
    content = re.sub(r'fill="[^"]*"', 'fill="none"', content)
    content = re.sub(r"fill='[^']*'", "fill='none'", content)
    content = re.sub(r"<image[^>]*/>", "", content, flags=re.I)
    if "stroke=" not in content and "<text" not in content:
        content = content.replace("<svg ", f'<svg stroke="{STROKE}" stroke-width="2.5" ', 1)
    content = re.sub(r'stroke="[^"]*"', f'stroke="{STROKE}"', content)
    content = re.sub(r"stroke-width=\"[^\"]*\"", 'stroke-width="2.5"', content)
    return content


def main():
    count = 0
    for svg_path in ROOT.rglob("*.svg"):
        if any(p in svg_path.parts for p in SKIP_DIRS):
            continue
        text = svg_path.read_text(encoding="utf-8")
        normalized = normalize_svg(text)
        if normalized != text:
            svg_path.write_text(normalized, encoding="utf-8")
            count += 1
    print(f"Normalized {count} files")


if __name__ == "__main__":
    main()
