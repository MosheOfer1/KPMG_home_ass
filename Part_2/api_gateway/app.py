from __future__ import annotations
import uuid
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import ApiConfig
from .orchestrator_client import OrchestratorClient
from ..core_models import ChatResponse, ChatRequest

cfg = ApiConfig()
app = FastAPI(title="MicroChat Medical – API Gateway", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cfg.cors_origins.split(",")] if cfg.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orch = OrchestratorClient(cfg)

@app.get("/health")
async def health() -> dict:
    return {"ok": True}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, response: Response) -> ChatResponse:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response.headers["X-Request-ID"] = request_id
    try:
        return await orch.chat(req, request_id=request_id)
    except Exception as e:  # keep gateway thin; detailed errors logged upstream
        raise HTTPException(status_code=502, detail=f"Upstream error: {e.__class__.__name__}")
