from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import random
from typing import List, Dict

from app.core.trends import get_trending_memes, reddit
from app.core.faceswap import swap_faces

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


@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Main page: Display trending memes with Drew face-swaps.
    """
    try:
        trends = get_trending_memes()
        # Shuffle to show different memes on each refresh
        random.shuffle(trends)
    except Exception as e:
        return HTMLResponse(
            content=f"<html><body><h1>Error fetching trends</h1><p>{str(e)}</p></body></html>",
            status_code=500
        )

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Drew Meme Generator</title>
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
            .subtitle {
                text-align: center;
                color: #666;
                margin-bottom: 30px;
            }
            .meme-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 20px;
            }
            .meme-card {
                background: white;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .meme-card img {
                width: 100%;
                height: auto;
                border-radius: 4px;
                margin-bottom: 10px;
            }
            .meme-title {
                font-weight: bold;
                color: #333;
                margin-bottom: 5px;
            }
            .meme-meta {
                font-size: 0.9em;
                color: #666;
            }
            .error {
                color: red;
                padding: 10px;
                background: #fee;
                border-radius: 4px;
                margin: 10px 0;
            }
            .loading {
                text-align: center;
                color: #666;
                padding: 20px;
            }
        </style>
    </head>
    <body>
        <h1>Drew Meme Generator</h1>
        <p class="subtitle">Trending Reddit memes with Drew's face auto-swapped</p>

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

        <div style="text-align: center; margin-bottom: 30px;">
            <button
                onclick="location.reload();"
                style="padding: 12px 24px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold;"
            >
                🔄 Refresh Trending Memes
            </button>
        </div>

        <div class="meme-grid">
    """

    # Process memes until we have 2 successful face swaps (reduced from 3 to save memory)
    successful_swaps = 0
    target_swaps = 2

    for trend in trends:
        if successful_swaps >= target_swaps:
            break

        try:
            swapped_path = swap_faces(trend["url"])
            if swapped_path:
                # Only add to output if face swap was successful
                html += f"""
                <div class="meme-card">
                    <img src="/{swapped_path}" alt="{trend['title']}" loading="lazy">
                    <div class="meme-title">{trend['title'][:80]}...</div>
                    <div class="meme-meta">
                        r/{trend['sub']} • Score: {trend['score']}
                    </div>
                </div>
                """
                successful_swaps += 1
            else:
                # Skip memes with no faces detected
                print(f"Skipping meme (no faces): {trend['title'][:50]}")
        except Exception as e:
            # Skip memes that error during processing
            print(f"Skipping meme (error): {trend['title'][:50]} - {str(e)[:100]}")

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
        trends = get_trending_memes()
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
    return {"status": "healthy", "service": "drew-meme-generator"}


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
        # Search Reddit for matching memes
        try:
            # Search across meme subreddits
            search_results = []
            for subreddit_name in ['memes', 'dankmemes', 'wholesomememes']:
                try:
                    subreddit = reddit.subreddit(subreddit_name)
                    for post in subreddit.search(query, limit=10):
                        if any(ext in post.url.lower() for ext in ['.jpg', '.jpeg', '.png', 'i.redd.it', 'i.imgur.com']):
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


if __name__ == "__main__":
    import uvicorn
    # Support both PORT (Render) and FLASK_PORT (local .env)
    port = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5000")))
    uvicorn.run(app, host="0.0.0.0", port=port)
