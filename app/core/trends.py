import praw
import redis
import json
import os
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# Config from environment
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
CACHE_TTL = int(os.getenv("CACHE_TTL_HOURS", "2")) * 3600  # Convert hours to seconds

# Redis setup (use in-memory cache for local dev if Redis not available)
try:
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.ping()
    USE_REDIS = True
except:
    USE_REDIS = False
    MEMORY_CACHE = {}
    print("Redis not available, using in-memory cache")

# Reddit setup
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)


def get_trending_memes(subreddits: List[str] = None) -> List[Dict]:
    """
    Fetch trending memes from specified subreddits with 2h cache.

    Args:
        subreddits: List of subreddit names. Defaults to ['memes', 'dankmemes']

    Returns:
        List of meme dictionaries with url, title, score, etc.
    """
    if subreddits is None:
        subreddits = ["memes", "dankmemes"]

    cache_key = f"trends:{'|'.join(subreddits)}"

    # Check cache
    if USE_REDIS:
        cached = r.get(cache_key)
        if cached:
            return json.loads(cached)
    else:
        if cache_key in MEMORY_CACHE:
            cached_data, timestamp = MEMORY_CACHE[cache_key]
            if (datetime.utcnow().timestamp() - timestamp) < CACHE_TTL:
                return cached_data

    # Fetch fresh data
    trends = []
    for sub in subreddits:
        try:
            subreddit = reddit.subreddit(sub)
            for post in subreddit.hot(limit=10):
                # Filter for image posts
                if any(ext in post.url.lower() for ext in ['.jpg', '.jpeg', '.png', 'i.redd.it', 'i.imgur.com']):
                    trends.append({
                        "title": post.title,
                        "url": post.url,
                        "id": post.id,
                        "sub": sub,
                        "score": post.score,
                        "fetched_at": datetime.utcnow().isoformat()
                    })
        except Exception as e:
            print(f"Error fetching from r/{sub}: {e}")
            continue

    # Dedupe by URL, sort by score
    unique_trends = {t["url"]: t for t in trends}
    trends_list = sorted(list(unique_trends.values()), key=lambda x: x["score"], reverse=True)[:20]

    # Cache results
    if USE_REDIS:
        r.setex(cache_key, CACHE_TTL, json.dumps(trends_list))
    else:
        MEMORY_CACHE[cache_key] = (trends_list, datetime.utcnow().timestamp())

    return trends_list


if __name__ == "__main__":
    # Test the fetcher
    memes = get_trending_memes()
    print(f"Fetched {len(memes)} trending memes:")
    for i, meme in enumerate(memes[:5], 1):
        print(f"{i}. {meme['title'][:50]}... (score: {meme['score']})")
        print(f"   URL: {meme['url']}")
