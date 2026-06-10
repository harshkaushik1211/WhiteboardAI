"""Timing constants and helpers for script, animation, and video sync."""

import re
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from models.schemas import SceneElement, ScenePlanSchema, SceneSchema, ScriptSchema

# Video
FPS = 30

# Speech rate for narration budgeting (~150 wpm)
WORDS_PER_SECOND = 2.2

# Animation pacing (seconds)
MIN_STROKE_REVEAL_SEC = 4.5
MIN_FADE_SEC = 2.0
MIN_HIGHLIGHT_SEC = 1.5
SCENE_END_HOLD_SEC = 1.5
MIN_SCENE_SEC = 5.0

# Canvas layout (1920x1080)
CANVAS_W = 1920
CANVAS_H = 1080
CANVAS_CENTER_X = 960
CANVAS_CENTER_Y = 540
DEFAULT_SHAPE_W = 380
DEFAULT_SHAPE_H = 320
MIN_SHAPE_W = 280
MAX_SHAPE_W = 560
MIN_TEXT_W = 500
TEXT_FONT_BASE = 42


def max_words_for_duration(seconds: float) -> int:
    return max(8, int(seconds * WORDS_PER_SECOND))


def trim_narration(text: str, duration_sec: float) -> str:
    """Trim narration so TTS fits within allocated scene time."""
    words = text.split()
    limit = max_words_for_duration(duration_sec)
    if len(words) <= limit:
        return text
    trimmed = " ".join(words[:limit])
    if not trimmed.endswith((".", "!", "?")):
        trimmed += "."
    return trimmed


def normalize_script_durations(script: "ScriptSchema", target_seconds: int) -> "ScriptSchema":
    """Preserve educational narration; proportionally scale scene durations to target.

    EDUCATIONAL QUALITY UPGRADE (Option B):
    ========================================
    OLD behaviour: truncated narration text to fit a hard word budget, causing
    explanation loss, missing analogies, and textbook-style output.

    NEW behaviour:
    1. Compute each scene's natural speaking duration from actual word count.
    2. Proportionally scale ALL scene durations so the total stays close to
       target_seconds (soft constraint, clamped to 70%–200% scaling).
    3. Fix rounding drift on the last scene.

    Result: narration is NEVER truncated. Educational quality is the primary
    constraint. Target duration is a soft constraint.
    """
    scenes = script.scenes
    if not scenes:
        script.total_duration = float(target_seconds)
        return script

    # Step 1: Compute natural speaking duration for each scene from word count.
    # Add 0.8 s per scene as a visual-hold buffer (animations need time to settle).
    for s in scenes:
        word_count = len((s.narration or "").split())
        natural_dur = (word_count / WORDS_PER_SECOND) + 0.8
        s.duration = max(MIN_SCENE_SEC, round(natural_dur, 1))

    # Step 2: Proportionally scale to target (soft constraint).
    # Clamp factor to [0.70, 2.00] to prevent extreme compression or inflation.
    total = sum(s.duration for s in scenes)
    if total > 0 and abs(total - target_seconds) > 1.0:
        factor = target_seconds / total
        factor = max(0.70, min(2.0, factor))
        for s in scenes:
            s.duration = max(MIN_SCENE_SEC, round(s.duration * factor, 1))

    # Step 3: Fix rounding drift — assign remainder to the last scene.
    total = sum(s.duration for s in scenes)
    diff = round(target_seconds - total, 1)
    if diff != 0 and scenes:
        scenes[-1].duration = max(MIN_SCENE_SEC, round(scenes[-1].duration + diff, 1))

    script.total_duration = float(target_seconds)
    return script


def get_dynamic_threshold(lesson_plan: dict, educational_level: str) -> float:
    """Calculate the dynamic quality threshold based on pedagogical complexity.

    Very Simple:      0.60
    Medium:           0.70
    Complex:          0.75
    Very Complex:     0.80

    Adjustments:
      - college or competitive_exam: +0.02 (higher rigor expected)
      - middle_school: -0.02 (adapted to simpler explanations)
      - >= 4 objectives: +0.01 (coverage expectation adjustment)
    """
    complexity = lesson_plan.get("concept_complexity", "medium").lower()
    
    # Base threshold from complexity
    if complexity in ("simple", "very_simple"):
        threshold = 0.60
    elif complexity == "medium":
        threshold = 0.70
    elif complexity == "complex":
        threshold = 0.75
    elif complexity in ("very_complex", "expert"):
        threshold = 0.80
    else:
        threshold = 0.70
        
    # Adjust for educational level
    if educational_level in ("college", "competitive_exam"):
        threshold += 0.02
    elif educational_level == "middle_school":
        threshold -= 0.02
        
    # Adjust for objectives count
    num_objs = len(lesson_plan.get("learning_objectives", []))
    if num_objs >= 4:
        threshold += 0.01
        
    # Clamp to prevent extreme values
    return round(max(0.55, min(0.85, threshold)), 2)


def min_animation_duration(animation: str) -> float:
    if animation == "static":
        return 0.0
    if animation in ("stroke_reveal", "sketch_reveal"):
        return MIN_STROKE_REVEAL_SEC
    if animation in ("fade_in", "scale_in"):
        return MIN_FADE_SEC
    if animation == "highlight":
        return MIN_HIGHLIGHT_SEC
    return MIN_FADE_SEC


def is_layer_sketch_element(el: "SceneElement") -> bool:
    return bool(el.id and re.search(r"-layer-\d+$", el.id))


def is_sketch_image_element(el: "SceneElement") -> bool:
    return el.type == "image" and bool(el.id and el.id.endswith("-sketch"))


def apply_sketch_image_timing(plan: "ScenePlanSchema", scene_duration: float) -> None:
    """Single PNG sketch: draw-on reveal in first ~45% of scene."""
    from models.schemas import Size

    sketch_els = [e for e in plan.elements if is_sketch_image_element(e)]
    if not sketch_els:
        return
    usable = max(scene_duration - SCENE_END_HOLD_SEC, MIN_SCENE_SEC * 0.5)
    for el in sketch_els:
        el.animation = "sketch_reveal"
        el.delay = 0.15
        el.duration = max(4.0, usable * 0.58)
        el.size = Size(w=float(CANVAS_W), h=float(CANVAS_H))


def apply_layer_sketch_timing(plan: "ScenePlanSchema", scene_duration: float) -> None:
    """Stagger scene-N-layer-M elements: draw layer 1, then 2, then 3."""
    from models.schemas import Size

    layer_els = [e for e in plan.elements if is_layer_sketch_element(e)]
    if not layer_els:
        return

    usable = max(scene_duration - SCENE_END_HOLD_SEC, MIN_SCENE_SEC * 0.5)
    if len(layer_els) == 1:
        el = layer_els[0]
        el.animation = "stroke_reveal"
        el.delay = 0.2
        el.duration = max(2.5, usable * 0.50)
        el.size = Size(w=float(CANVAS_W), h=float(CANVAS_H))
        return

    def _layer_num(el: "SceneElement") -> int:
        m = re.search(r"-layer-(\d+)$", el.id or "")
        return int(m.group(1)) if m else 0

    layer_els.sort(key=_layer_num)
    # Finish all layers in ~50% of scene so narration can run after drawings appear
    draw_budget = usable * 0.50
    n = len(layer_els)
    per_layer = draw_budget / n
    gap = per_layer * 0.05
    min_stroke = 1.5

    for i, el in enumerate(layer_els):
        el.animation = "stroke_reveal"
        el.delay = 0.15 + i * (per_layer + gap)
        el.duration = max(min_stroke, per_layer * 0.88)
        el.size = Size(w=float(CANVAS_W), h=float(CANVAS_H))


def is_static_headline(el: "SceneElement") -> bool:
    if is_sketch_image_element(el):
        return False
    if el.animation == "static":
        return True
    if el.id and el.id.startswith("scene-headline-"):
        return True
    return False


def enhance_scene_layout(plan: "ScenePlanSchema", scene_duration: float) -> "ScenePlanSchema":
    """Upscale elements and spread animation timing across the scene."""
    from models.schemas import Size, Position

    elements = plan.elements
    if not elements:
        return plan

    n = len(elements)
    usable = max(scene_duration - SCENE_END_HOLD_SEC, MIN_SCENE_SEC * 0.5)

    for i, el in enumerate(elements):
        if is_static_headline(el):
            el.animation = "static"
            el.delay = 0.0
            el.duration = scene_duration
            continue

        # Larger sizes — use more of the whiteboard
        if el.type in ("text", "label"):
            text_len = len(el.text or el.label or "")
            w = min(900, max(MIN_TEXT_W, 40 * text_len))
            el.size = Size(w=w, h=90 if el.type == "label" else 110)
            if el.position:
                el.position.x = max(200, min(CANVAS_W - 200, el.position.x))
                el.position.y = max(120, min(200, el.position.y))
        elif el.type == "svg":
            if not el.size:
                el.size = Size(w=DEFAULT_SHAPE_W, h=DEFAULT_SHAPE_H)
        elif el.type == "svg_shape":
            if el.size:
                el.size.w = max(MIN_SHAPE_W, min(MAX_SHAPE_W, el.size.w * 1.2))
                el.size.h = max(MIN_SHAPE_W * 0.65, min(MAX_SHAPE_W, el.size.h * 1.2))
            else:
                el.size = Size(w=DEFAULT_SHAPE_W, h=DEFAULT_SHAPE_H)
        elif el.type == "arrow":
            if el.from_point and el.to_point:
                # Scale arrow span if too short
                dx = el.to_point.x - el.from_point.x
                dy = el.to_point.y - el.from_point.y
                length = (dx * dx + dy * dy) ** 0.5
                if length < 200:
                    scale = 280 / max(length, 1)
                    mx = (el.from_point.x + el.to_point.x) / 2
                    my = (el.from_point.y + el.to_point.y) / 2
                    el.from_point.x = mx - dx * scale / 2
                    el.from_point.y = my - dy * scale / 2
                    el.to_point.x = mx + dx * scale / 2
                    el.to_point.y = my + dy * scale / 2

        min_dur = min_animation_duration(el.animation)
        el.duration = max(el.duration, min_dur)

        if el.id == "photosynthesis-diagram" and el.animation == "stroke_reveal":
            el.delay = 0.2
            el.duration = max(6.0, min_dur, usable * 0.88)
            continue

        if is_layer_sketch_element(el) or is_sketch_image_element(el):
            continue

        if el.id.endswith("-sketch") and el.animation in ("stroke_reveal", "sketch_reveal"):
            el.delay = 0.2
            el.duration = max(5.0, min_dur, usable * 0.85)
            continue

        # Spread draws across first ~75% of scene so they finish before transition
        slot = usable * 0.75 / n
        el.delay = 0.4 + i * slot * 0.55
        el.duration = max(min_dur, min(slot * 1.1, usable * 0.4))

    return plan


def calculate_min_anim_need(plan: "ScenePlanSchema") -> float:
    """Calculate the minimum required time to run active animations without stretching."""
    non_static = [el for el in plan.elements if not is_static_headline(el)]
    if not non_static:
        return 0.0

    # If there is a sketch image or layer sketches, it is a drawing scene
    has_sketches = any(
        is_sketch_image_element(el) or is_layer_sketch_element(el)
        for el in non_static
    )
    if has_sketches:
        # Drawing takes at least 4.0s to 4.5s
        return 4.5

    # Normal fade/reveal elements: stagger them with a minimum gap of 0.4s
    max_end = 0.0
    for i, el in enumerate(non_static):
        min_dur = min_animation_duration(el.animation)
        end = (i * 0.4) + min_dur
        max_end = max(max_end, end)
    return max_end


def scene_duration_seconds(
    plan: "ScenePlanSchema",
    voice_duration: float,
    script_scene_duration: float,
) -> float:
    """Scene length = longest of voice requirement or animation requirement."""
    # Safety fallback: if voice duration is invalid/zero, use planner's estimated duration
    effective_voice_dur = voice_duration if voice_duration > 0 else script_scene_duration

    min_anim_need = calculate_min_anim_need(plan)
    anim_need = min_anim_need + SCENE_END_HOLD_SEC
    # Enforce longest duration strategy
    return max(
        effective_voice_dur + 0.5,
        anim_need + 0.3,
        MIN_SCENE_SEC,
    )


def fit_scene_durations_to_target(
    durations: List[float],
    target_total: float,
) -> List[float]:
    """Adjust scene lengths to hit target video duration."""
    if not durations:
        return durations
    total = sum(durations)
    if total <= 0:
        return durations
    if abs(total - target_total) < 0.5:
        return durations
    if total > target_total:
        factor = target_total / total
        return [max(MIN_SCENE_SEC, d * factor) for d in durations]
    # Under target: add hold to final scene
    out = list(durations)
    out[-1] += target_total - total
    return out
