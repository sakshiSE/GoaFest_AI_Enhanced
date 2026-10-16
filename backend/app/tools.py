from pathlib import Path
import csv
from datetime import datetime, timedelta
DATA = Path(__file__).resolve().parent.parent / "data"
def rows(name):
    with (DATA/name).open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def search_festival_information(name):
    all_events=rows("events.csv")
    matches=[x for x in all_events if name.lower() in x["festival"].lower() or x["festival"].lower() in name.lower()]
    return matches or [x for x in all_events if x["festival"].lower()=="goa carnival"]
def search_attractions(interests=None):
    places=rows("places.csv"); interests=[x.lower() for x in (interests or [])]
    ranked=sorted(places,key=lambda p: sum(k in (p["category"]+" "+p["description"]).lower() for k in interests),reverse=True)
    return ranked

def search_food_options(preferences=None):
    food=rows("food.csv"); prefs=[x.lower() for x in (preferences or [])]
    return sorted(food,key=lambda p: sum(k in (p["dish"]+" "+p["type"]).lower() for k in prefs),reverse=True)

def calculate_trip_budget(request, itinerary):
    people=int(request["travellers"]); days=int(request["days"]); nights=max(days-1,0)
    style=request.get("travel_style","balanced")
    lodging_rate={"hostel":700,"budget hotel":1500,"mid-range hotel":3000,"already booked":0}.get(request.get("accommodation"),1500)
    food_pp_day={"budget":450,"balanced":750,"comfortable":1300}.get(style,750)
    transport_group_day={"budget":350,"balanced":700,"comfortable":1400}.get(style,700)
    # Static sample costs are estimates, never represented as live quotes.
    accommodation=lodging_rate*nights*max(1,(people+1)//2)
    food=food_pp_day*people*days
    transport=transport_group_day*days
    festival=0
    ticket_status="unavailable or unverified"
    activities=0
    for day in itinerary.get("days",[]):
        for item in day.get("schedule",[]):
            if item.get("type")=="attraction": activities += float(item.get("estimated_cost_per_person",0))*people
    lines=[{"item":"Accommodation","amount_inr":accommodation,"method":f"₹{lodging_rate} per room/night × {nights} nights × {max(1,(people+1)//2)} rooms","evidence_status":"estimated"},
           {"item":"Food","amount_inr":food,"method":f"₹{food_pp_day} per person/day × {people} travellers × {days} days","evidence_status":"estimated"},
           {"item":"Local transport","amount_inr":transport,"method":f"₹{transport_group_day} per group/day × {days} days","evidence_status":"estimated"},
           {"item":"Festival tickets","amount_inr":festival,"method":"Not included because current ticket price is not verified","evidence_status":ticket_status},
           {"item":"Attraction fees","amount_inr":activities,"method":"Sum of sample dataset entry estimates; verify before travel","evidence_status":"estimated"}]
    total=sum(x["amount_inr"] for x in lines)
    return {"currency":"INR","total_inr":total,"budget_inr":float(request["budget_inr"]),"remaining_inr":float(request["budget_inr"])-total,"within_budget":total<=float(request["budget_inr"]),"lines":lines,"assumptions":["Costs are planning estimates, not supplier quotes.","Festival ticket cost is excluded until verified.","Accommodation uses one room per two travellers, rounded up.","Travel to/from Goa is not included." ]}

def validate_itinerary(itinerary, budget):
    warnings=[]; seen=[]
    for day in itinerary.get("days",[]):
        prior_end=None
        for item in day.get("schedule",[]):
            start=item.get("start_time",""); end=item.get("end_time","")
            if start and end and start >= end: warnings.append(f"Day {day['day']}: invalid time range for {item.get('title')}")
            if prior_end and start and start < prior_end: warnings.append(f"Day {day['day']}: possible schedule overlap at {item.get('title')}")
            if end: prior_end=end
            if item.get("title") in seen: warnings.append(f"Repeated activity: {item.get('title')}")
            seen.append(item.get("title"))
    if not budget["within_budget"]: warnings.append(f"Estimated total exceeds budget by ₹{abs(budget['remaining_inr']):.0f}; adjust hotel, transport or meals.")
    warnings.append("Festival dates, event timings and venue are not confirmed by this demo dataset; verify official sources before booking.")
    return {"valid":not any("invalid time" in w or "overlap" in w for w in warnings),"warnings":warnings,"replanning_attempts":0}
