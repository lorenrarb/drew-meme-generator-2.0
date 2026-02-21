from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import time
import urllib.parse
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

from app.core.faceswap import swap_faces
from app.core.celebrity import search_celebrity_images
from pydantic import BaseModel

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
    description="Face-swap Drew onto celebrity photos or your own uploads",
    version="2.0.0"
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


@app.on_event("startup")
async def startup_event():
    """Pre-warm face detection models on startup for faster first request."""
    print("Starting up Drew Meme Generator 2.0...")
    print("Pre-warming face detection models...")

    # Check Grok API key availability
    if os.getenv("GROK_API_KEY"):
        print("GROK_API_KEY is set — roast feature enabled")
    else:
        print("WARNING: GROK_API_KEY not set — roast feature will be unavailable")

    try:
        from app.core.faceswap import get_face_app, get_face_swapper
        get_face_app()
        get_face_swapper()
        get_drew_face()
        print("Models loaded and ready!")
    except Exception as e:
        print(f"Warning: Model pre-warming failed: {e}")
        print("Models will load on first request instead.")


def _perform_face_swap(img_pil, prefix: str) -> Dict:
    """
    Shared face swap logic for both celebrity and upload endpoints.

    Args:
        img_pil: PIL Image in RGB mode
        prefix: Filename prefix (e.g. 'celebrity' or 'upload')

    Returns:
        Dict with original_path and swapped_path, or raises on failure
    """
    import cv2
    import numpy as np
    from PIL import Image as PILImage
    from app.core.faceswap import get_face_app, get_face_swapper
    import gc

    # Resize large images for faster processing
    max_width = 1200
    if img_pil.width > max_width:
        ratio = max_width / img_pil.width
        new_height = int(img_pil.height * ratio)
        img_pil = img_pil.resize((max_width, new_height), PILImage.Resampling.LANCZOS)

    # Save original
    timestamp = int(time.time() * 1000)
    original_filename = f"original_{prefix}_{timestamp}.jpg"
    original_path = os.path.join("static", original_filename)
    img_pil.save(original_path, "JPEG", quality=90)

    # Convert PIL to OpenCV
    meme_img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    app_face = get_face_app()
    swapper = get_face_swapper()
    if app_face is None:
        raise ValueError("Face detection model not available")

    drew_cache = get_drew_face()
    if drew_cache is None:
        raise ValueError("Could not load Drew's face")
    source_img, source_face = drew_cache

    target_faces = app_face.get(meme_img)
    if len(target_faces) == 0:
        raise ValueError("No faces detected in image")

    # Perform face swap
    result_img = meme_img.copy()
    if swapper is not None:
        for target_face in target_faces:
            result_img = swapper.get(result_img, target_face, source_face, paste_back=True)

    swapped_filename = f"swapped_{prefix}_{timestamp}.jpg"
    swapped_path = os.path.join("static", swapped_filename)
    cv2.imwrite(swapped_path, result_img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    # Memory cleanup
    del result_img, meme_img, target_faces
    gc.collect()

    return {
        "original_path": f"/{original_path}",
        "swapped_path": f"/{swapped_path}"
    }


# ── SPA Frontend ──────────────────────────────────────────────

SPA_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Drew Meme Generator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f5f5; color: #333; min-height: 100vh;
  }
  header {
    background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,.08);
    padding: 24px 0; text-align: center;
  }
  header h1 { font-size: 2rem; }
  header p { color: #666; margin-top: 6px; }
  .container { max-width: 960px; margin: 0 auto; padding: 24px 16px; }

  /* Cards */
  .card {
    background: #fff; border-radius: 12px; padding: 28px;
    box-shadow: 0 2px 8px rgba(0,0,0,.06); margin-bottom: 28px;
  }
  .card h2 { margin-bottom: 16px; font-size: 1.3rem; }

  /* Search bar */
  .search-row { display: flex; gap: 10px; }
  .search-row input {
    flex: 1; padding: 12px 16px; border: 2px solid #ddd; border-radius: 8px;
    font-size: 16px; outline: none; transition: border-color .2s;
  }
  .search-row input:focus { border-color: #007bff; }
  .btn {
    padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer;
    font-size: 16px; font-weight: 600; color: #fff; transition: opacity .2s;
  }
  .btn:hover { opacity: .85; }
  .btn:disabled { opacity: .5; cursor: not-allowed; }
  .btn-blue { background: #007bff; }
  .btn-red { background: #dc3545; }

  /* Spinner */
  .spinner {
    display: none; text-align: center; padding: 32px;
  }
  .spinner.active { display: block; }
  .spinner::after {
    content: ''; display: inline-block; width: 36px; height: 36px;
    border: 4px solid #ddd; border-top-color: #007bff; border-radius: 50%;
    animation: spin .7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Photo grid */
  .photo-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px; margin-top: 20px;
  }
  .photo-grid img {
    width: 100%; height: 160px; object-fit: cover; border-radius: 8px;
    cursor: pointer; border: 3px solid transparent; transition: border-color .2s, transform .15s;
  }
  .photo-grid img:hover { border-color: #007bff; transform: scale(1.03); }

  /* Before / After comparison */
  .comparison {
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;
  }
  .comparison .side { text-align: center; }
  .comparison img {
    width: 100%; height: auto; border-radius: 8px; border: 2px solid #ddd;
  }
  .comparison .label {
    margin-top: 8px; font-weight: 600; color: #555; font-size: 14px;
  }

  /* Drop zone */
  .drop-zone {
    border: 3px dashed #ccc; border-radius: 12px; padding: 48px 24px;
    text-align: center; color: #888; cursor: pointer; transition: border-color .2s, background .2s;
  }
  .drop-zone.dragover { border-color: #007bff; background: #f0f7ff; }
  .drop-zone p { font-size: 16px; }
  .drop-zone .hint { font-size: 13px; color: #aaa; margin-top: 8px; }

  /* Error */
  .error-msg {
    background: #fff0f0; color: #c00; padding: 14px 18px; border-radius: 8px;
    margin-top: 16px; display: none;
  }
  .error-msg.active { display: block; }

  /* Photo Booth — compact inline bar */
  .upload-bar {
    display: flex; align-items: center; gap: 12px;
    background: #fff; border-radius: 10px; padding: 12px 18px;
    border: 1px solid #e0e0e0; margin-bottom: 24px; flex-wrap: wrap;
  }
  .upload-bar .upload-label {
    font-size: 13px; color: #888; white-space: nowrap;
  }
  .upload-bar .btn-upload {
    padding: 8px 18px; border: 2px dashed #ccc; border-radius: 8px;
    background: #fafafa; cursor: pointer; font-size: 13px; color: #666;
    transition: border-color .2s, background .2s; white-space: nowrap;
  }
  .upload-bar .btn-upload:hover { border-color: #007bff; background: #f0f7ff; color: #007bff; }
  .upload-bar .upload-hint { font-size: 11px; color: #bbb; }
  #upload-result .comparison { margin-top: 16px; }

  /* Autocomplete */
  .search-wrapper { position: relative; flex: 1; }
  .search-wrapper input { width: 100%; }
  .autocomplete-list {
    position: absolute; top: 100%; left: 0; right: 0; z-index: 10;
    background: #fff; border: 1px solid #ddd; border-top: none;
    border-radius: 0 0 8px 8px; max-height: 220px; overflow-y: auto;
    box-shadow: 0 4px 12px rgba(0,0,0,.1); display: none;
  }
  .autocomplete-list.active { display: block; }
  .autocomplete-item {
    padding: 10px 16px; cursor: pointer; font-size: 15px;
    transition: background .15s;
  }
  .autocomplete-item:hover, .autocomplete-item.highlighted {
    background: #f0f7ff; color: #007bff;
  }

  /* Roast panel */
  .roast-panel {
    margin-top: 20px; padding: 20px; background: #fafafa; border-radius: 10px;
    border: 1px solid #e8e8e8;
  }
  .roast-panel h3 { font-size: 1rem; margin-bottom: 12px; }
  .preset-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
  .chip {
    padding: 8px 16px; border-radius: 20px; border: 2px solid #ddd;
    background: #fff; cursor: pointer; font-size: 14px; font-weight: 500;
    transition: all .2s; user-select: none;
  }
  .chip:hover { border-color: #007bff; color: #007bff; }
  .chip.active { border-color: #007bff; background: #007bff; color: #fff; }
  .roast-input {
    width: 100%; padding: 10px 14px; border: 2px solid #ddd; border-radius: 8px;
    font-size: 14px; outline: none; margin-bottom: 12px; transition: border-color .2s;
  }
  .roast-input:focus { border-color: #007bff; }
  .btn-roast {
    padding: 10px 22px; border: none; border-radius: 8px; cursor: pointer;
    font-size: 15px; font-weight: 600; color: #fff; background: #e65100;
    transition: opacity .2s;
  }
  .btn-roast:hover { opacity: .85; }
  .btn-roast:disabled { opacity: .5; cursor: not-allowed; }
  .roast-result {
    margin-top: 16px; padding: 18px 20px; background: #fff9e6;
    border-radius: 10px; border-left: 4px solid #e65100;
    font-size: 15px; line-height: 1.6; white-space: pre-wrap;
  }

  /* Responsive */
  @media (max-width: 600px) {
    .comparison { grid-template-columns: 1fr; }
    .photo-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
    .search-row { flex-direction: column; }
    .preset-chips { gap: 6px; }
    .chip { padding: 6px 12px; font-size: 13px; }
    .upload-bar { flex-direction: column; text-align: center; }
  }
</style>
</head>
<body>

<header>
  <h1>The Drew-ification Machine</h1>
  <p>Steal any celebrity's look. Then roast Drew for wearing it.</p>
</header>

<div class="container">

  <!-- Celebrity Face Swap -->
  <div class="card">
    <h2>Celebrity Face Swap</h2>
    <div class="search-row">
      <div class="search-wrapper">
        <input type="text" id="celeb-input" placeholder="Start typing a celebrity name..." autocomplete="off" />
        <div class="autocomplete-list" id="autocomplete-list"></div>
      </div>
      <button class="btn btn-blue" id="celeb-search-btn" onclick="searchCelebrity()">Search</button>
    </div>
    <div class="error-msg" id="celeb-error"></div>
    <div class="spinner" id="celeb-search-spinner"></div>
    <div id="celeb-grid" class="photo-grid"></div>
    <div class="spinner" id="celeb-swap-spinner"></div>
    <div id="celeb-result"></div>
  </div>

  <!-- Photo Booth — compact bar -->
  <div class="upload-bar" id="drop-zone">
    <span class="upload-label">Or use your own photo:</span>
    <span class="btn-upload" onclick="document.getElementById('file-input').click()">Choose file or drop here</span>
    <span class="upload-hint">JPEG, PNG, WebP &middot; max 10 MB</span>
    <input type="file" id="file-input" accept="image/jpeg,image/png,image/webp" style="display:none" />
  </div>
  <div class="error-msg" id="upload-error"></div>
  <div class="spinner" id="upload-spinner"></div>
  <div id="upload-result"></div>

</div>

<script>
// ── Autocomplete ──────────────────────────────────────────
const celebInput = document.getElementById('celeb-input');
const acList = document.getElementById('autocomplete-list');
let acTimer = null;
let acIndex = -1;

celebInput.addEventListener('input', () => {
  clearTimeout(acTimer);
  const q = celebInput.value.trim();
  if (q.length < 2) { acList.className = 'autocomplete-list'; return; }
  acTimer = setTimeout(() => fetchSuggestions(q), 250);
});

celebInput.addEventListener('keydown', e => {
  const items = acList.querySelectorAll('.autocomplete-item');
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    acIndex = Math.min(acIndex + 1, items.length - 1);
    highlightItem(items);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    acIndex = Math.max(acIndex - 1, 0);
    highlightItem(items);
  } else if (e.key === 'Enter') {
    if (acIndex >= 0 && items[acIndex]) {
      celebInput.value = items[acIndex].textContent;
      acList.className = 'autocomplete-list';
      acIndex = -1;
    }
    searchCelebrity();
  } else if (e.key === 'Escape') {
    acList.className = 'autocomplete-list';
    acIndex = -1;
  }
});

document.addEventListener('click', e => {
  if (!e.target.closest('.search-wrapper')) {
    acList.className = 'autocomplete-list';
    acIndex = -1;
  }
});

function highlightItem(items) {
  items.forEach((el, i) => el.classList.toggle('highlighted', i === acIndex));
}

async function fetchSuggestions(query) {
  try {
    const url = 'https://en.wikipedia.org/w/api.php?action=opensearch&limit=6&namespace=0&format=json&origin=*&search='
      + encodeURIComponent(query);
    const resp = await fetch(url);
    const data = await resp.json();
    const names = data[1] || [];
    acList.innerHTML = '';
    acIndex = -1;
    if (names.length === 0) { acList.className = 'autocomplete-list'; return; }
    names.forEach(name => {
      const div = document.createElement('div');
      div.className = 'autocomplete-item';
      div.textContent = name;
      div.onclick = () => {
        celebInput.value = name;
        acList.className = 'autocomplete-list';
        searchCelebrity();
      };
      acList.appendChild(div);
    });
    acList.className = 'autocomplete-list active';
  } catch (err) { /* silent fail for suggestions */ }
}

// ── Celebrity Search ───────────────────────────────────────

async function searchCelebrity() {
  const name = celebInput.value.trim();
  if (!name) return;

  // Dismiss autocomplete
  acList.className = 'autocomplete-list';
  acIndex = -1;

  const grid = document.getElementById('celeb-grid');
  const result = document.getElementById('celeb-result');
  const error = document.getElementById('celeb-error');
  const spinner = document.getElementById('celeb-search-spinner');
  const btn = document.getElementById('celeb-search-btn');

  grid.innerHTML = '';
  result.innerHTML = '';
  error.className = 'error-msg';
  error.textContent = '';
  spinner.className = 'spinner active';
  btn.disabled = true;

  try {
    const resp = await fetch('/api/celebrity/search?name=' + encodeURIComponent(name));
    const data = await resp.json();
    spinner.className = 'spinner';
    btn.disabled = false;

    if (!resp.ok) {
      error.textContent = data.detail || 'Search failed';
      error.className = 'error-msg active';
      return;
    }

    if (!data.images || data.images.length === 0) {
      error.textContent = 'No images found for "' + name + '". Try a different name.';
      error.className = 'error-msg active';
      return;
    }

    data.images.forEach(url => {
      const img = document.createElement('img');
      img.src = url;
      img.alt = name;
      img.loading = 'lazy';
      img.onclick = () => swapCelebrity(url);
      grid.appendChild(img);
    });
  } catch (err) {
    spinner.className = 'spinner';
    btn.disabled = false;
    error.textContent = 'Network error — please try again.';
    error.className = 'error-msg active';
  }
}

async function swapCelebrity(imageUrl) {
  const result = document.getElementById('celeb-result');
  const error = document.getElementById('celeb-error');
  const spinner = document.getElementById('celeb-swap-spinner');

  result.innerHTML = '';
  error.className = 'error-msg';
  spinner.className = 'spinner active';

  try {
    const resp = await fetch('/api/celebrity/swap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_url: imageUrl })
    });
    const data = await resp.json();
    spinner.className = 'spinner';

    if (!resp.ok) {
      error.textContent = data.detail || 'Face swap failed';
      error.className = 'error-msg active';
      return;
    }

    result.innerHTML = '<div class="comparison">'
      + '<div class="side"><img src="' + data.original_path + '"><div class="label">Original</div></div>'
      + '<div class="side"><img src="' + data.swapped_path + '"><div class="label">Drew-ified!</div></div>'
      + '</div>'
      + buildRoastPanel(data.original_path);
  } catch (err) {
    spinner.className = 'spinner';
    error.textContent = 'Network error — please try again.';
    error.className = 'error-msg active';
  }
}

// ── Roast ──────────────────────────────────────────────────
function buildRoastPanel(originalPath) {
  // Convert relative path to absolute URL for the API
  const absUrl = window.location.origin + originalPath;
  return '<div class="roast-panel">'
    + '<h3>Roast Drew</h3>'
    + '<div class="preset-chips">'
    + '  <span class="chip" data-preset="savage" onclick="toggleChip(this)">Extra Savage</span>'
    + '  <span class="chip" data-preset="outfit" onclick="toggleChip(this)">Roast the Outfit</span>'
    + '  <span class="chip" data-preset="gentle" onclick="toggleChip(this)">Be Gentle</span>'
    + '</div>'
    + '<input class="roast-input" type="text" placeholder="Add your own spin..." />'
    + '<button class="btn-roast" onclick="submitRoast(this, \\'' + absUrl.replace(/'/g, "\\\\'") + '\\')">Roast Drew</button>'
    + '<div class="spinner" id="roast-spinner"></div>'
    + '<div class="roast-result-container"></div>'
    + '</div>';
}

function toggleChip(el) {
  const siblings = el.parentElement.querySelectorAll('.chip');
  const wasActive = el.classList.contains('active');
  siblings.forEach(c => c.classList.remove('active'));
  if (!wasActive) el.classList.add('active');
}

async function submitRoast(btn, imageUrl) {
  const panel = btn.closest('.roast-panel');
  const activeChip = panel.querySelector('.chip.active');
  const customInput = panel.querySelector('.roast-input');
  const spinner = panel.querySelector('.spinner');
  const resultContainer = panel.querySelector('.roast-result-container');

  const preset = activeChip ? activeChip.dataset.preset : '';
  const customSpin = customInput ? customInput.value.trim() : '';

  btn.disabled = true;
  spinner.className = 'spinner active';
  resultContainer.innerHTML = '';

  try {
    const resp = await fetch('/api/roast', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_url: imageUrl, preset: preset, custom_spin: customSpin })
    });
    const data = await resp.json();
    spinner.className = 'spinner';
    btn.disabled = false;

    if (!resp.ok) {
      resultContainer.innerHTML = '<div class="error-msg active">' + (data.detail || 'Roast failed') + '</div>';
      return;
    }

    resultContainer.innerHTML = '<div class="roast-result">' + data.roast + '</div>';
  } catch (err) {
    spinner.className = 'spinner';
    btn.disabled = false;
    resultContainer.innerHTML = '<div class="error-msg active">Network error — please try again.</div>';
  }
}

// ── Photo Booth ────────────────────────────────────────────
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.style.borderColor = '#007bff'; dropZone.style.background = '#f0f7ff'; });
dropZone.addEventListener('dragleave', () => { dropZone.style.borderColor = ''; dropZone.style.background = ''; });
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.style.borderColor = ''; dropZone.style.background = '';
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => { if (fileInput.files.length) uploadFile(fileInput.files[0]); });

async function uploadFile(file) {
  const error = document.getElementById('upload-error');
  const spinner = document.getElementById('upload-spinner');
  const result = document.getElementById('upload-result');

  error.className = 'error-msg';
  result.innerHTML = '';

  // Validate
  const allowed = ['image/jpeg', 'image/png', 'image/webp'];
  if (!allowed.includes(file.type)) {
    error.textContent = 'Please upload a JPEG, PNG, or WebP image.';
    error.className = 'error-msg active';
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    error.textContent = 'File too large — max 10 MB.';
    error.className = 'error-msg active';
    return;
  }

  spinner.className = 'spinner active';

  try {
    const form = new FormData();
    form.append('file', file);

    const resp = await fetch('/api/upload/swap', { method: 'POST', body: form });
    const data = await resp.json();
    spinner.className = 'spinner';

    if (!resp.ok) {
      error.textContent = data.detail || 'Face swap failed';
      error.className = 'error-msg active';
      return;
    }

    result.innerHTML = '<div class="comparison">'
      + '<div class="side"><img src="' + data.original_path + '"><div class="label">Original</div></div>'
      + '<div class="side"><img src="' + data.swapped_path + '"><div class="label">Drew-ified!</div></div>'
      + '</div>'
      + buildRoastPanel(data.original_path);
  } catch (err) {
    spinner.className = 'spinner';
    error.textContent = 'Network error — please try again.';
    error.className = 'error-msg active';
  }

  // Reset file input so re-selecting same file triggers change event
  fileInput.value = '';
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the single-page app."""
    return HTMLResponse(content=SPA_HTML)


# ── Celebrity Endpoints ───────────────────────────────────────

@app.get("/api/celebrity/search")
async def celebrity_search(name: str):
    """Search for celebrity photos and return up to 10 image URLs."""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Name parameter is required")

    try:
        image_urls = search_celebrity_images(name.strip(), num_images=10)
        return {"name": name.strip(), "images": image_urls}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/celebrity/swap")
async def celebrity_swap(body: dict):
    """Download a celebrity image and perform face swap."""
    image_url = body.get("image_url")
    if not image_url:
        raise HTTPException(status_code=400, detail="image_url is required")

    try:
        import requests as req
        from PIL import Image as PILImage
        from io import BytesIO

        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = req.get(image_url, headers=headers, timeout=15)
        resp.raise_for_status()

        img_pil = PILImage.open(BytesIO(resp.content))
        if img_pil.mode != 'RGB':
            img_pil = img_pil.convert('RGB')

        result = _perform_face_swap(img_pil, "celebrity")
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Celebrity swap error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Upload Endpoint ───────────────────────────────────────────

@app.post("/api/upload/swap")
async def upload_swap(file: UploadFile = File(...)):
    """Accept a file upload and perform face swap."""
    # Validate content type
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are accepted")

    # Read and validate size (10 MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large — max 10 MB")

    try:
        from PIL import Image as PILImage
        from io import BytesIO

        img_pil = PILImage.open(BytesIO(contents))
        if img_pil.mode != 'RGB':
            img_pil = img_pil.convert('RGB')

        result = _perform_face_swap(img_pil, "upload")
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Upload swap error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Roast Endpoint ────────────────────────────────────────────

class RoastRequest(BaseModel):
    image_url: str
    preset: str = ""
    custom_spin: str = ""

ROAST_SYSTEM_PROMPT = """You are a workplace-appropriate roast comedian. You're roasting someone named Drew based on a photo.
Drew's known traits: risk averse, has luscious bangs, enormous calves, acts older than he is,
conservative spender, and extremely long-winded.

Look at the photo and call out specific details — attire, facial expression, pose, setting —
then weave them into a roast that mixes those observations with Drew's known traits.
Keep it professional enough for a workplace but make it sting. 2-3 paragraphs max."""

PRESET_GUIDANCE = {
    "savage": "Turn up the heat — be extra savage and ruthless with the roast. Don't hold back.",
    "outfit": "Focus heavily on what Drew is wearing in the photo. Roast the outfit, accessories, and overall fashion choices.",
    "gentle": "Be gentle — more playful teasing than a hard roast. Keep it lighthearted and fun.",
}

@app.post("/api/roast")
async def roast_drew(body: RoastRequest):
    """Generate a Grok-powered roast of Drew based on a photo."""
    grok_api_key = os.getenv("GROK_API_KEY")
    if not grok_api_key:
        raise HTTPException(status_code=503, detail="Roast feature unavailable — GROK_API_KEY not configured")

    if not body.image_url:
        raise HTTPException(status_code=400, detail="image_url is required")

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=grok_api_key,
            base_url="https://api.x.ai/v1"
        )

        # Build user message with optional preset and custom spin
        user_parts = ["Roast Drew based on this photo."]
        if body.preset and body.preset in PRESET_GUIDANCE:
            user_parts.append(PRESET_GUIDANCE[body.preset])
        if body.custom_spin:
            user_parts.append(f"Additional direction: {body.custom_spin}")

        response = client.chat.completions.create(
            model="grok-2-vision-1212",
            messages=[
                {"role": "system", "content": ROAST_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": body.image_url}},
                        {"type": "text", "text": " ".join(user_parts)},
                    ],
                },
            ],
            max_tokens=500,
            timeout=30,
        )

        roast_text = response.choices[0].message.content
        return {"roast": roast_text}

    except Exception as e:
        print(f"Roast error: {e}")
        raise HTTPException(status_code=500, detail=f"Roast generation failed: {str(e)}")


# ── Utility Endpoints ─────────────────────────────────────────

@app.get("/api/swap")
async def api_swap(url: str) -> Dict:
    """Perform face-swap on a specific image URL."""
    try:
        result_path = swap_faces(url)
        if result_path:
            return {
                "success": True,
                "swapped_image": f"/{result_path}",
                "original_url": url
            }
        else:
            raise HTTPException(status_code=400, detail="Face swap failed — no faces detected")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    grok_set = bool(os.getenv("GROK_API_KEY"))
    return {"status": "healthy", "service": "drew-meme-generator", "version": "2.0.0", "grok_available": grok_set}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5000")))
    uvicorn.run(app, host="0.0.0.0", port=port)
