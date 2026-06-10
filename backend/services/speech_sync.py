"""Align captions and animation timing to TTS word boundaries."""
from __future__ import annotations

import re
from typing import List, Optional, TYPE_CHECKING

from models.schemas import SceneVoiceResult, SubtitleEntry, WordTimestamp
from utils.timing import (
    FPS,
    is_layer_sketch_element,
    is_sketch_image_element,
    is_static_headline,
)

if TYPE_CHECKING:
    from models.schemas import ScenePlanSchema, SceneSchema


def _clean_word(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def estimate_word_timestamps(narration: str, duration_sec: float) -> List[WordTimestamp]:
    """Spread words evenly when edge-tts returns no boundaries."""
    words = [w for w in narration.split() if w]
    if not words or duration_sec <= 0:
        return []
    weights = [max(1, len(w)) for w in words]
    total = sum(weights)
    t = 0.0
    out: List[WordTimestamp] = []
    for word, weight in zip(words, weights):
        span = (weight / total) * duration_sec * 0.96
        out.append(WordTimestamp(word=word, start=t, end=t + span))
        t += span
    if out:
        out[-1].end = duration_sec
    return out


def get_scene_word_timestamps(
    voice: Optional[SceneVoiceResult],
    narration: str,
) -> List[WordTimestamp]:
    if voice and voice.timestamps:
        return voice.timestamps
    dur = voice.duration if voice else max(3.0, len(narration.split()) / 2.5)
    return estimate_word_timestamps(narration, dur)


def group_words_into_phrases(
    words: List[WordTimestamp],
    max_words: int = 6,
    max_chars: int = 48,
    pause_gap_sec: float = 0.38,
) -> List[SubtitleEntry]:
    """Readable caption chunks locked to spoken word times."""
    if not words:
        return []

    phrases: List[SubtitleEntry] = []
    bucket: List[WordTimestamp] = []

    def flush() -> None:
        if not bucket:
            return
        text = _clean_word(" ".join(w.word for w in bucket))
        if not text:
            bucket.clear()
            return
        phrases.append(
            SubtitleEntry(
                text=text,
                start_frame=max(0, int(bucket[0].start * FPS)),
                end_frame=max(
                    int(bucket[0].start * FPS) + 1,
                    int(bucket[-1].end * FPS) + 2,
                ),
            )
        )
        bucket.clear()

    for i, w in enumerate(words):
        if bucket:
            gap = w.start - bucket[-1].end
            text_len = len(" ".join(x.word for x in bucket))
            if gap > pause_gap_sec or len(bucket) >= max_words or text_len >= max_chars:
                flush()
        bucket.append(w)
    flush()
    return phrases


def build_subtitles_for_scene(
    voice: Optional[SceneVoiceResult],
    scene_script: Optional["SceneSchema"],
    scene_duration_frames: int,
) -> List[SubtitleEntry]:
    narration = scene_script.narration if scene_script else ""
    keywords = (scene_script.keywords[:3] if scene_script else []) or []

    voice_sec = voice.duration if voice else 0.0
    if voice_sec <= 0 and narration:
        voice_sec = max(3.0, len(narration.split()) / 2.5)
    caption_end_frame = min(
        scene_duration_frames - 1,
        max(1, int(voice_sec * FPS) + 1),
    )

    words = get_scene_word_timestamps(voice, narration)
    entries = group_words_into_phrases(words)

    if not entries and narration:
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", narration) if p.strip()]
        if len(parts) < 2:
            parts = []
            chunk = max(1, len(narration.split()) // 4)
            words_list = narration.split()
            for i in range(0, len(words_list), chunk):
                parts.append(" ".join(words_list[i : i + chunk]))
        slot = caption_end_frame / max(len(parts), 1)
        for i, text in enumerate(parts):
            sf = int(i * slot)
            ef = int((i + 1) * slot) if i < len(parts) - 1 else caption_end_frame
            entries.append(
                SubtitleEntry(
                    text=text,
                    start_frame=sf,
                    end_frame=max(sf + 1, ef),
                    highlight_words=keywords,
                )
            )

    for e in entries:
        e.end_frame = min(e.end_frame, caption_end_frame)
        e.start_frame = min(e.start_frame, e.end_frame - 1)
        if keywords and not e.highlight_words:
            e.highlight_words = keywords

    return entries


def schedule_scene_animations_to_voice(
    plan: "ScenePlanSchema",
    voice: Optional[SceneVoiceResult],
    scene_duration_sec: float,
) -> None:
    """
    Stretch or compress element delays/durations so drawing tracks narration length.
    """
    voice_sec = voice.duration if voice and voice.duration > 0 else scene_duration_sec * 0.85
    draw_budget = max(2.5, min(voice_sec * 0.78, scene_duration_sec * 0.82))

    sketch_els = [e for e in plan.elements if is_sketch_image_element(e)]
    layer_els = [e for e in plan.elements if is_layer_sketch_element(e)]
    other_anims = [
        e
        for e in plan.elements
        if not is_static_headline(e)
        and not is_sketch_image_element(e)
        and not is_layer_sketch_element(e)
        and e.animation in ("stroke_reveal", "sketch_reveal", "fade_in", "scale_in")
    ]

    if sketch_els:
        for el in sketch_els:
            el.delay = 0.1
            el.duration = draw_budget

    if layer_els:
        def _layer_num(el) -> int:
            m = re.search(r"-layer-(\d+)$", el.id or "")
            return int(m.group(1)) if m else 0

        layer_els.sort(key=_layer_num)
        n = len(layer_els)
        if n == 1:
            layer_els[0].delay = 0.12
            layer_els[0].duration = draw_budget
        else:
            slot = draw_budget / n
            gap = slot * 0.06
            for i, el in enumerate(layer_els):
                el.delay = 0.1 + i * (slot + gap)
                el.duration = max(1.2, slot * 0.88)

    if other_anims:
        slot = draw_budget / max(len(other_anims), 1)
        for i, el in enumerate(other_anims):
            el.delay = 0.2 + i * slot * 0.5
            el.duration = max(1.0, slot * 0.85)
