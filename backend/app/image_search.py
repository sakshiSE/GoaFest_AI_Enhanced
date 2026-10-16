"""Optional Wikimedia Commons image lookup; missing images are represented as null."""
import requests
from functools import lru_cache

@lru_cache(maxsize=128)
def find_image(query: str) -> dict:
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", params={"action":"query","generator":"search","gsrsearch":f"filetype:bitmap {query}","gsrnamespace":6,"gsrlimit":1,"prop":"imageinfo","iiprop":"url|extmetadata","format":"json"}, headers={"User-Agent":"GoaFestAI/1.0 educational project"}, timeout=3)
        r.raise_for_status()
        pages = r.json().get("query",{}).get("pages",{})
        if not pages: return {"url": None, "source_url": None, "attribution": None, "status":"unavailable"}
        page = next(iter(pages.values())); info=(page.get("imageinfo") or [{}])[0]; meta=info.get("extmetadata",{})
        return {"url":info.get("thumburl") or info.get("url"),"source_url":info.get("descriptionurl"),"attribution":meta.get("Artist",{}).get("value"),"status":"retrieved"}
    except Exception:
        return {"url": None, "source_url": None, "attribution": None, "status":"unavailable"}
