"""
Simulates real-time volunteer GPS movement along the planned route.

In a real deployment this would be replaced by the volunteer's phone
periodically POSTing its actual GPS coordinates (see
routers/volunteer.py `POST /location`) — the broadcast/DB-update path is
identical either way, so swapping in real GPS is a no-op for the rest of
the system. This simulator exists so the live-tracking map is genuinely
demoable without needing a physical device in the loop.
"""
import asyncio
from datetime import datetime

from app.db import SessionLocal
from app.models_db import Delivery, DeliveryStop, User, LocationPing, DeliveryStatus
from app.services.geo import haversine_km
from app.services.ws_manager import manager

STEP_SECONDS = 2.0
SPEED_KMPH = 25.0


async def run_delivery_simulation(delivery_id: str):
    while True:
        await asyncio.sleep(STEP_SECONDS)
        db = SessionLocal()
        try:
            delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
            if not delivery or delivery.status != DeliveryStatus.en_route:
                return
            volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first()
            pending_stops = sorted(
                [s for s in delivery.stops if s.status != "completed"],
                key=lambda s: s.sequence,
            )
            if not pending_stops:
                delivery.status = DeliveryStatus.completed
                delivery.completed_at = datetime.utcnow()
                db.add(delivery)
                db.commit()
                await manager.broadcast(delivery_id, {"type": "delivery_completed"})
                await manager.broadcast("admin", {"type": "delivery_completed", "delivery_id": delivery_id})
                return

            target = pending_stops[0]
            dist_km = haversine_km(volunteer.lat, volunteer.lng, target.lat, target.lng)
            step_km = SPEED_KMPH * (STEP_SECONDS / 3600.0)

            if dist_km <= step_km:
                volunteer.lat, volunteer.lng = target.lat, target.lng
                target.status = "completed"
                target.arrived_at = datetime.utcnow()
                db.add(target)
                event = {"type": "stop_arrived", "stop_id": target.id, "stop_type": target.stop_type}
            else:
                frac = step_km / dist_km
                volunteer.lat += (target.lat - volunteer.lat) * frac
                volunteer.lng += (target.lng - volunteer.lng) * frac
                event = {"type": "location_update"}

            db.add(volunteer)
            ping = LocationPing(volunteer_id=volunteer.id, delivery_id=delivery.id,
                                lat=volunteer.lat, lng=volunteer.lng)
            db.add(ping)
            db.commit()

            payload = {
                **event,
                "delivery_id": delivery_id,
                "volunteer_id": volunteer.id,
                "lat": volunteer.lat,
                "lng": volunteer.lng,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await manager.broadcast(delivery_id, payload)
            await manager.broadcast("admin", payload)
        finally:
            db.close()


def launch_simulation(delivery_id: str):
    asyncio.create_task(run_delivery_simulation(delivery_id))
