
from datetime import timedelta, date as date_type

from .tools import (
    search_festival_information,
    search_attractions,
    search_food_options,
    calculate_trip_budget,
    validate_itinerary,
)
from .web_search import search_web
from .image_search import find_image


def build_itinerary(
    request: dict,
    research=None,
    events=None,
    places=None,
    food=None,
) -> dict:
    festival_name = request["festival"]

    research = research or search_web(
        f"{festival_name} Goa official dates schedule venue "
        f"tickets {request['start_date']}"
    )

    events = (
        events
        if events is not None
        else search_festival_information(festival_name)
    )

    # Use the user's requested location when selecting attractions.
    requested_location = (
        request.get("event_location")
        or request.get("location")
        or request.get("destination")
    )

    places = (
        places
        if places is not None
        else search_attractions(
            interests=request.get("interests", []),
            location=requested_location,
            limit=20,
        )
    )

    food = (
        food
        if food is not None
        else search_food_options(request.get("food_preferences", []))
    )

    festival = {
        "name": festival_name,
        "date": str(request["start_date"]),
        "venue": "To be confirmed from an official festival source",
        "schedule_status": "unverified",
        "research_status": research["status"],
        "research_results": research["results"],
        "fallback_records": events[:3],
        "note": (
            "The selected date is a user-provided planning anchor, "
            "not a claim that the festival occurs on that date."
        ),
    }

    start_date = (
        request["start_date"]
        if isinstance(request["start_date"], date_type)
        else date_type.fromisoformat(str(request["start_date"]))
    )

    daily = []
    used_places = set()

    def next_place():
        """Return the next unused attraction from the ranked candidates."""
        for place in places:
            name = str(place.get("name", "")).strip()

            if name and name.casefold() not in used_places:
                used_places.add(name.casefold())
                return place

        return None

    def attraction_item(place, start_time, end_time):
        """Convert a dataset attraction into the itinerary's existing format."""
        return {
            "start_time": start_time,
            "end_time": end_time,
            "title": place.get("name", "Attraction"),
            "type": "attraction",
            "location": place.get("area", ""),
            "description": place.get("description", ""),
            "estimated_cost_per_person": float(
                place.get("estimated_fee_inr") or 0
            ),
            "evidence_status": "estimated / demo dataset",
            "source_url": place.get("source_url") or None,
            "image": find_image(place.get("name", "")),
        }

    for i in range(int(request["days"])):
        current_date = str(start_date + timedelta(days=i))
        schedule = []

        if i == 0:
            schedule.append({
                "start_time": "10:00",
                "end_time": "11:00",
                "title": "Arrival and check-in buffer",
                "type": "break",
                "location": requested_location or "Goa",
                "description": (
                    "Keep this flexible for your actual arrival time."
                ),
                "estimated_cost_per_person": 0,
            })

            schedule.append({
                "start_time": "11:00",
                "end_time": "11:30",
                "title": f"Confirm {festival_name} schedule and venue",
                "type": "festival",
                "location": requested_location or "Venue to be confirmed",
                "description": (
                    "Check the official organiser website or social channel. "
                    "Event time is not verified."
                ),
                "estimated_cost_per_person": 0,
            })

        # Morning/afternoon sightseeing: do not reuse an attraction.
        place = next_place()
        if place:
            schedule.append(
                attraction_item(place, "12:00", "13:30")
            )

        if food:
            meal = food[i % len(food)]
            schedule.append({
                "start_time": "13:30",
                "end_time": "14:15",
                "title": f"Lunch: {meal.get('dish', 'Local food')}",
                "type": "food",
                "location": meal.get("area", ""),
                "description": meal.get("description", ""),
                "estimated_cost_per_person": float(
                    meal.get("estimated_price_inr") or 0
                ),
                "evidence_status": "estimated / demo dataset",
                "source_url": meal.get("source_url") or None,
            })

        if i < int(request["days"]) - 1:
            place = next_place()
            if place:
                schedule.append(
                    attraction_item(place, "15:00", "16:30")
                )

        schedule.append({
            "start_time": "17:00",
            "end_time": "18:00",
            "title": "Festival window / rest and travel buffer",
            "type": "festival",
            "location": requested_location or "Venue to be confirmed",
            "description": (
                "Keep this time flexible for the actual event schedule. "
                "This is a planning buffer, not a confirmed event slot."
            ),
            "estimated_cost_per_person": 0,
        })

        daily.append({
            "day": i + 1,
            "date": current_date,
            "theme": [
                "Arrival, orientation and festival check",
                "Coastal and cultural Goa",
                "Flexible festival day and departure preparation",
            ][min(i, 2)],
            "schedule": schedule,
        })

    itinerary = {
        "festival": festival,
        "days": daily,
        "attractions": places[:6],
        "food_recommendations": food[:6],
        "transport": {
            "status": "estimated",
            "note": (
                "No live route or traffic provider is configured. "
                "Travel times are not calculated; verify routes before "
                "departure."
            ),
        },
        "sources": research["results"],
        "mode": (
            "live research available"
            if research["status"] == "live"
            else "demo / fallback mode"
        ),
    }

    budget = calculate_trip_budget(request, itinerary)
    validation = validate_itinerary(itinerary, budget)

    return {
        "trip_summary": {
            "festival": festival_name,
            "start_date": str(request["start_date"]),
            "days": request["days"],
            "travellers": request["travellers"],
            "mode": itinerary["mode"],
        },
        "itinerary": itinerary,
        "budget": budget,
        "validation": validation,
        "agents": {
            "coordinator": "completed",
            "festival_research": "completed with source status shown",
            "places": (
                "completed using ranked dataset attractions "
                "plus optional image lookup"
            ),
            "food": "completed using demo dataset",
            "budget": "deterministic calculation",
            "validator": "completed",
        },
    }
