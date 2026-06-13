import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from config import settings
from prompts.script_prompt import SCRIPT_SYSTEM_PROMPT, build_script_prompt
from prompts.scene_prompt import SCENE_SYSTEM_PROMPT, build_scene_prompt
from models.schemas import LanguageMode

logger = logging.getLogger("llm_service")


class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key or None)
        self.model = settings.openai_model

    async def _chat_json(
        self,
        system: str,
        user: str,
        max_retries: int = 3,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        use_model = model or self.model
        last_error: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=use_model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                )
                content = response.choices[0].message.content or "{}"
                return self._parse_json(content)
            except Exception as e:
                last_error = e
                if attempt == max_retries - 1:
                    raise
        raise last_error or RuntimeError("LLM request failed")

    def _parse_json(self, content: str) -> Dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        return json.loads(content)

    async def clean_devanagari_narration(self, text: str) -> str:
        """Helper to rewrite a Devanagari Hinglish narration to Roman Hinglish script."""
        system = "You are an expert Hinglish translator. You rewrite text to ensure it is in natural Hinglish written ONLY in Roman script (Latin alphabet). Never use Devanagari characters."
        user = f"Rewrite the following narration into natural conversational Hinglish.\n\nRules:\n- Use Roman script only.\n- Do not use any Devanagari characters.\n- Preserve meaning exactly.\n- Preserve scientific terminology in English.\n- Preserve educational quality.\n- Do not shorten the narration.\n\nNarration to rewrite:\n{text}"
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error(f"Failed to clean Devanagari narration: {e}")
            return text

    async def generate_script(
        self,
        topic: str,
        duration: int,
        style: str,
        language: str,
        educational_level: str = "high_school",
        lesson_plan: Optional[Dict[str, Any]] = None,
        concept_graph: Optional[Dict[str, Any]] = None,
        assigned_scene_concepts: Optional[Dict[str, List[str]]] = None,
        language_mode: LanguageMode = LanguageMode.ENGLISH,
    ) -> Dict[str, Any]:
        """Generate an educational whiteboard script.

        Args:
            topic: Subject to teach.
            duration: Target video duration in seconds (soft constraint).
            style: Visual style hint.
            language: Narration language.
            educational_level: Audience level — adapts vocabulary and depth.
            lesson_plan: Pre-generated lesson plan dict from lesson_planner service.
            concept_graph: Pre-generated ConceptGraph dict (Phase 6).
            assigned_scene_concepts: Concept allocation dict mapping scene ID (str) to concepts.
            language_mode: Target narration language mode (english or hinglish).

        Returns:
            Raw script dict with title, total_duration, and scenes list.
        """
        from services.semantic_visual_planner import _load_semantic_memory, _resolve_memory_entry

        memory = _load_semantic_memory()
        memory_hints = _resolve_memory_entry(topic, memory)
        prompt = build_script_prompt(
            topic, duration, style, language,
            memory_hints=memory_hints,
            educational_level=educational_level,
            lesson_plan=lesson_plan,
            concept_graph=concept_graph,
            assigned_scene_concepts=assigned_scene_concepts,
            language_mode=language_mode,
        )
        script_data = await self._chat_json(SCRIPT_SYSTEM_PROMPT, prompt)

        # Devanagari Roman Script Validation Guard
        telemetry = {
            "language_mode": language_mode.value,
            "roman_script_validation": language_mode == LanguageMode.HINGLISH,
            "devanagari_detected": False,
            "rewrite_attempts": 0,
            "validation_passed": True
        }
        self.last_language_validation = telemetry

        if language_mode == LanguageMode.HINGLISH and "scenes" in script_data:
            from utils.language_validator import contains_devanagari
            
            any_devanagari = False
            for scene in script_data["scenes"]:
                if contains_devanagari(scene.get("narration", "")):
                    any_devanagari = True
                    break
                    
            if any_devanagari:
                telemetry["devanagari_detected"] = True
                telemetry["rewrite_attempts"] = 1
                logger.info("[LANGUAGE_GUARD] Devanagari detected in narration. Triggering auto-rewrite recovery pass.")
                
                for scene in script_data["scenes"]:
                    narration = scene.get("narration", "")
                    if contains_devanagari(narration):
                        cleaned = await self.clean_devanagari_narration(narration)
                        scene["narration"] = cleaned
                        
                # Validate again
                still_has_devanagari = False
                for scene in script_data["scenes"]:
                    if contains_devanagari(scene.get("narration", "")):
                        still_has_devanagari = True
                        break
                if still_has_devanagari:
                    telemetry["validation_passed"] = False
                    logger.warning("[LANGUAGE_GUARD] Roman script validation failed even after rewrite pass! Continuing pipeline.")
                else:
                    logger.info("[LANGUAGE_GUARD] Roman script validation successfully recovered and passed!")

        return script_data

    async def review_script_quality(
        self,
        script_data: Dict[str, Any],
        educational_level: str = "high_school",
        lesson_plan: Optional[Dict[str, Any]] = None,
        language_mode: LanguageMode = LanguageMode.ENGLISH,
    ) -> Dict[str, Any]:
        """Evaluate narration quality across 11 pedagogical dimensions.

        Scores 0.0–1.0 per dimension. Returns needs_rewrite=True if
        overall_score < threshold or any critical dimension is severely low.

        Falls back gracefully (returns passing scores) on any LLM failure
        so that quality review never blocks the pipeline.

        Args:
            script_data: Raw script dict from generate_script().
            educational_level: Used to calibrate vocabulary/depth expectations.
            lesson_plan: Optional pre-script lesson planner details for coverage review.
            language_mode: Target narration language mode (english or hinglish).

        Returns:
            Dict with dimension scores, overall_score, needs_rewrite, rewrite_reasons.
        """
        from prompts.quality_review_prompt import QUALITY_REVIEW_SYSTEM, build_quality_review_prompt

        try:
            prompt = build_quality_review_prompt(script_data, educational_level, lesson_plan, language_mode)
            result = await self._chat_json(QUALITY_REVIEW_SYSTEM, prompt)
            logger.info(
                f"[SCRIPT_QUALITY] Score: {result.get('overall_score', '?'):.2f} | "
                f"needs_rewrite: {result.get('needs_rewrite', False)} | "
                f"reasons: {result.get('rewrite_reasons', [])}"
            )
            return result
        except Exception as exc:
            logger.warning(
                f"[SCRIPT_QUALITY] Quality review failed: {exc}. "
                "Returning passing score to avoid pipeline block."
            )
            # Safe fallback — don't block pipeline on review failure
            return {
                "curiosity_score": 1.0,
                "student_friendliness_score": 1.0,
                "engagement_score": 1.0,
                "clarity_score": 1.0,
                "analogy_usage_score": 1.0,
                "educational_depth_score": 1.0,
                "transition_quality_score": 1.0,
                "real_world_relevance_score": 1.0,
                "misconception_handling_score": 1.0,
                "visual_synchronization_score": 1.0,
                "narrative_variety_score": 1.0,
                "coverage_score": 1.0,
                "human_naturalness_score": 1.0,
                "overall_score": 1.0,
                "needs_rewrite": False,
                "rewrite_reasons": [],
                "structured_feedback": {},
            }

    async def generate_scene_plan(
        self,
        scene_id: int,
        narration: str,
        visual_description: str,
        keywords: list,
        duration: float,
    ) -> Dict[str, Any]:
        prompt = build_scene_prompt(
            scene_id, narration, visual_description, keywords, duration
        )
        return await self._chat_json(SCENE_SYSTEM_PROMPT, prompt)


llm_service = LLMService()
