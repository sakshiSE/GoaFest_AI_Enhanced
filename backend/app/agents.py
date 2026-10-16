from datetime import timedelta, date as date_type
from .tools import search_festival_information, search_attractions, search_food_options, calculate_trip_budget, validate_itinerary
from .web_search import search_web
from .image_search import find_image

def build_itinerary(request: dict, research=None, events=None, places=None, food=None) -> dict:
    festival_name=request["festival"]
    research = research or search_web(f"{festival_name} Goa official dates schedule venue tickets {request['start_date']}")
    events = events if events is not None else search_festival_information(festival_name)
    places = places if places is not None else search_attractions(request.get("interests",[]))
    food = food if food is not None else search_food_options(request.get("food_preferences",[]))
    # If live research succeeds, expose its sources for verification, but never infer an event schedule from snippets.
    festival={"name":festival_name,"date":str(request["start_date"]),"venue":"To be confirmed from an official festival source","schedule_status":"unverified","research_status":research["status"],"research_results":research["results"],"fallback_records":events[:3],"note":"The selected date is a user-provided planning anchor, not a claim that the festival occurs on that date."}
    daily=[]
    start_date = request["start_date"] if isinstance(request["start_date"], date_type) else date_type.fromisoformat(str(request["start_date"]))
    for i in range(request["days"]):
        date=str(start_date+timedelta(days=i)); sched=[]
        if i==0:
            sched.append({"start_time":"10:00","end_time":"11:00","title":"Arrival and check-in buffer","type":"break","location":"Goa","description":"Keep this flexible for your actual arrival time.","estimated_cost_per_person":0})
        # Festival is the trip anchor each day; do not invent a start time or venue.
        if i==0:
            sched.append({"start_time":"11:00","end_time":"11:30","title":f"Confirm {festival_name} schedule and venue","type":"festival","location":"Official venue to be confirmed","description":"Check the official organiser website/social channel before travelling. Event time is not verified.","estimated_cost_per_person":0})
        if places:
            p=places[(i*2)%len(places)]
            sched.append({"start_time":"12:00","end_time":"13:30","title":p["name"],"type":"attraction","location":p["area"],"description":p["description"],"estimated_cost_per_person":float(p.get("estimated_fee_inr") or 0),"evidence_status":"estimated / demo dataset","source_url":p.get("source_url") or None,"image":find_image(p["name"])})
        if food:
            f=food[i%len(food)]
            sched.append({"start_time":"13:30","end_time":"14:15","title":f"Lunch: {f['dish']}","type":"food","location":f["area"],"description":f["description"],"estimated_cost_per_person":float(f.get("estimated_price_inr") or 0),"evidence_status":"estimated / demo dataset","source_url":f.get("source_url") or None})
        if i < request["days"]-1 and places:
            p=places[(i*2+1)%len(places)]
            sched.append({"start_time":"15:00","end_time":"16:30","title":p["name"],"type":"attraction","location":p["area"],"description":p["description"],"estimated_cost_per_person":float(p.get("estimated_fee_inr") or 0),"evidence_status":"estimated / demo dataset","source_url":p.get("source_url") or None,"image":find_image(p["name"])})
        sched.append({"start_time":"17:00","end_time":"18:00","title":"Festival window / rest and travel buffer","type":"festival","location":"Venue to be confirmed","description":"Keep this time flexible for the actual event schedule. This is a planning buffer, not a confirmed event slot.","estimated_cost_per_person":0})
        daily.append({"day":i+1,"date":date,"theme":["Arrival, orientation and festival check","Coastal and cultural Goa","Flexible festival day and departure preparation"][min(i,2)],"schedule":sched})
    itinerary={"festival":festival,"days":daily,"attractions":places[:6],"food_recommendations":food[:6],"transport":{"status":"estimated","note":"No live route or traffic provider is configured. Travel times are not fabricated; allow 30–60 minutes between nearby stops and verify routes before departure."},"sources":research["results"],"mode":"live research available" if research["status"]=="live" else "demo / fallback mode"}
    budget=calculate_trip_budget(request,itinerary)
    validation=validate_itinerary(itinerary,budget)
    return {"trip_summary":{"festival":festival_name,"start_date":str(request["start_date"]),"days":request["days"],"travellers":request["travellers"],"mode":itinerary["mode"]},"itinerary":itinerary,"budget":budget,"validation":validation,"agents":{"coordinator":"completed","festival_research":"completed with source status shown","places":"completed using demo dataset plus optional image lookup","food":"completed using demo dataset","budget":"deterministic calculation","validator":"completed"}}
