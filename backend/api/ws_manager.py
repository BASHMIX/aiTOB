from fastapi import WebSocket
from typing import List, Dict, Set
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, Set[WebSocket]] = {} # tournament_slug -> {websockets}
        self.overlay_connections: Dict[str, Set[WebSocket]] = {} # slot -> {websockets}
        self.bot_connection: WebSocket | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def connect_bot(self, websocket: WebSocket):
        await websocket.accept()
        self.bot_connection = websocket

    def disconnect_bot(self):
        self.bot_connection = None

    async def connect_overlay(self, websocket: WebSocket, slot: str):
        await websocket.accept()
        if slot not in self.overlay_connections:
            self.overlay_connections[slot] = set()
        self.overlay_connections[slot].add(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from all subscriptions
        for conns in self.subscriptions.values():
            if websocket in conns:
                conns.remove(websocket)
        
        # Remove from overlays
        for conns in self.overlay_connections.values():
            if websocket in conns:
                conns.remove(websocket)

        if websocket == self.bot_connection:
            self.bot_connection = None

    async def subscribe(self, websocket: WebSocket, tournament_slug: str):
        if tournament_slug not in self.subscriptions:
            self.subscriptions[tournament_slug] = set()
        self.subscriptions[tournament_slug].add(websocket)

    async def broadcast(self, message: dict):
        """Broadcast to all connected clients."""
        payload = json.dumps(message)
        # Combine all unique active connections (hub + overlays)
        all_conns = set(self.active_connections)
        for conns in self.overlay_connections.values():
            all_conns.update(conns)
            
        if not all_conns:
            return
            
        await asyncio.gather(
            *[connection.send_text(payload) for connection in all_conns],
            return_exceptions=True
        )

    async def broadcast_to_tournament(self, tournament_slug: str, message: dict):
        """Broadcast only to clients subscribed to a specific tournament."""
        if tournament_slug not in self.subscriptions or not self.subscriptions[tournament_slug]:
            await self.broadcast(message)
            return

        payload = json.dumps(message)
        await asyncio.gather(
            *[connection.send_text(payload) for connection in self.subscriptions[tournament_slug]],
            return_exceptions=True
        )

    async def broadcast_to_slot(self, slot: str, message: dict):
        """Broadcast to specific overlay slot."""
        if slot not in self.overlay_connections or not self.overlay_connections[slot]:
            return

        payload = json.dumps(message)
        await asyncio.gather(
            *[connection.send_text(payload) for connection in self.overlay_connections[slot]],
            return_exceptions=True
        )

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))

# Global instance
manager = ConnectionManager()
