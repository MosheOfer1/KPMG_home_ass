from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AzureOpenAIConfig:
    endpoint: str
    api_key: str
    api_version: str
    chat_deployment: str
    embeddings_deployment: str
    # Client behavior
    request_timeout_s: float
    max_retries: int
    backoff_base_s: float


def load_config() -> AzureOpenAIConfig:
    return AzureOpenAIConfig(
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        chat_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        embeddings_deployment=os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT"),
        request_timeout_s=float(os.getenv("AZURE_OPENAI_TIMEOUT_S", "30")),
        max_retries=int(os.getenv("AZURE_OPENAI_MAX_RETRIES", "3")),
        backoff_base_s=float(os.getenv("AZURE_OPENAI_BACKOFF_S", "0.6")),
    )
