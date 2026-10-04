"""The chatbot: collects the data, builds the instructions, asks the AI, returns the reply."""
from .prompts import build_system_prompt

MAX_HISTORY_MESSAGES = 20   # remember the last 10 questions + 10 answers
MAX_MESSAGE_LENGTH = 2000


class Chatbot:
    def __init__(self, ai_client, provider):
        self.ai_client = ai_client
        self.provider = provider

    @staticmethod
    def _clean_history(history):
        """Keep only valid, recent messages sent by the browser."""
        clean = []
        for item in history or []:
            if (
                isinstance(item, dict)
                and item.get("role") in ("user", "assistant")
                and isinstance(item.get("content"), str)
            ):
                clean.append({"role": item["role"], "content": item["content"][:MAX_MESSAGE_LENGTH]})
        return clean[-MAX_HISTORY_MESSAGES:]

    def reply(self, user_message, history=None):
        snapshot = self.provider.get_snapshot()          # 1. what data do we have right now?
        system_prompt = build_system_prompt(snapshot)    # 2. rules + data for the AI
        return self.ai_client.generate(                  # 3. ask the AI
            system_prompt=system_prompt,
            history=self._clean_history(history),
            user_message=user_message,
            snapshot=snapshot,
        )
