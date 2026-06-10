"""Build scene plans from GPT-generated per-scene layered SVG line art."""
from typing import Any, Dict, List, Tuple

from config import settings
from models.schemas import SceneElement, ScenePlanSchema, SceneSchema, ScriptSchema, Size, Position
from services.ai_line_art_service import SceneLayerArt, generate_scene_line_art
from utils.file_manager import ensure_project_dirs, save_json, save_text
from utils.timing import (
    CANVAS_CENTER_X,
    CANVAS_CENTER_Y,
    CANVAS_H,
    CANVAS_W,
    apply_layer_sketch_timing,
    enhance_scene_layout,
)


def _save_layer_svg(project_id: str, scene_id: int, layer_index: int, content: str) -> str:
    filename = f"svgs/scene-{scene_id}-layer-{layer_index}.svg"
    save_text(project_id, filename, content)
    return filename


def _headline_element(headline: str, scene_id: int) -> SceneElement:
    return SceneElement(
        id=f"scene-headline-{scene_id}",
        type="text",
        text=headline[:48],
        position=Position(x=CANVAS_CENTER_X, y=88),
        size=Size(w=900, h=100),
        animation="static",
        delay=0.0,
        duration=0.0,
        color="#1a1a2e",
    )


def _layer_element(scene_id: int, layer: SceneLayerArt, svg_path: str) -> SceneElement:
    return SceneElement(
        id=f"scene-{scene_id}-layer-{layer.layer_index}",
        type="svg",
        label=layer.label,
        position=Position(x=CANVAS_CENTER_X, y=CANVAS_CENTER_Y),
        size=Size(w=float(CANVAS_W), h=float(CANVAS_H)),
        animation="stroke_reveal",
        delay=0.0,
        duration=0.0,
        svg_path=svg_path,
        color="#1a1a2e",
    )


async def build_scene_plans_from_ai_sketch(
    project_id: str,
    script: ScriptSchema,
    topic: str,
) -> Tuple[List[ScenePlanSchema], List[Dict[str, Any]]]:
    ensure_project_dirs(project_id)
    audit: List[Dict[str, Any]] = []
    prior_summary = ""

    scene_plans: List[ScenePlanSchema] = []
    for scene in script.scenes:
        try:
            headline, layers = await generate_scene_line_art(
                scene.scene_id,
                topic,
                scene.narration,
                scene.visual_description,
                scene.keywords,
                scene.duration,
                style="whiteboard",
                prior_scene_summary=prior_summary,
            )
        except Exception as e:
            raise RuntimeError(
                f"AI line art failed for scene {scene.scene_id}: {e}"
            ) from e

        elements: List[SceneElement] = [_headline_element(headline, scene.scene_id)]
        layer_audit: List[Dict[str, Any]] = []
        for layer in layers:
            rel = _save_layer_svg(project_id, scene.scene_id, layer.layer_index, layer.svg_markup)
            elements.append(_layer_element(scene.scene_id, layer, rel))
            layer_audit.append(
                {
                    "layer_index": layer.layer_index,
                    "label": layer.label,
                    "svg_path": rel,
                    "path_count": layer.path_count,
                }
            )

        plan = ScenePlanSchema(
            scene_id=scene.scene_id,
            background="white",
            camera={"zoom": 1.0, "focusX": CANVAS_CENTER_X, "focusY": CANVAS_CENTER_Y},
            elements=elements,
        )
        apply_layer_sketch_timing(plan, scene.duration)
        enhance_scene_layout(plan, scene.duration)

        scene_plans.append(plan)
        audit.append(
            {
                "scene_id": scene.scene_id,
                "headline": headline,
                "layers": layer_audit,
                "layer_count": len(layers),
                "model": settings.openai_line_art_model,
                "visual_mode": "ai_line_art",
            }
        )
        prior_summary = headline

    save_json(project_id, "scene_plans.json", [p.model_dump() for p in scene_plans])
    save_json(project_id, "ai_sketch_audit.json", audit)
    return scene_plans, audit
