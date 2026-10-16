"""FastAPI entry point for GoaFest AI."""
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .models import PlanRequest
from .graph import run_planning
from .web_search import search_web
from .catalog import router as catalog_router
from .mcp_client import list_mcp_tools, call_single_mcp_tool

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
app = FastAPI(title="GoaFest AI", version="1.1.0",
              description="Festival-centred Goa trip planner with LangGraph, MCP tools, CSV listings and source-aware estimates.")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(catalog_router)

@app.get("/health")
def health():
    return {"service": "GoaFest AI", "status": "running",
            "search_configured": bool(os.getenv("TAVILY_API_KEY")),
            "mode": "live-search-enabled" if os.getenv("TAVILY_API_KEY") else "demo/fallback"}

@app.get("/config")
def config():
    return {"search_provider": "Tavily", "search_configured": bool(os.getenv("TAVILY_API_KEY")),
            "fallback_available": True, "images": "Wikimedia Commons lookup; unavailable images are labelled",
            "llm_required": False, "frontend_api_base": "Set VITE_API_BASE_URL in the frontend deployment"}

@app.post("/plan")
def plan(req: PlanRequest):
    try:
        return run_planning(req.model_dump(mode="json"))
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": "Planning failed", "detail": type(exc).__name__,
                              "hint": "Check backend logs; verify CSV files and installed dependencies."})

@app.get("/search")
def search(q: str):
    if not q.strip():
        raise HTTPException(status_code=422, detail="Search query must not be empty")
    return search_web(q.strip())

@app.get("/mcp/tools")
async def mcp_tools():
    """Inspect tool names and input schemas from the running MCP server over MCP protocol."""
    try:
        return {"transport": "stdio", "server": "GoaFest Tourism Tools", "tools": await list_mcp_tools()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MCP server unavailable: {type(exc).__name__}") from exc

@app.post("/mcp/tools/{tool_name}")
async def invoke_mcp_tool(tool_name: str, arguments: dict):
    """Invoke one registered MCP tool for debugging and classroom demonstration."""
    try:
        return await call_single_mcp_tool(tool_name, arguments)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MCP tool invocation failed: {type(exc).__name__}") from exc
