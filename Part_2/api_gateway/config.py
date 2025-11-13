from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class ApiConfig:
    """
    Represents the configuration for an API.

    This class defines various configuration settings required for an API, including
    the orchestrator URL, CORS origins, and request timeout. It is designed to be
    immutable and relies on environment variables for default values. The class
    leverages dataclasses for cleaner and more structured code.

    :ivar orchestrator_url: The URL of the orchestrator service.
    :type orchestrator_url: str
    :ivar cors_origins: A comma-separated list of allowed CORS origins.
    :type cors_origins: str
    :ivar request_timeout_s: The timeout for API requests, in seconds.
    :type request_timeout_s: float
    """
    orchestrator_url: str = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
    request_timeout_s: float = float(os.getenv("API_TIMEOUT_S", "45"))
