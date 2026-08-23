from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/track/{channel}")
async def track(websocket: WebSocket, channel: str):
    """
    channel = a delivery_id (donor/NGO watching one delivery) or "admin"
    (global live feed of every location update / status change).
    """
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; client doesn't need to send anything meaningful
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)
