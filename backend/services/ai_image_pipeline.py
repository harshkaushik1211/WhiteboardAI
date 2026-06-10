"""Build scene plans from OpenAI-generated whiteboard PNGs (storyboard-ai style)."""
from typing import Any, Dict, List, Tuple

from config import settings
from models.schemas import SceneElement, ScenePlanSchema, SceneSchema, ScriptSchema, Size, Position
from services.ai_image_service import generate_scene_image_for_project
from utils.file_manager import ensure_project_dirs, save_json
from utils.timing import (
    CANVAS_CENTER_X,
    CANVAS_CENTER_Y,
    CANVAS_H,
    CANVAS_W,
    apply_sketch_image_timing,
    enhance_scene_layout,
)


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


def _sketch_image_element(
    scene_id: int, image_path: str, stroke_data_path: str
) -> SceneElement:
    return SceneElement(
        id=f"scene-{scene_id}-sketch",
        type="image",
        position=Position(x=CANVAS_CENTER_X, y=CANVAS_CENTER_Y),
        size=Size(w=float(CANVAS_W), h=float(CANVAS_H)),
        animation="sketch_reveal",
        delay=0.15,
        duration=5.0,
        image_path=image_path,
        stroke_data_path=stroke_data_path,
        color="#1a1a2e",
    )


async def build_scene_plans_from_ai_image(
    project_id: str,
    script: ScriptSchema,
    topic: str,
) -> Tuple[List[ScenePlanSchema], List[Dict[str, Any]]]:
    ensure_project_dirs(project_id)
    audit: List[Dict[str, Any]] = []
    prior_headline = ""
    scene_plans: List[ScenePlanSchema] = []

    for scene in script.scenes:
        try:
            headline, image_prompt, rel, stroke_rel, model = await generate_scene_image_for_project(
                project_id,
                scene.scene_id,
                topic,
                scene.narration,
                scene.visual_description,
                scene.keywords,
                prior_headline,
            )
        except Exception as e:
            raise RuntimeError(
                f"AI image generation failed for scene {scene.scene_id}: {e}"
            ) from e

        elements: List[SceneElement] = [
            _headline_element(headline, scene.scene_id),
            _sketch_image_element(scene.scene_id, rel, stroke_rel),
        ]
        plan = ScenePlanSchema(
            scene_id=scene.scene_id,
            background="white",
            camera={"zoom": 1.0, "focusX": CANVAS_CENTER_X, "focusY": CANVAS_CENTER_Y},
            elements=elements,
        )
        apply_sketch_image_timing(plan, scene.duration)
        enhance_scene_layout(plan, scene.duration)
        scene_plans.append(plan)
        audit.append(
            {
                "scene_id": scene.scene_id,
                "headline": headline,
                "image_path": rel,
                "stroke_data_path": stroke_rel,
                "image_prompt": image_prompt[:500],
                "model": model,
                "visual_mode": "ai_image",
            }
        )
        prior_headline = headline

    save_json(project_id, "scene_plans.json", [p.model_dump() for p in scene_plans])
    save_json(project_id, "ai_image_audit.json", audit)
    return scene_plans, audit
