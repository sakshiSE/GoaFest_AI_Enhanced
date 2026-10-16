"""Real MCP stdio server exposing typed, documented Goa tourism tools."""
from mcp.server.fastmcp import FastMCP
from .tools import search_festival_information, search_attractions, search_food_options, calculate_trip_budget, validate_itinerary

mcp = FastMCP("GoaFest Tourism Tools")

@mcp.tool()
def festival_information(festival: str) -> list[dict]:
    """Search the local events.csv dataset for records matching a festival name."""
    return search_festival_information(festival)

@mcp.tool()
def attractions(interests: list[str]) -> list[dict]:
    """Retrieve and rank attraction records from places.csv for visitor interests."""
    return search_attractions(interests)[:8]

@mcp.tool()
def food_options(preferences: list[str]) -> list[dict]:
    """Retrieve and rank local food options from food.csv using preferences."""
    return search_food_options(preferences)[:8]

@mcp.tool()
def trip_budget(request: dict, itinerary: dict) -> dict:
    """Calculate an itemised INR trip estimate from the request and scheduled activities."""
    return calculate_trip_budget(request, itinerary)

@mcp.tool()
def itinerary_validation(itinerary: dict, budget: dict) -> dict:
    """Check time ordering, schedule overlaps, repeated activities and budget overruns."""
    return validate_itinerary(itinerary, budget)

if __name__ == "__main__":
    mcp.run(transport="stdio")
