import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from config import settings
from models.schemas import PipelineStep, RenderManifest, ScriptSchema, LanguageMode
from services.scene_planner import build_visual_scenes
from services.timeline_sync import build_render_manifest
from services.voice_service import generate_voices_for_script  # kept for backward compat
from services.voice.factory import get_voice_provider, get_provider_key
from services.avatar.factory import get_avatar_provider, get_avatar_provider_key
from services.llm_service import llm_service
from utils.file_manager import load_json, project_dir, save_json
from utils.job_queue import job_queue


async def run_full_pipeline(
    job_id: str,
    project_id: str,
    topic: str,
    duration: int,
    style: str,
    voice: str,
    language: str,
    educational_level: str = "high_school",
    language_mode: str = "english",
    tts_provider: str = "edge_tts",
) -> None:
    try:
        import logging
        logger = logging.getLogger("render_service")

        job_queue.update_job(job_id, step=PipelineStep.SCRIPT, progress=5, message="Planning lesson...")

        from utils.timing import normalize_script_durations
        from services.semantic_visual_planner import _load_semantic_memory, _resolve_memory_entry

        memory = _load_semantic_memory()
        memory_hints = _resolve_memory_entry(topic, memory)
        lang_mode = LanguageMode(language_mode)

        # ── Lesson Plan: reuse existing if available, else generate fresh ───────
        existing_plan = load_json(project_id, "lesson_plan.json")
        if existing_plan:
            lesson_plan_dict = existing_plan
            logger.info(f"[PIPELINE] Reusing existing lesson plan for '{topic}'")
        else:
            from services.lesson_planner import generate_lesson_plan
            lesson_plan_obj = await generate_lesson_plan(
                topic, duration, educational_level, style, memory_hints
            )
            lesson_plan_dict = lesson_plan_obj.model_dump()
            save_json(project_id, "lesson_plan.json", lesson_plan_dict)
            logger.info(f"[PIPELINE] Generated new lesson plan for '{topic}'")

        job_queue.update_job(job_id, step=PipelineStep.SCRIPT, progress=12, message="Generating educational script...")

        # ── Educational Script Generation ───────────────────────────────────────
        script_data = await llm_service.generate_script(
            topic, duration, style, language,
            educational_level=educational_level,
            lesson_plan=lesson_plan_dict,
            language_mode=lang_mode,
        )

        # ── Narration Quality Review (with dynamic thresholds & cost controls) ──
        from utils.timing import get_dynamic_threshold
        threshold = get_dynamic_threshold(lesson_plan_dict, educational_level)
        attempts = 0
        max_attempts = 2

        # Save defaults in case review is disabled
        quality_data = {
            "overall_score": 1.0,
            "needs_rewrite": False,
            "rewrite_reasons": [],
            "structured_feedback": {},
        }

        if settings.quality_review_enabled:
            quality_data = await llm_service.review_script_quality(script_data, educational_level, lesson_plan_dict, lang_mode)
            quality_data["threshold_applied"] = threshold
            save_json(project_id, "script_quality_review.json", quality_data)

            # ── Step 4: Auto-rewrite loop with cost controls (MAX_REWRITE_ATTEMPTS = 2) ──
            best_script = script_data
            best_score = quality_data.get("overall_score", 0.0)
            best_quality = quality_data

            while settings.rewrite_enabled and (
                quality_data.get("needs_rewrite", False) or
                quality_data.get("overall_score", 1.0) < threshold
            ) and attempts < max_attempts:
                attempts += 1
                logger.warning(
                    f"[SCRIPT_QUALITY] Score {quality_data.get('overall_score', '?'):.2f} below "
                    f"threshold ({threshold:.2f}). Attempting rewrite {attempts}/{max_attempts} in pipeline. "
                    f"Reasons: {quality_data.get('rewrite_reasons', [])}"
                )
                job_queue.update_job(
                    job_id, step=PipelineStep.SCRIPT, progress=12 + attempts * 3,
                    message=f"Improving educational quality (attempt {attempts})..."
                )
                # Inject structured review feedback directly into lesson plan for the LLM
                lesson_plan_dict["quality_feedback"] = quality_data.get("rewrite_reasons", [])
                lesson_plan_dict["structured_feedback"] = quality_data.get("structured_feedback", {})

                script_data = await llm_service.generate_script(
                    topic, duration, style, language,
                    educational_level=educational_level,
                    lesson_plan=lesson_plan_dict,
                    language_mode=lang_mode,
                )
                quality_data = await llm_service.review_script_quality(script_data, educational_level, lesson_plan_dict, lang_mode)
                quality_data["threshold_applied"] = threshold
                save_json(project_id, "script_quality_review.json", quality_data)

                score = quality_data.get("overall_score", 0.0)
                if score > best_score:
                    best_score = score
                    best_script = script_data
                    best_quality = quality_data

            # Fall back to best version generated if all attempts failed
            script_data = best_script
            quality_data = best_quality

        # Save validation telemetry/audit logs
        validation_telemetry = getattr(llm_service, "last_language_validation", None)
        if validation_telemetry:
            quality_data["language_validation"] = validation_telemetry
            save_json(project_id, "script_quality_review.json", quality_data)

        # ── Store Pedagogical Metrics (Phase 3) ──────────────────────────────────
        metrics_data = {
            "engagement_score": quality_data.get("engagement_score", 1.0),
            "clarity_score": quality_data.get("clarity_score", 1.0),
            "coverage_score": quality_data.get("coverage_score", 1.0),
            "visual_synchronization_score": quality_data.get("visual_synchronization_score", 1.0),
            "threshold": threshold if settings.quality_review_enabled else 0.0,
            "rewrite_attempts": attempts,
            "passed": not (
                quality_data.get("needs_rewrite", False) or
                quality_data.get("overall_score", 1.0) < (threshold if settings.quality_review_enabled else 0.0)
            )
        }
        if validation_telemetry:
            metrics_data["language_validation"] = validation_telemetry
        save_json(project_id, "pedagogical_metrics.json", metrics_data)

        script = ScriptSchema.model_validate(script_data)
        script.language_mode = lang_mode
        for scene in script.scenes:
            scene.language_mode = lang_mode
        script = normalize_script_durations(script, duration)
        save_json(project_id, "script.json", script.model_dump())

        # Generate project_manifest.json
        manifest_data = {
            "language_mode": lang_mode.value,
            "requested_language": lang_mode.value,
            "screen_language": "english",
            "narration_language": lang_mode.value,
            "tts_provider": tts_provider,
        }
        save_json(project_id, "project_manifest.json", manifest_data)

        existing_cfg = load_json(project_id, "config.json") or {}
        save_json(project_id, "config.json", {
            **existing_cfg,
            "topic": topic,
            "duration": duration,
            "style": style,
            "voice": voice,
            "language": language,
            "educational_level": educational_level,
            "language_mode": lang_mode.value,
            "tts_provider": tts_provider,
        })

        job_queue.update_job(
            job_id,
            step=PipelineStep.SCENES,
            progress=20,
            message="Generating AI whiteboard images (PNG)...",
        )
        scene_plans, _audit = await build_visual_scenes(project_id, script, topic)

        job_queue.update_job(
            job_id, step=PipelineStep.SVG, progress=35, message="AI images and stroke data saved..."
        )

        # -----------------------------------------------------------------
        # Voice generation — provider-aware
        # -----------------------------------------------------------------
        provider_key = get_provider_key(project_id)

        if provider_key == "f5tts":
            # F5-TTS: check if audio has already been imported.
            cfg = load_json(project_id, "config.json") or {}
            voice_status = cfg.get("voice_generation_status", "pending")

            if voice_status != "completed":
                # Narration package was not yet imported.  Export it now so
                # the full pipeline call still does something useful.
                job_queue.update_job(
                    job_id,
                    step=PipelineStep.VOICE_EXPORTED,
                    progress=50,
                    message=(
                        "F5-TTS mode: narration package exported. "
                        "Import audio via /import-f5-audio to complete rendering."
                    ),
                )
                provider = get_voice_provider(project_id)
                await provider.generate(project_id, script, voice)
                # Cannot continue rendering without audio — stop here.
                raise RuntimeError(
                    "F5-TTS audio not yet imported. "
                    "Download the narration package, run F5-TTS, "
                    "and upload the result via /import-f5-audio."
                )

            # Audio has been imported — load voice_results from disk.
            job_queue.update_job(
                job_id, step=PipelineStep.VOICE, progress=50,
                message="F5-TTS audio loaded from import...",
            )
            from models.schemas import SceneVoiceResult
            vr_data = load_json(project_id, "voice_results.json") or []
            voice_results = [SceneVoiceResult.model_validate(r) for r in vr_data]
        else:
            # Edge-TTS: generate audio now.
            job_queue.update_job(
                job_id, step=PipelineStep.VOICE, progress=50,
                message="Generating voice narration...",
            )
            provider = get_voice_provider(project_id)
            voice_results = await provider.generate(project_id, script, voice)

        job_queue.update_job(job_id, step=PipelineStep.TIMELINE, progress=65, message="Synchronizing timeline...")
        manifest = build_render_manifest(
            project_id,
            script,
            scene_plans,
            voice_results,
            target_duration=float(duration),
        )

        # -----------------------------------------------------------------
        # Avatar generation — optional, provider-aware (P1 single clip, P7 non-blocking)
        # -----------------------------------------------------------------
        avatar_provider_key = get_avatar_provider_key(project_id)
        avatar_result = None  # AvatarResult | None

        if avatar_provider_key:
            cfg = load_json(project_id, "config.json") or {}
            avatar_status = cfg.get("avatar_generation_status", "pending")

            if avatar_status == "completed":
                # Clip has been imported — load from avatar_result.json
                from models.schemas import AvatarResult
                ar_data = load_json(project_id, "avatar_result.json") or {}
                if ar_data:
                    avatar_result = AvatarResult.model_validate(ar_data)
                    # P2 duration validation check
                    if not avatar_result.duration_valid:
                        logger.warning(
                            f"[AVATAR_PROCESSING] Duration invalid for project {project_id} "
                            f"(drift={avatar_result.duration_drift}s). "
                            "Rendering without avatar (whiteboard+audio only)."
                        )
                        avatar_result = None
                    else:
                        job_queue.update_job(
                            job_id, step=PipelineStep.AVATAR, progress=70,
                            message="Avatar clip loaded and validated.",
                        )

            elif avatar_status == "failed":
                # P7: Avatar failed — render proceeds without it
                logger.warning(
                    f"[AVATAR_PROCESSING] Avatar generation FAILED for project {project_id}. "
                    "Rendering whiteboard+audio without avatar overlay."
                )

            else:  # pending
                # Package not yet imported. Export and block with clear message.
                job_queue.update_job(
                    job_id,
                    step=PipelineStep.AVATAR_EXPORTED,
                    progress=68,
                    message=(
                        f"{avatar_provider_key}: avatar package exported. "
                        "Import via /import-sadtalker-clips to complete rendering."
                    ),
                )
                avatar_provider = get_avatar_provider(project_id)
                if avatar_provider:
                    avatar_source = cfg.get("avatar_source", "avatar/source.png")
                    await avatar_provider.generate(project_id, script, avatar_source)
                raise RuntimeError(
                    f"{avatar_provider_key} clips not yet imported. "
                    "Download the avatar package, run SadTalker, "
                    "and upload via /import-sadtalker-clips."
                )

        job_queue.update_job(job_id, step=PipelineStep.RENDER, progress=75, message="Rendering video with Remotion...")
        await _render_remotion(project_id, manifest, job_id, avatar_result=avatar_result)

        job_queue.update_job(job_id, step=PipelineStep.RENDER, progress=90, message="Encoding final video...")
        await _merge_audio_ffmpeg(project_id, manifest)

        save_json(project_id, "status.json", {"step": PipelineStep.COMPLETE.value})
        job_queue.update_job(
            job_id,
            step=PipelineStep.COMPLETE,
            progress=100,
            message="Video ready!",
        )
    except Exception as e:
        job_queue.update_job(job_id, error=str(e), message=f"Pipeline failed: {e}")
        raise


def _remotion_asset_prefix(project_id: str) -> str:
    return f"render-assets/{project_id}"


def _stage_images_for_remotion(project_id: str, manifest_dict: dict) -> None:
    """Copy project PNGs into renderer/public so Remotion staticFile() can load them."""
    renderer_public = settings.renderer_path / "public" / "render-assets" / project_id
    renderer_public.mkdir(parents=True, exist_ok=True)
    proj = project_dir(project_id)

    for scene in manifest_dict.get("scenes", []):
        for el in scene.get("elements", []):
            if el.get("type") != "image":
                continue
            raw_src = el.get("image_src")
            if not raw_src:
                if el.get("id", "").endswith("-sketch"):
                    raise RuntimeError(
                        f"Missing sketch PNG for {el.get('id')}. "
                        "Re-run the pipeline to regenerate scene images."
                    )
                continue

            src_path = Path(raw_src)
            if not src_path.is_absolute():
                src_path = proj / raw_src
            if not src_path.exists():
                raise RuntimeError(
                    f"Sketch image not found: {src_path}. "
                    "Re-run the pipeline to regenerate scene images."
                )

            dest = renderer_public / src_path.name
            shutil.copy2(src_path, dest)
            el["image_src"] = f"{_remotion_asset_prefix(project_id)}/{src_path.name}"

            ink_raw = el.get("ink_image_src")
            if ink_raw:
                ink_path = Path(ink_raw)
                if not ink_path.is_absolute():
                    ink_path = proj / ink_raw
                if ink_path.exists():
                    ink_dest = renderer_public / ink_path.name
                    shutil.copy2(ink_path, ink_dest)
                    el["ink_image_src"] = (
                        f"{_remotion_asset_prefix(project_id)}/{ink_path.name}"
                    )
            elif el.get("stroke_data", {}).get("ink_image"):
                ink_rel = el["stroke_data"]["ink_image"]
                ink_path = proj / ink_rel
                if ink_path.exists():
                    shutil.copy2(ink_path, renderer_public / ink_path.name)
                    el["ink_image_src"] = (
                        f"{_remotion_asset_prefix(project_id)}/{ink_path.name}"
                    )


def _stage_avatar_single_clip(
    project_id: str,
    manifest_dict: dict,
    avatar_result,  # AvatarResult
) -> None:
    """P1: Copy the single project avatar.webm into renderer/public and inject
    per-scene frame offsets into the manifest so Remotion shows the correct
    window of the clip for each scene.

    Args:
        project_id: Unique project identifier.
        manifest_dict: In-place mutable manifest dict (``scenes`` already populated).
        avatar_result: :class:`AvatarResult` loaded from ``avatar_result.json``.
    """
    renderer_public = settings.renderer_path / "public" / "render-assets" / project_id
    renderer_public.mkdir(parents=True, exist_ok=True)
    proj = project_dir(project_id)

    rel_path = avatar_result.clip_path
    src_path = proj / rel_path
    if not src_path.exists():
        logger.warning(
            f"[AVATAR_PROCESSING] Avatar clip not found: {src_path}; skipping overlay."
        )
        return

    dest = renderer_public / src_path.name
    shutil.copy2(src_path, dest)

    cfg = load_json(project_id, "config.json") or {}
    avatar_position = cfg.get("avatar_position", "bottom_right")
    avatar_scale = float(cfg.get("avatar_scale", 0.25))
    avatar_layout = cfg.get("avatar_layout", "pip")
    fps = manifest_dict.get("fps", 30)

    # Inject global avatar config into manifest root (P10 layout field)
    remotion_clip_src = f"{_remotion_asset_prefix(project_id)}/{src_path.name}"
    manifest_dict["avatar_clip_src"] = remotion_clip_src
    manifest_dict["avatar_position"] = avatar_position
    manifest_dict["avatar_scale"] = avatar_scale
    manifest_dict["avatar_layout"] = avatar_layout
    manifest_dict["avatar_duration_valid"] = avatar_result.duration_valid

    # Compute per-scene start_frame offset into the single avatar clip
    elapsed_frames = 0
    for scene in manifest_dict.get("scenes", []):
        scene["avatar_start_frame"] = elapsed_frames
        elapsed_frames += scene.get("duration_frames", 0)

    logger.info(
        f"[AVATAR_PROCESSING] Single avatar clip staged: {src_path.name} "
        f"position={avatar_position} scale={avatar_scale} layout={avatar_layout}"
    )


def _stage_avatar_clips_for_remotion(
    project_id: str,
    manifest_dict: dict,
    avatar_clips: dict,
) -> None:
    """Legacy per-scene clip staging (kept for backward compatibility).

    .. deprecated::
        Use :func:`_stage_avatar_single_clip` instead.  This function exists
        only so that any external code calling the old API does not break.
    """
    logger.warning(
        "[AVATAR_PROCESSING] _stage_avatar_clips_for_remotion is deprecated. "
        "Use _stage_avatar_single_clip with a single AvatarResult."
    )
    renderer_public = settings.renderer_path / "public" / "render-assets" / project_id
    renderer_public.mkdir(parents=True, exist_ok=True)
    proj = project_dir(project_id)
    config = load_json(project_id, "config.json") or {}
    avatar_position = config.get("avatar_position", "bottom_right")
    avatar_scale = config.get("avatar_scale", 0.25)
    for scene in manifest_dict.get("scenes", []):
        scene_id = scene.get("scene_id")
        if scene_id not in avatar_clips:
            continue
        rel_path = avatar_clips[scene_id]
        src_path = proj / rel_path
        if not src_path.exists():
            continue
        dest = renderer_public / src_path.name
        shutil.copy2(src_path, dest)
        scene["avatar_clip_src"] = f"{_remotion_asset_prefix(project_id)}/{src_path.name}"
        scene["avatar_position"] = avatar_position
        scene["avatar_scale"] = avatar_scale


async def _render_remotion(
    project_id: str,
    manifest: RenderManifest,
    job_id: str,
    avatar_result=None,  # AvatarResult | None  (P1 single clip)
) -> Path:
    proj_path = project_dir(project_id)
    manifest_dict = manifest.model_dump(by_alias=True)
    _stage_images_for_remotion(project_id, manifest_dict)

    # P1: Stage single avatar clip for Remotion (compute per-scene frame offsets)
    if avatar_result and avatar_result.duration_valid:
        _stage_avatar_single_clip(project_id, manifest_dict, avatar_result)

    manifest_path = proj_path / "render_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_dict, indent=2),
        encoding="utf-8",
    )

    output_path = proj_path / "videos" / "raw_video.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    renderer_path = settings.renderer_path
    env = os.environ.copy()

    # Pass full manifest via --props (Remotion bundles for browser; no Node fs)
    props_path = proj_path / "render_props.json"
    props_path.write_text(
        json.dumps({"manifest": manifest_dict}),
        encoding="utf-8",
    )

    npx_path = shutil.which("npx") or "npx"
    cmd = [
        npx_path, "remotion", "render",
        "src/index.ts",
        "WhiteboardVideo",
        str(output_path),
        "--props", str(props_path.resolve()),
        "--concurrency", str(settings.remotion_concurrency),
    ]

    log_lines: list[str] = []

    def run_remotion_sync() -> int:
        proc = subprocess.Popen(
            cmd,
            cwd=str(renderer_path),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            bufsize=1,
        )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        while True:
            line = proc.stdout.readline()
            if not line:
                break
            text = line.strip()
            if text:
                log_lines.append(text)
                match = re.search(r"(\d+)%", text)
                if match:
                    pct = int(match.group(1))
                    if loop:
                        loop.call_soon_threadsafe(
                            job_queue.update_job,
                            job_id,
                            None,
                            75 + pct * 0.15,
                            f"Rendering: {pct}%"
                        )
                    else:
                        job_queue.update_job(
                            job_id,
                            progress=75 + pct * 0.15,
                            message=f"Rendering: {pct}%"
                        )
        proc.wait()
        return proc.returncode

    return_code = await asyncio.to_thread(run_remotion_sync)

    if return_code != 0:
        log_path = proj_path / "render_log.txt"
        log_path.write_text("\n".join(log_lines[-50:]), encoding="utf-8")
        tail = "\n".join(log_lines[-8:]) if log_lines else "no output"
        raise RuntimeError(
            f"Remotion render failed with code {return_code}. Last output:\n{tail}"
        )

    return output_path


def _probe_duration(ffmpeg: str, path: str) -> float:
    ffmpeg_path = Path(ffmpeg)
    ffprobe_name = ffmpeg_path.name.replace("ffmpeg", "ffprobe").replace("FFMPEG", "FFPROBE")
    ffprobe = str(ffmpeg_path.parent / ffprobe_name)
    if not Path(ffprobe).exists() and Path("/opt/homebrew/bin/ffprobe").exists():
        ffprobe = "/opt/homebrew/bin/ffprobe"
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


async def _merge_audio_ffmpeg(project_id: str, manifest: RenderManifest) -> Path:
    proj_path = project_dir(project_id)
    raw_video = proj_path / "videos" / "raw_video.mp4"
    final_video = proj_path / "videos" / "final_video.mp4"

    ffmpeg = settings.ffmpeg_path
    fps = manifest.fps or 30
    combined_audio = proj_path / "voices" / "combined.mp3"

    scene_audio_inputs = []
    for scene in manifest.scenes:
        if not scene.audio:
            continue
        p = proj_path / scene.audio
        if not p.exists():
            continue
        scene_audio_inputs.append((scene, str(p.resolve())))

    if not scene_audio_inputs:
        if raw_video.exists():
            raw_video.rename(final_video)
        return final_video

    # Detect audio format from first scene's file extension
    first_audio_ext = Path(scene_audio_inputs[0][1]).suffix.lower()  # e.g. ".wav" or ".mp3"
    # Use mp3 for combined output (ffmpeg can always encode to mp3 regardless of source format)
    combined_audio = proj_path / "voices" / "combined.mp3"

    # Pad each scene's voice to its video slot, then concat (matches scene boundaries)
    padded_paths: List[str] = []
    for scene, audio_path in scene_audio_inputs:
        slot_sec = scene.duration_frames / fps
        padded = proj_path / "voices" / f"padded_scene_{scene.scene_id}.mp3"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                audio_path,
                "-af",
                "apad",
                "-t",
                f"{slot_sec:.3f}",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(padded),
            ],
            check=True,
            capture_output=True,
        )
        padded_paths.append(padded.resolve().as_posix())

    concat_list = proj_path / "voices" / "concat_list.txt"
    with open(concat_list, "w") as f:
        for vf in padded_paths:
            f.write(f"file '{vf}'\n")

    if len(padded_paths) > 1:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(combined_audio),
            ],
            check=True,
            capture_output=True,
        )
        audio_input = str(combined_audio)
    else:
        audio_input = padded_paths[0]

    if raw_video.exists():
        video_dur = _probe_duration(ffmpeg, str(raw_video))
        audio_dur = _probe_duration(ffmpeg, audio_input)
        pad_sec = max(0.0, audio_dur - video_dur + 0.05)

        cmd = [
            ffmpeg, "-y",
            "-i", str(raw_video),
            "-i", audio_input,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-ac", "2",
            "-movflags", "+faststart",
        ]
        if pad_sec > 0.1:
            cmd = [
                ffmpeg, "-y",
                "-i", str(raw_video),
                "-i", audio_input,
                "-filter_complex",
                f"[0:v]tpad=stop_mode=clone:stop_duration={pad_sec:.3f}[v]",
                "-map", "[v]",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-ac", "2",
                "-movflags", "+faststart",
            ]
        else:
            cmd.extend(["-shortest"])

        cmd.append(str(final_video))
        subprocess.run(cmd, check=True, capture_output=True)
    else:
        subprocess.run(
            [
                ffmpeg, "-y",
                "-f", "lavfi", "-i", f"color=c=white:s={manifest.width}x{manifest.height}:d={manifest.total_frames / manifest.fps}",
                "-i", audio_input,
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-shortest",
                str(final_video),
            ],
            check=True,
            capture_output=True,
        )

    return final_video
