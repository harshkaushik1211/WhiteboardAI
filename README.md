# AI Educational Whiteboard Video Generator

Generate polished animated educational whiteboard videos locally from a single topic input.

## Features

- Topic → Script → Semantic visual plan → SVG asset retrieval → Layout → Voice → Remotion → MP4
- OpenAI GPT-4o for script and semantic visual planning
- Local curated SVG asset library (biology, physics, CS, etc.) — no random primitives
- Edge-TTS for narration (free, local)
- SVG stroke-reveal animations (Golpo / VideoScribe style)
- Remotion + FFmpeg for GPU-accelerated local rendering
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

## Full Pipeline (step-by-step)

From the **Project Viewer** (`/project/{id}`) you can run each stage manually:

1. **Scenes** — OpenAI semantic visual plan (concepts + layout, not geometry)
2. **SVGs** — Retrieved from local asset library and composed on canvas
3. **Voice** — Edge-TTS narration per scene
4. **Render Video** — Remotion render + FFmpeg encode

**Generate Full Video** on the home page runs the entire pipeline in one click.

## Visual modes

On the home page, choose **Visual source**:

| Mode | How visuals are built | Animation |
|------|----------------------|-----------|
| **Asset library** (default) | Match narration to curated SVGs under `assets/` | Per-icon stroke reveal |
| **AI line art** | `gpt-4o-mini` draws 2–3 outline SVG layers per scene | Staggered stroke reveal per layer |
| **AI image** | `gpt-image-1-mini` draws one PNG per scene (like [storyboard-ai](https://github.com/yogendra-yatnalkar/storyboard-ai)) | Left-to-right wipe reveal (no SAM) |

AI line art uses the **text** API (not DALL·E / `gpt-image-1-mini`). Each scene returns **2–3 layered SVGs** (e.g. box at rest → force arrow → box moved) drawn in sequence with staggered stroke reveal. Rough cost: ~$0.02–0.08 for an 8-scene / 60s video.

Env (optional in `.env`):

```bash
OPENAI_LINE_ART_MODEL=gpt-4o-mini
OPENAI_IMAGE_MODEL=gpt-image-1-mini
OPENAI_IMAGE_QUALITY=low
OPENAI_IMAGE_SIZE=1536x1024
VISUAL_MODE_DEFAULT=library
```

### Example: Newton’s first law (AI line art)

Topic: `Newton's laws`, visual source: **AI line art**, duration 60–90s.

Scene 1 prompt intent (automatic from script narration):

- Left: box on the ground, label “at rest”
- Right: same box with arrow labeled “force”, box shifted
- Outline only, navy stroke `#1a1a2e`, 1920×1080 whiteboard

The model writes SVG paths per layer; the renderer draws layer 1, then layer 2, then layer 3 (files like `scene-1-layer-1.svg`), then narration plays.

Audit file: `generated/projects/{id}/ai_sketch_audit.json`. Preview sketches on the project page.

## Semantic SVG Asset Pipeline

Educational visuals are **retrieved**, not procedurally drawn:

1. LLM outputs `required_visuals` (e.g. lungs, mitochondria, oxygen) per scene
2. [`svg_retriever`](backend/services/svg_retriever.py) matches concepts to [`assets/`](assets/)
3. [`layout_engine`](backend/services/layout_engine.py) positions assets (flow, pipeline, anatomy layouts)
4. Remotion animates real SVG paths with stroke reveal

### Adding assets

**From [SVG Repo](https://www.svgrepo.com/) (CC0 icons):**

1. Open an icon on svgrepo.com and copy the URL (e.g. `https://www.svgrepo.com/svg/489281/api`).
2. Download into the library:

```bash
python3 scripts/download_svgrepo.py \
  --url "https://www.svgrepo.com/svg/489281/api" \
  --concept lungs --category biology \
  --normalize --reindex
```

Or batch via `assets/svgrepo_manifest.json` (see `assets/svgrepo_manifest.example.json`):

```bash
python3 scripts/download_svgrepo.py --manifest assets/svgrepo_manifest.json --normalize --reindex
```

API: `POST /assets/svgrepo/download` with JSON `{"url": "...", "concept": "lungs", "category": "biology"}`.

**Curated (generated locally, no download):**

```bash
python3 scripts/generate_curated_assets.py
python3 scripts/normalize_svg_assets.py
curl -X POST http://localhost:8000/assets/reindex
```

Topic hints live in [`assets/semantic_memory.json`](assets/semantic_memory.json). Scene templates in [`templates/`](templates/).

### Photosynthesis video (single diagram)

Uses one full diagram SVG: [`assets/biology/photosynthesis-diagram.svg`](assets/biology/photosynthesis-diagram.svg) (Wikipedia-style illustration; colors preserved).

You can also keep your file as `assets/960px-Photosynthesis_en.svg.svg` — the indexer picks up any `*photosynthesis-diagram*.svg` under `assets/`.

Generate with topic **`photosynthesis`**, duration **90–120 seconds** (8 scenes). The video keeps the same diagram on screen, pans/zooms to each labeled part (light, CO₂, water, oxygen, glucose), with static scene headlines and narration.

Config: [`assets/semantic_memory.json`](assets/semantic_memory.json) + [`templates/biology/photosynthesis.json`](templates/biology/photosynthesis.json).

## Project Structure

```
animate_whiteboard/
├── frontend/          # Next.js 14 UI
├── backend/           # FastAPI pipeline
├── renderer/          # Remotion compositions
├── assets/            # Curated SVG library + index
├── templates/         # Topic scene templates
└── generated/         # Per-project outputs
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/generate-script` | Generate educational script |
| POST | `/generate-scenes` | Plan visual elements per scene |
| POST | `/generate-svg` | Generate SVG assets |
| POST | `/generate-voice` | Edge-TTS narration |
| POST | `/render-video` | Full render pipeline |
| GET | `/project/{id}` | Project status and artifacts |
| WS | `/ws/{job_id}` | Render progress stream |

## Pipeline

1. User enters topic + duration + voice style
2. OpenAI generates script JSON with scenes
3. Scene planner produces diagram elements
4. SVG engine creates hand-drawn assets
5. Edge-TTS generates narration + timestamps
6. Timeline sync builds `render_manifest.json`
7. Remotion renders 1080p video
8. FFmpeg merges audio and exports MP4

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model for script/scenes |
| `FFMPEG_PATH` | system `ffmpeg` | FFmpeg binary path |
| `REMOTION_CONCURRENCY` | `4` | Parallel render threads |

## License

MIT
