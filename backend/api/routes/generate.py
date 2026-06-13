import asyncio
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import Response

from config import settings
from models.schemas import (
    GenerateScriptRequest,
    GenerateScenesRequest,
    GenerateSvgRequest,
    GenerateVoiceRequest,
    GenerateAvatarRequest,
    RenderVideoRequest,
    PipelineStep,
    ProjectResponse,
    ScriptSchema,
    ScenePlanSchema,
    AvatarSceneResult,
    LanguageMode,
)
from services.llm_service import llm_service
from services.scene_planner import plan_scenes_for_script
from services.voice_service import generate_voices_for_script  # kept for backward compat
from services.voice.factory import get_voice_provider, get_provider_key
from services.voice.exporter import F5ExportService
from services.voice.importer import F5ImportService
from services.timeline_sync import build_render_manifest
from services.render_service import run_full_pipeline
from utils.file_manager import (
    ensure_project_dirs,
    load_json,
    new_project_id,
    project_dir,
    save_json,
    list_voice_files,
    list_audio_files,
)
from utils.job_queue import job_queue
from utils.timing import normalize_script_durations

router = APIRouter()


def _get_script(project_id: str) -> ScriptSchema:
    data = load_json(project_id, "script.json")
    if not data:
        raise HTTPException(404, "Script not found. Run /generate-script first.")
    return ScriptSchema.model_validate(data)


@router.post("/generate-script")
async def generate_script(req: GenerateScriptRequest):
    import logging
    logger = logging.getLogger("generate_script")

    project_id = new_project_id()
    ensure_project_dirs(project_id)
    educational_level = req.educational_level

    # ── Step 1: Lesson Planning ───────────────────────────────────────────────
    # Generate a pedagogically-sound lesson plan BEFORE script generation.
    # Produces learning objectives, scene sequence, complexity, and examples.
    from services.lesson_planner import generate_lesson_plan
    from services.semantic_visual_planner import _load_semantic_memory, _resolve_memory_entry
    memory = _load_semantic_memory()
    memory_hints = _resolve_memory_entry(req.topic, memory)

    lesson_plan_obj = await generate_lesson_plan(
        req.topic, req.duration, educational_level, req.style, memory_hints
    )
    lesson_plan_dict = lesson_plan_obj.model_dump()
    save_json(project_id, "lesson_plan.json", lesson_plan_dict)
    logger.info(
        f"[PIPELINE] Lesson plan ready for '{req.topic}' "
        f"(complexity={lesson_plan_obj.concept_complexity}, "
        f"scenes={lesson_plan_obj.estimated_scene_count})"
    )

    # ── Step 1.5: Concept Decomposition & Allocation (Phase 6) ──────────────────
    from services.concept_decomposer import (
        generate_concept_graph,
        allocate_scene_concepts,
        validate_concept_diversity,
        validate_coverage,
    )

    # 1. Generate Concept Graph
    concept_graph = await generate_concept_graph(req.topic, lesson_plan_obj)
    save_json(project_id, "concept_graph.json", concept_graph.model_dump())

    # 2. Perform Scene Concept Allocation with validation and re-try limits
    num_scenes = lesson_plan_obj.estimated_scene_count
    allocation = allocate_scene_concepts(concept_graph, lesson_plan_obj, num_scenes)

    diversity = {}
    coverage = {}

    for attempt in range(3):
        diversity = validate_concept_diversity(allocation, num_scenes)
        coverage = validate_coverage(concept_graph, lesson_plan_obj, allocation)

        is_diverse = diversity["overlap_ratio"] <= 0.60
        is_novel = diversity["visual_novelty_score"] >= 0.70
        is_covered = coverage["coverage_rate"] >= 0.90
        is_type_balanced = coverage["concept_type_balance"] >= 0.80
        is_reuse_balanced = coverage["concept_reuse_balance"] >= 0.70

        if is_diverse and is_novel and is_covered and is_type_balanced and is_reuse_balanced:
            logger.info(f"[DECOMPOSER] Concept allocation validation passed on attempt {attempt + 1}.")
            break

        logger.warning(
            f"[DECOMPOSER] Validation failed on attempt {attempt + 1}. "
            f"Overlap: {diversity['overlap_ratio']:.2f} | Novelty: {diversity['visual_novelty_score']:.2f} | "
            f"Coverage: {coverage['coverage_rate']:.2f}. Forcing reallocation."
        )
        allocation = allocate_scene_concepts(concept_graph, lesson_plan_obj, num_scenes, force_reallocate=True)

    # Re-evaluate final stats
    diversity = validate_concept_diversity(allocation, num_scenes)
    coverage = validate_coverage(concept_graph, lesson_plan_obj, allocation)

    # Save canonical scene_concept_allocation.json
    save_json(project_id, "scene_concept_allocation.json", allocation)

    # Save diagnostics audit logs concept_graph_audit.json
    audit_data = {
        "metrics": {
            "total_concepts": len(concept_graph.concepts),
            "unique_concepts": len(set(c.concept_id for c in concept_graph.concepts)),
            "scene_diversity_score": round(diversity["diversity_score"], 2),
            "overlap_ratio": round(diversity["overlap_ratio"], 2),
            "visual_novelty_score": round(diversity["visual_novelty_score"], 2),
            "average_visual_concepts_per_scene": round(diversity["average_concepts_per_scene"], 2),
            "coverage_rate": round(coverage["coverage_rate"], 2),
            "concept_reuse_balance": round(coverage["concept_reuse_balance"], 2),
            "concept_type_balance": round(coverage["concept_type_balance"], 2),
            "objectives_covered_pct": round(coverage["objectives_covered_pct"], 2),
            "core_concepts_covered_pct": round(coverage["core_concepts_covered_pct"], 2),
        },
        "allocation": allocation,
        "validation_passed": (
            diversity["overlap_ratio"] <= 0.60
            and diversity["visual_novelty_score"] >= 0.70
            and coverage["coverage_rate"] >= 0.90
        )
    }
    save_json(project_id, "concept_graph_audit.json", audit_data)

    # ── Step 2: Educational Script Generation ────────────────────────────────
    script_data = await llm_service.generate_script(
        req.topic, req.duration, req.style, req.language,
        educational_level=educational_level,
        lesson_plan=lesson_plan_dict,
        concept_graph=concept_graph.model_dump(),
        assigned_scene_concepts=allocation,
        language_mode=req.language_mode,
    )

    # ── Step 3: Narration Quality Review (with dynamic thresholds & cost controls) ──
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
        quality_data = await llm_service.review_script_quality(script_data, educational_level, lesson_plan_dict, req.language_mode)
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
                f"threshold ({threshold:.2f}). Attempting rewrite {attempts}/{max_attempts}. "
                f"Reasons: {quality_data.get('rewrite_reasons', [])}"
            )
            # Inject structured review feedback directly into lesson plan for the LLM
            lesson_plan_dict["quality_feedback"] = quality_data.get("rewrite_reasons", [])
            lesson_plan_dict["structured_feedback"] = quality_data.get("structured_feedback", {})

            script_data = await llm_service.generate_script(
                req.topic, req.duration, req.style, req.language,
                educational_level=educational_level,
                lesson_plan=lesson_plan_dict,
                language_mode=req.language_mode,
            )
            quality_data = await llm_service.review_script_quality(script_data, educational_level, lesson_plan_dict, req.language_mode)
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

    # ── Step 5: Normalize durations (narration-preserving) ───────────────────
    script = ScriptSchema.model_validate(script_data)
    script.language_mode = req.language_mode
    for scene in script.scenes:
        scene.language_mode = req.language_mode
    script = normalize_script_durations(script, req.duration)
    save_json(project_id, "script.json", script.model_dump())

    # Generate project_manifest.json with original language request metadata
    manifest_data = {
        "language_mode": req.language_mode.value,
        "requested_language": req.language_mode.value,
        "screen_language": "english",
        "narration_language": req.language_mode.value,
        "tts_provider": req.tts_provider,
    }
    save_json(project_id, "project_manifest.json", manifest_data)

    # Persist full config including educational level and new voice/avatar provider fields.
    config = req.model_dump()
    config["visual_mode"] = "ai_image"
    config["voice_generation_status"] = "pending"
    config["f5_package_exported"] = False
    config["avatar_status"] = None      # future hook — liveportrait | musetalk | sadtalker
    config["audio_imported_at"] = None  # populated on F5 audio import
    save_json(project_id, "config.json", config)
    save_json(project_id, "status.json", {"step": PipelineStep.SCRIPT.value})

    return {
        "project_id": project_id,
        "script": script.model_dump(),
        "voice_provider": req.voice_provider,
        "tts_provider": req.tts_provider,
        "avatar_provider": req.avatar_provider,
        "lesson_plan": lesson_plan_dict,
        "quality_review": quality_data,
        "pedagogical_metrics": metrics_data,
    }


@router.post("/generate-scenes")
async def generate_scenes(req: GenerateScenesRequest):
    script = _get_script(req.project_id)
    config = load_json(req.project_id, "config.json") or {}
    topic = config.get("topic", script.title)
    scene_plans = await plan_scenes_for_script(req.project_id, script, topic)
    save_json(req.project_id, "status.json", {"step": PipelineStep.SCENES.value})

    return {
        "project_id": req.project_id,
        "scene_plans": [p.model_dump() for p in scene_plans],
    }


@router.post("/generate-svg")
async def generate_svg(req: GenerateSvgRequest):
    """Legacy alias — AI image visuals are produced in /generate-scenes."""
    data = load_json(req.project_id, "scene_plans.json")
    if not data:
        raise HTTPException(
            404, "Scene plans not found. Run /generate-scenes first (generates PNG + stroke data)."
        )
    scene_plans = [ScenePlanSchema.model_validate(p) for p in data]
    save_json(req.project_id, "status.json", {"step": PipelineStep.SVG.value})

    return {
        "project_id": req.project_id,
        "svg_files": [],
        "scene_plans": [p.model_dump() for p in scene_plans],
    }


@router.post("/generate-voice")
async def generate_voice(req: GenerateVoiceRequest):
    """Generate (or export) voice for the project.

    Behaviour depends on ``voice_provider`` stored in project config:

    - ``"edge"``  — generates MP3 narration via Edge-TTS immediately.
    - ``"f5tts"`` — exports a narration text package (ZIP) for external
      F5-TTS processing.  Audio is supplied later via ``/import-f5-audio``.
    """
    script = _get_script(req.project_id)
    config = load_json(req.project_id, "config.json") or {}
    voice = config.get("voice", "male")
    provider_key = get_provider_key(req.project_id)

    provider = get_voice_provider(req.project_id)
    voice_results = await provider.generate(req.project_id, script, voice)

    if provider_key == "f5tts":
        # Narration package was exported; audio will arrive via /import-f5-audio.
        save_json(
            req.project_id,
            "status.json",
            {"step": PipelineStep.VOICE_EXPORTED.value},
        )
        return {
            "project_id": req.project_id,
            "voice_provider": "f5tts",
            "tts_provider": "f5tts",
            "status": "narration_package_exported",
            "message": (
                "Narration package exported. Download it from "
                "/export-f5-package, run F5-TTS externally, then "
                "upload results to /import-f5-audio."
            ),
            "voice_files": [],
            "voice_results": [],
        }

    # Edge-TTS / XTTS Hindi: audio is generated immediately and ready.
    save_json(req.project_id, "status.json", {"step": PipelineStep.VOICE.value})
    return {
        "project_id": req.project_id,
        "voice_provider": "edge" if provider_key in ("edge", "edge_tts") else provider_key,
        "tts_provider": provider_key,
        "voice_files": [v.audio_path for v in voice_results],
        "voice_results": [v.model_dump() for v in voice_results],
    }


@router.post("/render-video")
async def render_video(req: RenderVideoRequest, background_tasks: BackgroundTasks):
    config = load_json(req.project_id, "config.json")
    if not config:
        raise HTTPException(404, "Project not found")

    job_id = str(uuid.uuid4())[:12]
    job_queue.create_job(job_id, req.project_id)

    background_tasks.add_task(
        _run_pipeline_task,
        job_id,
        req.project_id,
        config.get("topic", ""),
        config.get("duration", 60),
        config.get("style", "whiteboard"),
        config.get("voice", "male"),
        config.get("language", "english"),
        config.get("educational_level", "high_school"),  # Forward educational level
        config.get("language_mode", "english"),          # Forward language mode
        config.get("tts_provider", "edge_tts"),          # Forward tts_provider
    )

    return {"job_id": job_id, "project_id": req.project_id}


async def _run_pipeline_task(
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
):
    await job_queue.run_job(
        job_id,
        run_full_pipeline,
        project_id,
        topic,
        duration,
        style,
        voice,
        language,
        educational_level,
        language_mode,
        tts_provider,
    )


@router.get("/project/{project_id}")
async def get_project(project_id: str):
    config = load_json(project_id, "config.json")
    if not config:
        raise HTTPException(404, "Project not found")

    status_data = load_json(project_id, "status.json") or {}
    script_data = load_json(project_id, "script.json")
    scene_plans_data = load_json(project_id, "scene_plans.json")
    ai_sketch_audit = load_json(project_id, "ai_sketch_audit.json")
    ai_image_audit = load_json(project_id, "ai_image_audit.json")

    video_path = None
    final = project_dir(project_id) / "videos" / "final_video.mp4"
    if final.exists():
        video_path = f"/media/projects/{project_id}/videos/final_video.mp4"

    return ProjectResponse(
        project_id=project_id,
        topic=config.get("topic", ""),
        status=PipelineStep(status_data.get("step", "pending")),
        script=ScriptSchema.model_validate(script_data) if script_data else None,
        scene_plans=[ScenePlanSchema.model_validate(p) for p in scene_plans_data] if scene_plans_data else None,
        voice_files=list_audio_files(project_id),
        video_url=video_path,
        render_manifest_path="render_manifest.json" if load_json(project_id, "render_manifest.json") else None,
        config=config,
        ai_sketch_audit=ai_sketch_audit,
        ai_image_audit=ai_image_audit,
        voice_generation_status=config.get("voice_generation_status"),
        f5_package_exported=config.get("f5_package_exported", False),
        f5_processing_status=config.get("f5_processing_status"),
        audio_imported_at=config.get("audio_imported_at"),
        # Avatar pipeline fields
        avatar_provider=config.get("avatar_provider"),
        avatar_source=config.get("avatar_source"),
        avatar_status=config.get("avatar_status"),
        avatar_generation_status=config.get("avatar_generation_status"),
        sadtalker_package_exported=config.get("sadtalker_package_exported", False),
        sadtalker_processing_status=config.get("sadtalker_processing_status"),
        avatar_imported_at=config.get("avatar_imported_at"),
        avatar_position=config.get("avatar_position", "bottom_right"),
        avatar_scale=config.get("avatar_scale", 0.25),
    ).model_dump()


@router.post("/export-f5-package")
async def export_f5_package(body: dict):
    """Download the narration text package as a ZIP for external F5-TTS processing.

    Request body: ``{"project_id": "<id>"}``

    Returns a ZIP archive containing ``narration_pack.json`` and one
    ``scene_N.txt`` per scene.  If the package has not been generated yet
    (i.e. ``/generate-voice`` was not called with ``voice_provider=f5tts``)
    this endpoint will generate it on the fly.
    """
    project_id = body.get("project_id", "")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    config = load_json(project_id, "config.json")
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")

    script = _get_script(project_id)
    exporter = F5ExportService()

    # Regenerate package if not already exported (idempotent).
    exporter.export(project_id, script)

    try:
        zip_bytes = exporter.build_zip(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="narration_pack_{project_id}.zip"'
        },
    )


@router.post("/import-f5-audio")
async def import_f5_audio(
    project_id: str,
    audio_zip: UploadFile = File(...),
):
    """Import F5-TTS audio files and generate ``voice_results.json``.

    Accepts a ZIP archive containing scene audio files named
    ``scene_1.wav``, ``scene_2.wav`` … (WAV or MP3).

    After successful import:
    - Audio files are stored in ``<project>/voices/``.
    - ``voice_results.json`` is written with actual probed durations.
    - ``voices/combined.wav`` is generated for the future avatar pipeline.
    - ``voice_generation_status`` is set to ``"completed"``.
    """
    config = load_json(project_id, "config.json")
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")

    if audio_zip.content_type not in (
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    ):
        raise HTTPException(
            status_code=400,
            detail="Upload must be a ZIP archive containing WAV or MP3 files.",
        )

    zip_bytes = await audio_zip.read()
    script = _get_script(project_id)

    importer = F5ImportService()
    try:
        voice_results, validation_report = importer.import_audio(
            project_id, zip_bytes, script
        )
    except Exception as exc:
        # ImportValidationError carries a structured report; surface it.
        from services.voice.importer import ImportValidationError
        if isinstance(exc, ImportValidationError):
            raise HTTPException(
                status_code=422,
                detail={"message": str(exc), "validation_report": exc.report},
            )
        raise HTTPException(status_code=422, detail=str(exc))

    save_json(
        project_id,
        "status.json",
        {"step": PipelineStep.VOICE_IMPORTED.value},
    )

    return {
        "project_id": project_id,
        "voice_provider": "f5tts",
        "voice_generation_status": "completed",
        "combined_wav": "voices/combined.wav",
        "voice_results": [v.model_dump() for v in voice_results],
        # Structured validation report (#7)
        "validation_report": validation_report,
    }


@router.get("/project/{project_id}/f5-status")
async def get_f5_status(project_id: str):
    import logging
    import re
    import json
    from datetime import datetime, timezone
    from config import settings
    from utils.file_manager import load_json, save_json, project_dir

    logger = logging.getLogger("f5_status_api")

    # Safe project ID validation (reliability enhancement #3)
    if not re.match(r"^[a-zA-Z0-9_-]+$", project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id format")

    config = load_json(project_id, "config.json")
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")

    status = config.get("f5_processing_status", "queued")
    queued_at = config.get("f5_queued_at")
    last_update = config.get("f5_last_update")
    audio_ready = status == "audio_ready" or config.get("voice_generation_status") == "completed"

    if not audio_ready:
        # Check Drive completed folder first to trigger self-healing sync
        completed_folder = settings.f5_completed_path / f"project_{project_id}"
        if completed_folder.exists():
            # Trigger self-healing import immediately (snap sync!)
            try:
                status_file = completed_folder / "status.json"
                if status_file.exists():
                    with open(status_file, "r", encoding="utf-8") as f:
                        status_data = json.load(f)

                    if status_data.get("status") == "completed":
                        # Perform count validation
                        expected_count = status_data.get("scene_count")
                        audio_files = [
                            f for f in completed_folder.iterdir()
                            if f.is_file() and f.suffix.lower() in (".wav", ".mp3") and re.match(r"^scene_\d+\.(wav|mp3)$", f.name, re.IGNORECASE)
                        ]

                        if expected_count is not None and len(audio_files) == expected_count:
                            # Build ZIP
                            import zipfile
                            from io import BytesIO
                            zip_buf = BytesIO()
                            with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                                for audio_path in audio_files:
                                    zf.write(audio_path, arcname=audio_path.name)
                                zf.write(status_file, arcname="status.json")
                            zip_bytes = zip_buf.getvalue()

                            # Import
                            from services.voice.importer import F5ImportService
                            importer = F5ImportService()
                            importer.import_audio(project_id, zip_bytes)

                            # Reload config to get updated fields
                            config = load_json(project_id, "config.json") or {}
                            status = "audio_ready"
                            audio_ready = True
                            last_update = config.get("f5_last_update")
                            logger.info(f"[F5_IMPORT] Snap sync: successfully imported audio for project {project_id}")
            except Exception as e:
                logger.error(f"[F5_STATUS_API] Failed during self-healing import: {e}", exc_info=True)

    # If status is still not audio_ready, check other folders to sync state dynamically
    if not audio_ready:
        # Check processing
        processing_folder = settings.f5_processing_path / f"project_{project_id}"
        if processing_folder.exists():
            status = "processing"
        # Check failed
        elif (settings.f5_failed_path / f"project_{project_id}").exists():
            status = "failed"
        # Check queue
        elif (settings.f5_queue_path / f"project_{project_id}").exists():
            status = "queued"

        # Update local config status if it has changed
        if status != config.get("f5_processing_status"):
            config["f5_processing_status"] = status
            config["f5_last_update"] = datetime.now(timezone.utc).isoformat()
            save_json(project_id, "config.json", config)
            last_update = config["f5_last_update"]

    return {
        "status": status,
        "audio_ready": audio_ready,
        "queued_at": queued_at,
        "last_update": last_update,
    }

# =============================================================================
# PHASE-4: SADTALKER AVATAR PIPELINE ROUTES
# =============================================================================


@router.post("/upload-avatar-source")
async def upload_avatar_source(
    project_id: str,
    image: UploadFile = File(...),
):
    """Upload a reference portrait photo for SadTalker processing.

    Stores the image as ``<project>/avatar/source.<ext>`` and records
    ``avatar_source`` in ``config.json`` for subsequent pipeline steps.

    Returns:
        JSON with the stored ``avatar_source`` relative path.
    """
    config = load_json(project_id, "config.json")
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")

    allowed_exts = (".png", ".jpg", ".jpeg", ".webp")
    suffix = Path(image.filename or "source.png").suffix.lower()
    if suffix not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Image must be one of: {', '.join(allowed_exts)}",
        )

    proj = project_dir(project_id)
    avatar_dir = proj / "avatar"
    avatar_dir.mkdir(parents=True, exist_ok=True)

    dest = avatar_dir / f"source{suffix}"
    dest.write_bytes(await image.read())

    rel_path = f"avatar/source{suffix}"
    config["avatar_source"] = rel_path
    save_json(project_id, "config.json", config)

    return {
        "project_id": project_id,
        "avatar_source": rel_path,
        "message": "Source image stored. Call /generate-avatar next.",
    }


@router.post("/generate-avatar")
async def generate_avatar(req: GenerateAvatarRequest):
    """Generate (or export) avatar clips for the project.

    Behaviour depends on ``avatar_provider`` stored in project config:

    - ``"sadtalker"`` — exports an avatar package (ZIP) for external
      SadTalker processing.  Clips are supplied later via
      ``/import-sadtalker-clips``.
    """
    from services.avatar.factory import get_avatar_provider, get_avatar_provider_key

    config = load_json(req.project_id, "config.json")
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")

    provider_key = get_avatar_provider_key(req.project_id)
    if not provider_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "No avatar_provider configured for this project. "
                "Set avatar_provider=sadtalker when calling /generate-script."
            ),
        )

    script = _get_script(req.project_id)
    avatar_source = req.avatar_source or config.get("avatar_source", "avatar/source.png")

    provider = get_avatar_provider(req.project_id)
    if not provider:
        raise HTTPException(status_code=500, detail="Failed to instantiate avatar provider.")

    await provider.generate(req.project_id, script, avatar_source)

    save_json(
        req.project_id,
        "status.json",
        {"step": PipelineStep.AVATAR_EXPORTED.value},
    )
    return {
        "project_id": req.project_id,
        "avatar_provider": provider_key,
        "status": "avatar_package_exported",
        "message": (
            "Avatar package exported. Download it from "
            "/export-sadtalker-package, run SadTalker externally, "
            "then upload results to /import-sadtalker-clips."
        ),
    }


@router.post("/export-sadtalker-package")
async def export_sadtalker_package(body: dict):
    """Download the SadTalker avatar package as a ZIP for external processing.

    Request body: ``{"project_id": "<id>"}``

    Returns a ZIP archive containing ``avatar_pack.json``, per-scene audio
    clips, and the source portrait image.
    """
    from services.avatar.exporter import SadTalkerExportService

    project_id = body.get("project_id", "")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    config = load_json(project_id, "config.json")
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")

    script = _get_script(project_id)
    exporter = SadTalkerExportService()
    avatar_source = config.get("avatar_source", "avatar/source.png")

    # Regenerate package if not already exported (idempotent).
    exporter.export(project_id, script, avatar_source)

    try:
        zip_bytes = exporter.build_zip(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="sadtalker_pack_{project_id}.zip"'
        },
    )


@router.post("/import-sadtalker-clips")
async def import_sadtalker_clips(
    project_id: str,
    clips_zip: UploadFile = File(...),
):
    """Import SadTalker transparent WebM clips and generate ``avatar_result.json``.

    Accepts a ZIP archive containing the single avatar video (``avatar.webm``
    or ``avatar.mp4``) driven by the full project combined narration.

    After successful import:
    - Clip files are stored in ``<project>/avatars/``.
    - ``avatar_result.json`` is written with metadata (drift validation, etc).
    - ``avatar_generation_status`` is set to ``"completed"``.
    """
    from services.avatar.importer import SadTalkerImportService, ImportValidationError

    config = load_json(project_id, "config.json")
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")

    if clips_zip.content_type not in (
        "application/zip",
        "application/x-zip-compressed",
        "application/octet-stream",
    ):
        raise HTTPException(
            status_code=400,
            detail="Upload must be a ZIP archive containing WebM or MP4 files.",
        )

    zip_bytes = await clips_zip.read()
    script = _get_script(project_id)

    importer = SadTalkerImportService()
    try:
        avatar_result, validation_report = importer.import_clips(
            project_id, zip_bytes, script
        )
    except ImportValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "validation_report": exc.report},
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    save_json(
        project_id,
        "status.json",
        {"step": PipelineStep.AVATAR_IMPORTED.value},
    )

    return {
        "project_id": project_id,
        "avatar_provider": "sadtalker",
        "avatar_generation_status": "completed",
        "avatar_result": avatar_result.model_dump(),
        "avatar_results": [avatar_result.model_dump()],  # Keep for backward compatibility
        "validation_report": validation_report,
    }


@router.get("/project/{project_id}/sadtalker-status")
async def get_sadtalker_status(project_id: str):
    """Poll the SadTalker processing queue status.

    Mirrors the GET /project/{id}/f5-status endpoint exactly.
    Checks queue/processing/completed/failed Drive folders and triggers
    self-healing import when the Colab worker has finished.
    """
    import logging
    import re
    import json as _json
    from datetime import datetime, timezone

    _logger = logging.getLogger("sadtalker_status_api")

    if not re.match(r"^[a-zA-Z0-9_-]+$", project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id format")

    config = load_json(project_id, "config.json")
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")

    status = config.get("sadtalker_processing_status", "queued")
    queued_at = config.get("sadtalker_queued_at")
    last_update = config.get("sadtalker_last_update")
    clips_ready = (
        status == "clips_ready"
        or config.get("avatar_generation_status") == "completed"
    )

    if not clips_ready:
        # Check completed Drive folder and trigger self-healing import
        completed_folder = settings.sadtalker_completed_path / f"project_{project_id}"
        if completed_folder.exists():
            try:
                status_file = completed_folder / "status.json"
                if status_file.exists():
                    with open(status_file, "r", encoding="utf-8") as f:
                        status_data = _json.load(f)

                    if status_data.get("status") == "completed":
                        # Check for primary clip (avatar.webm or avatar.mp4)
                        has_clip = (completed_folder / "avatar.webm").exists() or (completed_folder / "avatar.mp4").exists()
                        if has_clip:
                            import zipfile
                            from io import BytesIO
                            zip_buf = BytesIO()
                            with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                                for f_in_dir in completed_folder.iterdir():
                                    if f_in_dir.is_file() and f_in_dir.name.lower() in ("avatar.webm", "avatar.mp4", "avatar_mask.mp4", "status.json"):
                                        zf.write(f_in_dir, arcname=f_in_dir.name)
                            zip_bytes = zip_buf.getvalue()

                            from services.avatar.importer import SadTalkerImportService
                            importer = SadTalkerImportService()
                            importer.import_clips(project_id, zip_bytes)

                            config = load_json(project_id, "config.json") or {}
                            status = "clips_ready"
                            clips_ready = True
                            last_update = config.get("sadtalker_last_update")
                            _logger.info(
                                f"[SADTALKER_IMPORT] Snap sync: imported combined avatar for {project_id}"
                            )
            except Exception as e:
                _logger.error(
                    f"[SADTALKER_STATUS_API] Self-healing import failed: {e}", exc_info=True
                )

    if not clips_ready:
        processing_folder = settings.sadtalker_processing_path / f"project_{project_id}"
        if processing_folder.exists():
            status = "processing"
        elif (settings.sadtalker_failed_path / f"project_{project_id}").exists():
            status = "failed"
        elif (settings.sadtalker_queue_path / f"project_{project_id}").exists():
            status = "queued"

        if status != config.get("sadtalker_processing_status"):
            config["sadtalker_processing_status"] = status
            config["sadtalker_last_update"] = datetime.now(timezone.utc).isoformat()
            save_json(project_id, "config.json", config)
            last_update = config["sadtalker_last_update"]

    return {
        "status": status,
        "clips_ready": clips_ready,
        "queued_at": queued_at,
        "last_update": last_update,
    }


@router.get("/project/{project_id}/pipeline-status")
async def get_pipeline_status(project_id: str):
    """Consolidated endpoint returning status info for voice, avatar, and render pipelines.

    P8 implementation: helps client poll unified status in one request.
    """
    import re
    from datetime import datetime, timezone
    from utils.file_manager import load_json, project_dir

    if not re.match(r"^[a-zA-Z0-9_-]+$", project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id format")

    config = load_json(project_id, "config.json")
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")

    proj = project_dir(project_id)

    # 1. Voice pipeline status
    voice_provider = config.get("voice_provider", "edge")
    voice_status = "none"
    audio_ready = False
    voice_queued_at = config.get("f5_queued_at")

    # Check if combined voice file exists
    combined_audio = proj / "voices" / "combined.wav"
    if not combined_audio.exists():
        combined_audio = proj / "voices" / "combined.mp3"
    audio_ready = combined_audio.exists()

    if voice_provider == "f5tts":
        voice_status = config.get("f5_processing_status", "queued")
        if audio_ready or config.get("voice_generation_status") == "completed":
            voice_status = "completed"
            audio_ready = True
    elif voice_provider == "edge":
        voice_status = "completed" if audio_ready else "pending"

    # 2. Avatar pipeline status
    avatar_provider = config.get("avatar_provider")
    avatar_status = "none"
    clips_ready = False
    avatar_queued_at = config.get("sadtalker_queued_at")
    avatar_capabilities = None

    if avatar_provider:
        # Load provider capabilities (Refinement I & Hardening 6)
        try:
            from services.avatar.factory import get_avatar_provider
            prov = get_avatar_provider(project_id)
            if prov:
                avatar_capabilities = prov.get_capabilities().model_dump()
        except Exception:
            pass

        avatar_status = config.get("sadtalker_processing_status", "queued")
        clips_ready = (
            avatar_status == "clips_ready"
            or config.get("avatar_generation_status") == "completed"
        )

        # Trigger self-healing import check on poll
        if not clips_ready:
            completed_folder = settings.sadtalker_completed_path / f"project_{project_id}"
            if completed_folder.exists():
                try:
                    status_file = completed_folder / "status.json"
                    if status_file.exists():
                        with open(status_file, "r", encoding="utf-8") as f:
                            import json as _json
                            status_data = _json.load(f)
                        if status_data.get("status") == "completed":
                            has_clip = (completed_folder / "avatar.webm").exists() or (completed_folder / "avatar.mp4").exists()
                            if has_clip:
                                import zipfile
                                from io import BytesIO
                                zip_buf = BytesIO()
                                with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                                    for f_in_dir in completed_folder.iterdir():
                                        if f_in_dir.is_file() and f_in_dir.name.lower() in ("avatar.webm", "avatar.mp4", "avatar_mask.mp4", "status.json"):
                                            zf.write(f_in_dir, arcname=f_in_dir.name)
                                zip_bytes = zip_buf.getvalue()

                                from services.avatar.importer import SadTalkerImportService
                                importer = SadTalkerImportService()
                                importer.import_clips(project_id, zip_bytes)

                                # Reload config
                                config = load_json(project_id, "config.json") or {}
                                avatar_status = "completed"
                                clips_ready = True
                except Exception:
                    pass

        # If still not ready, dynamically sync folder states
        if not clips_ready:
            processing_folder = settings.sadtalker_processing_path / f"project_{project_id}"
            if processing_folder.exists():
                avatar_status = "processing"
            elif (settings.sadtalker_failed_path / f"project_{project_id}").exists():
                avatar_status = "failed"
            elif (settings.sadtalker_queue_path / f"project_{project_id}").exists():
                avatar_status = "queued"
            else:
                avatar_status = config.get("avatar_generation_status", "pending")
    else:
        avatar_status = "none"

    # 3. Render status
    render_status = "pending"
    video_file = proj / "videos" / "final_video.mp4"
    if video_file.exists():
        render_status = "complete"
    else:
        # Check if job is active in job queue
        job = None
        for j in job_queue._jobs.values():
            if j.project_id == project_id:
                job = j
                break
        if job:
            if job.error:
                render_status = "failed"
            elif job.step == PipelineStep.COMPLETE:
                render_status = "complete"
            else:
                render_status = "rendering"
        else:
            status_data = load_json(project_id, "status.json") or {}
            step = status_data.get("step")
            if step == "complete":
                render_status = "complete"
            elif step == "error":
                render_status = "failed"

    video_url = config.get("video_url")
    if render_status == "complete" and not video_url:
        video_url = f"/generated/{project_id}/videos/final_video.mp4"

    return {
        "voice": {
            "status": voice_status,
            "audio_ready": audio_ready,
            "queued_at": voice_queued_at,
        },
        "avatar": {
            "status": avatar_status,
            "clips_ready": clips_ready,
            "queued_at": avatar_queued_at,
            "capabilities": avatar_capabilities,
        },
        "render": {
            "status": render_status,
            "video_url": video_url,
        }
    }


@router.get("/avatar/metrics")
async def get_avatar_metrics():
    """Retrieve operational metrics for the avatar pipeline.

    Hardening 8: Exposes only aggregate statistics and strips filesystem paths
    and project identifiers.
    """
    try:
        from services.avatar.metrics import AvatarMetricsService
        metrics_service = AvatarMetricsService()
        return metrics_service.get_aggregate_metrics()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load metrics: {exc}")


@router.get("/debug-jobs")
async def debug_jobs():
    from utils.job_queue import job_queue
    return {
        job_id: {
            "project_id": job.project_id,
            "step": job.step,
            "progress": job.progress,
            "message": job.message,
            "error": job.error,
        }
        for job_id, job in job_queue._jobs.items()
    }
