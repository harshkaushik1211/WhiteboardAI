"""Orchestrate AI image visual pipeline (GPT image → stroke reveal per scene)."""
from typing import List, Tuple

from models.schemas import ScenePlanSchema, ScriptSchema, VisualAuditEntry
from services.ai_image_pipeline import build_scene_plans_from_ai_image
from utils.file_manager import load_json


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
    """Generate per-scene whiteboard PNGs and stroke data."""
    topic = _resolve_topic(project_id, script, topic)
    scene_plans, _ = await build_scene_plans_from_ai_image(project_id, script, topic)
    return scene_plans


async def build_visual_scenes(
    project_id: str,
    script: ScriptSchema,
    topic: str,
) -> Tuple[List[ScenePlanSchema], List[VisualAuditEntry]]:
    """Used by render pipeline."""
    topic = _resolve_topic(project_id, script, topic)
    scene_plans, _audit = await build_scene_plans_from_ai_image(project_id, script, topic)
    return scene_plans, []
