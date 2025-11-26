import requests
from typing import List, Optional
import random


def search_celebrity_images(celebrity_name: str, num_images: int = 2, max_fetch: int = 10) -> List[str]:
    """
    Search for celebrity images using Wikimedia Commons.

    Args:
        celebrity_name: Name of the celebrity
        num_images: Number of images to retrieve (default 2)
        max_fetch: Maximum number of images to fetch before randomly selecting (default 10)

    Returns:
        List of image URLs (randomly selected from available images)
    """
    try:
        # Use Wikipedia/Wikimedia Commons
        return search_wikimedia_images(celebrity_name, num_images, max_fetch)

    except Exception as e:
        print(f"Error searching for celebrity images: {e}")
        return []


def search_wikimedia_images(celebrity_name: str, num_images: int = 2, max_fetch: int = 10) -> List[str]:
    """
    Search for celebrity images from Wikimedia Commons.

    Args:
        celebrity_name: Name of the celebrity
        num_images: Number of images to retrieve

    Returns:
        List of image URLs
    """
    try:
        # Search Wikipedia for the celebrity
        wiki_api = "https://en.wikipedia.org/w/api.php"

        # Wikipedia requires a proper User-Agent header
        headers = {
            'User-Agent': 'DrewMemeGenerator/1.0 (https://github.com/yourrepo; contact@email.com) Python/3.x'
        }

        # First, search for the page
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": celebrity_name,
            "format": "json",
            "srlimit": 1
        }

        response = requests.get(wiki_api, params=search_params, headers=headers, timeout=10)
        response.raise_for_status()
        search_data = response.json()

        if not search_data.get("query", {}).get("search"):
            print(f"No Wikipedia page found for {celebrity_name}")
            return []

        # Get the page title
        page_title = search_data["query"]["search"][0]["title"]

        # Get images from the page
        image_params = {
            "action": "query",
            "titles": page_title,
            "prop": "images",
            "format": "json",
            "imlimit": 10
        }

        response = requests.get(wiki_api, params=image_params, headers=headers, timeout=10)
        response.raise_for_status()
        image_data = response.json()

        pages = image_data.get("query", {}).get("pages", {})
        if not pages:
            return []

        page = list(pages.values())[0]
        images = page.get("images", [])

        # Filter for likely portrait/photo images
        photo_images = [
            img["title"] for img in images
            if any(ext in img["title"].lower() for ext in [".jpg", ".jpeg", ".png"])
            and not any(skip in img["title"].lower() for skip in ["icon", "logo", "signature", "flag"])
        ]

        if not photo_images:
            print(f"No suitable images found for {celebrity_name}")
            return []

        # Get actual image URLs (fetch more than needed so we can randomly select)
        image_urls = []
        for img_title in photo_images[:max_fetch]:  # Fetch up to max_fetch images
            url_params = {
                "action": "query",
                "titles": img_title,
                "prop": "imageinfo",
                "iiprop": "url",
                "format": "json"
            }

            response = requests.get(wiki_api, params=url_params, headers=headers, timeout=10)
            response.raise_for_status()
            url_data = response.json()

            pages = url_data.get("query", {}).get("pages", {})
            if pages:
                page = list(pages.values())[0]
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    img_url = imageinfo[0].get("url")
                    if img_url:
                        image_urls.append(img_url)

                    if len(image_urls) >= max_fetch:
                        break

        # Randomly select num_images from the fetched URLs
        if len(image_urls) > num_images:
            import random
            return random.sample(image_urls, num_images)
        return image_urls[:num_images]

    except Exception as e:
        print(f"Error searching Wikimedia: {e}")
        return []


def search_pexels_images(celebrity_name: str, api_key: str, num_images: int = 2) -> List[str]:
    """
    Search for celebrity images using Pexels API (requires free API key).

    Args:
        celebrity_name: Name of the celebrity
        api_key: Pexels API key
        num_images: Number of images to retrieve

    Returns:
        List of image URLs
    """
    try:
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": api_key}
        params = {
            "query": f"{celebrity_name} portrait",
            "per_page": num_images,
            "orientation": "portrait"
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        image_urls = []
        for photo in data.get("photos", []):
            # Use medium-sized image
            img_url = photo.get("src", {}).get("large")
            if img_url:
                image_urls.append(img_url)

        return image_urls[:num_images]

    except Exception as e:
        print(f"Error searching Pexels: {e}")
        return []


def search_celebrity_google(celebrity_name: str, num_images: int = 2) -> List[str]:
    """
    Fallback: Use DuckDuckGo instant answer API for celebrity photos.

    Args:
        celebrity_name: Name of the celebrity
        num_images: Number of images to retrieve

    Returns:
        List of image URLs
    """
    try:
        # DuckDuckGo instant answer API (free, no key needed)
        url = f"https://api.duckduckgo.com/?q={celebrity_name}&format=json&t=drewmeme"

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        image_urls = []

        # Check for image in the main result
        if data.get("Image"):
            image_urls.append(data["Image"])

        # Check related topics for images
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Icon", {}).get("URL"):
                icon_url = topic["Icon"]["URL"]
                if icon_url and not icon_url.endswith(".ico"):
                    image_urls.append("https://duckduckgo.com" + icon_url if icon_url.startswith("/") else icon_url)

        return image_urls[:num_images]

    except Exception as e:
        print(f"Error searching DuckDuckGo: {e}")
        return []
