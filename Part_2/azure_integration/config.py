from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AzureOpenAIConfig:
    """
    This class encapsulates the configuration required to interact with the Azure OpenAI
    service. It is designed to include all necessary parameters needed for making API
    requests to the Azure OpenAI service. Usage of this class ensures consistent
    configuration and ease of access to required settings.

    The configuration includes endpoint data, authentication credentials, deployment
    identifiers, and client behavior parameters such as timeout and retry policies.

    :ivar endpoint: The Azure OpenAI endpoint URL for making API requests.
    :type endpoint: str
    :ivar api_key: The API key used to authenticate with Azure OpenAI.
    :type api_key: str
    :ivar api_version: The version of the Azure OpenAI API to use.
    :type api_version: str
    :ivar chat_deployment: The name of the specific chat model deployment in Azure OpenAI.
    :type chat_deployment: str
    :ivar embeddings_deployment: The name of the specific embeddings model deployment in
        Azure OpenAI.
    :type embeddings_deployment: str
    :ivar request_timeout_s: The timeout for API requests, in seconds.
    :type request_timeout_s: float
    :ivar max_retries: The maximum number of retry attempts for failed requests.
    :type max_retries: int
    :ivar backoff_base_s: The base backoff interval, in seconds, for handling retries.
    :type backoff_base_s: float
    """
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
