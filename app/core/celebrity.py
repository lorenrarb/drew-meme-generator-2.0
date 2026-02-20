import requests
from typing import List


def search_celebrity_images(celebrity_name: str, num_images: int = 10) -> List[str]:
    """
    Search for celebrity images using Wikimedia Commons, with DuckDuckGo fallback.

    Args:
        celebrity_name: Name of the celebrity
        num_images: Maximum number of images to return (default 10)

    Returns:
        List of image URLs
    """
    try:
        urls = search_wikimedia_images(celebrity_name, num_images)
        if len(urls) < 5:
            ddg_urls = search_celebrity_duckduckgo(celebrity_name, num_images)
            seen = set(urls)
            for u in ddg_urls:
                if u not in seen:
                    urls.append(u)
                    seen.add(u)
            urls = urls[:num_images]
        return urls
    except Exception as e:
        print(f"Error searching for celebrity images: {e}")
        return []


def search_wikimedia_images(celebrity_name: str, num_images: int = 10) -> List[str]:
    """
    Search for celebrity images from Wikimedia Commons.

    Returns:
        List of image URLs (up to num_images)
    """
    try:
        wiki_api = "https://en.wikipedia.org/w/api.php"
        headers = {
            'User-Agent': 'DrewMemeGenerator/2.0 (https://github.com/yourrepo; contact@email.com) Python/3.x'
        }

        # Search for the page
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

        page_title = search_data["query"]["search"][0]["title"]

        # Get images from the page (fetch up to 50)
        image_params = {
            "action": "query",
            "titles": page_title,
            "prop": "images",
            "format": "json",
            "imlimit": 50
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
            and not any(skip in img["title"].lower() for skip in ["icon", "logo", "signature", "flag", "map", "chart", "diagram"])
        ]

        if not photo_images:
            print(f"No suitable images found for {celebrity_name}")
            return []

        # Resolve actual URLs for all filtered images
        image_urls = []
        for img_title in photo_images:
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

            if len(image_urls) >= num_images:
                break

        return image_urls[:num_images]

    except Exception as e:
        print(f"Error searching Wikimedia: {e}")
        return []


def search_celebrity_duckduckgo(celebrity_name: str, num_images: int = 10) -> List[str]:
    """
    Fallback: Use DuckDuckGo instant answer API for celebrity photos.

    Returns:
        List of image URLs
    """
    try:
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
