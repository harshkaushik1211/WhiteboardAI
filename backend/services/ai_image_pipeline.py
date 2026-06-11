"""Build scene plans from OpenAI-generated whiteboard PNGs (storyboard-ai style)."""
import asyncio
import logging
from typing import Any, Dict, List, Tuple

from config import settings
from models.schemas import SceneElement, ScenePlanSchema, ScriptSchema, Size, Position
from services.ai_image_service import generate_scene_png_for_project
from services.png_stroke_extractor import extract_strokes_for_project_image
from utils.file_manager import ensure_project_dirs, load_json, save_json
from utils.timing import (
    CANVAS_CENTER_X,
    CANVAS_CENTER_Y,
    CANVAS_H,
    CANVAS_W,
    apply_sketch_image_timing,
    enhance_scene_layout,
)

logger = logging.getLogger("ai_image_pipeline")


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
    scenes = list(script.scenes)
    concurrency = max(1, settings.scene_image_concurrency)
    image_sem = asyncio.Semaphore(concurrency)

    # Phase 1: PNG generation in parallel (OpenAI image API is the slow step).
    async def _generate_png(scene):
        async with image_sem:
            try:
                return scene, await generate_scene_png_for_project(
                    project_id,
                    scene.scene_id,
                    topic,
                    scene.narration,
                    scene.visual_description,
                    scene.keywords,
                    "",  # parallel-safe; visual_description carries scene context
                )
            except Exception as e:
                raise RuntimeError(
                    f"AI image generation failed for scene {scene.scene_id}: {e}"
                ) from e

    png_results = sorted(
        await asyncio.gather(*[_generate_png(scene) for scene in scenes]),
        key=lambda row: row[0].scene_id,
    )
    png_results = [
        (scene, headline, image_prompt, rel, model)
        for scene, (headline, image_prompt, rel, model) in png_results
    ]

    logger.info(
        "Generated %d scene PNGs (concurrency=%d); extracting strokes...",
        len(png_results),
        concurrency,
    )

    # Phase 2: stroke extraction in parallel (vision + contours; local OpenCV).
    stroke_sem = asyncio.Semaphore(concurrency)

    async def _extract_strokes(scene, rel: str) -> str:
        async with stroke_sem:
            return await asyncio.to_thread(
                extract_strokes_for_project_image,
                project_id,
                rel,
                scene.keywords,
                scene.visual_description,
            )

    stroke_tasks = [
        _extract_strokes(scene, rel) for scene, _h, _p, rel, _m in png_results
    ]
    stroke_paths = await asyncio.gather(*stroke_tasks)

    audit: List[Dict[str, Any]] = []
    scene_plans: List[ScenePlanSchema] = []

    for (scene, headline, image_prompt, rel, model), stroke_rel in zip(
        png_results, stroke_paths
    ):
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
        stroke_meta = load_json(project_id, stroke_rel) or {}
        audit.append(
            {
                "scene_id": scene.scene_id,
                "headline": headline,
                "image_path": rel,
                "stroke_data_path": stroke_rel,
                "image_prompt": image_prompt[:500],
                "model": model,
                "visual_mode": "ai_image",
                "stroke_mode": stroke_meta.get("stroke_mode"),
                "segmentation_backend": stroke_meta.get("segmentation_backend"),
                "object_labels": stroke_meta.get("object_labels", []),
                "path_count": stroke_meta.get("path_count"),
                "object_count": stroke_meta.get("object_count"),
            }
        )

    save_json(project_id, "scene_plans.json", [p.model_dump() for p in scene_plans])
    save_json(project_id, "ai_image_audit.json", audit)
    return scene_plans, audit
