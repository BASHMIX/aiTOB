from fastapi import WebSocket
from typing import List, Dict, Set
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_workspaces: Dict[WebSocket, str] = {}
        self.subscriptions: Dict[tuple[str, str], Set[WebSocket]] = {}
        self.overlay_connections: Dict[str, Set[WebSocket]] = {} # slot -> {websockets}
        self.bot_connection: WebSocket | None = None

    async def connect(self, websocket: WebSocket, workspace_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_workspaces[websocket] = workspace_id

    async def connect_bot(self, websocket: WebSocket):
        await websocket.accept()
        self.bot_connection = websocket

    def disconnect_bot(self):
        self.bot_connection = None

    async def connect_overlay(self, websocket: WebSocket, slot: str, workspace_id: str | None = None):
        await websocket.accept()
        self.register_overlay(websocket, slot, workspace_id)

    def register_overlay(self, websocket: WebSocket, slot: str, workspace_id: str | None = None):
        key = f"{workspace_id or ''}:{slot}"
        if key not in self.overlay_connections:
            self.overlay_connections[key] = set()
        self.overlay_connections[key].add(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_workspaces.pop(websocket, None)
        
        # Remove from all subscriptions
        for subscribers in self.subscriptions.values():
            if websocket in subscribers:
                subscribers.remove(websocket)
        
        # Remove from overlays
        for conns in self.overlay_connections.values():
            if websocket in conns:
                conns.remove(websocket)

        if websocket == self.bot_connection:
            self.bot_connection = None

    async def subscribe(self, websocket: WebSocket, workspace_id: str, tournament_slug: str):
        key = (workspace_id, tournament_slug)
        if key not in self.subscriptions:
            self.subscriptions[key] = set()
        self.subscriptions[key].add(websocket)

    async def broadcast(self, message: dict):
        """Broadcast only inside an explicitly supplied trusted workspace."""
        payload_message = dict(message)
        workspace_id = payload_message.pop("_workspace_id", None)
        if not workspace_id:
            return
        payload = json.dumps(payload_message)
        all_conns = {ws for ws in self.active_connections if self.connection_workspaces.get(ws) == workspace_id}
            
        if not all_conns:
            return
            
        await asyncio.gather(
            *[connection.send_text(payload) for connection in all_conns],
            return_exceptions=True
        )

    async def broadcast_to_tournament(self, workspace_id: str, tournament_slug: str, message: dict):
        """Broadcast only to clients subscribed to a specific tournament."""
        key = (workspace_id, tournament_slug)
        if key not in self.subscriptions or not self.subscriptions[key]:
            return

        payload = json.dumps(message)
        await asyncio.gather(
            *[connection.send_text(payload) for connection in self.subscriptions[key]],
            return_exceptions=True
        )

    async def broadcast_to_slot(self, slot: str, message: dict, workspace_id: str | None = None):
        """Broadcast to specific overlay slot."""
        key = f"{workspace_id or ''}:{slot}"
        if key not in self.overlay_connections or not self.overlay_connections[key]:
            return

        payload = json.dumps(message)
        await asyncio.gather(
            *[connection.send_text(payload) for connection in self.overlay_connections[key]],
            return_exceptions=True
        )

    async def broadcast_to_workspace_overlays(self, workspace_id: str, message: dict):
        """Notify every OBS overlay owned by one workspace.

        Player/character overrides are entrant-scoped rather than station-
        scoped, so the writer does not know which station currently displays
        that entrant. Each connected overlay performs its normal authenticated
        data refresh and receives only its own active match projection.
        """
        prefix = f"{workspace_id}:"
        connections = {
            connection
            for key, values in self.overlay_connections.items()
            if key.startswith(prefix)
            for connection in values
        }
        if not connections:
            return
        payload = json.dumps(message)
        await asyncio.gather(
            *[connection.send_text(payload) for connection in connections],
            return_exceptions=True,
        )

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))

# Global instance
manager = ConnectionManager()
