
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
                "tool_calls": retrieved.get("tool_calls", []),
                "mcp": {
                    "status": "invoked",
                    "tools": retrieved.get("tools_used", []),
                    "trace": retrieved.get("tool_calls", []),
                },
            }

        except Exception as exc:
            # MCP failed: use local CSV tools, but report the failure honestly.
            trace = getattr(exc, "trace", [])

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
                "tool_calls": trace,
                "mcp": {
                    "status": "fallback",
                    "tools": [
                        item["tool"]
                        for item in trace
                        if item.get("error") is None
                    ],
                    "trace": trace,
                    "reason": f"{type(exc).__name__}: {exc}",
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

        result["tool_calls"] = state.get("tool_calls", [])

        result["workflow"] = {
            "engine": "LangGraph",
            "nodes": [
                "retrieve_with_mcp",
                "build_itinerary",
                "validate_and_finalize",
            ],
            "tools_used": state["mcp"].get("tools", []),
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
        _print_execution_trace(result)
        return result

    except Exception as exc:
        result = build_itinerary(request)

        result["tool_calls"] = []
        result["workflow"] = {
            "engine": "deterministic fallback",
            "checkpointing": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "tools_used": [],
            "mcp": {
                "status": "not-confirmed",
                "tools": [],
                "trace": [],
            },
        }

        _print_execution_trace(result)
        return result


def _print_execution_trace(result: dict):
    import json

    print("\nTool calls:")
    for call in result.get("tool_calls", []):
        print(
            f"- {call.get('tool', 'unknown')} | "
            f"{call.get('execution_ms', 0)} ms | "
            f"error={call.get('error')}"
        )

    print("\nShared state snapshot:")
    state_view = {
        "user_input": result.get("request"),
        "event_data": result.get("events"),
        "activity_data": result.get("places"),
        "food_data": result.get("food"),
        "logistics_data": result.get("transport"),
        "estimated_cost": result.get("estimated_cost"),
        "conflicts": result.get("conflicts", []),
        "itinerary": result.get("itinerary", result),
        "replanned": result.get("replanned", False),
        "status": result.get("status", "completed"),
    }
    print(json.dumps(state_view, indent=2, default=str))
