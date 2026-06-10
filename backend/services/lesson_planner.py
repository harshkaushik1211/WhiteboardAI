"""Lesson Planning Service — Stage 1 of the educational script pipeline.

Runs BEFORE script generation to produce a pedagogically-sound lesson plan:
  - Learning objectives
  - Optimal scene sequence (HOOK → INTUITION → EXPLANATION → ...)
  - Concept complexity estimate (simple | medium | complex)
  - Recommended scene count
  - Domain-relevant real-world examples

The plan is passed to the script generator and saved as lesson_plan.json.
On any failure, a sensible default plan is returned — the pipeline never blocks.
"""
import logging
from typing import Optional

from models.schemas import LessonPlan
from prompts.lesson_planner_prompt import LESSON_PLANNER_SYSTEM, build_lesson_plan_prompt

logger = logging.getLogger("lesson_planner")


async def generate_lesson_plan(
    topic: str,
    duration: int,
    educational_level: str = "high_school",
    style: str = "whiteboard",
    memory_hints: Optional[dict] = None,
) -> LessonPlan:
    """Generate an educational lesson plan to guide script generation.

    Args:
        topic: The subject to teach.
        duration: Target video duration in seconds.
        educational_level: Target audience level (middle_school | high_school |
                           college | competitive_exam).
        style: Visual style (whiteboard, etc.).
        memory_hints: Optional topic hints from semantic_memory.json.

    Returns:
        A LessonPlan instance. Never raises — falls back to a default plan.
    """
    # Import here to avoid circular imports at module load time
    from services.llm_service import llm_service

    memory_hints = memory_hints or {}
    try:
        prompt = build_lesson_plan_prompt(
            topic, duration, educational_level, style, memory_hints
        )
        data = await llm_service._chat_json(LESSON_PLANNER_SYSTEM, prompt)
        plan = LessonPlan.model_validate(data)
        logger.info(
            f"[LESSON_PLANNER] Plan generated for '{topic}' "
            f"(complexity={plan.concept_complexity}, scenes={plan.estimated_scene_count}, "
            f"domain={plan.domain})"
        )
        return plan
    except Exception as exc:
        logger.warning(
            f"[LESSON_PLANNER] Lesson planning failed for '{topic}': {exc}. "
            "Using default fallback plan."
        )
        return _build_default_plan(topic, duration)


def _build_default_plan(topic: str, duration: int) -> LessonPlan:
    """Return a sensible default lesson plan when LLM call fails.

    Selects scene count and sequence based on duration as a proxy for complexity.
    """
    if duration <= 45:
        count = 5
        seq = [
            "HOOK",
            "EXPLANATION",
            "EXAMPLE",
            "REAL_WORLD_APPLICATION",
            "SUMMARY",
        ]
    elif duration <= 75:
        count = 6
        seq = [
            "HOOK",
            "INTUITION",
            "EXPLANATION",
            "EXAMPLE",
            "REAL_WORLD_APPLICATION",
            "SUMMARY",
        ]
    elif duration <= 120:
        count = 8
        seq = [
            "HOOK",
            "INTUITION",
            "EXPLANATION",
            "EXAMPLE",
            "CAUSE_EFFECT",
            "COMPARISON",
            "REAL_WORLD_APPLICATION",
            "SUMMARY",
        ]
    else:
        count = 10
        seq = [
            "HOOK",
            "INTUITION",
            "EXPLANATION",
            "EXAMPLE",
            "VISUALIZATION",
            "FORMULA",
            "CAUSE_EFFECT",
            "COMPARISON",
            "REAL_WORLD_APPLICATION",
            "SUMMARY",
        ]

    return LessonPlan(
        learning_objectives=[
            f"Understand the core concept of {topic}",
            f"Explain {topic} in simple, intuitive terms",
            f"Connect {topic} to at least one real-world application",
        ],
        scene_sequence=seq,
        concept_complexity="medium",
        estimated_scene_count=count,
        recommended_examples=[],
        domain="general",
    )
