"""
Data provider: collects everything the assistant is allowed to know.

Each "data source" (Gmail, Calendar, reminders ...) is a small function that
returns its data. The chatbot never talks to Gmail or Calendar directly. It only
asks this provider for a "snapshot". If a source is not connected, the snapshot
says so clearly, so the AI can tell the user "this information is unavailable"
instead of guessing.
"""
import time
from datetime import datetime

# Every source the assistant knows about. Add new ones here when your app grows.
KNOWN_SOURCES = {
    "gmail": "Gmail emails",
    "meetings": "Meetings detected from emails",
    "calendar": "Google Calendar events",
    "reminders": "Reminders",
    "sync_status": "Gmail-to-Calendar synchronization status",
}

CACHE_SECONDS = 60  # reuse loaded data for 1 minute so Gmail is not called on every message


class DataProvider:
    def __init__(self):
        self._labels = dict(KNOWN_SOURCES)
        self._loaders = {}
        self._cache = {}

    def register(self, name, loader, label=None):
        """Connect a data source. `loader` is a function that returns a dict."""
        self._loaders[name] = loader
        if label:
            self._labels[name] = label
        self._cache.pop(name, None)

    def clear_cache(self):
        self._cache.clear()

    def _load(self, name, label):
        loader = self._loaders.get(name)
        if loader is None:
            return {
                "label": label,
                "available": False,
                "reason": "This data source is not connected to the assistant yet.",
            }

        cached = self._cache.get(name)
        if cached and time.time() - cached[0] < CACHE_SECONDS:
            return cached[1]

        try:
            result = dict(loader())
        except Exception as error:
            return {"label": label, "available": False, "reason": f"Could not load this data: {error}"}

        result["label"] = label
        result.setdefault("available", True)
        if result["available"]:
            self._cache[name] = (time.time(), result)  # only successful loads are cached
        return result

    def get_snapshot(self):
        """Return the current time plus the status and data of every source."""
        return {
            "current_time": datetime.now().astimezone().strftime("%A, %Y-%m-%d %H:%M %Z (UTC%z)"),
            "sources": {name: self._load(name, label) for name, label in self._labels.items()},
        }


# One shared provider for the whole app
provider = DataProvider()
