import asyncio
import json
import re
from pathlib import Path
from typing import List, Tuple

import edge_tts

from models.schemas import SceneSchema, SceneVoiceResult, ScriptSchema, WordTimestamp
from utils.file_manager import ensure_project_dirs, save_json
from utils.timing import trim_narration


VOICE_MAP = {
    "male": "en-US-GuyNeural",
    "female": "en-US-JennyNeural",
    "male_uk": "en-GB-RyanNeural",
    "female_uk": "en-GB-SoniaNeural",
}


def _boundary_to_seconds(offset: float, duration: float) -> Tuple[float, float]:
    """edge-tts may send offsets in ticks (100ns) or seconds."""
    if offset > 1000:
        start = offset / 10_000_000
        end = (offset + duration) / 10_000_000
    else:
        start = offset
        end = offset + duration
    return start, end


async def generate_voice_for_scene(
    text: str,
    output_path: Path,
    voice: str = "male",
) -> Tuple[float, List[WordTimestamp]]:
    voice_name = VOICE_MAP.get(voice, VOICE_MAP["male"])
    communicate = edge_tts.Communicate(
        text, voice_name, boundary="WordBoundary"
    )

    timestamps: List[WordTimestamp] = []
    audio_chunks: List[bytes] = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            offset = float(chunk.get("offset", 0))
            dur = float(chunk.get("duration", 0))
            start, end = _boundary_to_seconds(offset, dur)
            word = chunk.get("text", "").strip()
            if not word:
                continue
            timestamps.append(WordTimestamp(word=word, start=start, end=end))

    audio_data = b"".join(audio_chunks)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_data)

    duration = _probe_audio_duration(output_path)
    if duration <= 0 and timestamps:
        duration = timestamps[-1].end
    if duration <= 0:
        duration = _estimate_duration(text)
    if timestamps:
        timestamps[-1].end = max(timestamps[-1].end, duration)
    return duration, timestamps


def _probe_audio_duration(path: Path) -> float:
    import subprocess

    from config import settings

    try:
        result = subprocess.run(
            [
                settings.ffmpeg_path,
                "-i",
                str(path),
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
        if m:
            h, mi, s, cs = m.groups()
            return int(h) * 3600 + int(mi) * 60 + int(s) + int(cs) / 100
    except (OSError, subprocess.SubprocessError):
        pass
    return 0.0


def _estimate_duration(text: str) -> float:
    words = len(text.split())
    return max(3.0, words / 2.5)


async def generate_voices_for_script(
    project_id: str,
    script: ScriptSchema,
    voice: str = "male",
) -> List[SceneVoiceResult]:
    dirs = ensure_project_dirs(project_id)
    results: List[SceneVoiceResult] = []

    async def process_scene(scene: SceneSchema) -> SceneVoiceResult:
        output_path = dirs["voices"] / f"scene_{scene.scene_id}.mp3"
        narration = scene.narration
        duration, timestamps = await generate_voice_for_scene(
            narration, output_path, voice
        )
        ts_path = dirs["voices"] / f"scene_{scene.scene_id}_timestamps.json"
        with open(ts_path, "w", encoding="utf-8") as f:
            json.dump([t.model_dump() for t in timestamps], f, indent=2)

        return SceneVoiceResult(
            scene_id=scene.scene_id,
            audio_path=f"voices/scene_{scene.scene_id}.mp3",
            duration=duration or scene.duration,
            timestamps=timestamps,
        )

    tasks = [process_scene(s) for s in script.scenes]
    results = await asyncio.gather(*tasks)

    save_json(project_id, "voice_results.json", [r.model_dump() for r in results])
    return results
