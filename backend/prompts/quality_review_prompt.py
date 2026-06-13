# =============================================================================
# WHITEBOARD AI — NARRATION QUALITY REVIEW PROMPT
# =============================================================================
#
# Stage: Post-script quality gate (runs AFTER script generation)
# Purpose: Evaluate whether generated narration meets educational standards.
#          If score < threshold, the pipeline triggers an automatic rewrite.
# =============================================================================
import json

QUALITY_REVIEW_SYSTEM = """You are a senior educational content director, pedagogy expert, and curriculum quality reviewer.

You evaluate whiteboard video scripts to ensure they meet high educational quality standards.

You think like:
- A Khan Academy content director reviewing new lesson submissions
- An experienced teacher watching a peer's lesson and giving honest feedback
- A curriculum designer checking if learning objectives are actually addressed

You are STRICT. You have seen too many scripts that read like textbook summaries or definitions.

WHAT EXCELLENT EDUCATIONAL NARRATION LOOKS LIKE:
===============================================
- Conversational tone, spoken-lecture flow, natural teacher behaviors (e.g. Veritasium, Crash Course, Khan Academy).
- Starts with curiosity, a question, or an observation — never a definition.
- Builds intuition BEFORE introducing formal terms.
- Uses analogies for abstract concepts ("it's like water flowing through a pipe").
- Connects concepts to real life ("this is why your car brakes the way it does").
- Addresses and debunks common misconceptions naturally ("many people think... but in reality...").
- Flows naturally from scene to scene with smooth transitions.
- High sentence structure diversity; avoids repetitive phrases (e.g. starting multiple scenes with "Imagine..." or "Let's look at...").
- Narration is visually supportable — references what is actually drawn on the whiteboard.

WHAT ROBOTIC/BAD NARRATION LOOKS LIKE:
======================================
- Meta-narration: "In this video, we will learn..." or "Let's conclude by..."
- Academic passive voice: "It can be observed that..."
- Definition-first: "Newton's first law states that..." or "Force is defined as..."
- repetitive opening phrases or transitions in every scene.
- Narration references objects that are NOT shown on the whiteboard.
- Missing real-world connection or skipped objectives.

SCORING DIMENSIONS (0.0 to 1.0 each):
=======================================
1. engagement_score             — Sparks curiosity, energetic, conversational.
2. clarity_score                — Explains concepts clearly, easy to grasp.
3. analogy_usage_score          — Effective analogies for abstract ideas.
4. educational_depth_score      — Teaches "why" it works, avoids superficiality.
5. transition_quality_score     — Flows smoothly between scenes using logical links.
6. real_world_relevance_score   — Connects concept to daily student experience.
7. misconception_handling_score — Debunks misconceptions naturally.
8. visual_synchronization_score — Aligns with the whiteboard visuals, avoids referencing unshown objects, visually supportable.
9. narrative_variety_score      — Avoids repetition ("Imagine", "Let's look at", etc.). High vocabulary & syntax diversity.
10. coverage_score              — Addressed objectives fully. Key concepts covered.
11. human_naturalness_score      — Conversational, spoken tone. Sounds like a human teacher, not a textbook.

SCORING THRESHOLDS:
===================
overall_score < dynamic_threshold  → needs_rewrite = true

Output valid JSON only. No markdown. No explanation."""


from models.schemas import LanguageMode

def build_quality_review_prompt(script_data: dict, educational_level: str, lesson_plan: dict = None, language_mode: LanguageMode = LanguageMode.ENGLISH) -> str:
    """Build the quality review prompt from a generated script dict.

    Args:
        script_data: The raw dict from the LLM script generation response.
        educational_level: Target educational level for the script.
        lesson_plan: The lesson plan dictionary to check objectives/misconceptions coverage.
        language_mode: Target narration language mode (english or hinglish).

    Returns:
        Prompt string for the quality review LLM call.
    """
    title = script_data.get("title", "Unknown Topic")
    scenes = script_data.get("scenes", [])
    lesson_plan = lesson_plan or {}

    # Build a compact scene summary — narration, scene_type, transition, and visual
    scenes_for_review = []
    for scene in scenes:
        scenes_for_review.append({
            "scene_id": scene.get("scene_id"),
            "scene_type": scene.get("scene_type", "unspecified"),
            "narration": (scene.get("narration") or "")[:500],
            "visual_description": (scene.get("visual_description") or "")[:300],
            "transition_phrase": scene.get("transition_phrase", ""),
        })

    # Count programmatically the repetitive opening patterns in narration for telemetry
    lower_narrations = [s.get("narration", "").lower().strip() for s in scenes]
    repetition_stats = {
        "starts_with_imagine": sum(1 for n in lower_narrations if n.startswith("imagine")),
        "starts_with_lets": sum(1 for n in lower_narrations if n.startswith("let's") or n.startswith("lets")),
        "contains_we_can_see": sum(1 for n in lower_narrations if "we can see" in n),
        "contains_look_at": sum(1 for n in lower_narrations if "look at" in n),
    }

    # Extract target objectives, misconceptions, and prerequisites
    objectives = lesson_plan.get("learning_objectives", [])
    misconceptions = lesson_plan.get("common_misconceptions", [])
    prerequisites = lesson_plan.get("prerequisites", [])

    # Check specific red-flag patterns
    first_narration = (scenes[0].get("narration") or "") if scenes else ""
    definition_red_flags = [
        first_narration.lower().startswith(phrase)
        for phrase in [
            "in this", "today we", "this video", "we will learn", "we are going to",
            "x is defined", "is defined as", " states that", "refers to", "is the process"
        ]
    ]
    has_definition_start = any(definition_red_flags)
    has_real_world = any(
        s.get("scene_type") == "REAL_WORLD_APPLICATION" for s in scenes
    )
    has_hook = any(s.get("scene_type") == "HOOK" for s in scenes)

    # ── Language mode quality review instructions ───────────────────────────
    if language_mode == LanguageMode.HINGLISH:
        language_instructions = """
━━━ HINGLISH QUALITY REVIEW RULES (CRITICAL) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The script was generated in HINGLISH mode.
When evaluating quality:
1. Do NOT penalize the script for using Hindi words, conversational phrases, or mixed grammatical structures (Hinglish narration). This is intentional and expected.
2. Evaluate 'human_naturalness_score' and 'engagement_score' based on whether it is a natural, conversational Hinglish flow that a teacher in India would use to speak to a student (e.g. "Socho...", "Maan lo...").
3. Make sure all technical and scientific terminology (e.g. Force, Acceleration, Photosynthesis) is in English. If technical terminology is in Devanagari Hindi (e.g., "gati", "bal"), the score should be lower.
4. Ensure explanations are in Hinglish, not pure Hindi (which is dry and formal) or pure English.
5. All visual descriptions, title, and keywords should still be in English. Verify that ONLY the narration field contains Hinglish.
6. Verify that there are absolutely NO Devanagari script characters (e.g. "एक", "बल") in the narration. It must be written in Roman script only.
"""
    else:
        language_instructions = """
━━━ ENGLISH QUALITY REVIEW RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The script was generated in ENGLISH mode. Narration must be fully in professional educational English.
"""

    return f"""Review this educational whiteboard video script for narration quality.

Video Title: {title}
Educational Level: {educational_level}
Total Scenes: {len(scenes)}

Pedagogical Checkpoints:
- First scene starts with a definition: {has_definition_start}
- Has a REAL_WORLD_APPLICATION scene: {has_real_world}
- Has a HOOK scene: {has_hook}

Target Learning Objectives:
{json.dumps(objectives, indent=2, ensure_ascii=False)}

Expected Misconceptions to Address:
{json.dumps(misconceptions, indent=2, ensure_ascii=False)}

Expected Prerequisites to Respect:
{json.dumps(prerequisites, indent=2, ensure_ascii=False)}

Pedagogical Repetition Telemetry (Pre-calculated):
{json.dumps(repetition_stats, indent=2)}
(Note: high counts here should severely lower the narrative_variety_score!)

Scene Content Details:
{json.dumps(scenes_for_review, indent=2, ensure_ascii=False)}

{language_instructions}

Evaluate carefully according to the 11 SCORING DIMENSIONS.
For every dimension, output a nested structured feedback dictionary.

Your output JSON must match this schema exactly:
{{
  "curiosity_score": 0.80,  -- Keep for backward compatibility (curiosity_score = engagement_score)
  "student_friendliness_score": 0.85, -- Keep for backward compatibility (student_friendliness_score = human_naturalness_score)
  
  "engagement_score": 0.80,
  "clarity_score": 0.85,
  "analogy_usage_score": 0.70,
  "educational_depth_score": 0.75,
  "transition_quality_score": 0.80,
  "real_world_relevance_score": 0.85,
  "misconception_handling_score": 0.75,
  "visual_synchronization_score": 0.80,
  "narrative_variety_score": 0.85,
  "coverage_score": 0.90,
  "human_naturalness_score": 0.85,
  
  "overall_score": 0.81, -- average of the 11 scores above
  "needs_rewrite": false,
  "rewrite_reasons": [],
  "structured_feedback": {{
    "engagement": {{
      "rating": "good",
      "reason": "Curiosity hook in opening scene gets student attention."
    }},
    "clarity": {{
      "rating": "excellent",
      "reason": "Explanations are clear and structured."
    }},
    "analogy_usage": {{
      "rating": "weak",
      "reason": "Only one analogy used, could explain abstract ideas more concretely."
    }},
    "educational_depth": {{
      "rating": "good",
      "reason": "Goes beyond superficial definitions."
    }},
    "transition_quality": {{
      "rating": "poor",
      "reason": "Scene 3 to 4 transition is abrupt without bridging phrase."
    }},
    "real_world_relevance": {{
      "rating": "good",
      "reason": "Connected lesson to real-world experience."
    }},
    "misconception_handling": {{
      "rating": "missing",
      "reason": "Does not address the misconception that force keeps objects moving."
    }},
    "visual_synchronization": {{
      "rating": "good",
      "reason": "Visual descriptions match narrations."
    }},
    "narrative_variety": {{
      "rating": "poor",
      "reason": "Starts 3 separate scenes with the word 'Imagine'."
    }},
    "coverage": {{
      "rating": "incomplete",
      "reason": "Objective 3 (calculating force) was not covered in the scenes."
    }},
    "human_naturalness": {{
      "rating": "good",
      "reason": "Conversational, spoken-like vocabulary."
    }}
  }}
}}

Valid structured_feedback rating values: excellent, good, weak, poor, missing, incomplete.
For any rating under 'good' (weak, poor, missing, incomplete), you MUST supply a specific constructive critique in 'reason' and list it in 'rewrite_reasons'.

Output valid JSON only."""
