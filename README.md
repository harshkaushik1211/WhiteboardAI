# AI Educational Whiteboard Video Generator

Generate polished animated educational whiteboard videos locally from a single topic input.

## Features

- Topic → Script → AI whiteboard image per scene → Stroke reveal → Voice → Remotion → MP4
- OpenAI GPT-4o for script and lesson planning
- `gpt-image-1-mini` generates one whiteboard PNG per scene
- Object-wise stroke-reveal animation (storyboard-ai style)
- Edge-TTS for narration (free, local)
- Remotion + FFmpeg for local rendering
- Next.js 14 UI with preview and export

## Prerequisites

- **Node.js** 18+ (v24 recommended)
- **Python** 3.9+
- **FFmpeg** (`brew install ffmpeg` on macOS)
- **OpenAI API key**

## Quick Start

### 1. Environment

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Renderer (install deps)

```bash
cd renderer
npm install
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**, enter a topic (e.g. "Newton Laws"), and generate.

Or use helper scripts from the repo root:

```bash
chmod +x scripts/*.sh
./scripts/start-backend.sh   # terminal 1
./scripts/start-frontend.sh  # terminal 2
```

## Pipeline

1. User enters topic + duration + voice style
2. OpenAI generates educational script with scenes
3. `gpt-image-1-mini` draws one whiteboard PNG per scene
4. Stroke extractor builds object-wise reveal order
5. Edge-TTS generates narration per scene
6. Timeline sync builds `render_manifest.json`
7. Remotion renders 1080p video with stroke animation
8. FFmpeg merges audio and exports MP4

**Generate Full Video** on the home page runs the entire pipeline in one click.

From the **Project Viewer** (`/project/{id}`) you can run each stage manually:

1. **Images** — Generate scene PNGs + stroke data
2. **Voice** — Edge-TTS narration per scene
3. **Render Video** — Remotion render + FFmpeg encode

## AI image pipeline

Each scene:

1. GPT writes an image prompt from narration + visual description
2. `gpt-image-1-mini` generates a 1536×1024 whiteboard PNG
3. Stroke extractor segments ink and orders grid cells for reveal
4. Remotion animates ink → color object-by-object

Env (optional in `.env`):

```bash
OPENAI_IMAGE_MODEL=gpt-image-1-mini
OPENAI_IMAGE_QUALITY=low
OPENAI_IMAGE_SIZE=1536x1024
OPENAI_LINE_ART_MODEL=gpt-4o-mini   # used for image prompt writing
```

Audit file: `generated/projects/{id}/ai_image_audit.json`. Preview sketches on the project page.

## Project Structure

```
WhiteboardAI/
├── frontend/          # Next.js 14 UI
├── backend/           # FastAPI pipeline
├── renderer/          # Remotion compositions
└── generated/         # Per-project outputs
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/generate-script` | Generate educational script |
| POST | `/generate-scenes` | Generate scene PNGs + stroke data |
| POST | `/generate-voice` | Edge-TTS narration |
| POST | `/render-video` | Full render pipeline |
| GET | `/project/{id}` | Project status and artifacts |
| WS | `/ws/{job_id}` | Render progress stream |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model for script/scenes |
| `OPENAI_IMAGE_MODEL` | `gpt-image-1-mini` | Image model per scene |
| `FFMPEG_PATH` | system `ffmpeg` | FFmpeg binary path |
| `REMOTION_CONCURRENCY` | `4` | Parallel render threads |

## License

MIT
