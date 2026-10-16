import os
from datetime import datetime, timezone
import requests

def search_web(query: str, max_results: int = 5) -> dict:
    """Tavily search. Returns explicit unavailable status when no key or request fails."""
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        return {"status": "unavailable", "reason": "TAVILY_API_KEY is not configured", "results": [], "retrieved_at": datetime.now(timezone.utc).isoformat()}
    try:
        response = requests.post("https://api.tavily.com/search", json={"api_key": key, "query": query, "search_depth": "basic", "max_results": max_results, "include_answer": False}, timeout=15)
        response.raise_for_status()
        data = response.json()
        return {"status": "live", "results": [{"title": x.get("title", "Untitled"), "url": x.get("url", ""), "content": x.get("content", "")[:700], "source_type": "third-party / unclassified"} for x in data.get("results", [])], "retrieved_at": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        return {"status": "unavailable", "reason": f"Search request failed: {type(exc).__name__}", "results": [], "retrieved_at": datetime.now(timezone.utc).isoformat()}
