from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import ApiConfig
from .orchestrator_client import OrchestratorClient
from ..core_models import ChatResponse, ChatRequest
from ..logging_config import setup_logging
setup_logging("api-gateway")
log = logging.getLogger("api_gateway.app")

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
    """
    Handles the health check endpoint for the application.

    This function provides a simple health status for the application, typically
    used to verify if the service is running and reachable. It returns a JSON response
    indicating the health status.

    :return: A dictionary containing the health status of the application
    :rtype: dict
    """
    return {"ok": True}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, response: Response) -> ChatResponse:
    """
    Handles the POST request to the `/chat` endpoint, processes the input data, logs the request and response
    details, invokes the orchestrator for chat processing, and manages error handling for upstream issues.

    Logs important information, including request ID, and adapts responses based on success or failure of
    the process. If an upstream timeout or HTTP error occurs, the corresponding HTTP exceptions are raised
    with appropriate status codes.

    :param req: Request payload for the chat operation
    :type req: ChatRequest
    :param request: Incoming HTTP request object
    :type request: Request
    :param response: HTTP response object to set response headers
    :type response: Response
    :return: Processed chat response
    :rtype: ChatResponse
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response.headers["X-Request-ID"] = request_id
    adapter = logging.LoggerAdapter(log, extra={"request_id": request_id})

    adapter.info("Incoming /chat request")

    try:
        resp = await orch.chat(req, request_id=request_id)
        adapter.info("Outgoing /chat response OK")
        return resp
    except httpx.TimeoutException as e:
        adapter.warning("Upstream timeout: %s", e)
        raise HTTPException(status_code=504, detail="Upstream timeout")
    except httpx.HTTPStatusError as e:
        adapter.error("Upstream HTTP error %s: %s", e.response.status_code, e)
        raise HTTPException(status_code=502, detail=f"Upstream error: {e.response.status_code}")
    except Exception as e:
        adapter.exception("Unexpected error in gateway")
        raise HTTPException(status_code=502, detail="Upstream error")
