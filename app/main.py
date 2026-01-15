from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import random
from typing import List, Dict

from app.core.trends import get_trending_memes, reddit, is_content_appropriate, SAFE_SUBREDDITS
from app.core.faceswap import swap_faces
from app.core.celebrity import search_celebrity_images
from app.core.cache import load_cached_memes, save_cached_memes, is_cache_valid, get_cache_age

# Cache for Drew's face to avoid reloading
_drew_face_cache = None

def get_drew_face():
    """Get cached Drew's face and source face."""
    global _drew_face_cache
    if _drew_face_cache is None:
        import cv2
        from app.core.faceswap import get_face_app
        drew_face_path = os.getenv("DREW_FACE_PATH", "./assets/drew_face.jpg")
        source_img = cv2.imread(drew_face_path)
        if source_img is not None:
            app_face = get_face_app()
            if app_face is not None:
                source_faces = app_face.get(source_img)
                if len(source_faces) > 0:
                    _drew_face_cache = (source_img, source_faces[0])
                    print("Drew's face cached successfully")
    return _drew_face_cache

app = FastAPI(
    title="Drew Meme Generator",
    description="Auto-detect trending memes and face-swap with Drew's face",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Startup event to pre-warm models for faster first request
@app.on_event("startup")
async def startup_event():
    """Pre-warm face detection models on startup for better performance."""
    print("🚀 Starting up Drew Meme Generator...")
    print("🔥 Pre-warming face detection models...")

    try:
        # Load models in background
        from app.core.faceswap import get_face_app, get_face_swapper
        get_face_app()
        get_face_swapper()

        # Pre-load Drew's face
        get_drew_face()

        print("✅ Models loaded and ready!")
    except Exception as e:
        print(f"⚠️  Warning: Model pre-warming failed: {e}")
        print("Models will load on first request instead.")

    # Check cache status
    cache_age = get_cache_age()
    if is_cache_valid():
        print(f"✅ Cache is valid (age: {cache_age:.1f}h)")
    else:
        print("⚠️  No valid cache found - first homepage load will generate fresh memes")


async def generate_fresh_memes() -> List[Dict]:
    """Generate fresh face-swapped memes (called when cache is expired)."""
    trends = await get_trending_memes()
    random.shuffle(trends)

    memes = []
    successful_swaps = 0
    target_swaps = 3  # Generate 3 memes for cache
    max_attempts = 15

    for attempt, trend in enumerate(trends):
        if successful_swaps >= target_swaps or attempt >= max_attempts:
            break

        try:
            swapped_path = swap_faces(trend["url"])
            if swapped_path:
                memes.append({
                    "swapped_path": swapped_path,
                    "title": trend["title"],
                    "sub": trend["sub"],
                    "score": trend["score"]
                })
                successful_swaps += 1
                print(f"Cached meme {successful_swaps}/{target_swaps}: {trend['title'][:50]}")
        except Exception as e:
            print(f"Error generating meme: {str(e)[:100]}")

    return memes


@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Main page: Display trending memes with Drew face-swaps.
    Uses cache for instant loading!
    """
    # Try to load from cache first
    cached_memes = load_cached_memes()
    cache_age = get_cache_age()

    if cached_memes and len(cached_memes) > 0:
        # Serve from cache instantly!
        memes = cached_memes
        cache_status = f"⚡ Lightning-fast load! (cached {cache_age:.1f}h ago)" if cache_age else "⚡ From cache"
        print(f"Serving {len(memes)} memes from cache")
    else:
        # Generate fresh memes if no cache
        cache_status = "🔄 Generating fresh memes..."
        print("No valid cache, generating fresh memes")
        try:
            memes = await generate_fresh_memes()
            # Save to cache for next time
            if len(memes) > 0:
                save_cached_memes(memes)
        except Exception as e:
            return HTMLResponse(
                content=f"<html><body><h1>Error fetching trends</h1><p>{str(e)}</p></body></html>",
                status_code=500
            )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Drew Meme Generator</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            h1 {{
                color: #333;
                text-align: center;
            }}
            .subtitle {{
                text-align: center;
                color: #666;
                margin-bottom: 10px;
            }}
            .cache-status {{
                text-align: center;
                color: #28a745;
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 20px;
            }}
            .meme-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 20px;
            }}
            .meme-card {{
                background: white;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .meme-card img {{
                width: 100%;
                height: auto;
                border-radius: 4px;
                margin-bottom: 10px;
            }}
            .meme-title {{
                font-weight: bold;
                color: #333;
                margin-bottom: 5px;
            }}
            .meme-meta {{
                font-size: 0.9em;
                color: #666;
            }}
            .error {{
                color: red;
                padding: 10px;
                background: #fee;
                border-radius: 4px;
                margin: 10px 0;
            }}
            .loading {{
                text-align: center;
                color: #666;
                padding: 20px;
            }}
        </style>
    </head>
    <body>
        <h1>Drew Meme Generator</h1>
        <p class="subtitle">Trending Reddit memes with Drew's face auto-swapped</p>
        <p class="cache-status">{cache_status}</p>

        <div style="max-width: 600px; margin: 0 auto 30px auto;">
            <form action="/custom" method="post" style="display: flex; gap: 10px;">
                <input
                    type="text"
                    name="query"
                    placeholder="Search for a meme or paste image URL..."
                    style="flex: 1; padding: 12px; border: 2px solid #ddd; border-radius: 4px; font-size: 16px;"
                    required
                />
                <button
                    type="submit"
                    style="padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;"
                >
                    Swap Face
                </button>
            </form>
            <p style="text-align: center; color: #999; font-size: 14px; margin-top: 10px;">
                Enter keywords to search Reddit or paste a direct image URL
            </p>
        </div>

        <div style="max-width: 600px; margin: 0 auto 30px auto; padding-top: 20px; border-top: 2px solid #ddd;">
            <h3 style="text-align: center; color: #555; margin-bottom: 15px;">Celebrity Face Swap</h3>
            <form action="/celebrity" method="post" style="display: flex; gap: 10px;">
                <input
                    type="text"
                    name="celebrity_name"
                    placeholder="Enter celebrity name (e.g., Tom Hanks, Taylor Swift)..."
                    style="flex: 1; padding: 12px; border: 2px solid #ddd; border-radius: 4px; font-size: 16px;"
                    required
                />
                <button
                    type="submit"
                    style="padding: 12px 24px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;"
                >
                    Drew-ify
                </button>
            </form>
            <p style="text-align: center; color: #999; font-size: 14px; margin-top: 10px;">
                Type a celebrity's name and we'll put Drew's face on their photos!
            </p>
        </div>

        <div style="text-align: center; margin-bottom: 30px;">
            <a
                href="/refresh"
                style="display: inline-block; padding: 12px 24px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; text-decoration: none;"
            >
                🔄 Refresh Trending Memes
            </a>
        </div>

        <div class="meme-grid">
    """

    # Render cached memes
    for meme in memes:
        html += f"""
            <div class="meme-card">
                <img src="/{meme['swapped_path']}" alt="{meme['title']}" loading="lazy">
                <div class="meme-title">{meme['title'][:80]}...</div>
                <div class="meme-meta">
                    r/{meme['sub']} • Score: {meme['score']}
                </div>
            </div>
        """

    html += """
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.get("/api/trends")
async def api_trends(limit: int = 20) -> List[Dict]:
    """
    API endpoint: Get raw trending memes data without face-swap.
    """
    try:
        trends = await get_trending_memes()
        return trends[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/swap")
async def api_swap(url: str) -> Dict:
    """
    API endpoint: Perform face-swap on a specific image URL.

    Args:
        url: Image URL to process

    Returns:
        Dictionary with swap result path
    """
    try:
        result_path = swap_faces(url)
        if result_path:
            return {
                "success": True,
                "swapped_image": f"/{result_path}",
                "original_url": url
            }
        else:
            raise HTTPException(status_code=400, detail="Face swap failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    cache_age = get_cache_age()
    return {
        "status": "healthy",
        "service": "drew-meme-generator",
        "cache_age_hours": round(cache_age, 2) if cache_age else None,
        "cache_valid": is_cache_valid()
    }


@app.get("/refresh")
async def refresh_memes():
    """
    Clear cache and redirect to homepage to force fresh meme generation.
    This is the user-facing refresh button endpoint.
    """
    try:
        print("User requested meme refresh - clearing cache...")
        from app.core.cache import clear_cache
        clear_cache()
        print("Cache cleared - redirecting to homepage for fresh memes")
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        print(f"Refresh error: {e}")
        return RedirectResponse(url="/", status_code=303)


@app.post("/api/refresh-cache")
async def refresh_cache():
    """
    Refresh the meme cache with fresh face-swapped memes.
    This endpoint can be called periodically (e.g., via cron job) to keep content fresh.
    """
    try:
        print("Starting cache refresh...")
        from app.core.cache import clear_cache
        clear_cache()

        # Generate fresh memes
        memes = await generate_fresh_memes()

        if len(memes) > 0:
            save_cached_memes(memes)
            return {
                "success": True,
                "message": f"Cache refreshed with {len(memes)} memes",
                "memes_count": len(memes)
            }
        else:
            return {
                "success": False,
                "message": "Failed to generate any memes"
            }
    except Exception as e:
        print(f"Cache refresh error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/custom")
async def custom_search(query: str = Form(...)):
    """
    Handle custom search or direct image URL face-swap.

    Args:
        query: Either a search query string or direct image URL

    Returns:
        HTML page with face-swapped result
    """
    # Check if query is a URL
    is_url = query.strip().startswith(('http://', 'https://'))

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Drew Meme Generator - Custom Result</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .back-link {
                text-align: center;
                margin-bottom: 20px;
            }
            .back-link a {
                color: #007bff;
                text-decoration: none;
                font-size: 16px;
            }
            .result-container {
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .result-container img {
                width: 100%;
                height: auto;
                border-radius: 4px;
                margin: 20px 0;
            }
            .meta {
                color: #666;
                text-align: center;
                margin-top: 10px;
            }
            .error {
                color: red;
                padding: 20px;
                background: #fee;
                border-radius: 4px;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <h1>Drew Meme Generator</h1>
        <div class="back-link">
            <a href="/">← Back to Trending Memes</a>
        </div>
        <div class="result-container">
    """

    if is_url:
        # Direct URL face-swap
        try:
            swapped_path = swap_faces(query)
            if swapped_path:
                html += f"""
                    <h2 style="text-align: center;">Custom Face Swap Result</h2>
                    <img src="/{swapped_path}" alt="Face-swapped meme">
                    <p class="meta">Source: {query[:100]}...</p>
                """
            else:
                html += f"""
                    <div class="error">
                        <h3>No faces detected in the image</h3>
                        <p>Try a different image with visible faces.</p>
                    </div>
                """
        except Exception as e:
            html += f"""
                <div class="error">
                    <h3>Error processing image</h3>
                    <p>{str(e)[:200]}</p>
                </div>
            """
    else:
        # Search Reddit for matching memes (safe subreddits only)
        try:
            # Search across safe meme subreddits with content filtering
            search_results = []
            for subreddit_name in SAFE_SUBREDDITS:
                try:
                    subreddit = await reddit.subreddit(subreddit_name)
                    async for post in subreddit.search(query, limit=10):
                        if any(ext in post.url.lower() for ext in ['.jpg', '.jpeg', '.png', 'i.redd.it', 'i.imgur.com']):
                            # Apply content filter
                            if is_content_appropriate(post.title, post):
                                search_results.append({
                                    "title": post.title,
                                    "url": post.url,
                                    "sub": subreddit_name,
                                    "score": post.score
                                })
                except:
                    continue

            # Sort by score and try to face-swap the first one with faces
            search_results.sort(key=lambda x: x['score'], reverse=True)

            swapped = False
            for result in search_results[:10]:
                try:
                    swapped_path = swap_faces(result['url'])
                    if swapped_path:
                        html += f"""
                            <h2 style="text-align: center;">Search Result: "{query}"</h2>
                            <img src="/{swapped_path}" alt="{result['title']}">
                            <h3 style="text-align: center;">{result['title']}</h3>
                            <p class="meta">r/{result['sub']} • Score: {result['score']}</p>
                        """
                        swapped = True
                        break
                except:
                    continue

            if not swapped:
                html += f"""
                    <div class="error">
                        <h3>No results found with faces</h3>
                        <p>Couldn't find any memes matching "{query}" with detectable faces.</p>
                        <p>Try different keywords or paste a direct image URL.</p>
                    </div>
                """
        except Exception as e:
            html += f"""
                <div class="error">
                    <h3>Search error</h3>
                    <p>{str(e)[:200]}</p>
                </div>
            """

    html += """
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@app.post("/celebrity")
async def celebrity_faceswap(celebrity_name: str = Form(...)):
    """
    Handle celebrity face swap - search for celebrity images and swap Drew's face.

    Args:
        celebrity_name: Name of the celebrity

    Returns:
        HTML page with face-swapped celebrity photos
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Drew Meme Generator - Celebrity Face Swap</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .back-link {
                text-align: center;
                margin-bottom: 20px;
            }
            .back-link a {
                color: #007bff;
                text-decoration: none;
                font-size: 16px;
            }
            .result-container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .celebrity-grid {
                display: flex;
                justify-content: center;
                margin-top: 30px;
            }
            .celebrity-card {
                background: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                max-width: 1000px;
                width: 100%;
            }
            .comparison-container {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 25px;
                margin-bottom: 20px;
            }
            .comparison-item {
                text-align: center;
            }
            .comparison-item img {
                width: 100%;
                height: auto;
                border-radius: 4px;
                border: 2px solid #ddd;
            }
            .comparison-label {
                font-weight: bold;
                margin-top: 8px;
                color: #555;
                font-size: 14px;
            }
            .meta {
                color: #666;
                text-align: center;
                margin-top: 10px;
                font-size: 14px;
            }
            .error {
                color: red;
                padding: 20px;
                background: #fee;
                border-radius: 4px;
                text-align: center;
                margin: 20px auto;
                max-width: 600px;
            }
            .loading {
                text-align: center;
                color: #666;
                padding: 40px;
                font-size: 18px;
            }
        </style>
    </head>
    <body>
        <h1>Drew Meme Generator</h1>
        <div class="back-link">
            <a href="/">← Back to Trending Memes</a>
        </div>
        <div class="result-container">
    """

    try:
        html += f"""
            <h2 style="text-align: center; color: #555;">Drew-ifying: {celebrity_name}</h2>
            <div class="loading">Searching for photos and swapping faces...</div>
        """

        # Search for celebrity images (fetch up to 10, randomly select 1)
        print(f"Searching for celebrity: {celebrity_name}")
        image_urls = search_celebrity_images(celebrity_name, num_images=1)

        if not image_urls:
            html += f"""
                <div class="error">
                    <h3>No images found</h3>
                    <p>Couldn't find photos for "{celebrity_name}".</p>
                    <p>Try a different name or check the spelling.</p>
                </div>
            """
        else:
            html += '<div class="celebrity-grid">'
            successful_swaps = 0

            for i, img_url in enumerate(image_urls):
                try:
                    print(f"Processing image {i+1}/{len(image_urls)}: {img_url}")

                    # Save original image to static folder
                    import requests
                    from io import BytesIO
                    from PIL import Image as PILImage
                    import time
                    import urllib.parse

                    # Create a simple, clean filename using timestamp and index
                    timestamp = int(time.time() * 1000)
                    # Get extension from URL
                    url_path = urllib.parse.urlparse(img_url).path
                    ext = os.path.splitext(url_path)[1]
                    if not ext or ext.lower() not in ['.jpg', '.jpeg', '.png']:
                        ext = '.jpg'

                    original_filename = f"original_{celebrity_name.replace(' ', '_')}_{i}_{timestamp}{ext}"
                    original_path = os.path.join('static', original_filename)

                    # Download image once and convert to both PIL and OpenCV formats
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    resp = requests.get(img_url, headers=headers, timeout=10)
                    resp.raise_for_status()

                    # Convert to PIL for saving original
                    img_pil = PILImage.open(BytesIO(resp.content))
                    if img_pil.mode != 'RGB':
                        img_pil = img_pil.convert('RGB')

                    # Optimize: Resize very large images to max 1200px width for faster processing
                    max_width = 1200
                    if img_pil.width > max_width:
                        ratio = max_width / img_pil.width
                        new_height = int(img_pil.height * ratio)
                        img_pil = img_pil.resize((max_width, new_height), PILImage.Resampling.LANCZOS)
                        print(f"Resized image from original size to {max_width}x{new_height} for faster processing")

                    # Save original
                    img_pil.save(original_path)
                    print(f"Saved original to: {original_path}")

                    # Perform face swap - use the same base filename
                    swapped_filename = f"swapped_{celebrity_name.replace(' ', '_')}_{i}_{timestamp}{ext}"
                    swapped_path_full = os.path.join('static', swapped_filename)

                    # Import face swap functions
                    from app.core.faceswap import get_face_app, get_face_swapper
                    import cv2
                    import numpy as np

                    # Pre-load models (already cached after first use)
                    app_face = get_face_app()
                    swapper = get_face_swapper()

                    if app_face is None:
                        raise ValueError("Face detection model not available")

                    # Use cached Drew's face (much faster)
                    drew_cache = get_drew_face()
                    if drew_cache is None:
                        raise ValueError("Could not load Drew's face")

                    source_img, source_face = drew_cache

                    # Convert PIL image to OpenCV format (reuse downloaded image)
                    meme_img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                    if meme_img is None:
                        raise ValueError(f"Could not process image: {img_url}")

                    target_faces = app_face.get(meme_img)
                    if len(target_faces) == 0:
                        print(f"No faces detected in image {i+1}")
                        continue

                    # Perform face swap
                    result_img = meme_img.copy()

                    if swapper is not None:
                        print(f"Swapping {len(target_faces)} face(s) with inswapper...")
                        for target_face in target_faces:
                            result_img = swapper.get(result_img, target_face, source_face, paste_back=True)
                        print("Inswapper face swap completed")

                    # Save result with clean filename
                    cv2.imwrite(swapped_path_full, result_img)
                    print(f"Face swap complete: {swapped_path_full}")

                    # Cleanup (but not source_img/source_face since they're cached)
                    del result_img, meme_img, target_faces, img_pil
                    import gc
                    gc.collect()

                    swapped_path = swapped_path_full

                    if swapped_path:
                        html += f"""
                            <div class="celebrity-card">
                                <div class="comparison-container">
                                    <div class="comparison-item">
                                        <img src="/{original_path}" alt="Original {celebrity_name}">
                                        <div class="comparison-label">Original</div>
                                    </div>
                                    <div class="comparison-item">
                                        <img src="/{swapped_path}" alt="{celebrity_name} with Drew's face">
                                        <div class="comparison-label">Drew-ified!</div>
                                    </div>
                                </div>
                            </div>
                        """
                        successful_swaps += 1
                    else:
                        print(f"No faces detected in image {i+1}")

                except Exception as e:
                    print(f"Error processing image {i+1}: {str(e)[:100]}")
                    continue

            html += '</div>'

            if successful_swaps == 0:
                html += f"""
                    <div class="error">
                        <h3>No faces detected</h3>
                        <p>Found photos for "{celebrity_name}" but couldn't detect any faces to swap.</p>
                        <p>Try a different celebrity.</p>
                    </div>
                """
            else:
                html += f"""
                    <p style="text-align: center; color: #28a745; margin-top: 20px; font-weight: bold; font-size: 18px;">
                        ✨ Drew-ification Complete! ✨
                    </p>
                    <div style="text-align: center; margin-top: 20px;">
                        <form action="/celebrity" method="post" style="display: inline;">
                            <input type="hidden" name="celebrity_name" value="{celebrity_name}">
                            <button
                                type="submit"
                                style="padding: 12px 24px; background: #17a2b8; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; margin-right: 10px;"
                            >
                                🔄 Try Another {celebrity_name} Photo
                            </button>
                        </form>
                        <a href="/" style="padding: 12px 24px; background: #6c757d; color: white; text-decoration: none; border-radius: 4px; font-size: 16px; font-weight: bold; display: inline-block;">
                            ← Back to Home
                        </a>
                    </div>
                """

    except Exception as e:
        html += f"""
            <div class="error">
                <h3>Error processing request</h3>
                <p>{str(e)[:200]}</p>
            </div>
        """
        print(f"Celebrity face swap error: {e}")
        import traceback
        traceback.print_exc()

    html += """
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    # Support both PORT (Render) and FLASK_PORT (local .env)
    port = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5000")))
    uvicorn.run(app, host="0.0.0.0", port=port)
