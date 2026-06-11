"""Copy retrieved library SVGs into project folder and build visual audit."""
import json
from pathlib import Path
from typing import Dict, List, Set

from config import settings
from models.schemas import (
    RetrievedAsset,
    RequiredVisual,
    ScenePlanSchema,
    SemanticScenePlan,
    VisualAuditEntry,
    ResolutionResult,
)
from services.layout_engine import layout_engine
from services.semantic_visual_planner import _load_semantic_memory, _resolve_memory_entry
from services.svg_retriever import RetrievalOptions, svg_retriever
from services.svg_utils import (
    copy_asset_to_project,
    copy_image_to_project,
    generate_arrow_svg,
    generate_text_svg,
    is_diagram_svg_path,
)
from utils.file_manager import ensure_project_dirs, save_json


def _importance_map(semantic: SemanticScenePlan) -> Dict[str, str]:
    return {v.concept: v.importance for v in semantic.required_visuals}


async def build_scene_plans_from_semantic(
    project_id: str,
    semantic_plans: List[SemanticScenePlan],
    topic: str,
) -> tuple[List[ScenePlanSchema], List[VisualAuditEntry]]:
    memory = _load_semantic_memory()
    memory_hints = _resolve_memory_entry(topic, memory)
    preferred = memory_hints.get("preferred_visuals", [])
    retrieval_options = RetrievalOptions.from_memory(memory_hints)
    if retrieval_options.allowed_paths:
        from services.svg_indexer import ensure_paths_indexed

        ensure_paths_indexed(list(retrieval_options.allowed_paths))
        svg_retriever.reload()

    # Determine lesson domain from memory hints or lesson_plan.json
    lesson_domain = memory_hints.get("domain", "")
    if not lesson_domain:
        try:
            from utils.file_manager import load_json
            lp = load_json(project_id, "lesson_plan.json")
            if lp:
                lesson_domain = lp.get("domain", "")
        except Exception:
            pass

    used_asset_ids: Set[str] = set()
    scene_plans: List[ScenePlanSchema] = []
    audit: List[VisualAuditEntry] = []

    resolution_audit_entries: List[ResolutionResult] = []

    ensure_project_dirs(project_id)

    for semantic in semantic_plans:
        from services.action_mapper import map_action_to_motion
        from services.concept_resolver import resolve_concept

        for rv in semantic.required_visuals:
            result = resolve_concept(rv.concept, lesson_domain)
            resolution_audit_entries.append(result)
            rv.concept = result.canonical_concept

        rv_map = {rv.concept.lower(): rv for rv in semantic.required_visuals}

        retrieved = svg_retriever.retrieve_assets(
            semantic.required_visuals,
            topic,
            used_asset_ids,
            preferred_visuals=preferred,
            retrieval_options=retrieval_options,
            lesson_domain=lesson_domain,
        )

        for r in retrieved:
            rv = rv_map.get(r.concept.lower())
            action = rv.action if rv else None
            motion_profile = map_action_to_motion(action) if action else None
            action_executed = bool(action and r.approved and not r.fallback)

            audit.append(
                VisualAuditEntry(
                    scene_id=semantic.scene_id,
                    concept=r.concept,
                    asset_id=r.asset_id,
                    library_path=r.library_path,
                    score=r.score,
                    fallback=r.fallback,
                    approved=r.approved,
                    rejection_reason=r.rejection_reason,
                    action=action,
                    motion_profile=motion_profile,
                    action_executed=action_executed,
                )
            )

        plan = layout_engine.compose(
            semantic,
            retrieved,
            _importance_map(semantic),
        )

        # Post-process elements to attach actions, intents, and relationship links (Component 2 & 5)
        concept_to_id = {el.concept.lower(): el.id for el in plan.elements if el.concept}
        
        for el in plan.elements:
            if el.concept:
                rv = rv_map.get(el.concept.lower())
                if rv:
                    el.action = rv.action
                    el.animation_intent = rv.animation_intent
                    el.motion_profile = map_action_to_motion(rv.action)
                    if rv.related_to:
                        target_concept = rv.related_to[0].lower()
                        if target_concept in concept_to_id:
                            el.target_id = concept_to_id[target_concept]

        for el in plan.elements:
            if el.type == "image" and el.asset_library_path:
                rel = copy_image_to_project(project_id, el.id, el.asset_library_path)
                el.image_path = rel
            elif el.type == "svg" and el.asset_library_path:
                preserve = is_diagram_svg_path(el.asset_library_path)
                rel = copy_asset_to_project(
                    project_id, el.id, el.asset_library_path, preserve_colors=preserve
                )
                el.svg_path = rel
            elif el.type == "arrow" and el.from_point and el.to_point:
                svg = generate_arrow_svg(
                    el.from_point.x, el.from_point.y,
                    el.to_point.x, el.to_point.y,
                    el.label,
                )
                rel = _save_project_svg(project_id, el.id, svg)
                el.svg_path = rel
            elif el.type in ("text", "label") and (el.text or el.label):
                w = el.size.w if el.size else 500
                h = el.size.h if el.size else 80
                svg = generate_text_svg(el.text or el.label or "", w, h)
                rel = _save_project_svg(project_id, el.id, svg)
                el.svg_path = rel

        scene_plans.append(plan)

    # Calculate retrieval statistics (Review 5)
    total_retrievals = len(audit)
    approved_count = sum(1 for a in audit if a.approved and not a.fallback)
    domain_consistent_count = sum(1 for a in audit if a.rejection_reason != "domain_mismatch")
    invalid_count = sum(1 for a in audit if not a.approved)
    fallback_count = sum(1 for a in audit if a.fallback)
    
    accuracy = approved_count / total_retrievals if total_retrievals > 0 else 1.0
    domain_consistency = domain_consistent_count / total_retrievals if total_retrievals > 0 else 1.0
    fallback_rate = fallback_count / total_retrievals if total_retrievals > 0 else 0.0

    # Calculate scene level action statistics (Component 7)
    scene_action_stats = []
    for semantic in semantic_plans:
        scene_id = semantic.scene_id
        scene_audit = [a for a in audit if a.scene_id == scene_id]
        
        # Planned actions: count visuals that requested an active action
        actions_detected = sum(1 for rv in semantic.required_visuals if rv.action)
        # Executed actions: count approved visuals that had an active action successfully matched
        actions_executed = sum(1 for a in scene_audit if a.action and a.action_executed)
        
        exec_rate = actions_executed / actions_detected if actions_detected > 0 else 1.0
        
        scene_action_stats.append({
            "scene_id": scene_id,
            "actions_detected": actions_detected,
            "actions_executed": actions_executed,
            "execution_rate": round(exec_rate, 2),
        })

    retrieval_audit_data = {
        "metrics": {
            "retrieval_accuracy": round(accuracy, 2),
            "domain_consistency": round(domain_consistency, 2),
            "invalid_match_count": invalid_count,
            "fallback_rate": round(fallback_rate, 2),
        },
        "retrievals": [a.model_dump() for a in audit],
        "action_execution_stats": scene_action_stats
    }

    # Calculate concept resolution statistics
    total_resolutions = len(resolution_audit_entries)
    resolved_count = sum(1 for r in resolution_audit_entries if r.resolution_type != "fallback")
    resolution_rate = resolved_count / total_resolutions if total_resolutions > 0 else 1.0

    match_types = {
        "exact_match": 0,
        "alias_match": 0,
        "ontology_match": 0,
        "semantic_match": 0,
        "fallback": 0
    }
    for r in resolution_audit_entries:
        match_types[r.resolution_type] = match_types.get(r.resolution_type, 0) + 1

    concept_resolution_audit_data = {
        "metrics": {
            "total_concepts": total_resolutions,
            "resolved_concepts": resolved_count,
            "resolution_rate": round(resolution_rate, 2),
            "match_types": match_types
        },
        "resolutions": [r.model_dump() for r in resolution_audit_entries]
    }

    save_json(project_id, "scene_plans.json", [p.model_dump() for p in scene_plans])
    save_json(project_id, "visual_audit.json", [a.model_dump() for a in audit])
    save_json(project_id, "retrieval_audit.json", retrieval_audit_data)
    save_json(project_id, "concept_resolution_audit.json", concept_resolution_audit_data)
    return scene_plans, audit


def _save_project_svg(project_id: str, element_id: str, content: str) -> str:
    from utils.file_manager import save_text
    filename = f"svgs/{element_id}.svg"
    save_text(project_id, filename, content)
    return filename
