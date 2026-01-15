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
            # Use buffalo_l for highest quality face detection
            _face_app = insightface.app.FaceAnalysis(name='buffalo_l')
            # Lower detection threshold for better sensitivity (default is 0.5)
            # det_size=(640, 640) is the detection resolution
            _face_app.prepare(ctx_id=-1, det_size=(640, 640), det_thresh=0.3)
            print("InsightFace face analysis model loaded successfully (buffalo_l, det_thresh=0.3)")
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
            import urllib.request

            # Try multiple model locations for deployment compatibility
            # 1. Local project directory (for bundled deployments)
            local_model_paths = [
                './models/inswapper_128.onnx',  # Project directory
                '/opt/render/.insightface/models/inswapper_128.onnx',  # Render persistent disk
                '/tmp/inswapper_128.onnx',  # Temporary storage
            ]

            # 2. Home directory (for local dev)
            home_model_dir = os.path.join(os.path.expanduser('~'), '.insightface', 'models')
            os.makedirs(home_model_dir, exist_ok=True)
            home_model_path = os.path.join(home_model_dir, 'inswapper_128.onnx')

            # Check all possible locations
            model_file = None
            for path in local_model_paths + [home_model_path]:
                if os.path.exists(path):
                    model_file = path
                    print(f"Found inswapper model at: {model_file}")
                    break

            # Download model if not found anywhere
            if model_file is None:
                print("Inswapper model not found, downloading high-quality version (529MB)...")
                # Try to save to project directory first (best for deployment)
                os.makedirs('./models', exist_ok=True)
                if os.access('./models', os.W_OK):
                    model_file = './models/inswapper_128.onnx'
                    print("Saving to project directory: ./models/")
                elif os.access('/tmp', os.W_OK):
                    model_file = '/tmp/inswapper_128.onnx'
                    print("Saving to /tmp/ (ephemeral)")
                else:
                    model_file = home_model_path
                    print(f"Saving to home directory: {home_model_dir}")

                # Download high-quality model from HuggingFace
                url = "https://huggingface.co/CountFloyd/deepfake/resolve/main/inswapper_128.onnx"
                urllib.request.urlretrieve(url, model_file)
                print(f"Model downloaded to {model_file}")

            # Try loading with insightface's built-in swapper
            try:
                _face_swapper = insightface.model_zoo.get_model(
                    model_file,
                    download=False,
                    download_zip=False
                )
                print("Inswapper model loaded successfully via model_zoo")
            except Exception as e:
                print(f"model_zoo loading failed, trying direct ONNX: {e}")
                import onnxruntime
                _face_swapper = onnxruntime.InferenceSession(
                    model_file,
                    providers=['CPUExecutionProvider']
                )
                print("Inswapper loaded via ONNX runtime")

        except Exception as e:
            print(f"CRITICAL: Error loading inswapper: {e}")
            import traceback
            traceback.print_exc()
            _face_swapper = None
    return _face_swapper


def is_good_face_candidate(face, img_width: int, img_height: int) -> bool:
    """
    Check if a detected face is a good candidate for face swapping.
    Filters out small faces, profile views, non-human faces, etc.

    Args:
        face: InsightFace face detection object
        img_width: Width of the image in pixels
        img_height: Height of the image in pixels

    Returns:
        True if face is a good swap candidate, False otherwise
    """
    try:
        # Calculate face bounding box dimensions
        bbox = face.bbox.astype(int)
        x1, y1, x2, y2 = bbox
        face_width = x2 - x1
        face_height = y2 - y1
        face_area = face_width * face_height
        img_area = img_width * img_height

        # Filter 1: Face must be at least 8% of image area (prevents tiny background faces)
        face_ratio = face_area / img_area
        if face_ratio < 0.08:
            print(f"✗ Face too small: {face_ratio*100:.1f}% of image (need >8%)")
            return False

        # Filter 2: Face must have high detection confidence (>0.6)
        if hasattr(face, 'det_score') and face.det_score < 0.6:
            print(f"✗ Low confidence: {face.det_score:.2f} (need >0.6)")
            return False

        # Filter 3: Check if face is reasonably frontal (not profile/turned away)
        # InsightFace pose: [pitch, yaw, roll] in degrees
        if hasattr(face, 'pose') and face.pose is not None:
            pitch, yaw, roll = face.pose
            # Yaw: left/right rotation - should be close to 0 for frontal faces
            # Pitch: up/down rotation
            if abs(yaw) > 45:  # Face turned more than 45 degrees left/right
                print(f"✗ Profile view detected: yaw={yaw:.1f}° (need <45°)")
                return False
            if abs(pitch) > 35:  # Face tilted too far up/down
                print(f"✗ Face tilted too much: pitch={pitch:.1f}° (need <35°)")
                return False

        # Filter 4: Face size should be reasonable (not extreme close-up or tiny)
        # Face should be between 100-2000 pixels in width for good results
        if face_width < 100:
            print(f"✗ Face too narrow: {face_width}px (need >100px)")
            return False
        if face_width > 2000:
            print(f"✗ Face too large: {face_width}px (need <2000px) - likely extreme close-up")
            return False

        # Filter 5: Aspect ratio check - faces should be roughly portrait orientation
        aspect_ratio = face_width / face_height if face_height > 0 else 0
        if aspect_ratio < 0.6 or aspect_ratio > 1.4:
            print(f"✗ Unusual aspect ratio: {aspect_ratio:.2f} (need 0.6-1.4)")
            return False

        print(f"✓ Good face candidate: {face_width}x{face_height}px ({face_ratio*100:.1f}% of image)")
        return True

    except Exception as e:
        print(f"Warning: Error checking face quality: {e}")
        # If we can't determine quality, be conservative and reject
        return False


def download_image(url: str) -> Optional[np.ndarray]:
    """Download image from URL and convert to OpenCV format."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
        }
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()

        # Load image from bytes
        img = Image.open(BytesIO(resp.content))
        print(f"Downloaded image: {img.size[0]}x{img.size[1]}px, mode: {img.mode}")

        # Convert to RGB if needed (handles RGBA, L, P, etc.)
        if img.mode not in ['RGB', 'BGR']:
            print(f"Converting image from {img.mode} to RGB")
            img = img.convert('RGB')

        # Convert PIL to OpenCV (numpy array)
        img_array = np.array(img)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Ensure image has valid dimensions
        if img_bgr.shape[0] < 50 or img_bgr.shape[1] < 50:
            print(f"Warning: Image is very small ({img_bgr.shape[1]}x{img_bgr.shape[0]}px)")

        return img_bgr
    except Exception as e:
        print(f"Error downloading image from {url[:100]}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
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

        # Log image dimensions for debugging
        h, w = meme_img.shape[:2]
        print(f"Target image dimensions: {w}x{h}px")

        # Try face detection with current image
        target_faces = app.get(meme_img)

        # If no faces found, try with different image sizes
        if len(target_faces) == 0:
            print(f"No faces detected at original size, trying alternative sizes...")

            # Try resizing image if it's very large (might help with detection)
            if max(h, w) > 1920:
                scale = 1920 / max(h, w)
                new_w, new_h = int(w * scale), int(h * scale)
                resized_img = cv2.resize(meme_img, (new_w, new_h))
                print(f"Trying detection on resized image: {new_w}x{new_h}px")
                target_faces = app.get(resized_img)
                if len(target_faces) > 0:
                    # Scale is working, use resized image
                    meme_img = resized_img
                    print(f"✓ Found {len(target_faces)} face(s) after resize")

            # Still no faces? Try with smaller image if it's medium-sized
            if len(target_faces) == 0 and max(h, w) > 800:
                scale = 800 / max(h, w)
                new_w, new_h = int(w * scale), int(h * scale)
                resized_img = cv2.resize(meme_img, (new_w, new_h))
                print(f"Trying detection on smaller image: {new_w}x{new_h}px")
                target_faces = app.get(resized_img)
                if len(target_faces) > 0:
                    meme_img = resized_img
                    print(f"✓ Found {len(target_faces)} face(s) after smaller resize")

        if len(target_faces) == 0:
            print(f"✗ No faces detected in target meme after trying multiple sizes: {meme_url[:100]}")
            return None  # Return None instead of raising exception for better performance

        print(f"✓ Successfully detected {len(target_faces)} face(s) in target image")

        # Filter for good face candidates (frontal, large enough, high confidence)
        h, w = meme_img.shape[:2]
        good_faces = [face for face in target_faces if is_good_face_candidate(face, w, h)]

        if len(good_faces) == 0:
            print(f"✗ No suitable faces for swapping (all faces filtered out as poor candidates)")
            return None

        print(f"✓ Found {len(good_faces)} good face candidate(s) out of {len(target_faces)} detected")
        target_faces = good_faces  # Use only the good faces

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

        # Save result with optimized compression for faster loading
        # Use JPEG quality 85 for good balance between quality and file size
        if output_path.endswith('.jpg') or output_path.endswith('.jpeg'):
            cv2.imwrite(output_path, result_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        elif output_path.endswith('.png'):
            # PNG compression level 6 (0-9, higher = more compression)
            cv2.imwrite(output_path, result_img, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        else:
            cv2.imwrite(output_path, result_img, [cv2.IMWRITE_JPEG_QUALITY, 85])

        print(f"Face swap complete: {output_path}")

        # Aggressive memory cleanup
        del result_img, meme_img, source_img, target_faces, source_faces
        import gc
        gc.collect()

        return output_path

    except Exception as e:
        print(f"Face swap error for {meme_url}: {e}")
        import traceback
        traceback.print_exc()

        # Cleanup on error too
        import gc
        gc.collect()

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
