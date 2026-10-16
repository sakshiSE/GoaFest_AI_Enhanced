"""Small, explicit LangGraph workflow: retrieve -> plan -> validate/finalize."""
from .agents import build_itinerary
from .state import TripState


def create_planning_graph():
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    from .mcp_client import call_tourism_tools
    from .web_search import search_web
    from .tools import search_festival_information, search_attractions, search_food_options

    def retrieve_node(state: TripState):
        request = state["request"]
        research = search_web(
            f"{request['festival']} Goa official dates schedule venue tickets {request['start_date']}"
        )
        try:
            retrieved = call_tourism_tools(
                request["festival"], request.get("interests", []), request.get("food_preferences", [])
            )
            return {
                "research": research,
                "events": retrieved.get("festival_information") or [],
                "places": retrieved.get("attractions") or [],
                "food": retrieved.get("food_options") or [],
                "mcp": {"status": "invoked", "tools": ["festival_information", "attractions", "food_options"]},
            }
        except Exception as exc:
            # Keep planning available when the MCP SDK/server cannot start, and make fallback visible.
            return {
                "research": research,
                "events": search_festival_information(request["festival"]),
                "places": search_attractions(request.get("interests", [])),
                "food": search_food_options(request.get("food_preferences", [])),
                "mcp": {"status": "fallback", "tools": [], "reason": type(exc).__name__},
            }

    def plan_node(state: TripState):
        result = build_itinerary(
            state["request"],
            research=state["research"],
            events=state["events"],
            places=state["places"],
            food=state["food"],
        )
        result["workflow"] = {
            "engine": "LangGraph",
            "nodes": ["retrieve_with_mcp", "build_itinerary", "validate_and_finalize"],
            "mcp": state["mcp"],
        }
        return {"draft": result}

    def validate_node(state: TripState):
        result = state["draft"]
        result["workflow"]["completed"] = True
        return {"final": result}

    graph = StateGraph(TripState)
    graph.add_node("retrieve_with_mcp", retrieve_node)
    graph.add_node("build_itinerary", plan_node)
    graph.add_node("validate_and_finalize", validate_node)
    graph.add_edge(START, "retrieve_with_mcp")
    graph.add_edge("retrieve_with_mcp", "build_itinerary")
    graph.add_edge("build_itinerary", "validate_and_finalize")
    graph.add_edge("validate_and_finalize", END)
    try:
        return graph.compile(checkpointer=MemorySaver()), True
    except Exception:
        return graph.compile(), False


def run_planning(request: dict):
    try:
        graph, checkpointed = create_planning_graph()
        config = {"configurable": {"thread_id": f"trip-{request.get('start_date')}-{request.get('festival', 'goa').lower().replace(' ', '-')}"}}
        result = graph.invoke({"request": request}, config=config)["final"]
        result["workflow"]["checkpointing"] = checkpointed
        return result
    except Exception as exc:
        # A clearly labelled deterministic fallback is retained for dependency/runtime failures.
        result = build_itinerary(request)
        result["workflow"] = {
            "engine": "deterministic fallback",
            "checkpointing": False,
            "reason": type(exc).__name__,
            "mcp": {"status": "not-confirmed", "tools": []},
        }
        return result
