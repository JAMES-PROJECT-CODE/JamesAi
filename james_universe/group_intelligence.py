"""Short-lived, in-memory group context. No raw chat history is persisted."""
from collections import defaultdict, deque

class GroupContext:
    def __init__(self, max_messages: int = 16):
        self.messages = defaultdict(lambda: deque(maxlen=max_messages))

    def add(self, chat_id: int, speaker: str, text: str):
        self.messages[chat_id].append({
            "role": "user",
            "content": f"{speaker}: {text[:1200]}"
        })

    def prompt_messages(self, chat_id: int):
        return list(self.messages[chat_id])

    def add_assistant(self, chat_id: int, text: str):
        self.messages[chat_id].append({
            "role": "assistant",
            "content": text[:1800]
        })
