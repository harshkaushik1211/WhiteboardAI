# F5-TTS Integration Guide

## Overview

This document describes the **F5-TTS Voice Provider** integration for the AI Whiteboard Video Generator.  The system uses a **pluggable Voice Provider Architecture** that allows narration audio to be produced by different engines without changing any downstream rendering code.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  Voice Provider System                    │
│                                                          │
│  services/voice/                                         │
│  ├── providers/                                          │
│  │   ├── base.py          ← VoiceProvider ABC            │
│  │   ├── edge.py          ← EdgeTTSProvider              │
│  │   └── f5.py            ← F5TTSProvider                │
│  ├── factory.py           ← get_voice_provider()         │
│  ├── exporter.py          ← F5ExportService              │
│  └── importer.py          ← F5ImportService              │
└──────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────┐     ┌──────────────────────────┐
│   Edge-TTS mode          │     │   F5-TTS mode             │
│                          │     │                           │
│ generate() → MP3 files   │     │ generate() → export ZIP   │
│ → voice_results.json     │     │ ← user uploads WAV ZIP    │
│ → render pipeline        │     │ → voice_results.json      │
│                          │     │ → combined.wav            │
│                          │     │ → render pipeline         │
└──────────────────────────┘     └──────────────────────────┘
```

### Key Design Principles

1. **VoiceProvider interface is minimal** — only `generate()`.  Export and import are F5-specific concerns handled by dedicated services.
2. **Render pipeline is provider-agnostic** — it only reads `voice_results.json`.
3. **Backward compatible** — old projects without `voice_provider` in config default to Edge-TTS automatically.

---

## F5-TTS Export Workflow

### Step 1: Create Project with F5-TTS

```bash
POST /generate-script
{
  "topic": "Newton's Laws",
  "duration": 60,
  "voice_provider": "f5tts",
  "voice": "male"
}
```

Response includes `project_id` and `voice_provider: "f5tts"`.

### Step 2: Export Narration Package

```bash
POST /generate-voice
{ "project_id": "<id>" }
```

Or trigger download directly:

```bash
POST /export-f5-package
{ "project_id": "<id>" }
```

**Response:** ZIP file download containing:

```
narration_pack_<id>.zip
├── narration_pack.json
├── scene_1.txt
├── scene_2.txt
└── scene_N.txt
```

### narration_pack.json structure

```json
{
  "project_id": "abc12345",
  "voice_provider": "f5tts",
  "total_scenes": 6,
  "created_at": "2026-06-04T10:00:00Z",
  "scenes": [
    {
      "scene_id": 1,
      "title": "Introduction to Newton's First Law",
      "estimated_duration": 8.5,
      "text_file": "scene_1.txt"
    }
  ]
}
```

### Step 3: Run F5-TTS Externally

Use the text files as input to your F5-TTS installation:

```bash
# Example (your command may differ based on F5-TTS setup):
f5-tts_infer --model F5TTS_v1 \
  --ref_audio ref_voice.wav \
  --ref_text "Reference text" \
  --gen_text "$(cat scene_1.txt)" \
  --output_file scene_1.wav
```

Produce one `scene_N.wav` per scene text file.

---

## F5-TTS Import Workflow

### Step 4: Package and Upload WAV Files

Create a ZIP of your generated WAV (or MP3) files:

```
audio_upload.zip
├── scene_1.wav
├── scene_2.wav
└── scene_N.wav
```

Upload via API:

```bash
POST /import-f5-audio?project_id=<id>
Content-Type: multipart/form-data
audio_zip: @audio_upload.zip
```

### What happens on import

1. ZIP is extracted, files validated against `scene_N.(wav|mp3)` pattern.
2. Files stored in `<project>/voices/`.
3. FFmpeg probes actual duration of each file.
4. `voice_results.json` written with real durations + `provider: "f5tts"`.
5. `voices/combined.wav` generated (all scenes concatenated, mono 44100 Hz).
6. `voice_generation_status` set to `"completed"`.

### voice_results.json structure (after import)

```json
[
  {
    "provider": "f5tts",
    "scene_id": 1,
    "audio_path": "voices/scene_1.wav",
    "duration": 4.53,
    "timestamps": []
  }
]
```

---

## Step 5: Render Video

Once import is complete:

```bash
POST /render-video
{ "project_id": "<id>" }
```

The render pipeline reads `voice_results.json` and works identically regardless of whether audio came from Edge-TTS or F5-TTS.

---

## Project Folder Structure (F5-TTS mode)

```
generated/projects/<id>/
├── config.json                  ← voice_provider: "f5tts"
├── script.json
├── status.json
├── voice_results.json           ← generated after import
├── render_manifest.json
├── f5_package/
│   ├── narration_pack.json
│   ├── scene_1.txt
│   └── scene_N.txt
├── voices/
│   ├── scene_1.wav              ← imported F5-TTS audio
│   ├── scene_N.wav
│   └── combined.wav             ← auto-generated, for avatar pipeline
├── svgs/
└── videos/
    └── final_video.mp4
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/generate-script` | Create project; set `voice_provider: "f5tts"` |
| `POST` | `/generate-voice` | Export narration package (F5 mode) |
| `POST` | `/export-f5-package` | Download narration ZIP directly |
| `POST` | `/import-f5-audio` | Upload WAV ZIP, generate voice_results.json |
| `POST` | `/render-video` | Render video (works with any provider) |
| `GET`  | `/project/{id}` | Project status including `voice_generation_status` |

### Project status fields (new)

| Field | Type | Values |
|-------|------|--------|
| `voice_generation_status` | `string` | `"pending"` \| `"completed"` |
| `f5_package_exported` | `bool` | `true` once package has been exported |

---

## Supported Audio Formats (Import)

| Format | Supported |
|--------|-----------|
| WAV | ✅ |
| MP3 | ✅ |
| FLAC | ❌ |
| OGG | ❌ |
| M4A | ❌ |

---

## Future Avatar Pipeline Integration Points

The `combined.wav` file generated during F5 import is the **primary integration point** for future avatar systems:

```
voices/combined.wav
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  Future Avatar Pipeline                               │
│                                                       │
│  avatar_provider: "liveportrait"                      │
│    → LivePortrait drives face from combined.wav       │
│                                                       │
│  avatar_provider: "musetalk"                          │
│    → MuseTalk generates lip-sync video                │
│                                                       │
│  avatar_provider: "sadtalker"                         │
│    → SadTalker generates talking head                 │
└──────────────────────────────────────────────────────┘
```

The `avatar_provider` field is already present in `config.json` (stored as `null` in Phase 1).  Adding avatar support in a future phase requires:

1. Creating `services/avatar/providers/<name>.py`
2. Adding a factory in `services/avatar/factory.py`
3. Calling `get_avatar_provider(project_id).generate(combined_wav)` in `render_service.py` after `_merge_audio_ffmpeg`.

No changes to existing voice or rendering code will be needed.

---

## Backward Compatibility

Old projects that do not have `voice_provider` in their `config.json` automatically use Edge-TTS.  The factory function `get_voice_provider()` defaults to `"edge"` when the key is absent.

Old `voice_results.json` files that do not have a `provider` field will deserialise correctly because `SceneVoiceResult.provider` defaults to `"edge"`.

---

## Adding a New Voice Provider

1. Create `services/voice/providers/<name>.py` extending `VoiceProvider`.
2. Implement `async def generate(self, project_id, script, voice) -> List[SceneVoiceResult]`.
3. Register the provider in `services/voice/factory.py`:
   ```python
   _PROVIDERS["elevenlabs"] = "services.voice.providers.elevenlabs.ElevenLabsProvider"
   ```
4. Add `"elevenlabs"` as a valid option in `GenerateScriptRequest.voice_provider`.
5. Add it to the frontend dropdown in `app/page.tsx`.
