from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv

from .utils import _gather_text_lines, _gather_labeled_checkboxes, _build_system_prompt, _build_user_prompt, \
    _ensure_json
from .azure_client import analyze_document, generate_chat_completion_json

# ------------------------------------------------------
# Logging setup
# ------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("extract")


# ------------------------------------------------------
# Main
# ------------------------------------------------------
def run(
    file_path: Optional[str],
    out_path: str,
    hebrew_keys: bool,
    model_id: Optional[str],
    url_source: Optional[str],
):
    """Run the full pipeline: DI → pre-extract → AOAI normalize → JSON file."""
    load_dotenv()

    # ---- Document Intelligence config ----
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    api_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_API_KEY")
    model_id = model_id or os.getenv("DI_MODEL", "prebuilt-document")

    if not endpoint or not api_key:
        log.error("Missing Azure Document Intelligence endpoint or key in .env")
        sys.exit(2)

    # ---- Read input ----
    pdf_bytes = None
    if file_path:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

    # ---- Analyze with DI ----
    log.info(
        "Analyzing document via DI model '%s' using %s...",
        model_id,
        "URL" if url_source else "local file",
    )
    result = analyze_document(
        endpoint,
        api_key,
        model_id=model_id,
        pdf_bytes=pdf_bytes,
        url_source=url_source,
    )

    # ---- Gather raw evidence ----
    lines = _gather_text_lines(result)
    checks = _gather_labeled_checkboxes(result)
    log.info("Collected %d lines, %d checkbox labels for LLM post-processing.", len(lines), len(checks))

    # # Quick debug prints
    # for ln in lines[:20]:
    #     print("•", ln)
    # print("Checkboxes:", checks)

    # ---- Azure OpenAI post-processing ----
    sys_prompt = _build_system_prompt(hebrew_keys=hebrew_keys)
    user_prompt = _build_user_prompt(lines, checks, hebrew_keys=hebrew_keys)

    # # Quick debug prints
    # print("System prompt:", sys_prompt)
    # print("User prompt:", user_prompt)
    try:
        llm_json = generate_chat_completion_json(system_prompt=sys_prompt, user_prompt=user_prompt)
    except Exception as e:
        log.error("Azure OpenAI extraction failed: %s", e)
        sys.exit(3)

    data = _ensure_json(llm_json)

    # ---- Final safety: ensure JSON serializable ----
    try:
        serialized = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error("Result is not JSON-serializable: %s", e)
        sys.exit(4)

    # ---- Write output ----
    with open(out_path, "w", encoding="utf-8") as wf:
        wf.write(serialized)

    log.info("✅ Extraction completed → %s", out_path)


# ------------------------------------------------------
# CLI entrypoint
# ------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Extract structured JSON from Hebrew forms using DI + Azure OpenAI."
    )
    parser.add_argument("--file", help="Path to local PDF file")
    parser.add_argument("--url", help="Public URL to analyze (uses url_source)")
    parser.add_argument("--model", help="DI Model ID (default .env DI_MODEL or prebuilt-document)")
    parser.add_argument("--out", required=True, help="Path to output JSON file")
    parser.add_argument("--hebrew", action="store_true", help="Output with Hebrew keys")

    args = parser.parse_args()
    if not args.file and not args.url:
        parser.error("You must provide either --file or --url")

    run(args.file, args.out, args.hebrew, args.model, args.url)


if __name__ == "__main__":
    main()
