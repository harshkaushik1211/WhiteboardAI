"""
Deprecated: primitive SVG generation removed.
Use semantic asset pipeline (svg_retriever + layout_engine + svg_utils).
"""
from typing import Dict, List

from models.schemas import ScenePlanSchema
from services.svg_utils import copy_asset_to_project, load_library_svg


async def generate_svgs_for_project(
    project_id: str,
    scene_plans: List[ScenePlanSchema],
) -> Dict[str, str]:
    """Re-copy library assets into project (idempotent)."""
    svg_map: Dict[str, str] = {}
    for plan in scene_plans:
        for el in plan.elements:
            if el.type == "svg" and el.asset_library_path:
                rel = copy_asset_to_project(project_id, el.id, el.asset_library_path)
                el.svg_path = rel
                svg_map[el.id] = rel
            elif el.svg_path:
                svg_map[el.id] = el.svg_path
    return svg_map


def generate_element_svg(element) -> str:
    """Load from library path only — never generate primitives."""
    if getattr(element, "asset_library_path", None):
        return load_library_svg(element.asset_library_path)
    if getattr(element, "svg_path", None):
        from config import settings
        from utils.file_manager import project_dir
        # Best-effort read if path is project-relative
        return ""
    from services.svg_utils import _minimal_placeholder
    return _minimal_placeholder()
