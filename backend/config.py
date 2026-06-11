from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings
from models.schemas import AvatarQuality


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_line_art_model: str = "gpt-4o-mini"
    openai_image_model: str = "gpt-image-1-mini"
    openai_image_quality: str = "low"
    openai_image_size: str = "1536x1024"
    png_stroke_width: int = 1920
    png_stroke_height: int = 1080
    png_stroke_split_len: int = 10
    png_stroke_min_area: int = 120

    # Enhanced stroke: vision bboxes → contour → SVG paths
    stroke_backend: str = "vision_contour"  # vision_contour | opencv
    segmentation_vision_model: str = "gpt-4o-mini"
    vision_max_objects: int = 5
    vision_bbox_padding: float = 0.08
    contour_canny_low: int = 40
    contour_canny_high: int = 120
    contour_min_area: int = 25
    contour_approx_epsilon: float = 0.004
    vision_image_max_side: int = 768  # smaller payload for vision bbox API
    scene_image_concurrency: int = 3  # parallel OpenAI image calls per project

    port: int = 8000
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    ffmpeg_path: str = "ffmpeg"
    generated_dir: str = "generated"
    assets_dir: str = "assets"
    renderer_dir: str = "renderer"
    remotion_concurrency: int = 4

    # Cost control configuration flags (Phase 3)
    quality_review_enabled: bool = True
    rewrite_enabled: bool = True
    evaluation_enabled: bool = True

    # Google Drive Queue Automation Settings — F5-TTS
    f5_drive_root: str = "WhiteboardAI"
    f5_queue_dir: str = "queue"
    f5_processing_dir: str = "processing"
    f5_completed_dir: str = "completed"
    f5_failed_dir: str = "failed"
    completed_cleanup_days: int = 7

    # Google Drive Queue Automation Settings — SadTalker Avatar
    sadtalker_drive_root: str = "WhiteboardAI_Avatar"
    sadtalker_queue_dir: str = "queue"
    sadtalker_processing_dir: str = "processing"
    sadtalker_completed_dir: str = "completed"
    sadtalker_failed_dir: str = "failed"

    # Avatar pipeline behaviour settings
    # P2: Maximum allowed drift between audio and avatar video durations (seconds)
    avatar_duration_tolerance: float = 0.10
    # P3: Hours before a project stuck in "processing" is timed out and moved to failed
    avatar_processing_timeout_hours: int = 12
    # P6: Directory (relative to ROOT_DIR) used as the avatar clip cache store
    avatar_cache_dir: str = "avatar_cache"
    # P9: Days to retain completed avatar assets before cleanup is allowed
    avatar_retention_days: int = 7

    # Refinement D & 5: validated quality preset
    avatar_quality: AvatarQuality = AvatarQuality.STANDARD
    # Refinement E & 7: Cache limits and retention policy settings
    avatar_cache_retention_days: int = 30
    avatar_cache_max_gb: float = 20.0
    # Refinement F & 4: Retry configuration
    avatar_max_retries: int = 1
    # Refinement G & 3: Queue limit configuration
    max_avatar_queue_size: int = 20

    @model_validator(mode="after")
    def validate_ffmpeg_path(self) -> "Settings":
        import shutil

        # If the configured path does not exist on disk, check if it can be found in PATH
        if not Path(self.ffmpeg_path).exists():
            resolved = shutil.which("ffmpeg")
            if resolved:
                self.ffmpeg_path = resolved
            else:
                self.ffmpeg_path = "ffmpeg"
        return self

    class Config:
        env_file = str(ROOT_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def generated_path(self) -> Path:
        return ROOT_DIR / self.generated_dir

    @property
    def assets_path(self) -> Path:
        return ROOT_DIR / self.assets_dir

    @property
    def renderer_path(self) -> Path:
        return ROOT_DIR / self.renderer_dir

    @property
    def f5_drive_root_path(self) -> Path:
        p = Path(self.f5_drive_root)
        if not p.is_absolute():
            return ROOT_DIR / p
        return p

    @property
    def f5_queue_path(self) -> Path:
        p = Path(self.f5_queue_dir)
        if not p.is_absolute():
            return self.f5_drive_root_path / p
        return p

    @property
    def f5_processing_path(self) -> Path:
        p = Path(self.f5_processing_dir)
        if not p.is_absolute():
            return self.f5_drive_root_path / p
        return p

    @property
    def f5_completed_path(self) -> Path:
        p = Path(self.f5_completed_dir)
        if not p.is_absolute():
            return self.f5_drive_root_path / p
        return p

    @property
    def f5_failed_path(self) -> Path:
        p = Path(self.f5_failed_dir)
        if not p.is_absolute():
            return self.f5_drive_root_path / p
        return p

    # --- SadTalker Drive path properties ---

    @property
    def sadtalker_drive_root_path(self) -> Path:
        p = Path(self.sadtalker_drive_root)
        if not p.is_absolute():
            return ROOT_DIR / p
        return p

    @property
    def sadtalker_queue_path(self) -> Path:
        p = Path(self.sadtalker_queue_dir)
        if not p.is_absolute():
            return self.sadtalker_drive_root_path / p
        return p

    @property
    def sadtalker_processing_path(self) -> Path:
        p = Path(self.sadtalker_processing_dir)
        if not p.is_absolute():
            return self.sadtalker_drive_root_path / p
        return p

    @property
    def sadtalker_completed_path(self) -> Path:
        p = Path(self.sadtalker_completed_dir)
        if not p.is_absolute():
            return self.sadtalker_drive_root_path / p
        return p

    @property
    def sadtalker_failed_path(self) -> Path:
        p = Path(self.sadtalker_failed_dir)
        if not p.is_absolute():
            return self.sadtalker_drive_root_path / p
        return p

    @property
    def avatar_cache_path(self) -> Path:
        """Local on-disk cache for reusable avatar clips (SHA256-keyed)."""
        p = Path(self.avatar_cache_dir)
        if not p.is_absolute():
            return ROOT_DIR / p
        return p


settings = Settings()
