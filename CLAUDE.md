# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Drew Meme Generator 2.0 is a single-page FastAPI web application that lets visitors:
1. **Search for celebrity photos** — pick one from a grid of ~10 results and get Drew's face swapped onto it
2. **Upload their own photo** (Photo Booth) — drag-and-drop or file picker, instant face swap

All interactions happen via JavaScript `fetch()` on one page — no redirects, no server-rendered HTML beyond the initial SPA shell.

## Development Commands

### Environment Setup
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Development with hot reload
python -m uvicorn app.main:app --reload --port 5000

# Direct run (production mode)
python app/main.py
```

## Architecture

### API Surface

```
GET  /                       → Single-page HTML app (all JS/CSS inline)
GET  /api/celebrity/search   → ?name=Tom+Hanks → JSON with up to 10 image URLs
POST /api/celebrity/swap     → {image_url: "..."} → JSON with original + swapped paths
POST /api/upload/swap        → FormData file upload → JSON with original + swapped paths
POST /api/roast              → {image_url, preset?, custom_spin?} → {roast: "..."}
GET  /api/swap               → ?url=... → Utility endpoint for direct URL face swap
GET  /health                 → Health check
```

### Key Modules

**`app/main.py`** (FastAPI Application + SPA Frontend)
- Serves inline HTML/CSS/JS single-page app at `GET /`
- JSON API endpoints for celebrity search, celebrity swap, and upload swap
- `_perform_face_swap(img_pil, prefix)` — shared helper used by both swap endpoints
- Drew's face caching in memory via `get_drew_face()`
- Startup pre-warming of InsightFace models

**`app/core/celebrity.py`** (Celebrity Image Search)
- `search_celebrity_images()` — returns up to 10 image URLs from Wikimedia Commons
- Wikipedia API with `imlimit=50` for broader image discovery
- DuckDuckGo fallback when Wikimedia returns < 5 results
- Filters out icons, logos, signatures, maps, charts

**`POST /api/roast`** (Grok Vision Roast)
- Sends the original celebrity/upload photo to Grok `grok-2-vision-1212` via OpenAI SDK
- System prompt includes Drew's roastable traits (risk averse, luscious bangs, enormous calves, acts old, cheap, long-winded)
- Presets: `savage`, `outfit`, `gentle` — inject tone guidance into user message
- Optional `custom_spin` free-text appended as additional user direction
- Requires `GROK_API_KEY` env var; returns 503 if not set
- 30s timeout on vision request

**`app/core/faceswap.py`** (Face Swap Engine)
- Lazy-loads InsightFace models (`get_face_app()`, `get_face_swapper()`)
- Uses buffalo_l for detection and inswapper_128.onnx for swapping
- Face quality threshold: 2% of image area minimum
- Auto-downloads 529MB inswapper model from HuggingFace on first run
- Aggressive memory cleanup after each swap

### Important Implementation Details

**Performance Optimizations:**
- Model pre-warming on startup
- Drew's face cached in memory (avoids repeated file I/O)
- Large images auto-resized to 1200px width before processing
- JPEG quality 85 output compression

**Face Swap Pipeline:**
1. Image received (download from URL or file upload)
2. Convert to RGB PIL Image, resize if > 1200px wide
3. Save original to `static/`
4. Convert to OpenCV BGR, detect faces with InsightFace
5. Swap all detected faces with cached Drew face via inswapper
6. Save result to `static/`, return both paths as JSON

## Environment Variables

Optional:
- `GROK_API_KEY` — Grok API key for the roast feature (uses `grok-2-vision-1212` via `api.x.ai`)
- `DREW_FACE_PATH` — Path to Drew's face image (default: `./assets/drew_face.jpg`)
- `PORT` or `FLASK_PORT` — Server port (default: 5000)

## Code Patterns to Follow

- Always use `get_face_app()` and `get_face_swapper()` for lazy model loading
- Use `get_drew_face()` to reuse cached Drew's face
- Include `gc.collect()` after face swap processing
- Return `None` on face detection failure, don't raise exceptions (in faceswap.py)
- Use `_perform_face_swap()` for new swap endpoints to avoid code duplication
- Every time we add a feature or fix a bug, create and push a commit.
