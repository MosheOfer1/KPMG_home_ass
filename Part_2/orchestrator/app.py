from __future__ import annotations
import logging, uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import OrchestratorConfig
from .service import OrchestratorService
from ..azure_integration import load_config
from ..core_models import ChatResponse, ChatRequest
from ..logging_config import setup_logging
from ..retriever.config import RetrieverConfig

setup_logging("orchestrator")
log = logging.getLogger("orchestrator.app")

orch_cfg = OrchestratorConfig()
aoai_cfg = load_config()
ret_cfg = RetrieverConfig()
svc = OrchestratorService(orch_cfg, aoai_cfg, ret_cfg)

app = FastAPI(title="MicroChat Medical – Orchestrator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

@app.get("/health")
async def health() -> dict:
    return {"ok": True, "kb_dir": ret_cfg.kb_dir}

@app.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    log.info("Orchestrator /v1/chat start")

    try:
        resp = await svc.handle_chat(req, request_id=request_id)
        log.info("Orchestrator /v1/chat success")
        return resp
    except Exception as e:
        log.exception("orchestrator error")
        # Let gateway convert this into 502
        raise
