# Deployment Guide for Drew Meme Generator

## The Problem

The inswapper face swap model (`inswapper_128.onnx`) is **529MB**, which causes deployment issues:

- **Vercel**: 250MB deployment limit (won't work)
- **Most serverless platforms**: Similar size limits
- **Ephemeral storage**: Model gets deleted on cold starts
- **Download time**: 529MB download on each restart (slow)

## Solutions by Platform

### Option 1: Render (Recommended)

Render supports persistent disks and larger deployments.

**Steps:**

1. **Use Git LFS (Large File Storage)**
   ```bash
   # Install Git LFS
   git lfs install

   # Track the model file
   git lfs track "models/*.onnx"

   # Add and commit
   git add .gitattributes models/inswapper_128.onnx
   git commit -m "Add inswapper model via Git LFS"
   git push
   ```

2. **Deploy to Render**
   - The model will be included in your deployment
   - Use the existing `render.yaml` configuration
   - Set environment variables in Render dashboard

**Alternative: Persistent Disk**
```yaml
# In render.yaml, add:
disk:
  name: model-storage
  mountPath: /opt/render/.insightface/models
  sizeGB: 1
```

Then manually upload the model to the disk via Render shell.

---

### Option 2: Railway / Fly.io

These platforms support larger deployments.

**Railway:**
```bash
# Install Railway CLI
npm i -g railway

# Deploy
railway login
railway init
railway up
```

**Fly.io:**
```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Deploy
fly launch
fly deploy
```

Both will include the `models/` directory in your deployment.

---

### Option 3: Cloud Storage (S3/GCS)

For serverless platforms, store the model externally.

**1. Upload model to S3/GCS:**
```bash
# AWS S3
aws s3 cp models/inswapper_128.onnx s3://your-bucket/models/

# Google Cloud Storage
gsutil cp models/inswapper_128.onnx gs://your-bucket/models/
```

**2. Update `app/core/faceswap.py`:**
```python
# Add to get_face_swapper() function
import boto3

# Download from S3 if not found locally
if model_file is None:
    s3 = boto3.client('s3')
    model_file = '/tmp/inswapper_128.onnx'
    s3.download_file('your-bucket', 'models/inswapper_128.onnx', model_file)
```

---

### Option 4: Hugging Face Spaces

Host on Hugging Face which is optimized for ML models.

**Steps:**
1. Create new Space at https://huggingface.co/spaces
2. Choose "Gradio" or "Streamlit" as framework
3. Upload your code and model
4. Model storage is free and persistent

---

## Using Higher Quality Models

Want better quality? Try these models:

1. **inswapper_128_fp16.onnx** (~265MB) - Half precision, smaller size
2. **w600k_r50.onnx** - Better face recognition
3. **GFPGANv1.4.onnx** - Face enhancement post-processing

**To switch models:**

```python
# In app/core/faceswap.py line 81, change:
url = "https://huggingface.co/CountFloyd/deepfake/resolve/main/inswapper_128_fp16.onnx"
```

---

## Current Setup

The code now checks multiple locations:
1. `./models/inswapper_128.onnx` (project directory)
2. `/opt/render/.insightface/models/inswapper_128.onnx` (Render persistent disk)
3. `/tmp/inswapper_128.onnx` (temporary)
4. `~/.insightface/models/inswapper_128.onnx` (home directory)

This ensures it works in both local dev and various deployment environments.

---

## Testing Locally

```bash
# Verify model is in place
ls -lh models/inswapper_128.onnx

# Run locally
source venv/bin/activate
python -m uvicorn app.main:app --reload --port 5000
```

Visit http://localhost:5000 to test.

---

## Troubleshooting

**Model not loading on deployment:**
- Check platform logs for file path errors
- Verify model file is included in deployment (check file size)
- Try downloading from cloud storage instead

**Out of memory errors:**
- Use fp16 (half precision) model variant
- Increase server memory in platform settings
- Use CPU-only inference (already configured)

**Slow cold starts:**
- Use persistent disk/storage
- Consider keeping one instance "warm" (paid plans)
- Pre-download model during build phase
