import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import settings


def new_project_id() -> str:
    return str(uuid.uuid4())[:8]


def project_dir(project_id: str) -> Path:
    path = settings.generated_path / "projects" / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_project_dirs(project_id: str) -> Dict[str, Path]:
    base = project_dir(project_id)
    dirs = {
        "base": base,
        "svgs": base / "svgs",
        "voices": base / "voices",
        "videos": base / "videos",
    }
    for key, p in dirs.items():
        if key != "base":
            p.mkdir(parents=True, exist_ok=True)
    return dirs


def save_json(project_id: str, filename: str, data: Any) -> Path:
    path = project_dir(project_id) / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def load_json(project_id: str, filename: str) -> Optional[Dict]:
    path = project_dir(project_id) / filename
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_text(project_id: str, filename: str, content: str) -> Path:
    path = project_dir(project_id) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def load_text(project_id: str, filename: str) -> Optional[str]:
    path = project_dir(project_id) / filename
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def list_svg_files(project_id: str) -> List[str]:
    svg_dir = project_dir(project_id) / "svgs"
    if not svg_dir.exists():
        return []
    return [str(p.relative_to(project_dir(project_id))) for p in svg_dir.glob("*.svg")]


def list_voice_files(project_id: str) -> List[str]:
    voice_dir = project_dir(project_id) / "voices"
    if not voice_dir.exists():
        return []
    return [str(p.relative_to(project_dir(project_id))) for p in voice_dir.glob("*.mp3")]


def list_audio_files(project_id: str) -> List[str]:
    """Return all audio files (.mp3 and .wav) in the project voices directory.

    Used by the project response so both Edge-TTS MP3 and F5-TTS WAV files
    are surfaced to the frontend for preview.
    """
    voice_dir = project_dir(project_id) / "voices"
    if not voice_dir.exists():
        return []
    paths: List[str] = []
    for ext in ("*.mp3", "*.wav"):
        paths.extend(
            str(p.relative_to(project_dir(project_id)))
            for p in sorted(voice_dir.glob(ext))
        )
    return paths


def ensure_f5_package_dir(project_id: str) -> Path:
    """Create and return the ``f5_package/`` directory for *project_id*."""
    pkg_dir = project_dir(project_id) / "f5_package"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    return pkg_dir
