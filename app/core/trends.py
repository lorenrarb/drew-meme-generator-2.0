import asyncpraw
import redis
import json
import os
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
from better_profanity import profanity

load_dotenv()

# Initialize profanity filter
profanity.load_censor_words()

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

# Reddit setup - async version
reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

# Additional custom words to block beyond better-profanity's defaults
CUSTOM_BLOCKED_WORDS = [
    "nsfw", "porn", "nude", "naked", "rape", "gore", "kill", "murder",
    "suicide", "death", "blood", "hentai", "xxx"
]

# Add custom words to profanity filter
profanity.add_censor_words(CUSTOM_BLOCKED_WORDS)

# Safe subreddits only (no NSFW or vulgar content)
SAFE_SUBREDDITS = ["wholesomememes", "memes", "aww", "funny"]


def is_content_appropriate(title: str, post_obj=None) -> bool:
    """
    Check if content is appropriate (not vulgar or NSFW).
    Uses better-profanity library for robust profanity detection.

    Args:
        title: Post title to check
        post_obj: Reddit post object (optional, for NSFW flag check)

    Returns:
        True if appropriate, False if should be filtered
    """
    # Check NSFW flag if post object provided
    if post_obj and hasattr(post_obj, 'over_18') and post_obj.over_18:
        print(f"Filtered NSFW post: {title[:50]}...")
        return False

    # Use better-profanity to detect profanity (catches variations, misspellings, leetspeak)
    if profanity.contains_profanity(title):
        print(f"Filtered profanity in title: {profanity.censor(title)}")
        return False

    return True


async def get_trending_memes(subreddits: List[str] = None) -> List[Dict]:
    """
    Fetch trending memes from specified subreddits with 2h cache.
    Filters out NSFW and vulgar content.

    Args:
        subreddits: List of subreddit names. Defaults to safe subreddits

    Returns:
        List of meme dictionaries with url, title, score, etc.
    """
    if subreddits is None:
        subreddits = SAFE_SUBREDDITS

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

    # Fetch fresh data with content filtering
    trends = []
    for sub in subreddits:
        try:
            subreddit = await reddit.subreddit(sub)
            async for post in subreddit.hot(limit=25):  # Increased to account for profanity and face filtering
                # Filter for image posts
                if any(ext in post.url.lower() for ext in ['.jpg', '.jpeg', '.png', 'i.redd.it', 'i.imgur.com']):
                    # Apply content filter (profanity + NSFW check)
                    if is_content_appropriate(post.title, post):
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
