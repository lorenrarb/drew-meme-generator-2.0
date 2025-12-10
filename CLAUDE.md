# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Drew Meme Generator is a FastAPI web application that auto-detects trending memes from Reddit and performs AI-powered face-swapping with Drew's face using InsightFace. It also supports custom meme generation via search or direct image URLs, plus celebrity face-swapping using Wikimedia images.

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Run development server with hot reload
python -m uvicorn app.main:app --reload --port 5000

# Direct run (production mode)
python app/main.py
```

### Testing Individual Components
```bash
# Test Reddit trending fetcher
python app/core/trends.py

# Test face swap functionality
python app/core/faceswap.py
```

## Architecture

### Core Application Flow

1. **Startup** (`app/main.py:startup_event`): Pre-warms InsightFace models and Drew's face cache for faster first request
2. **Homepage Request** (`app/main.py:root`):
   - Checks `static/meme_cache.json` for cached memes (24h TTL)
   - If cache valid: instant load from cache
   - If cache expired: generates 3 fresh face-swapped memes and caches them
3. **Face Swap Pipeline**: Reddit fetch → face detection → face swap → image compression → cache save

### Key Modules

**`app/main.py`** (FastAPI Application)
- Main web server with HTML rendering
- Endpoints: `/` (homepage), `/api/trends`, `/api/swap`, `/custom` (search/URL), `/celebrity`, `/api/refresh-cache`
- Drew's face caching in memory via `get_drew_face()` to avoid reloading on every request
- Startup pre-warming of InsightFace models for better performance

**`app/core/trends.py`** (Reddit Integration)
- Fetches trending memes from safe subreddits: wholesomememes, memes, aww, funny
- Content filtering: blocks NSFW posts and vulgar keywords via `is_content_appropriate()`
- 2-hour Redis cache with in-memory fallback
- Returns deduplicated, score-sorted meme list

**`app/core/faceswap.py`** (Face Swap Engine)
- Lazy-loads InsightFace models (`get_face_app()`, `get_face_swapper()`) to avoid startup delays
- Uses buffalo_l for face detection and inswapper_128.onnx for face swapping
- Model download: tries local `./models/`, `/tmp/`, or `~/.insightface/models/` in priority order
- Downloads 529MB inswapper model from HuggingFace on first run if not found
- Image optimization: JPEG quality 85, PNG compression level 6
- Aggressive memory cleanup after each swap to prevent OOM

**`app/core/cache.py`** (Meme Cache System)
- File-based cache at `static/meme_cache.json` with 24h TTL
- Stores pre-generated face-swapped memes for instant homepage loading
- Functions: `load_cached_memes()`, `save_cached_memes()`, `is_cache_valid()`, `clear_cache()`

**`app/core/celebrity.py`** (Celebrity Search)
- Searches Wikimedia Commons for celebrity photos
- Filters out icons, logos, signatures for better portrait results
- Randomly selects from available images for variety

### Important Implementation Details

**Performance Optimizations:**
- Model pre-warming on startup (app/main.py:56-73)
- Drew's face cached in memory to avoid repeated file I/O (app/main.py:14-32)
- Face-swapped memes cached for 24h (app/core/cache.py)
- Image compression: JPEG quality 85 reduces file size ~60% with minimal quality loss
- Large celebrity images auto-resized to 1200px width before processing
- Aggressive memory cleanup with `gc.collect()` after each face swap

**Content Safety:**
- Safe subreddits only: wholesomememes, memes, aww, funny (app/core/trends.py:42)
- NSFW flag checking and keyword filtering (app/core/trends.py:45-66)
- Blocked keywords list includes vulgar language and inappropriate terms

**Error Handling:**
- Face detection failures return `None` instead of raising exceptions for better UX
- Model loading failures print warnings but allow app to continue
- Redis connection failures gracefully fallback to in-memory cache

**Deployment Considerations:**
- Supports multiple deployment platforms: Vercel, Railway, Render, Fly.io
- PORT environment variable for dynamic port binding (Railway/Render)
- Model persistence: tries to save to `./models/` for deployment, falls back to `/tmp/`
- First deployment requires ~150MB InsightFace models + 529MB inswapper model download

## Environment Variables

Required:
- `REDDIT_CLIENT_ID` - Reddit API client ID
- `REDDIT_CLIENT_SECRET` - Reddit API secret
- `REDDIT_USER_AGENT` - Reddit API user agent (e.g., "drewmemeapp")

Optional:
- `GROK_API_KEY` - Grok API key for LLM guidance (currently unused in main flow)
- `DREW_FACE_PATH` - Path to Drew's face image (default: `./assets/drew_face.jpg`)
- `CACHE_TTL_HOURS` - Reddit trends cache TTL in hours (default: 2)
- `PORT` or `FLASK_PORT` - Server port (default: 5000)

## Code Patterns to Follow

**Face Swap Operations:**
- Always use `get_face_app()` and `get_face_swapper()` for lazy model loading
- Use `get_drew_face()` from main.py when available to reuse cached Drew's face
- Include aggressive memory cleanup (`del` objects + `gc.collect()`) after processing
- Return `None` on face detection failure, don't raise exceptions

**Adding New Endpoints:**
- Follow existing HTML response pattern with inline CSS for consistency
- Include "Back to Home" navigation links
- Add cache status indicators where relevant
- Use form-based POST for user input with `Form(...)` parameter

**Reddit Integration:**
- Always use `is_content_appropriate()` before adding memes to results
- Search within `SAFE_SUBREDDITS` only
- Handle subreddit access failures gracefully (some may be private/banned)

**Caching:**
- Check cache validity before generating fresh content
- Save cache immediately after successful generation
- Include cache age in health checks and user-facing messages
- memorize Every time we add a feature or fix a bug, create and push a commit.