"""
Meme cache system for fast homepage loading.
Pre-generates face-swapped memes and serves them from cache.
"""
import os
import json
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta


CACHE_FILE = "static/meme_cache.json"
CACHE_TTL_HOURS = 24  # Cache valid for 24 hours


def get_cache_age() -> Optional[float]:
    """Get cache age in hours. Returns None if cache doesn't exist."""
    if not os.path.exists(CACHE_FILE):
        return None

    cache_modified = os.path.getmtime(CACHE_FILE)
    age_seconds = time.time() - cache_modified
    return age_seconds / 3600  # Convert to hours


def is_cache_valid() -> bool:
    """Check if cache exists and is not expired."""
    age = get_cache_age()
    if age is None:
        return False
    return age < CACHE_TTL_HOURS


def load_cached_memes() -> Optional[List[Dict]]:
    """Load cached memes if valid."""
    if not is_cache_valid():
        return None

    try:
        with open(CACHE_FILE, 'r') as f:
            data = json.load(f)
            return data.get('memes', [])
    except Exception as e:
        print(f"Error loading cache: {e}")
        return None


def save_cached_memes(memes: List[Dict]) -> bool:
    """Save memes to cache file."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        cache_data = {
            'memes': memes,
            'cached_at': datetime.now().isoformat(),
            'ttl_hours': CACHE_TTL_HOURS
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        print(f"Cache saved with {len(memes)} memes")
        return True
    except Exception as e:
        print(f"Error saving cache: {e}")
        return False


def clear_cache():
    """Clear the meme cache."""
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            print("Cache cleared")
    except Exception as e:
        print(f"Error clearing cache: {e}")
