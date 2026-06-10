SEMANTIC_VISUAL_SYSTEM = """You are an educational visual director for whiteboard explainer videos.

You plan WHAT visuals are needed and HOW they interact, focusing on active educational demonstrations rather than static slides.

Rules:
- Pick real educational concepts that exist as icons/diagrams (lungs, mitochondria, oxygen, car, server, array, etc.).
- Use layout_type from: flow_diagram, process_pipeline, comparison, hierarchy, circular_process, labeled_anatomy, timeline, centered_focus.

ATTENTION MANAGEMENT (Strict limits to avoid cognitive overload):
- Maximum 1-2 primary concepts ("importance": "primary").
- Maximum 2-4 supporting elements ("importance": "secondary").

EVENT-BASED SEMANTIC PLANNING (Think in active demonstrations):
For each required visual, specify:
- `action`: The active educational verb describing the event.
  * Physics: push, pull, accelerate, decelerate, collide, fall, rotate, bounce
  * Biology: grow, divide, flow, transport, absorb, release, replicate
  * Chemistry: react, combine, separate, bond, break, exchange
  * CS/Math: search, compare, swap, traverse, send, receive, store
- `timing_hint`: Staged reveal sequence (e.g. "reveal first", "during explanation", "highlight relationship", "sequence 2").
- `related_to`: List of other concepts in the scene that this concept interacts with.
- `relationship`: The causal or physical connection (e.g. "causes", "enters", "travels_to", "binds").
- `animation_intent`: Use one of: demonstration, comparison, transformation, flow, cause_effect, emphasis.

RELATIONSHIP GRAPH:
Include top-level "nodes" and "edges" mapping the concept causal graph:
- "nodes": List of concept names present in the scene.
- "edges": List of connection relationships where each edge has:
  * "from": Starting concept
  * "to": Destination concept
  * "type": Causal type (e.g. "causes", "enters", "inhibits")

Output valid JSON only matching the schema exactly."""


# Scene-type-specific layout and visual count guidance
_SCENE_TYPE_LAYOUT_HINTS: dict = {
    "HOOK":                   ("flow_diagram",      "1-2 visuals max. Choose ONE powerful, attention-grabbing image."),
    "INTUITION":              ("flow_diagram",      "2-3 visuals. Use analogy objects (pipe for current, manual for DNA, etc.)."),
    "EXPLANATION":            ("flow_diagram",      "2-4 visuals. Show the concept clearly with supporting context."),
    "EXAMPLE":                ("process_pipeline",  "2-4 visuals showing the example scenario step by step."),
    "VISUALIZATION":          ("flow_diagram",      "3-5 visuals. Focus on making the abstract visible."),
    "COMPARISON":             ("comparison",        "Exactly 2 primary visuals side by side representing each concept."),
    "CAUSE_EFFECT":           ("process_pipeline",  "2-4 visuals connected with arrows showing cause → effect chain."),
    "FORMULA":                ("centered_focus",    "1-2 visuals. Center the formula symbol or equation. Minimal clutter."),
    "SUMMARY":                ("flow_diagram",      "3-5 visuals recapping the key concepts from the lesson."),
    "REAL_WORLD_APPLICATION": ("flow_diagram",      "2-4 real-world objects (car, rocket, plant, smartphone, etc.)."),
}


def build_semantic_visual_prompt(
    scene_id: int,
    narration: str,
    visual_description: str,
    keywords: list,
    duration: float,
    topic: str,
    memory_hints: dict,
    template_hints: dict,
    asset_catalog: list = None,
    scene_type: str = None,  # Educational scene role from SceneSchema.scene_type
) -> str:
    preferred = memory_hints.get("preferred_visuals", [])
    default_layout = memory_hints.get("preferred_layout", template_hints.get("default_layout", "flow_diagram"))
    template_visuals = template_hints.get("preferred_visuals", [])
    catalog = asset_catalog or memory_hints.get("asset_catalog") or template_hints.get("asset_catalog")
    catalog_str = ", ".join(catalog) if catalog else ", ".join(preferred) or "none"

    # Derive layout and visual intent from scene_type when available
    scene_type_layout, scene_type_guidance = _SCENE_TYPE_LAYOUT_HINTS.get(
        (scene_type or "").upper(),
        (default_layout, ""),
    )
    layout = scene_type_layout if scene_type else default_layout

    restrict = ""
    if catalog:
        restrict = f"\nCRITICAL: Use ONLY these concept names: {catalog_str}. No other icons."

    scene_type_block = ""
    if scene_type:
        scene_type_block = f"\nScene type: {scene_type} — {scene_type_guidance}"

    return f"""Plan semantic visuals for scene {scene_id}.
{restrict}
Topic: {topic}
Narration: {narration}
Visual description: {visual_description}
Scene keywords: {", ".join(keywords) if keywords else "none"}
Duration: {duration}s
Suggested layout: {layout}{scene_type_block}
Topic preferred visuals: {", ".join(preferred) if preferred else "none"}
Template visuals: {", ".join(template_visuals) if template_visuals else "none"}

Return JSON conforming strictly to the following structure:
{{
  "scene_id": {scene_id},
  "topic": "{topic}",
  "layout_type": "{layout}",
  "required_visuals": [
    {{
      "concept": "car",
      "keywords": ["car", "vehicle", "automobile"],
      "importance": "primary",
      "action": "accelerate",
      "timing_hint": "reveal first",
      "related_to": ["force_arrow"],
      "relationship": "causes",
      "animation_intent": "demonstration"
    }},
    {{
      "concept": "force_arrow",
      "keywords": ["force", "arrow", "push"],
      "importance": "secondary",
      "action": "push",
      "timing_hint": "during explanation",
      "related_to": ["car"],
      "relationship": "applied_to",
      "animation_intent": "cause_effect"
    }}
  ],
  "connections": [
    {{ "from": "force_arrow", "to": "car" }}
  ],
  "animation_style": "whiteboard_draw",
  "nodes": ["force_arrow", "car"],
  "edges": [
    {{ "from": "force_arrow", "to": "car", "type": "applies_force" }}
  ]
}}"""
