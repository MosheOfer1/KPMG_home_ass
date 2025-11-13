from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class ApiConfig:
    orchestrator_url: str = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
    request_timeout_s: float = float(os.getenv("API_TIMEOUT_S", "45"))
