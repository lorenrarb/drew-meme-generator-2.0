# Drew Meme Generator

Auto-detect trending memes from Reddit and face-swap with Drew's face using AI.

## Features

- Fetches trending memes from Reddit (safe subreddits only)
- **Robust profanity filtering** using better-profanity library
  - Blocks NSFW content automatically
  - Detects profanity, variations, misspellings, and leetspeak
  - Custom blocklist for inappropriate content
- 2-hour caching for efficiency
- AI-powered face detection and swapping using InsightFace
- Optional LLM guidance via Grok API
- Clean web interface via FastAPI
- Ready for Vercel deployment

## Setup

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Your `.env` file should contain:

```
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=drewmemeapp
GROK_API_KEY=your_grok_key
DREW_FACE_PATH=./assets/drew_face.jpg
CACHE_TTL_HOURS=2
FLASK_PORT=5000
```

### 3. Run Locally

```bash
python -m uvicorn app.main:app --reload --port 5000
```

Visit: http://localhost:5000

### 4. Test Components

Test Reddit fetcher:
```bash
python app/core/trends.py
```

Test face swap:
```bash
python app/core/faceswap.py
```

## API Endpoints

- `GET /` - Main web interface with face-swapped memes
- `GET /api/trends` - Get raw trending memes data
- `GET /api/swap?url=<image_url>` - Swap faces in a specific image
- `GET /health` - Health check

## Deployment

### Vercel

1. Install Vercel CLI:
```bash
npm i -g vercel
```

2. Deploy:
```bash
vercel login
vercel --prod
```

3. Set environment variables in Vercel dashboard:
   - REDDIT_CLIENT_ID
   - REDDIT_CLIENT_SECRET
   - REDDIT_USER_AGENT
   - GROK_API_KEY

4. Add custom domain (www.drewgeiger.com) in Vercel dashboard

## Architecture

```
app/
├── main.py              # FastAPI application
└── core/
    ├── trends.py        # Reddit API + caching
    └── faceswap.py      # InsightFace + Grok integration
assets/
└── drew_face.jpg        # Source face for swapping
static/                  # Generated swapped images
```

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Reddit API**: PRAW
- **Face Swap**: InsightFace + OpenCV
- **LLM**: Grok API (xAI)
- **Cache**: Redis (with in-memory fallback)
- **Deployment**: Vercel

## Notes

- First run downloads InsightFace models (~150MB)
- Redis is optional; falls back to in-memory cache
- Grok API is pay-per-use for LLM guidance
- Face swap processes top 5 trending memes by default
