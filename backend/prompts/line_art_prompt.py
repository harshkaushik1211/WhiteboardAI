LINE_ART_SYSTEM = """You are an educational whiteboard illustrator who outputs layered SVG line art.

Rules:
- Output valid JSON only (no markdown).
- Provide exactly 2 or 3 layers in draw_order sequence (story beats).
- Each layer's svg_markup is ONE complete <svg viewBox="0 0 1920 1080"> with ONLY the NEW strokes for that beat.
  Do NOT repeat artwork from earlier layers — later layers add only new lines/shapes/text.
- Layer 1: setup (ground line, first objects). Layer 2: action (arrows, force, motion cues). Layer 3 (optional): result or labels.
- Style: hand-drawn educational sketch, outline ONLY (fill="none" on paths/shapes).
- Stroke: #1a1a2e, stroke-width 2.5, stroke-linecap round, stroke-linejoin round.
- 5-20 drawable elements per layer: <path>, <line>, <polyline>, <polygon>, <circle>, <rect>.
- Add data-path-length="N" on each path/line (rough pixel length).
- <text> labels: fill="#1a1a2e", font-family sans-serif, font-size 28-36.
- Valid XML only: self-close with /> e.g. <line x1="0" y1="0" x2="10" y2="10" fill="none"/>.
- Never use '/ fill="none">' broken syntax.
- Concrete objects (box, arrow, stick figure) — not abstract-only diagrams.
- White background is implicit; no full-page fill rectangle."""

STYLE_PREAMBLE = (
    "Consistent whiteboard style: navy stroke #1a1a2e, 2.5px lines, simple shapes, "
    "no shading, no color fills."
)

MIN_LAYERS = 2
MAX_LAYERS = 3


def build_line_art_prompt(
    scene_id: int,
    topic: str,
    narration: str,
    visual_description: str,
    keywords: list,
    duration: float,
    style: str,
    prior_scene_summary: str = "",
) -> str:
    kw = ", ".join(keywords) if keywords else "none"
    prior = ""
    if prior_scene_summary:
        prior = f"\nPrior scene visual (keep same stroke style): {prior_scene_summary}"

    per_layer_sec = max(2.5, duration * 0.22)

    return f"""Draw layered whiteboard line art for scene {scene_id}.

Topic: {topic}
Style preset: {style}
{STYLE_PREAMBLE}
Narration: {narration}
Visual description: {visual_description}
Keywords: {kw}
Scene duration: {duration}s — each layer draws for ~{per_layer_sec:.1f}s in sequence.
{prior}

Example (Newton first law): layer 1 = box on ground + "at rest"; layer 2 = arrow labeled "force" + person pushing; layer 3 = box shifted right + motion hint.

Return JSON:
{{
  "scene_id": {scene_id},
  "headline": "Short scene title (max 6 words)",
  "layers": [
    {{
      "layer_index": 1,
      "label": "setup",
      "svg_markup": "<svg xmlns=\\"http://www.w3.org/2000/svg\\" viewBox=\\"0 0 1920 1080\\" fill=\\"none\\" stroke=\\"#1a1a2e\\" stroke-width=\\"2.5\\">...</svg>"
    }},
    {{
      "layer_index": 2,
      "label": "action",
      "svg_markup": "<svg>...</svg>"
    }}
  ]
}}"""
