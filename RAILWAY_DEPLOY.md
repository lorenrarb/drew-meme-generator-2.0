# Railway Deployment Guide

## Pre-Deployment Checklist

### 1. Files Updated
- ✅ `requirements.txt` - Changed to `opencv-python-headless` (lighter, no display libs needed)
- ✅ `nixpacks.toml` - Simplified dependencies
- ✅ `railway.json` - Configured for single worker
- ✅ `Procfile` - Backup deployment method

### 2. Environment Variables to Set in Railway

Go to your Railway project → Variables tab and add:

```
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=drewmemeapp
Grok_API_KEY=your_grok_api_key
DREW_FACE_PATH=./assets/drew_face.jpg
FLASK_ENV=production
```

**Important:** Copy the actual values from your `.env` file - don't use these placeholders!

### 3. Memory Requirements

**Minimum Plan Required:**
- **Railway**: 2GB RAM plan ($5-10/month)
- Free tier (512MB-1GB) will likely fail due to memory constraints

The app needs:
- Face detection model: ~150-500MB
- Face swap model: ~700MB
- Processing overhead: ~300MB
- **Total: ~1.5GB RAM minimum**

### 4. Deployment Steps

**Option A: GitHub Integration (Recommended)**

1. Push your code to GitHub:
   ```bash
   git add .
   git commit -m "Update deployment config for Railway"
   git push origin main
   ```

2. In Railway dashboard:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository
   - Railway will auto-detect and deploy

**Option B: Railway CLI**

1. Install Railway CLI:
   ```bash
   npm i -g @railway/cli
   ```

2. Login and deploy:
   ```bash
   railway login
   railway init
   railway up
   ```

3. Link to your project:
   ```bash
   railway link
   ```

### 5. Common Issues & Solutions

#### Issue: "Out of Memory" Error
**Solution:** Upgrade to a plan with at least 2GB RAM

#### Issue: OpenCV Import Error
**Solution:** Already fixed - we switched to `opencv-python-headless`

#### Issue: Model Download Timeout
**Solution:** The app downloads the 529MB face swap model on first start. This is normal and takes 2-5 minutes. Subsequent starts will be faster as the model is cached.

#### Issue: Build Takes Too Long
**Solution:**
- First build takes 5-10 minutes (installing all dependencies)
- Add to `.railwayignore` if you have one:
  ```
  venv/
  __pycache__/
  *.pyc
  .git/
  ```

#### Issue: Port Not Found
**Solution:** Railway automatically sets the `$PORT` environment variable. The app is configured to use it.

### 6. Monitoring After Deployment

1. **Check Logs:**
   - Railway Dashboard → Your Project → Deployments → View Logs
   - Look for: "Uvicorn running on http://0.0.0.0:PORT"

2. **Test Endpoints:**
   - Homepage: `https://your-app.railway.app/`
   - Health check: `https://your-app.railway.app/health`

3. **First Request Will Be Slow:**
   - Models need to load (~30 seconds)
   - Face swap model downloads (~2-5 minutes first time)
   - Subsequent requests will be fast

### 7. Cost Optimization

Railway charges based on:
- RAM usage
- CPU time
- Network egress

**Tips to reduce costs:**
1. Use single worker (`--workers 1`) ✅ Already configured
2. Don't run 24/7 if not needed - Railway can auto-sleep
3. Monitor usage in Railway dashboard

### 8. Troubleshooting Commands

If deployed but not working, check Railway logs for:

```bash
# Common error messages and what they mean:

"ModuleNotFoundError: No module named 'cv2'"
→ OpenCV not installed (should be fixed with opencv-python-headless)

"Killed" or "Out of Memory"
→ Need to upgrade to larger RAM plan

"Model not found" or "FileNotFoundError"
→ Model is downloading, wait 2-5 minutes

"Port 5000 is already in use"
→ Not an issue on Railway, Railway assigns random ports
```

### 9. Success Indicators

You'll know it's working when you see in logs:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:PORT
```

Then visit your Railway URL and you should see the Drew Meme Generator homepage!

### 10. Need Help?

If deployment fails, share the Railway logs and error messages.
