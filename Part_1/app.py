#!/usr/bin/env python3
# app.py — Simple Gradio UI for DI → AOAI → JSON
from __future__ import annotations

import json
import os

import gradio as gr
from dotenv import load_dotenv

# Reuse your existing modules
from azure_client import analyze_document, generate_chat_completion_json
from extract import _gather_text_lines, _gather_labeled_checkboxes, _build_system_prompt, _build_user_prompt, \
    _ensure_json


# ---------- Core pipeline for the UI ----------
def process(file, url, hebrew_keys, model_id):
    """
    file: gr.File (optional)
    url: str (optional)
    """
    load_dotenv()

    di_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    di_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_API_KEY")
    if not di_endpoint or not di_key:
        return None, None, None, "Missing DI credentials in environment."

    model = model_id or os.getenv("DI_MODEL", "prebuilt-document")
    pdf_bytes = None
    url_source = None

    if url and url.strip():
        url_source = url.strip()
    elif file is not None:
        pdf_bytes = file  # works for PDFs and images; azure_client now infers content_type (see patch below)
    else:
        return None, None, None, "Please upload a file or provide a URL."

    try:
        result = analyze_document(
            di_endpoint, di_key,
            model_id=model,
            pdf_bytes=pdf_bytes,
            url_source=url_source
        )
    except Exception as e:
        return None, None, None, f"Document Intelligence error: {e}"

    # Collect evidence
    lines = _gather_text_lines(result)
    checks = _gather_labeled_checkboxes(result)

    # AOAI normalize
    try:
        sys_prompt = _build_system_prompt(hebrew_keys=hebrew_keys)
        user_prompt = _build_user_prompt(lines, checks, hebrew_keys=hebrew_keys)
        llm_json = generate_chat_completion_json(system_prompt=sys_prompt, user_prompt=user_prompt)
        data = _ensure_json(llm_json)
        pretty = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return None, None, None, f"Azure OpenAI error: {e}"

    # Return: JSON, raw lines (preview), checkbox map (preview), status
    lines_preview = "\n".join(lines[:50])  # show up to 50 lines as a peek
    checks_preview = json.dumps(checks, ensure_ascii=False, indent=2)
    return pretty, lines_preview, checks_preview, "Done ✅"

# ---------- Gradio UI ----------
with gr.Blocks(title="Form→JSON (Azure DI + AOAI)") as demo:
    gr.Markdown("## Upload a PDF/JPG/PNG **or** paste a URL → get structured JSON")

    with gr.Row():
        file_in = gr.File(label="Upload PDF/JPG/PNG", file_types=[".pdf", ".jpg", ".jpeg", ".png"], type="binary")
        url_in = gr.Textbox(label="Or analyze public URL (PDF/Image)", placeholder="https://...")

    with gr.Row():
        model_in = gr.Textbox(label="DI Model ID (optional)", placeholder="prebuilt-document")
        hebrew_in = gr.Checkbox(label="Output Hebrew keys", value=False)

    run_btn = gr.Button("Extract JSON")

    json_out = gr.Code(label="Result JSON", language="json")
    with gr.Accordion("Raw DI lines (first 50)", open=False):
        lines_out = gr.Textbox(show_label=False, lines=12)
    with gr.Accordion("Detected checkboxes", open=False):
        checks_out = gr.Code(language="json", show_label=False)

    status = gr.Markdown()

    run_btn.click(
        fn=process,
        inputs=[file_in, url_in, hebrew_in, model_in],
        outputs=[json_out, lines_out, checks_out, status]
    )

if __name__ == "__main__":
    # Set share=True if you want a public link during dev
    demo.launch()
