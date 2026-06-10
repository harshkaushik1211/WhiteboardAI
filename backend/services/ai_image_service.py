"""Generate per-scene whiteboard PNGs via OpenAI Images API (gpt-image-1-mini)."""
import base64
from typing import Tuple

from config import settings
from prompts.image_prompt import IMAGE_PROMPT_SYSTEM, build_image_prompt
from services.llm_service import llm_service
from services.png_stroke_extractor import extract_strokes_for_project_image
from utils.file_manager import project_dir


def save_png_to_project(project_id: str, element_id: str, png_bytes: bytes) -> str:
    rel = f"assets/{element_id}.png"
    path = project_dir(project_id) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes)
    return rel


async def _build_image_prompt(
    scene_id: int,
    topic: str,
    narration: str,
    visual_description: str,
    keywords: list,
    prior_headline: str,
) -> str:
    user = build_image_prompt(
        scene_id, topic, narration, visual_description, keywords, prior_headline
    )
    data = await llm_service._chat_json(
        IMAGE_PROMPT_SYSTEM, user, model=settings.openai_line_art_model
    )
    prompt = (data.get("image_prompt") or "").strip()
    if not prompt:
        prompt = (
            f"Educational whiteboard line drawing on pure white background: "
            f"{visual_description}. Black marker lines, simple, no hands or pens."
        )
    return prompt


def _headline_from_narration(narration: str, scene_id: int) -> str:
    words = narration.split()
    if len(words) <= 8:
        return narration[:48]
    return " ".join(words[:6])[:48] or f"Scene {scene_id}"


async def generate_scene_image_for_project(
    project_id: str,
    scene_id: int,
    topic: str,
    narration: str,
    visual_description: str,
    keywords: list,
    prior_headline: str = "",
) -> Tuple[str, str, str, str, str]:
    """Returns (headline, image_prompt, rel_path, stroke_rel_path, model_name)."""
    image_prompt = await _build_image_prompt(
        scene_id, topic, narration, visual_description, keywords, prior_headline
    )

    response = await llm_service.client.images.generate(
        model=settings.openai_image_model,
        prompt=image_prompt,
        size=settings.openai_image_size,
        quality=settings.openai_image_quality,
        output_format="png",
        n=1,
    )

    if not response.data or not response.data[0].b64_json:
        raise RuntimeError("OpenAI image API returned no image data")

    png_bytes = base64.b64decode(response.data[0].b64_json)
    element_id = f"scene-{scene_id}-sketch"
    rel = save_png_to_project(project_id, element_id, png_bytes)
    stroke_rel = extract_strokes_for_project_image(project_id, rel)
    headline = _headline_from_narration(narration, scene_id)
    return headline, image_prompt, rel, stroke_rel, settings.openai_image_model
