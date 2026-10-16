"""CSV-backed tourism directory with best-effort, attributed Wikimedia images."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import csv
from fastapi import APIRouter
from .image_search import find_image

router = APIRouter()
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def _read_csv(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))

def _title(item: dict) -> str:
    return item.get("name") or item.get("dish") or item.get("event") or item.get("festival") or item.get("activity") or item.get("mode") or "Goa"

@router.get("/catalog")
def get_catalog():
    """Return local CSV listings; attach real Commons image results where available."""
    result = {
        "places": _read_csv("places.csv"),
        "food": _read_csv("food.csv"),
        "restaurants": _read_csv("restaurants.csv"),
        "events": _read_csv("events.csv"),
        "activities": _read_csv("activities.csv"),
        "transport": _read_csv("transport.csv"),
    }
    # Enrich a small visible sample concurrently so the directory stays responsive.
    targets = []
    for category, limit in (("places", 6), ("food", 3), ("restaurants", 4), ("events", 3), ("activities", 3)):
        for item in result[category][:limit]:
            targets.append((item, _title(item)))
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            images = list(pool.map(lambda pair: find_image(pair[1] + " Goa"), targets))
        for (item, _), image in zip(targets, images):
            item["image"] = image
    except Exception:
        for item, _ in targets:
            item["image"] = {"url": None, "source_url": None, "status": "unavailable"}
    return result
