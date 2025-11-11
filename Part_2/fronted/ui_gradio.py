# -*- coding: utf-8 -*-
from __future__ import annotations
import uuid
from typing import List, Tuple

import gradio as gr
import httpx

from ..core_models import ChatResponse, ChatRequest, SessionBundle, UserProfile, ConversationHistory, Phase, Locale

# ---- Import your existing classes ----


API_BASE = "http://localhost:8000"

# ----------------- Helpers -----------------

def new_session_bundle() -> SessionBundle:
    # Start with an empty profile; the LLM will collect details conversationally
    profile = UserProfile()
    return SessionBundle(
        user_profile=profile,
        history=ConversationHistory(),
        phase=Phase.INFO_COLLECTION,
        locale=profile.locale or Locale.HE,
        request_id=None,
    )

async def post_chat(req: ChatRequest) -> ChatResponse:
    """Send ChatRequest → ChatResponse (HTTP)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{API_BASE}/chat",
            json=req.model_dump(),
            headers={"X-Request-ID": str(uuid.uuid4())},
        )
        r.raise_for_status()
        return ChatResponse.model_validate(r.json())

async def on_send(message: str, history: List[List[str]], sb: SessionBundle) -> Tuple[List[List[str]], SessionBundle]:
    if not message or not message.strip():
        return history, sb

    # Show the user message immediately
    history = history + [[message, None]]

    try:
        resp = await post_chat(ChatRequest(session_bundle=sb, user_input=message))
        assistant_text = resp.assistant_text
        # Append citations (under the assistant message)
        if resp.citations:
            bullets = "\n".join(f"• {c}" for c in resp.citations)
            assistant_text += f"\n\n—\n**מקורות:**\n{bullets}"

        # Optional phase badge
        if resp.suggested_phase:
            phase_label = "איסוף פרטים" if resp.suggested_phase == Phase.INFO_COLLECTION else "שאלות ותשובות"
            assistant_text = f"**[{phase_label}]**\n\n" + assistant_text

        history[-1][1] = assistant_text

        # Update session bundle from response (profile + phase)
        sb.user_profile = resp.user_profile
        sb.phase = resp.suggested_phase
        return history, sb

    except Exception as e:
        history[-1][1] = f"⚠️ שגיאה: {type(e).__name__}: {e}"
        return history, sb

# ----------------- UI -----------------
with gr.Blocks(title="MicroChat Medical") as demo:
    gr.Markdown(
        """
        # 🩺 MicroChat Medical — Client UI
        """
    )

    chat = gr.Chatbot(height=560)
    msg = gr.Textbox(label="Message", placeholder="כתוב/י הודעה…", autofocus=True)
    send = gr.Button("Send", variant="primary")

    sb_state = gr.State(new_session_bundle())

    send.click(on_send, inputs=[msg, chat, sb_state], outputs=[chat, sb_state])
    msg.submit(on_send, inputs=[msg, chat, sb_state], outputs=[chat, sb_state])

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=7860)
