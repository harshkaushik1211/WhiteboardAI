SCENE_SYSTEM_PROMPT = """You are a visual director for educational whiteboard animations on a 1920x1080 canvas.

Available element types:
- svg_shape: shapes from catalog (car, human, cell, atom, arrow, circle, rectangle, triangle, flask, dna, circuit, tree, sun, earth, heart, brain, book, lightbulb, gear, rocket, ball, box, flowchart_box, chart_bar, chart_line, magnet, battery, wave, etc.)
- arrow: from/to points with label (spans 250-600px)
- text: large title text (size w: 600-900, h: 100)
- label: annotation (size w: 300-500)
- highlight: underline emphasis

Animations: stroke_reveal (main diagrams), fade_in (text), highlight

LAYOUT RULES (IMPORTANT):
- Use the FULL whiteboard: center main visuals around (960, 540)
- Main shapes: size w: 350-520, h: 280-450
- Place 3-6 elements per scene, avoid clutter
- Stagger delays from 0.5s upward across the scene duration
- stroke_reveal duration: 4-6 seconds per element (slow hand-drawn reveal)
- fade_in duration: 2-3 seconds
- Arrows should span meaningful distance (200+ px)
- Position x: 200-1720, y: 150-900

Output valid JSON only."""


def build_scene_prompt(
    scene_id: int,
    narration: str,
    visual_description: str,
    keywords: list,
    duration: float,
) -> str:
    kw = ", ".join(keywords) if keywords else "none"
    return f"""Plan whiteboard visuals for scene {scene_id}.

Narration: {narration}
Visual description: {visual_description}
Keywords to highlight: {kw}
Scene duration: {duration} seconds (all animations must complete before {duration}s)

Return JSON:
{{
  "scene_id": {scene_id},
  "background": "white",
  "camera": {{ "zoom": 1.0, "focusX": 960, "focusY": 540 }},
  "elements": [
    {{
      "id": "main-diagram",
      "type": "svg_shape",
      "shape": "lightbulb",
      "position": {{ "x": 960, "y": 480 }},
      "size": {{ "w": 420, "h": 360 }},
      "animation": "stroke_reveal",
      "delay": 0.6,
      "duration": 5.0,
      "label": "Key concept",
      "color": "#1a1a2e"
    }},
    {{
      "id": "arrow-1",
      "type": "arrow",
      "from": {{ "x": 500, "y": 540 }},
      "to": {{ "x": 900, "y": 540 }},
      "animation": "stroke_reveal",
      "delay": 3.0,
      "duration": 4.5,
      "label": "Force"
    }}
  ]
}}"""
