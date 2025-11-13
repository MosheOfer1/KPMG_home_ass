# -*- coding: utf-8 -*-
from __future__ import annotations
import gradio as gr

from Part_2.core_models import Locale
from Part_2.fronted.ui_logic import (
    TRANSLATIONS,
    new_session_bundle,
    add_user_message,
    fetch_assistant_reply,
    initialize_session,
    change_language,
    header_html,
)

css = """
#chatbot {
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
#msg-box {
    border-radius: 8px;
}
.header-text {
    text-align: center;
    margin-bottom: 1.5rem;
}
#lang-selector {
    max-width: 150px;
}
"""

with gr.Blocks(css=css, title="MicroChat Medical") as demo:
    lang_state = gr.State("he")
    sb_state = gr.State(new_session_bundle(Locale.HE))

    # Header
    header_md = gr.Markdown(
        header_html("he"),
        elem_id="header"
    )

    # Language selector
    lang_dropdown = gr.Dropdown(
        choices=[("עברית", "he"), ("English", "en")],
        value="he",
        label=TRANSLATIONS["he"]["language"],
        elem_id="lang-selector",
        scale=1,
    )

    # Chat + input
    chat = gr.Chatbot(
        height=500,
        elem_id="chatbot",
        show_label=False,
        bubble_full_width=False,
        render_markdown=True,
    )

    msg = gr.Textbox(
        placeholder=TRANSLATIONS["he"]["placeholder"],
        show_label=False,
        scale=9,
        elem_id="msg-box",
        autofocus=True,
    )
    send = gr.Button(TRANSLATIONS["he"]["send"], variant="primary", scale=1)

    # On load – show system intro
    demo.load(
        initialize_session,
        inputs=[sb_state, lang_state],
        outputs=[chat, sb_state],
    )

    # Language change
    lang_dropdown.change(
        change_language,
        inputs=[lang_dropdown],
        outputs=[header_md, msg, send, lang_dropdown, sb_state],
    ).then(
        lambda lang: lang,
        inputs=[lang_dropdown],
        outputs=[lang_state],
    ).then(
        initialize_session,
        inputs=[sb_state, lang_state],
        outputs=[chat, sb_state],
    )

    # Send button
    send.click(
        add_user_message,
        inputs=[msg, chat, sb_state, lang_state],
        outputs=[chat, msg, sb_state],
    ).then(
        fetch_assistant_reply,
        inputs=[chat, sb_state, lang_state],
        outputs=[chat, sb_state],
    )

    # Enter key
    msg.submit(
        add_user_message,
        inputs=[msg, chat, sb_state, lang_state],
        outputs=[chat, msg, sb_state],
    ).then(
        fetch_assistant_reply,
        inputs=[chat, sb_state, lang_state],
        outputs=[chat, sb_state],
    )

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, inbrowser=True)
