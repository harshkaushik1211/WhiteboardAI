import json
from pathlib import Path
from typing import List, Optional

from models.schemas import (
    RenderElement,
    RenderManifest,
    RenderScene,
    ScenePlanSchema,
    SceneVoiceResult,
    ScriptSchema,
    SubtitleEntry,
)
from services.speech_sync import (
    build_subtitles_for_scene,
    schedule_scene_animations_to_voice,
)
from services.svg_utils import load_library_svg
from utils.file_manager import project_dir, save_json
from utils.timing import (
    FPS,
    fit_scene_durations_to_target,
    is_layer_sketch_element,
    is_sketch_image_element,
    is_static_headline,
    min_animation_duration,
    scene_duration_seconds,
)


def _seconds_to_frames(seconds: float) -> int:
    return max(1, int(seconds * FPS))


def build_render_manifest(
    project_id: str,
    script: ScriptSchema,
    scene_plans: List[ScenePlanSchema],
    voice_results: List[SceneVoiceResult],
    target_duration: Optional[float] = None,
) -> RenderManifest:
    import copy
    import logging
    logger = logging.getLogger("timeline_sync")

    script_copy = copy.deepcopy(script)
    voice_by_scene = {v.scene_id: v for v in voice_results}

    # Map scene_id to original planned duration for stats and overflow analysis
    original_planned_durations = {s.scene_id: s.duration for s in script.scenes}

    # Scene length = max(voice, animation need); then fit total to target if set
    raw_durations: List[float] = []
    for plan in scene_plans:
        scene_script = next(
            (s for s in script_copy.scenes if s.scene_id == plan.scene_id), None
        )
        voice = voice_by_scene.get(plan.scene_id)
        script_dur = scene_script.duration if scene_script else 8.0
        voice_dur = voice.duration if voice else 0.0
        raw_durations.append(
            scene_duration_seconds(plan, voice_dur, script_dur)
        )

    if target_duration and target_duration > 0:
        scene_durations = fit_scene_durations_to_target(raw_durations, float(target_duration))
    else:
        scene_durations = raw_durations

    # Enforce STEP 4: VALIDATION PASS (Ensuring final scene_durations >= voice_dur + 0.5)
    buffer = 0.5
    for i, plan in enumerate(scene_plans):
        voice = voice_by_scene.get(plan.scene_id)
        voice_dur = voice.duration if voice else 0.0
        
        # Enforce safety fallback: if voice_dur <= 0, fallback to planned_dur
        effective_voice_dur = voice_dur if voice_dur > 0 else original_planned_durations.get(plan.scene_id, 8.0)
        
        # Calculate minimum anim_need
        from utils.timing import calculate_min_anim_need
        min_anim_need = calculate_min_anim_need(plan)
        anim_need = min_anim_need + 1.5  # SCENE_END_HOLD_SEC = 1.5

        min_allowed = max(
            effective_voice_dur + buffer,
            anim_need + 0.3,
            5.0,  # MIN_SCENE_SEC = 5.0
        )
        if scene_durations[i] < min_allowed:
            scene_durations[i] = min_allowed

    current_frame = 0
    render_scenes: List[RenderScene] = []

    diagnostics = []
    worst_scene_id = None
    worst_overflow_seconds = 0.0
    overflow_scenes_count = 0

    actuals = []
    finals = []
    buffers_diffs = []
    errors = []

    for i, plan in enumerate(scene_plans):
        duration_sec = scene_durations[i]
        scene_script = next(
            (s for s in script_copy.scenes if s.scene_id == plan.scene_id), None
        )
        if scene_script:
            scene_script.duration = duration_sec

        voice = voice_by_scene.get(plan.scene_id)
        voice_dur = voice.duration if voice else 0.0
        effective_voice_dur = voice_dur if voice_dur > 0 else original_planned_durations.get(plan.scene_id, 8.0)

        # Re-enhance layout with the final duration (Step 3 feedback comment)
        from utils.timing import enhance_scene_layout
        enhance_scene_layout(plan, duration_sec)

        # Schedule animations to the voice with final duration
        schedule_scene_animations_to_voice(plan, voice, duration_sec)

        # Build stats
        est_dur = original_planned_durations.get(plan.scene_id, 8.0)
        diff = round(duration_sec - est_dur, 2)
        
        overflow = voice_dur - est_dur
        if overflow > 0:
            overflow_scenes_count += 1
            if overflow > worst_overflow_seconds:
                worst_overflow_seconds = round(overflow, 2)
                worst_scene_id = plan.scene_id

        diag_log = {
            "scene_id": plan.scene_id,
            "estimated_duration": est_dur,
            "actual_audio_duration": voice_dur,
            "final_scene_duration": duration_sec,
            "difference": diff
        }
        diagnostics.append(diag_log)

        logger.info(
            f"[SYNC_DIAGNOSTIC] Scene {plan.scene_id}: "
            f"Est={est_dur}s | ActualAudio={voice_dur}s | "
            f"FinalScene={duration_sec}s | Diff={diff:+}s"
        )

        actuals.append(voice_dur)
        finals.append(duration_sec)
        buffers_diffs.append(duration_sec - voice_dur)
        errors.append(abs(diff))

        duration_frames = _seconds_to_frames(duration_sec)
        usable_sec = max(duration_sec - 1.2, 4.0)

        # Call the motion timeline scheduler (Component 6)
        from services.motion_timeline import schedule_motion_timeline
        motion_schedule = schedule_motion_timeline(plan.elements, duration_sec)

        elements = []
        raw_ends: List[float] = []

        for el in plan.elements:
            svg_content = None
            svg_path = el.svg_path
            image_src = None
            stroke_data = None
            if getattr(el, "image_path", None):
                full = project_dir(project_id) / el.image_path
                if full.exists():
                    image_src = str(full.resolve())
            stroke_rel = getattr(el, "stroke_data_path", None)
            if not stroke_rel and getattr(el, "image_path", None) and (
                el.id or ""
            ).endswith("-sketch"):
                from services.png_stroke_extractor import stroke_json_path_for_sketch

                stroke_rel = stroke_json_path_for_sketch(el.image_path)
            ink_image_src = None
            if stroke_rel:
                stroke_full = project_dir(project_id) / stroke_rel
                if stroke_full.exists():
                    stroke_data = json.loads(
                        stroke_full.read_text(encoding="utf-8")
                    )
            if stroke_data and stroke_data.get("ink_image"):
                ink_full = project_dir(project_id) / stroke_data["ink_image"]
                if ink_full.exists():
                    ink_image_src = str(ink_full.resolve())
            elif getattr(el, "image_path", None):
                from services.png_stroke_extractor import ink_image_path_for_sketch

                ink_rel = ink_image_path_for_sketch(el.image_path)
                ink_full = project_dir(project_id) / ink_rel
                if ink_full.exists():
                    ink_image_src = str(ink_full.resolve())
            if svg_path:
                full = project_dir(project_id) / svg_path
                if full.exists():
                    svg_content = full.read_text(encoding="utf-8")
            elif el.asset_library_path and el.type != "image":
                svg_content = load_library_svg(el.asset_library_path)
            elif el.type in ("text", "label"):
                from services.svg_utils import generate_text_svg
                w = el.size.w if el.size else 500
                h = el.size.h if el.size else 80
                svg_content = generate_text_svg(el.text or el.label or "", w, h)
            elif el.type == "arrow" and el.from_point and el.to_point:
                from services.svg_utils import generate_arrow_svg
                svg_content = generate_arrow_svg(
                    el.from_point.x, el.from_point.y,
                    el.to_point.x, el.to_point.y,
                    el.label,
                )

            if is_static_headline(el):
                elements.append(
                    (el, svg_content, 0.0, duration_sec, image_src, stroke_data, ink_image_src)
                )
                continue

            delay, end_time = motion_schedule.get(el.id, (el.delay, el.delay + el.duration))
            anim_dur = max(end_time - delay, min_animation_duration(el.animation))
            raw_ends.append(delay + anim_dur)

            elements.append(
                (el, svg_content, delay, anim_dur, image_src, stroke_data, ink_image_src)
            )

        # Fit animations to narration length (voice-aligned plan), cap at ~85% of scene
        voice_sec = voice.duration if voice and voice.duration > 0 else usable_sec
        budget = min(usable_sec * 0.85, max(voice_sec * 0.82, usable_sec * 0.5))
        max_end = max(raw_ends) if raw_ends else 0
        time_scale = 1.0
        if max_end > budget and max_end > 0:
            time_scale = budget / max_end

        def _min_anim_sec(el) -> float:
            if is_layer_sketch_element(el):
                return 1.2
            if is_sketch_image_element(el):
                return 1.5
            if el.animation == "stroke_reveal":
                return 2.0
            if el.animation == "sketch_reveal":
                return 1.5
            return min_animation_duration(el.animation) * 0.5

        render_elements: List[RenderElement] = []
        for el, svg_content, delay, anim_dur, image_src, stroke_data, ink_image_src in elements:
            if is_static_headline(el):
                start_frame = 0
                end_frame = max(1, duration_frames - 1)
            else:
                delay *= time_scale
                anim_dur *= time_scale
                min_sec = _min_anim_sec(el)
                anim_dur = max(min_sec, anim_dur)

                start_frame = _seconds_to_frames(delay)
                end_frame = _seconds_to_frames(delay + anim_dur)
                min_frames = max(1, _seconds_to_frames(min_sec * 0.85))
                end_frame = max(start_frame + min_frames, end_frame)
                end_frame = min(end_frame, duration_frames - 2)

            # Keep sketch element through scene end so completed art stays on screen
            if is_sketch_image_element(el) or is_layer_sketch_element(el):
                end_frame = max(end_frame, duration_frames - 3)

            render_elements.append(
                RenderElement(
                    id=el.id,
                    type=el.type,
                    shape=el.shape,
                    position=el.position,
                    size=el.size,
                    from_point=el.from_point,
                    to_point=el.to_point,
                    animation=el.animation,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    label=el.label,
                    text=el.text,
                    color=el.color,
                    svg_content=svg_content,
                    svg_path=el.svg_path,
                    image_src=image_src,
                    stroke_data=stroke_data,
                    ink_image_src=ink_image_src,
                    action=getattr(el, "action", None),
                    animation_intent=getattr(el, "animation_intent", None),
                    motion_profile=getattr(el, "motion_profile", None),
                    target_id=getattr(el, "target_id", None),
                )
            )

        subtitles = build_subtitles_for_scene(voice, scene_script, duration_frames)

        render_scenes.append(
            RenderScene(
                scene_id=plan.scene_id,
                start_frame=current_frame,
                duration_frames=duration_frames,
                audio=voice.audio_path if voice else None,
                narration=scene_script.narration if scene_script else "",
                subtitles=subtitles,
                elements=render_elements,
                camera=plan.camera,
            )
        )
        current_frame += duration_frames

    # STEP 8: Generate synchronization report & save scene plans on disk
    avg_audio = round(sum(actuals) / len(actuals), 2) if actuals else 0.0
    avg_scene = round(sum(finals) / len(finals), 2) if finals else 0.0
    avg_buffer = round(sum(buffers_diffs) / len(buffers_diffs), 2) if buffers_diffs else 0.0
    max_err = round(max(errors), 2) if errors else 0.0
    avg_err = round(sum(errors) / len(errors), 2) if errors else 0.0

    # Sync health classification
    if max_err < 0.3:
        sync_health = "excellent"
    elif max_err <= 0.8:
        sync_health = "good"
    elif max_err <= 1.5:
        sync_health = "acceptable"
    else:
        sync_health = "poor"

    sync_passed = all(f >= a + 0.49 for f, a in zip(finals, actuals))

    sync_report = {
        "total_scenes": len(scene_plans),
        "max_duration_error": max_err,
        "average_duration_error": avg_err,
        "audio_overflow_scenes": overflow_scenes_count,
        "worst_scene_id": worst_scene_id,
        "worst_overflow_seconds": worst_overflow_seconds,
        "average_audio_duration": avg_audio,
        "average_scene_duration": avg_scene,
        "configured_buffer": buffer,
        "effective_average_buffer": avg_buffer,
        "sync_passed": sync_passed,
        "sync_health": sync_health,
        "scene_diagnostics": diagnostics
    }

    # Save sync report and modified scene plans to disk
    save_json(project_id, "sync_report.json", sync_report)
    save_json(project_id, "scene_plans.json", [p.model_dump() for p in scene_plans])

    logger.info(
        f"[SYNC_REPORT] Sync health: {sync_health.upper()} | "
        f"Max error: {max_err}s | Avg error: {avg_err}s | "
        f"Overflow scenes: {overflow_scenes_count} (Worst: Scene {worst_scene_id} by {worst_overflow_seconds}s)"
    )

    manifest = RenderManifest(
        title=script.title,
        fps=FPS,
        width=1920,
        height=1080,
        total_frames=current_frame,
        scenes=render_scenes,
    )

    save_json(project_id, "render_manifest.json", manifest.model_dump(by_alias=True))
    return manifest


