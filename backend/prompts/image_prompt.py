IMAGE_PROMPT_SYSTEM = """You write prompts for an AI image model that draws educational whiteboard frames.

Output valid JSON only:
{
  "image_prompt": "single paragraph prompt for the image model"
}

Rules for image_prompt:
- Clean WHITE background, dry-erase whiteboard look
- Black line drawings, hand-drawn, simple — not photorealistic
- NO hands, arms, pens, markers, or people drawing on the board — only the finished artwork
- 1-2 focal objects may use selective color; rest black lines
- 16:9 composition, centered, readable at 1920x1080
- Match narration and visual_description literally (boxes, arrows, labels as described)"""


def build_image_prompt(
    scene_id: int,
    topic: str,
    narration: str,
    visual_description: str,
    keywords: list,
    prior_headline: str = "",
) -> str:
    kw = ", ".join(keywords) if keywords else "none"
    prior = f"\nPrior scene (keep same style): {prior_headline}" if prior_headline else ""
    return f"""Whiteboard frame for scene {scene_id}.

Topic: {topic}
Narration: {narration}
Visual description: {visual_description}
Keywords: {kw}
{prior}

Return JSON with image_prompt only."""
