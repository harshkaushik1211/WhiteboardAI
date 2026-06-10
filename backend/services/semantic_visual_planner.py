import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import settings
from models.schemas import RequiredVisual, ScriptSchema, SemanticScenePlan, VisualConnection
from prompts.semantic_visual_prompt import SEMANTIC_VISUAL_SYSTEM, build_semantic_visual_prompt
from services.concept_catalog import normalize_concept
from services.llm_service import llm_service
from utils.file_manager import save_json


def _load_semantic_memory() -> Dict[str, Any]:
    path = settings.assets_path / "semantic_memory.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _topic_key(topic: str) -> str:
    return topic.strip().lower()


def _resolve_memory_entry(topic: str, memory: Dict) -> Dict[str, Any]:
    key = _topic_key(topic)
    if key in memory:
        return memory[key]
    for mem_key, entry in memory.items():
        if mem_key in key or key in mem_key:
            return entry
    if "photosynthesis" in key:
        return memory.get("photosynthesis", {})
    return {}


def _load_template(topic: str, memory: Dict) -> Dict[str, Any]:
    entry = _resolve_memory_entry(topic, memory)
    template_ref = entry.get("template")
    if not template_ref:
        return {}
    tpl_path = settings.assets_path.parent / "templates" / f"{template_ref}.json"
    if tpl_path.exists():
        return json.loads(tpl_path.read_text(encoding="utf-8"))
    return {}


def _hint_for_scene(template: Dict, scene_index: int) -> Optional[dict]:
    for hint in template.get("scene_hints", []):
        if hint.get("scene_index") == scene_index:
            return hint
    return None


def _plan_from_template_hint(
    scene,
    topic: str,
    hint: dict,
    template: Dict,
) -> SemanticScenePlan:
    visuals = [
        RequiredVisual(
            concept=normalize_concept(rv["concept"]),
            keywords=rv.get("keywords", [rv["concept"]]),
            importance=rv.get("importance", "secondary"),
        )
        for rv in hint.get("required_visuals", [])
    ]
    connections = [
        VisualConnection.model_validate(c) for c in hint.get("connections", [])
    ]
    return SemanticScenePlan(
        scene_id=scene.scene_id,
        topic=topic,
        headline=hint.get("headline", ""),
        layout_type=hint.get("layout_type", template.get("default_layout", "flow_diagram")),
        required_visuals=visuals,
        connections=connections,
        animation_style=template.get("animation_style", "whiteboard_draw"),
        camera=hint.get("camera"),
    )


def _merge_template_hints(
    semantic: SemanticScenePlan,
    template: Dict,
    scene_index: int,
) -> SemanticScenePlan:
    hint = _hint_for_scene(template, scene_index)
    if not hint:
        return semantic

    if hint.get("headline"):
        semantic.headline = hint["headline"]
    if hint.get("layout_type"):
        semantic.layout_type = hint["layout_type"]
    if hint.get("camera"):
        semantic.camera = hint["camera"]

    existing = {v.concept.lower() for v in semantic.required_visuals}
    for rv in hint.get("required_visuals", []):
        c = normalize_concept(rv.get("concept", ""))
        if c.lower() not in existing:
            semantic.required_visuals.append(
                RequiredVisual(
                    concept=c,
                    keywords=rv.get("keywords", [c]),
                    importance=rv.get("importance", "secondary"),
                )
            )
            existing.add(c.lower())

    for conn in hint.get("connections", []):
        semantic.connections.append(VisualConnection.model_validate(conn))

    return semantic


def _fallback_semantic(scene, topic: str, memory_hints: dict) -> SemanticScenePlan:
    preferred = memory_hints.get("preferred_visuals", memory_hints.get("asset_catalog", []))
    if not preferred:
        preferred = ["plant", "leaf", "sun", "magnify"]
    visuals = [
        RequiredVisual(
            concept=normalize_concept(c),
            keywords=[c, topic],
            importance="primary" if i == 0 else "secondary",
        )
        for i, c in enumerate(preferred[:4])
    ]
    return SemanticScenePlan(
        scene_id=scene.scene_id,
        topic=topic,
        layout_type=memory_hints.get("preferred_layout", "flow_diagram"),
        required_visuals=visuals,
        animation_style="whiteboard_draw",
    )


async def plan_semantic_scenes(
    project_id: str,
    script: ScriptSchema,
    topic: str,
) -> List[SemanticScenePlan]:
    memory = _load_semantic_memory()
    memory_hints = _resolve_memory_entry(topic, memory)
    template = _load_template(topic, memory)
    template_only = template.get("visual_plan_mode") == "template_only"
    catalog = memory_hints.get("asset_catalog") or template.get("asset_catalog")

    async def plan_one(scene, index: int) -> SemanticScenePlan:
        hint = _hint_for_scene(template, index)
        if template_only and hint:
            return _plan_from_template_hint(scene, topic, hint, template)

        prompt = build_semantic_visual_prompt(
            scene.scene_id,
            scene.narration,
            scene.visual_description,
            scene.keywords,
            scene.duration,
            topic,
            memory_hints,
            template,
            catalog,
            scene_type=scene.scene_type,  # Forward educational scene role for intent-aware layout
        )
        data = await llm_service._chat_json(SEMANTIC_VISUAL_SYSTEM, prompt)
        try:
            plan = SemanticScenePlan.model_validate(data)
            for rv in plan.required_visuals:
                rv.concept = normalize_concept(rv.concept)
        except Exception:
            plan = _fallback_semantic(scene, topic, memory_hints)

        plan = _merge_template_hints(plan, template, index)
        if hint and hint.get("headline"):
            plan.headline = hint["headline"]
        if not plan.required_visuals:
            plan = _fallback_semantic(scene, topic, memory_hints)
        return plan

    tasks = [plan_one(s, i) for i, s in enumerate(script.scenes)]
    plans = await asyncio.gather(*tasks, return_exceptions=True)

    result: List[SemanticScenePlan] = []
    for i, p in enumerate(plans):
        if isinstance(p, Exception):
            hint = _hint_for_scene(template, i)
            if hint:
                result.append(_plan_from_template_hint(script.scenes[i], topic, hint, template))
            else:
                result.append(_fallback_semantic(script.scenes[i], topic, memory_hints))
        else:
            result.append(p)

    save_json(project_id, "semantic_plans.json", [p.model_dump(by_alias=True) for p in result])
    return result
