"""Orchestrate semantic visual planning → retrieval → layout, or AI line art."""
from typing import List, Tuple

from models.schemas import ScenePlanSchema, ScriptSchema, VisualAuditEntry
from services.asset_pipeline import build_scene_plans_from_semantic
from services.semantic_visual_planner import plan_semantic_scenes
from services.visual_mode import is_ai_image, is_ai_line_art
from utils.file_manager import load_json, save_json
from utils.timing import enhance_scene_layout


def _resolve_topic(project_id: str, script: ScriptSchema, topic: str) -> str:
    if topic:
        return topic
    config = load_json(project_id, "config.json") or {}
    return config.get("topic", script.title)


async def plan_scenes_for_script(
    project_id: str,
    script: ScriptSchema,
    topic: str = "",
) -> List[ScenePlanSchema]:
    """Full visual pipeline: library assets or AI line art per scene."""
    topic = _resolve_topic(project_id, script, topic)

    if is_ai_image(project_id):
        from services.ai_image_pipeline import build_scene_plans_from_ai_image

        scene_plans, _ = await build_scene_plans_from_ai_image(project_id, script, topic)
        return scene_plans

    if is_ai_line_art(project_id):
        from services.ai_sketch_pipeline import build_scene_plans_from_ai_sketch

        scene_plans, _ = await build_scene_plans_from_ai_sketch(project_id, script, topic)
        return scene_plans

    semantic_plans = await plan_semantic_scenes(project_id, script, topic)
    scene_plans, _audit = await build_scene_plans_from_semantic(
        project_id, semantic_plans, topic
    )

    for i, plan in enumerate(scene_plans):
        dur = script.scenes[i].duration if i < len(script.scenes) else 8.0
        enhance_scene_layout(plan, dur)

    save_json(project_id, "scene_plans.json", [p.model_dump() for p in scene_plans])
    return scene_plans


async def build_visual_scenes(
    project_id: str,
    script: ScriptSchema,
    topic: str,
) -> Tuple[List[ScenePlanSchema], List[VisualAuditEntry]]:
    """Used by render pipeline."""
    topic = _resolve_topic(project_id, script, topic)

    if is_ai_image(project_id):
        from services.ai_image_pipeline import build_scene_plans_from_ai_image

        scene_plans, _audit = await build_scene_plans_from_ai_image(
            project_id, script, topic
        )
        return scene_plans, []

    if is_ai_line_art(project_id):
        from services.ai_sketch_pipeline import build_scene_plans_from_ai_sketch

        scene_plans, _audit = await build_scene_plans_from_ai_sketch(
            project_id, script, topic
        )
        return scene_plans, []

    semantic_plans = await plan_semantic_scenes(project_id, script, topic)
    scene_plans, audit = await build_scene_plans_from_semantic(
        project_id, semantic_plans, topic
    )

    for i, plan in enumerate(scene_plans):
        dur = script.scenes[i].duration if i < len(script.scenes) else 8.0
        enhance_scene_layout(plan, dur)

    return scene_plans, audit
