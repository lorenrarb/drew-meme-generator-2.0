import os
import cv2
import numpy as np
from PIL import Image
import requests
from io import BytesIO
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Config
DREW_FACE_PATH = os.getenv("DREW_FACE_PATH", "./assets/drew_face.jpg")
GROK_API_KEY = os.getenv("GROK_API_KEY")

# Lazy load insightface models to avoid startup delays
_face_app = None
_face_swapper = None


def get_face_app():
    """Lazy initialization of insightface face analysis model."""
    global _face_app
    if _face_app is None:
        try:
            import insightface
            _face_app = insightface.app.FaceAnalysis(name='buffalo_l')
            _face_app.prepare(ctx_id=0, det_size=(640, 640))  # Use ctx_id=-1 for GPU
            print("InsightFace face analysis model loaded successfully")
        except Exception as e:
            print(f"Error loading InsightFace: {e}")
            _face_app = None
    return _face_app


def get_face_swapper():
    """Lazy initialization of inswapper model."""
    global _face_swapper
    if _face_swapper is None:
        try:
            import insightface
            from insightface.app import FaceAnalysis

            # Download and load inswapper_128.onnx model
            model_path = os.path.join(insightface.app.DEFAULT_MP_NAME, 'inswapper_128.onnx')

            # Try loading with insightface's built-in swapper
            _face_swapper = insightface.model_zoo.get_model(
                'inswapper_128.onnx',
                download=True,
                download_zip=True
            )
            print("Inswapper model loaded successfully")
        except Exception as e:
            print(f"Error loading inswapper: {e}")
            try:
                # Alternative: try direct ONNX loading
                import onnxruntime
                model_file = os.path.join(os.path.expanduser('~'), '.insightface', 'models', 'inswapper_128.onnx')
                if os.path.exists(model_file):
                    _face_swapper = onnxruntime.InferenceSession(model_file, providers=['CPUExecutionProvider'])
                    print("Inswapper loaded via ONNX runtime")
                else:
                    print("Inswapper model file not found")
                    _face_swapper = None
            except Exception as e2:
                print(f"Alternative inswapper loading failed: {e2}")
                _face_swapper = None
    return _face_swapper


def download_image(url: str) -> Optional[np.ndarray]:
    """Download image from URL and convert to OpenCV format."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content))
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"Error downloading image from {url}: {e}")
        return None


def swap_faces(meme_url: str, source_face_path: str = None) -> Optional[str]:
    """
    Swap faces in a meme with Drew's face using inswapper.

    Args:
        meme_url: URL of the meme image
        source_face_path: Path to Drew's face image

    Returns:
        Path to the swapped image file, or None on error
    """
    if source_face_path is None:
        source_face_path = DREW_FACE_PATH

    try:
        # Get face detection and swapper models
        app = get_face_app()
        swapper = get_face_swapper()

        if app is None:
            raise ValueError("Face detection model not available")

        # Load source face (Drew's face)
        if not os.path.exists(source_face_path):
            raise FileNotFoundError(f"Source face not found: {source_face_path}")

        source_img = cv2.imread(source_face_path)
        if source_img is None:
            raise ValueError(f"Could not read source image: {source_face_path}")

        source_faces = app.get(source_img)
        if len(source_faces) == 0:
            raise ValueError("No face detected in source image")

        source_face = source_faces[0]

        # Download and process target meme
        meme_img = download_image(meme_url)
        if meme_img is None:
            raise ValueError(f"Could not download meme: {meme_url}")

        target_faces = app.get(meme_img)
        if len(target_faces) == 0:
            raise ValueError("No faces detected in target meme")

        # Perform face swap using inswapper
        result_img = meme_img.copy()

        if swapper is not None:
            # Use inswapper for high-quality face swap
            print(f"Swapping {len(target_faces)} face(s) with inswapper...")
            for target_face in target_faces:
                result_img = swapper.get(result_img, target_face, source_face, paste_back=True)
            print("Inswapper face swap completed")
        else:
            # Fallback: simple blend method if inswapper not available
            print("WARNING: Inswapper not available, using basic blend fallback")
            for target_face in target_faces:
                bbox = target_face.bbox.astype(int)
                x1, y1, x2, y2 = bbox

                # Ensure bbox is within image bounds
                h, w = result_img.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                if x2 <= x1 or y2 <= y1:
                    continue

                # Resize Drew's face to match target bbox
                drew_face_resized = cv2.resize(source_img, (x2-x1, y2-y1))

                # Simple alpha blend
                result_img[y1:y2, x1:x2] = cv2.addWeighted(
                    result_img[y1:y2, x1:x2], 0.3,
                    drew_face_resized, 0.7, 0
                )

        # Generate unique filename
        filename = f"swapped_{meme_url.split('/')[-1].split('?')[0]}"
        if not any(filename.endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
            filename += '.jpg'

        output_path = os.path.join('static', filename)

        # Save result
        cv2.imwrite(output_path, result_img)
        print(f"Face swap complete: {output_path}")
        return output_path

    except Exception as e:
        print(f"Face swap error for {meme_url}: {e}")
        import traceback
        traceback.print_exc()
        return None


def llm_guide_swap(meme_description: str) -> dict:
    """
    Optional: Use Grok API to analyze meme and guide face swap.
    Returns metadata about the meme for better processing.
    """
    if not GROK_API_KEY:
        return {"guided": False, "reason": "No API key"}

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=GROK_API_KEY,
            base_url="https://api.x.ai/v1"
        )

        response = client.chat.completions.create(
            model="grok-beta",
            messages=[{
                "role": "user",
                "content": f"Analyze this meme title and suggest which face(s) should be swapped: '{meme_description}'. Respond with JSON."
            }],
            max_tokens=100
        )

        guidance = response.choices[0].message.content
        return {"guided": True, "guidance": guidance}

    except Exception as e:
        print(f"LLM guidance error: {e}")
        return {"guided": False, "error": str(e)}


if __name__ == "__main__":
    # Test face swap
    test_url = "https://i.redd.it/sample.jpg"
    result = swap_faces(test_url)
    if result:
        print(f"Test successful: {result}")
    else:
        print("Test failed")
