import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.auth import get_user_from_token
from app.db import SessionLocal
from app.models_db import Delivery, Donation, DeliveryStop
from app.schemas_v2 import LocationUpdate
from app.routers.volunteer_router import record_location
from app.services.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/track/{channel}")
async def track(websocket: WebSocket, channel: str):
    """
    channel = a delivery_id (donor/NGO watching one delivery) or "admin"
    (global live feed of every location update / status change).
    """
    token = websocket.query_params.get("token")
    db: Session = SessionLocal()
    try:
        if not token:
            await websocket.close(code=1008)
            return
        user = get_user_from_token(token, db)

        if channel == "admin":
            allowed = user.role.value == "admin"
        elif channel.startswith("donor:"):
            allowed = user.role.value == "donor" and channel == f"donor:{user.id}"
        elif channel.startswith("ngo:"):
            allowed = user.role.value == "ngo" and channel == f"ngo:{user.id}"
        elif channel.startswith("volunteer:"):
            allowed = user.role.value == "volunteer" and channel == f"volunteer:{user.id}"
        else:
            delivery = db.query(Delivery).filter(Delivery.id == channel).first()
            allowed = bool(delivery and (
                delivery.volunteer_id == user.id or
                db.query(DeliveryStop).filter(
                    DeliveryStop.delivery_id == delivery.id,
                    DeliveryStop.ngo_id == user.id,
                ).first() or
                db.query(Donation).join(DeliveryStop, Donation.id == DeliveryStop.donation_id).filter(
                    DeliveryStop.delivery_id == delivery.id,
                    Donation.donor_id == user.id,
                ).first()
            ))

        if not allowed:
            await websocket.close(code=1008)
            return

        await manager.connect(channel, websocket)
    except Exception:
        await websocket.close(code=1008)
        return
    finally:
        db.close()

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=30)
            except asyncio.TimeoutError:
                db = SessionLocal()
                try:
                    get_user_from_token(token, db)
                finally:
                    db.close()
                continue
            if message.get("type") != "location_update":
                continue
            if (user.role.value != "volunteer" or not channel
                    or channel.startswith(("admin", "donor:", "ngo:", "volunteer:"))
                    or message.get("delivery_id") != channel
                    or message.get("volunteer_id") not in (None, user.id)):
                continue
            payload = LocationUpdate.parse_obj(message)
            db = SessionLocal()
            try:
                await record_location(db, user, payload, channel)
            finally:
                db.close()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)
