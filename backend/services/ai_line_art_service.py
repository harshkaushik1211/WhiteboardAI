"""Generate per-scene hand-drawn SVG line art via OpenAI text models."""
import math
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from config import settings
from prompts.line_art_prompt import (
    LINE_ART_SYSTEM,
    MAX_LAYERS,
    MIN_LAYERS,
    build_line_art_prompt,
)
from services.llm_service import llm_service

MAX_PATHS_PER_LAYER = 25
STROKE = "#1a1a2e"
SW = "2.5"
DRAWABLE_TAG = re.compile(
    r"<(path|circle|rect|ellipse|line|polyline|polygon)\b[^>]*>",
    re.IGNORECASE,
)


@dataclass
class SceneLayerArt:
    layer_index: int
    label: str
    svg_markup: str
    path_count: int


def count_drawable_paths(svg: str) -> int:
    return len(DRAWABLE_TAG.findall(svg))


def _estimate_path_length_from_d(d: str) -> float:
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", d)]
    if len(nums) < 4:
        return 200.0
    total = 0.0
    for i in range(2, len(nums), 2):
        if i + 1 < len(nums):
            total += math.hypot(nums[i] - nums[i - 2], nums[i + 1] - nums[i - 1])
    return max(80.0, min(8000.0, total * 1.15))


def _path_length_for_tag(tag: str) -> float:
    existing = re.search(r'data-path-length="([\d.]+)"', tag, re.I)
    if existing:
        return max(40.0, float(existing.group(1)) * 1.08)

    tag_l = tag.lower()
    if "circle" in tag_l:
        r = re.search(r'\br="([\d.]+)"', tag, re.I)
        if r:
            return max(80.0, 2 * math.pi * float(r.group(1)) * 1.08)
    if "line" in tag_l:
        coords = re.findall(r'-?\d+\.?\d*', tag)
        if len(coords) >= 4:
            x1, y1, x2, y2 = (float(coords[i]) for i in range(4))
            return max(40.0, math.hypot(x2 - x1, y2 - y1) * 1.08)
    if "rect" in tag_l:
        w = re.search(r'\bwidth="([\d.]+)"', tag, re.I)
        h = re.search(r'\bheight="([\d.]+)"', tag, re.I)
        if w and h:
            return max(80.0, 2 * (float(w.group(1)) + float(h.group(1))) * 1.08)
    if "ellipse" in tag_l:
        rx = re.search(r'\brx="([\d.]+)"', tag, re.I)
        ry = re.search(r'\bry="([\d.]+)"', tag, re.I)
        if rx and ry:
            a, b = float(rx.group(1)), float(ry.group(1))
            return max(80.0, math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b))) * 1.08)
    d = re.search(r'\sd="([^"]*)"', tag, re.I)
    if d:
        return _estimate_path_length_from_d(d.group(1))
    return 400.0


def _inject_path_lengths(content: str) -> str:
    def _repl(match: re.Match) -> str:
        tag = match.group(0)
        if re.search(r'data-path-length="', tag, re.I):
            length = _path_length_for_tag(tag)
            return re.sub(
                r'data-path-length="[\d.]+"',
                f'data-path-length="{length:.1f}"',
                tag,
                count=1,
                flags=re.I,
            )
        length = _path_length_for_tag(tag)
        if tag.rstrip().endswith("/>"):
            return tag.rstrip()[:-2] + f' data-path-length="{length:.1f}"/>'
        if tag.rstrip().endswith(">"):
            return tag.rstrip()[:-1] + f' data-path-length="{length:.1f}">'
        return tag

    return DRAWABLE_TAG.sub(_repl, content)


def _repair_malformed_tags(content: str) -> str:
    """Fix common LLM mistakes like '<circle ..."/ fill="none">'."""
    content = re.sub(
        r'data-path-length="([\d.]+)"\s*/\s*fill="none"\s*>',
        r'data-path-length="\1"/>',
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"(<(?:path|circle|rect|ellipse|line|polyline|polygon)\b[^>]*?)/\s*fill=\"none\"\s*>",
        r"\1/>",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"(<(?:path|circle|rect|ellipse|line|polyline|polygon)\b[^>]*?)/\s+([^>]+)>",
        r"\1 \2/>",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(r">\s*fill=\"none\"\s*>", "/>", content, flags=re.IGNORECASE)
    return content


def sanitize_scene_svg(svg_markup: str) -> str:
    """Normalize LLM SVG for stroke-reveal rendering."""
    content = (svg_markup or "").strip()
    content = re.sub(r"<script[\s\S]*?</script>", "", content, flags=re.IGNORECASE)
    content = re.sub(r"on\w+\s*=\s*\"[^\"]*\"", "", content, flags=re.IGNORECASE)
    content = _repair_malformed_tags(content)

    if not content.lower().startswith("<svg"):
        content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" '
            f'fill="none" stroke="{STROKE}" stroke-width="{SW}">{content}</svg>'
        )

    if "viewBox" not in content[:400]:
        content = content.replace("<svg ", '<svg viewBox="0 0 1920 1080" ', 1)

    if 'xmlns="http://www.w3.org/2000/svg"' not in content:
        content = content.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)

    def _fix_fill(tag: str) -> str:
        if re.search(r'fill="', tag, re.I):
            return re.sub(r'fill="[^"]*"', 'fill="none"', tag, flags=re.I)
        stripped = tag.rstrip()
        if stripped.endswith("/>"):
            return stripped[:-2] + ' fill="none"/>'
        return tag.replace(">", ' fill="none">', 1)

    content = DRAWABLE_TAG.sub(lambda m: _fix_fill(m.group(0)), content)
    content = _inject_path_lengths(content)
    content = _repair_malformed_tags(content)

    if f'stroke="{STROKE}"' not in content[:500] and "stroke=" not in content[:500]:
        content = content.replace("<svg ", f'<svg stroke="{STROKE}" stroke-width="{SW}" ', 1)

    return content


def _parse_layers_from_response(data: dict, scene_id: int) -> List[SceneLayerArt]:
    layers_raw = data.get("layers")
    if isinstance(layers_raw, list) and len(layers_raw) >= MIN_LAYERS:
        parsed: List[SceneLayerArt] = []
        for item in layers_raw[:MAX_LAYERS]:
            if not isinstance(item, dict):
                continue
            raw_svg = item.get("svg_markup") or item.get("svg") or ""
            if not raw_svg:
                continue
            svg = sanitize_scene_svg(raw_svg)
            n = count_drawable_paths(svg)
            if n < 1:
                continue
            if n > MAX_PATHS_PER_LAYER:
                raise ValueError(f"Layer has too many paths ({n}); max {MAX_PATHS_PER_LAYER}")
            idx = int(item.get("layer_index") or len(parsed) + 1)
            label = str(item.get("label") or f"layer-{idx}")[:40]
            parsed.append(SceneLayerArt(layer_index=idx, label=label, svg_markup=svg, path_count=n))
        if len(parsed) >= MIN_LAYERS:
            parsed.sort(key=lambda x: x.layer_index)
            return parsed

    # Fallback: single combined sketch as one layer
    raw = data.get("svg_markup") or data.get("svg") or ""
    if not raw:
        raise ValueError("Missing layers or svg_markup in LLM response")
    svg = sanitize_scene_svg(raw)
    n = count_drawable_paths(svg)
    if n < 3:
        raise ValueError(f"Too few drawable paths ({n})")
    return [
        SceneLayerArt(
            layer_index=1,
            label="full-scene",
            svg_markup=svg,
            path_count=n,
        )
    ]


async def generate_scene_line_art(
    scene_id: int,
    topic: str,
    narration: str,
    visual_description: str,
    keywords: list,
    duration: float,
    style: str = "whiteboard",
    prior_scene_summary: str = "",
) -> Tuple[str, List[SceneLayerArt]]:
    """
    Returns (headline, layers) where layers are 2-3 staggered SVG groups.
    """
    prompt = build_line_art_prompt(
        scene_id,
        topic,
        narration,
        visual_description,
        keywords,
        duration,
        style,
        prior_scene_summary,
    )
    model = settings.openai_line_art_model
    last_err: Optional[Exception] = None

    for attempt in range(2):
        try:
            data = await llm_service._chat_json(LINE_ART_SYSTEM, prompt, model=model)
            headline = (data.get("headline") or f"Scene {scene_id}").strip()[:48]
            layers = _parse_layers_from_response(data, scene_id)
            return headline, layers
        except Exception as e:
            last_err = e
            prompt += (
                f"\n\nIMPORTANT: Return exactly {MIN_LAYERS}-{MAX_LAYERS} layers in "
                '"layers" array. Each layer valid svg_markup with 5+ paths. '
                "Later layers must NOT repeat earlier artwork."
            )

    raise last_err or RuntimeError("Failed to generate scene line art")
