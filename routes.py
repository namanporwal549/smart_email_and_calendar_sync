from flask import Blueprint, request, jsonify, render_template
import logging

from .ai_client import get_ai_client
from .chatbot import Chatbot
from .data_provider import provider


logger = logging.getLogger(__name__)

assistant_bp = Blueprint(
    "assistant",
    __name__,
    url_prefix="/assistant"
)


chatbot = Chatbot(
    get_ai_client(),
    provider
)


# ============================================================
# CHATBOT PAGE
# ============================================================

@assistant_bp.get("/")
def assistant_page():
    """
    Open the chatbot UI.
    """
    return render_template("assistant.html")


# ============================================================
# CHAT API
# ============================================================

@assistant_bp.post("/chat")
def assistant_chat():
    """
    Receive a message from the chatbot frontend
    and return Gemini's response.
    """

    try:
        data = request.get_json(silent=True) or {}

        message = (data.get("message") or "").strip()

        if not message:
            return jsonify({
                "error": "Message cannot be empty."
            }), 400

        if len(message) > 1000:
            return jsonify({
                "error": "Message is too long."
            }), 400

        history = data.get("history") or []

        reply = chatbot.reply(
            message,
            history
        )

        return jsonify({
            "reply": reply
        })

    except Exception as e:
        logger.exception("Assistant chat error")

        return jsonify({
            "error": "Assistant error occurred."
        }), 500