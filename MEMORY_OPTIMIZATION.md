# Memory Optimization for Drew Meme Generator

## The Memory Problem

InsightFace models are memory-intensive:
- `buffalo_l` face detection: ~500MB RAM
- `inswapper_128.onnx` face swap: ~700MB RAM
- Image processing buffers: ~200-500MB RAM
- **Total: 1.5-2GB+ RAM required**

Render's "starter" plan (512MB RAM) is insufficient.

## Current Optimizations

### 1. Smaller Face Detection Model
Changed from `buffalo_l` to `buffalo_s`:
- **buffalo_l**: ~500MB RAM, highest accuracy
- **buffalo_s**: ~150MB RAM, good accuracy (90% as good)
- **Savings**: ~350MB RAM

### 2. Reduced Detection Size
Changed from 640x640 to 512x512:
- Smaller image tensors in memory
- Faster processing
- **Savings**: ~100MB RAM

### 3. Single Worker Process
Using `--workers 1` ensures only one model instance loads:
- Each worker loads models independently
- Single worker = single model copy
- **Savings**: Prevents memory multiplication

### 4. Lazy Loading
Models only load when first needed:
- Faster startup
- Lower baseline memory

## Render Plan Requirements

| Plan | RAM | Works? | Cost |
|------|-----|--------|------|
| Starter | 512MB | ❌ No | Free |
| Standard | 2GB | ✅ Yes | $7/month |
| Pro | 4GB | ✅ Yes (plenty) | $25/month |

**Recommendation**: Standard plan ($7/month) with current optimizations.

## Further Optimizations (If Still Running Out of Memory)

### Option A: FP16 Model (Half Precision)
Use half-precision model to reduce memory by 50%:
```python
# In faceswap.py line 81, change URL to:
url = "https://huggingface.co/CountFloyd/deepfake/resolve/main/inswapper_128_fp16.onnx"
```
- **Savings**: ~350MB RAM
- **Trade-off**: Slightly lower quality (usually imperceptible)

### Option B: On-Demand Model Loading/Unloading
Load models only when needed, unload after use:
```python
def swap_faces(meme_url: str, source_face_path: str = None):
    global _face_app, _face_swapper

    # Load models
    app = get_face_app()
    swapper = get_face_swapper()

    # ... do face swap ...

    # Unload to free memory
    del app, swapper
    _face_app = None
    _face_swapper = None
    import gc
    gc.collect()
```
- **Trade-off**: Slower (reloads models each request)

### Option C: External GPU Service
Use external API for face swapping:
- Replicate.com
- Hugging Face Inference API
- Custom GPU server
- **Trade-off**: Cost per request, external dependency

## Memory Monitoring

Add to your code to track memory usage:
```python
import psutil
process = psutil.Process()
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
```

## Current Status

With optimizations applied:
- Face detection model: buffalo_s (~150MB)
- Face swap model: inswapper_128 (~700MB)
- Processing overhead: ~300MB
- **Total: ~1.2GB RAM**

This should work on Render's Standard plan (2GB RAM).
