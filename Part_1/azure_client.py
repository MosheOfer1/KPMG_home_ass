import json
import logging
import os
from typing import Optional, Any

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult
from openai import AzureOpenAI

log = logging.getLogger(__name__)


# ---------------------------
# Document Intelligence
# ---------------------------
def analyze_document(
    endpoint: str,
    api_key: str,
    *,
    model_id: str = "prebuilt-document",
    pdf_bytes: Optional[bytes] = None,
    url_source: Optional[str] = None,
) -> AnalyzeResult:
    """
    Analyze either a remote document (URL) or a local file (bytes) with Azure AI Document Intelligence.
    Supports PDF and common image types by inferring content_type.
    """
    client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(api_key))

    if url_source:
        poller = client.begin_analyze_document(
            model_id,
            body=AnalyzeDocumentRequest(url_source=url_source),
        )
        return poller.result()

    if pdf_bytes is None:
        raise ValueError("Provide either pdf_bytes or url_source")

    # --- Infer content type from magic bytes (very light heuristic) ---
    content_type = "application/pdf"
    if pdf_bytes.startswith(b"%PDF"):
        content_type = "application/pdf"
    elif pdf_bytes[0:3] == b"\xff\xd8\xff":
        content_type = "image/jpeg"
    elif pdf_bytes[0:8] == b"\x89PNG\r\n\x1a\n":
        content_type = "image/png"

    poller = client.begin_analyze_document(
        model_id=model_id,
        body=pdf_bytes,
        content_type=content_type,
    )
    return poller.result()


# ---------------------------
# Azure OpenAI (LLM step)
# ---------------------------
def _get_aoai_client() -> AzureOpenAI:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    if not endpoint or not api_key:
        raise RuntimeError("Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY in environment.")
    return AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint)


def generate_chat_completion_json(*, system_prompt: str, user_prompt: str) -> Any:
    """
    Call Azure OpenAI chat to produce STRICT JSON.
    Expects deployment name in AZURE_OPENAI_DEPLOYMENT (e.g., gpt-4o-mini).
    """
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    if not deployment:
        raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is not set.")

    client = _get_aoai_client()
    resp = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},  # Ask the model to return pure JSON
    )
    content = resp.choices[0].message.content
    return json.loads(content)


