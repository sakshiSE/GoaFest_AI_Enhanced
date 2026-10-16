
from pathlib import Path
import csv
from datetime import datetime, timedelta

DATA = Path(__file__).resolve().parent.parent / "data"


def rows(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def search_festival_information(name):
    all_events = rows("events.csv")
    query = (name or "").strip().lower()

    if not query:
        return []

    matches = [
        event for event in all_events
        if query in event.get("festival", "").lower()
        or event.get("festival", "").lower() in query
    ]

    # Do not silently return Goa Carnival for an unrelated festival.
    return matches


def search_attractions(interests=None, location=None, exclude=None, limit=None):
    """
    Rank attractions using location and user interests.

    Existing calls such as search_attractions(interests) remain valid.
    Location matching uses the location fields available in places.csv.
    """
    places = rows("places.csv")
    interests = [
        str(item).strip().lower()
        for item in (interests or [])
        if str(item).strip()
    ]
    exclude = {
        str(item).strip().lower()
        for item in (exclude or [])
        if str(item).strip()
    }
    location = (location or "").strip().lower()

    def text_field(place, *keys):
        return " ".join(
            str(place.get(key, "") or "")
            for key in keys
        ).lower()

    def score(place):
        title = text_field(place, "name", "title", "place", "attraction")
        category = text_field(place, "category", "type")
        description = text_field(place, "description")
        address = text_field(
            place, "location", "city", "area", "address", "district"
        )
        searchable = " ".join(
            [title, category, description, address]
        )

        # Exclude places explicitly requested to be avoided.
        if title and title in exclude:
            return -10000

        # Prefer matching locations, not merely mentions in descriptions.
        location_score = 0
        if location:
            location_terms = [
                term for term in location.replace(",", " ").split()
                if term
            ]
            if any(term in address for term in location_terms):
                location_score = 100
            elif any(term in title for term in location_terms):
                location_score = 30
            else:
                location_score = -20

        interest_score = sum(
            10 for interest in interests
            if interest in category or interest in description
            or interest in title
        )

        return location_score + interest_score

    # Keep matching-location attractions ahead of unrelated locations.
    ranked = sorted(places, key=score, reverse=True)

    if location:
        matching = [place for place in ranked if score(place) > -20]
        # If no location matches exist in the dataset, retain alternatives
        # but do not pretend they are located in the requested area.
        ranked = matching if matching else ranked

    if limit is not None:
        ranked = ranked[:max(0, int(limit))]

    return ranked


def search_food_options(preferences=None):
    food = rows("food.csv")
    prefs = [
        str(item).lower()
        for item in (preferences or [])
    ]

    return sorted(
        food,
        key=lambda item: sum(
            pref in (
                item.get("dish", "") + " " + item.get("type", "")
            ).lower()
            for pref in prefs
        ),
        reverse=True,
    )


def calculate_trip_budget(request, itinerary):
    people = int(request["travellers"])
    days = int(request["days"])
    nights = max(days - 1, 0)
    style = request.get("travel_style", "balanced")

    lodging_rate = {
        "hostel": 700,
        "budget hotel": 1500,
        "mid-range hotel": 3000,
        "already booked": 0,
    }.get(request.get("accommodation"), 1500)

    food_pp_day = {
        "budget": 450,
        "balanced": 750,
        "comfortable": 1300,
    }.get(style, 750)

    transport_group_day = {
        "budget": 350,
        "balanced": 700,
        "comfortable": 1400,
    }.get(style, 700)

    accommodation = lodging_rate * nights * max(1, (people + 1) // 2)
    food = food_pp_day * people * days
    transport = transport_group_day * days
    festival = 0
    ticket_status = "unavailable or unverified"
    activities = 0

    for day in itinerary.get("days", []):
        for item in day.get("schedule", []):
            if item.get("type") == "attraction":
                activities += (
                    float(item.get("estimated_cost_per_person", 0))
                    * people
                )

    lines = [
        {
            "item": "Accommodation",
            "amount_inr": accommodation,
            "method": (
                f"₹{lodging_rate} per room/night × {nights} nights × "
                f"{max(1, (people + 1) // 2)} rooms"
            ),
            "evidence_status": "estimated",
        },
        {
            "item": "Food",
            "amount_inr": food,
            "method": (
                f"₹{food_pp_day} per person/day × {people} travellers "
                f"× {days} days"
            ),
            "evidence_status": "estimated",
        },
        {
            "item": "Local transport",
            "amount_inr": transport,
            "method": f"₹{transport_group_day} per group/day × {days} days",
            "evidence_status": "estimated",
        },
        {
            "item": "Festival tickets",
            "amount_inr": festival,
            "method": "Not included because current ticket price is not verified",
            "evidence_status": ticket_status,
        },
        {
            "item": "Attraction fees",
            "amount_inr": activities,
            "method": "Sum of sample dataset entry estimates; verify before travel",
            "evidence_status": "estimated",
        },
    ]

    total = sum(item["amount_inr"] for item in lines)
    budget_inr = float(request["budget_inr"])

    return {
        "currency": "INR",
        "total_inr": total,
        "budget_inr": budget_inr,
        "remaining_inr": budget_inr - total,
        "within_budget": total <= budget_inr,
        "lines": lines,
        "assumptions": [
            "Costs are planning estimates, not supplier quotes.",
            "Festival ticket cost is excluded until verified.",
            "Accommodation uses one room per two travellers, rounded up.",
            "Travel to/from Goa is not included.",
        ],
    }


def validate_itinerary(itinerary, budget):
    warnings = []
    seen = []

    for day in itinerary.get("days", []):
        prior_end = None

        for item in day.get("schedule", []):
            start = item.get("start_time", "")
            end = item.get("end_time", "")
            title = item.get("title", "Untitled activity")

            if start and end and start >= end:
                warnings.append(
                    f"Day {day['day']}: invalid time range for {title}"
                )

            if prior_end and start and start < prior_end:
                warnings.append(
                    f"Day {day['day']}: possible schedule overlap at {title}"
                )

            if end:
                prior_end = end

            normalized_title = title.strip().lower()
            if normalized_title in seen:
                warnings.append(f"Repeated activity: {title}")

            seen.append(normalized_title)

    if not budget["within_budget"]:
        warnings.append(
            f"Estimated total exceeds budget by "
            f"₹{abs(budget['remaining_inr']):.0f}; "
            "adjust hotel, transport or meals."
        )

    warnings.append(
        "Festival dates, event timings and venue are not confirmed by "
        "this demo dataset; verify official sources before booking."
    )

    return {
        "valid": not any(
            "invalid time" in warning or "overlap" in warning
            for warning in warnings
        ),
        "warnings": warnings,
        "replanning_attempts": 0,
    }
