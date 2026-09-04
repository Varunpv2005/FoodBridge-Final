from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from fastapi import HTTPException

from app.services.deviation import (
    deviation_event_allowed,
    distance_to_route_meters,
    is_route_deviated,
)
from app.services.geo import _google_routes_route
from app.services.ws_manager import ConnectionManager
from app.auth import create_access_token, get_user_from_token


ROUTE = [[12.3052, 76.6552], [12.3052, 76.6562], [12.3052, 76.6572]]


class RouteDeviationTests(unittest.TestCase):
    def test_only_current_session_token_is_valid(self):
        user = SimpleNamespace(id="user-1", current_session_id="session-2")

        class Query:
            def filter(self, *args):
                return self

            def first(self):
                return user

        db = SimpleNamespace(query=lambda model: Query())
        old_token = create_access_token({"sub": user.id, "role": "donor"}, "session-1")
        current_token = create_access_token({"sub": user.id, "role": "donor"}, user.current_session_id)

        with self.assertRaises(HTTPException) as error:
            get_user_from_token(old_token, db)
        self.assertEqual(error.exception.status_code, 401)
        self.assertIs(get_user_from_token(current_token, db), user)

    def test_position_within_route_has_no_deviation(self):
        self.assertFalse(is_route_deviated([12.3052, 76.6565], ROUTE))


    def test_position_outside_threshold_is_deviation(self):
        self.assertGreater(distance_to_route_meters([12.3070, 76.6565], ROUTE), 125)
        self.assertTrue(is_route_deviated([12.3070, 76.6565], ROUTE))


    def test_deviation_event_is_throttled(self):
        now = datetime.utcnow()
        self.assertFalse(deviation_event_allowed(True, now - timedelta(seconds=30), now))
        self.assertTrue(deviation_event_allowed(True, now - timedelta(seconds=60), now))
        self.assertTrue(deviation_event_allowed(False, now, now))


    def test_google_route_recalculation_returns_multistop_metrics(self):
        response = SimpleNamespace(
            ok=True,
            json=lambda: {
                "routes": [{
                    "distanceMeters": 4200,
                    "legs": [{"distanceMeters": 2100, "duration": "300s"}, {"distanceMeters": 2100, "duration": "360s"}],
                    "polyline": {"encodedPolyline": "_cpjAypzrM?gEgE"},
                }],
            },
        )
        import os
        from unittest.mock import patch
        os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"
        with patch("app.services.geo.requests.post", lambda *args, **kwargs: response), patch("app.services.geo._decode_polyline", return_value=[[12.3052, 76.6552], [12.3070, 76.6570]]):
            result = _google_routes_route((12.3052, 76.6552), [
        {"id": "stop-1", "lat": 12.3060, "lng": 76.6560},
        {"id": "stop-2", "lat": 12.3070, "lng": 76.6570},
            ])
        self.assertEqual(result["total_distance_km"], 4.2)
        self.assertEqual([leg["eta_minutes"] for leg in result["legs"]], [5.0, 11.0])
        self.assertEqual(len(result["polyline"]), 2)


    def test_google_route_failure_is_explicit(self):
        response = SimpleNamespace(ok=False, status_code=403, text="permission denied")
        import os
        from unittest.mock import patch
        os.environ["GOOGLE_MAPS_API_KEY"] = "test-key"
        with patch("app.services.geo.requests.post", lambda *args, **kwargs: response):
            with self.assertRaisesRegex(RuntimeError, "Google Routes HTTP 403"):
                _google_routes_route((12.3052, 76.6552), [{"id": "stop-1", "lat": 12.3060, "lng": 76.6560}])

    def test_websocket_route_deviation_event_is_delivered(self):
        manager = ConnectionManager()
        socket = SimpleNamespace(send_text=AsyncMock())
        manager.channels["admin"] = [socket]
        import asyncio
        event = {"type": "route_deviation", "delivery_id": "delivery-1", "distance_from_route_meters": 180.0}
        asyncio.run(manager.broadcast("admin", event))
        socket.send_text.assert_awaited_once()
        self.assertIn('"type": "route_deviation"', socket.send_text.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
