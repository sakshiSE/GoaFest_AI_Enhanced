"""Shared state passed between LangGraph nodes."""
from typing import TypedDict, Any

class TripState(TypedDict, total=False):
    request: dict
    research: dict
    events: list
    places: list
    food: list
    mcp: dict
    draft: dict
    final: dict
    tool_calls: list
