"""
Minimal pub/sub WebSocket manager. Every connected client joins one
"channel" (e.g. a delivery id, or "admin" for the global feed) and
receives JSON messages broadcast to that channel — used for live
volunteer GPS pings and status changes so donor/NGO/admin dashboards
update instantly without polling.
"""
import json
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.channels: Dict[str, Set[WebSocket]] = {}

    async def connect(self, channel: str, ws: WebSocket):
        await ws.accept()
        self.channels.setdefault(channel, set()).add(ws)

    def disconnect(self, channel: str, ws: WebSocket):
        if channel in self.channels:
            self.channels[channel].discard(ws)

    async def broadcast(self, channel: str, message: dict):
        dead = []
        for ws in self.channels.get(channel, set()):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(channel, ws)


manager = ConnectionManager()
