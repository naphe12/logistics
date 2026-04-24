import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ShipmentTrackingHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, shipment_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[shipment_id].add(websocket)

    async def disconnect(self, shipment_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(shipment_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(shipment_id, None)

    async def broadcast(self, shipment_id: str, payload: dict) -> None:
        async with self._lock:
            sockets = list(self._connections.get(shipment_id, set()))

        stale: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)

        if stale:
            async with self._lock:
                current = self._connections.get(shipment_id, set())
                for ws in stale:
                    current.discard(ws)
                if not current:
                    self._connections.pop(shipment_id, None)


tracking_hub = ShipmentTrackingHub()

