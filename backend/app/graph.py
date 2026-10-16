
"""LangGraph workflow: retrieve -> plan -> validate/finalize."""

from .agents import build_itinerary
from .state import TripState


def create_planning_graph():
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    from .mcp_client import call_tourism_tools
    from .web_search import search_web
    from .tools import (
        search_festival_information,
        search_attractions,
        search_food_options,
    )

    def retrieve_node(state: TripState):
        request = state["request"]

        research = search_web(
            f"{request['festival']} Goa official dates schedule "
            f"venue tickets {request['start_date']}"
        )

        try:
            retrieved = call_tourism_tools(
                request["festival"],
                request.get("interests", []),
                request.get("food_preferences", []),
            )

            data = retrieved["results"]

            return {
                "research": research,
                "events": data.get("festival_information") or [],
                "places": data.get("attractions") or [],
                "food": data.get("food_options") or [],
                "mcp": {
                    "status": "invoked",
                    "tools": retrieved["tools_used"],
                },
            }

        except Exception:
            # Preserve planning if the MCP protocol is unavailable.
            # Local CSV functions are fallback tools, not MCP calls.
            return {
                "research": research,
                "events": search_festival_information(
                    request["festival"]
                ),
                "places": search_attractions(
                    request.get("interests", [])
                ),
                "food": search_food_options(
                    request.get("food_preferences", [])
                ),
                "mcp": {
                    "status": "fallback",
                    "tools": [],
                },
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
            "nodes": [
                "retrieve_with_mcp",
                "build_itinerary",
                "validate_and_finalize",
            ],
            "tools_used": state["mcp"].get("tools", []),
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

        config = {
            "configurable": {
                "thread_id": (
                    f"trip-{request.get('start_date')}-"
                    f"{request.get('festival', 'goa').lower().replace(' ', '-')}"
                )
            }
        }

        result = graph.invoke(
            {"request": request},
            config=config,
        )["final"]

        result["workflow"]["checkpointing"] = checkpointed
        return result

    except Exception:
        # Keep a clearly labelled fallback if the graph cannot run.
        result = build_itinerary(request)

        result["workflow"] = {
            "engine": "deterministic fallback",
            "checkpointing": False,
            "tools_used": [],
        }

        return result
