"""
Real Gemini AI client for the assistant.

The chatbot sends:
- system prompt
- conversation history
- current user message
- Gmail / Calendar snapshot

Gemini uses this information to answer the user.
"""

import json
import os

from google import genai
from google.genai import types


MODEL_NAME = "gemini-3.8-flash"


class GeminiAIClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is missing. "
                "Add GEMINI_API_KEY to your .env file."
            )

        self.client = genai.Client(api_key=self.api_key)

    def _build_contents(
        self,
        history,
        user_message,
        snapshot,
    ):
        parts = []

        # -----------------------------------------
        # Conversation history
        # -----------------------------------------
        if history:
            parts.append("CONVERSATION HISTORY:")

            for item in history:
                role = item.get("role", "user")
                content = item.get("content", "")

                if not content:
                    continue

                if role == "assistant":
                    parts.append(f"Assistant: {content}")
                else:
                    parts.append(f"User: {content}")

            parts.append("")

        # -----------------------------------------
        # Gmail / Calendar / Meetings / Reminders
        # -----------------------------------------
        parts.append("LIVE USER DATA:")

        parts.append(
            json.dumps(
                snapshot,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        parts.append("")

        # -----------------------------------------
        # Current user message
        # -----------------------------------------
        parts.append("CURRENT USER MESSAGE:")
        parts.append(user_message)

        return "\n".join(parts)

    def generate(
        self,
        system_prompt,
        history,
        user_message,
        snapshot,
    ):
        """
        Generate a response using Gemini.
        """

        contents = self._build_contents(
            history=history,
            user_message=user_message,
            snapshot=snapshot,
        )

        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                    max_output_tokens=1200,
                ),
            )

            reply = (response.text or "").strip()

            if not reply:
                return (
                    "Bhai, Gemini ne empty response diya. "
                    "Ek baar phir try karo."
                )

            return reply

        except Exception as exc:
            print("\n========== GEMINI API ERROR ==========")
            print(repr(exc))
            print("======================================\n")

            return (
                "Bhai, Gemini se response lene mein problem aa gayi. "
                "Terminal mein Gemini error check karo."
            )


def get_ai_client():
    return GeminiAIClient()