"""Resolve visual pipeline mode from project config."""
from config import settings
from utils.file_manager import load_json


def get_visual_mode(project_id: str) -> str:
    config = load_json(project_id, "config.json") or {}
    return config.get("visual_mode") or settings.visual_mode_default


def is_ai_line_art(project_id: str) -> bool:
    return get_visual_mode(project_id) == "ai_line_art"


def is_ai_image(project_id: str) -> bool:
    return get_visual_mode(project_id) == "ai_image"


def is_ai_visual(project_id: str) -> bool:
    return get_visual_mode(project_id) in ("ai_line_art", "ai_image")
