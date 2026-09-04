"""Google Maps road-routing utilities."""

import math
import logging
import os
import requests
import time
from pathlib import Path
from typing import List, Tuple
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logger = logging.getLogger(__name__)
_route_cache = {}
_ROUTE_CACHE_SECONDS = 300


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(dlambda / 2) ** 2
    )

    return 2 * R * math.asin(math.sqrt(a))


def route_length_km(points: List[Tuple[float, float]]) -> float:
    return sum(
        haversine_km(
            *points[i],
            *points[i + 1]
        )
        for i in range(len(points) - 1)
    )


def road_metrics(start: Tuple[float, float], end: Tuple[float, float]) -> dict:
    """Return Google road distance/duration or an explicit unavailable state."""
    try:
        result = _google_routes_route(start, [{"id": "destination", "lat": end[0], "lng": end[1]}])
        minutes = result["legs"][0]["eta_minutes"] if result["legs"] else None
        return {"distance_km": result["total_distance_km"], "duration_minutes": minutes, "source": "google"}
    except Exception:
        return {"distance_km": None, "duration_minutes": None, "source": "unavailable"}


def _decode_polyline(encoded):
    points = []
    index = latitude = longitude = 0
    while index < len(encoded):
        result = shift = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        latitude += ~(result >> 1) if result & 1 else result >> 1
        result = shift = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        longitude += ~(result >> 1) if result & 1 else result >> 1
        points.append([latitude / 1e5, longitude / 1e5])
    return points


def _google_routes_route(start, stops):
    """Return road geometry and metrics for the supplied stop order."""

    if not stops:
        return {
            "order": [],
            "total_distance_km": 0.0,
            "legs": [],
            "polyline": [],
        }

    api_key = os.getenv("GOOGLE_MAPS_SERVER_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("Google Maps key is not configured")
    location = lambda point: {"location": {"latLng": {"latitude": point["lat"], "longitude": point["lng"]}}}
    payload = {
        "origin": {"location": {"latLng": {"latitude": start[0], "longitude": start[1]}}},
        "destination": location(stops[-1]),
        "intermediates": [location(stop) for stop in stops[:-1]],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "polylineQuality": "HIGH_QUALITY",
        "polylineEncoding": "ENCODED_POLYLINE",
    }
    cache_key = (round(start[0], 5), round(start[1], 5), tuple((round(stop["lat"], 5), round(stop["lng"], 5)) for stop in stops))
    cached = _route_cache.get(cache_key)
    if cached and time.monotonic() - cached["created"] < _ROUTE_CACHE_SECONDS:
        return cached["result"]
    response = requests.post(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key, "Referer": os.getenv("GOOGLE_MAPS_HTTP_REFERRER", "http://localhost:5173/"), "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.legs.distanceMeters,routes.legs.duration,routes.polyline.encodedPolyline"},
        json=payload,
        timeout=20,
    )
    if not response.ok:
        detail = response.text[:300].replace("\n", " ")
        logger.error("Google Routes provider error: status=%s detail=%s", response.status_code, detail)
        raise RuntimeError(f"Google Routes HTTP {response.status_code}: {detail}")
    data = response.json()
    if not data.get("routes"):
        raise RuntimeError("Google Routes returned no route")
    route = data["routes"][0]
    cumulative_minutes = 0.0
    legs = []
    for stop, leg in zip(stops, route.get("legs", [])):
        duration_seconds = float(str(leg.get("duration", "0s")).rstrip("s"))
        cumulative_minutes += duration_seconds / 60.0
        legs.append({
            "stop_id": stop["id"],
            "distance_km": round(leg.get("distanceMeters", 0.0) / 1000.0, 3),
            "eta_minutes": round(cumulative_minutes, 1),
        })
    encoded = route.get("polyline", {}).get("encodedPolyline", "")
    polyline = _decode_polyline(encoded)
    if len(polyline) < 2:
        raise RuntimeError("Google Routes returned no usable route geometry")
    result = {
        "order": [stop["id"] for stop in stops],
        "total_distance_km": round(route.get("distanceMeters", 0.0) / 1000.0, 3),
        "legs": legs,
        "polyline": polyline,
    }
    _route_cache[cache_key] = {"created": time.monotonic(), "result": result}
    return result


def solve_route(
    start: Tuple[float, float],
    stops: List[dict],
) -> dict:

    if not stops:
        return {
            "order": [],
            "total_distance_km": 0.0,
            "legs": [],
            "polyline": [],
        }

    try:
        return _google_routes_route(start, stops)
    except Exception as error:
        return {
            "order": [stop["id"] for stop in stops],
            "total_distance_km": 0.0,
            "legs": [],
            "polyline": [],
            "route_error": f"Road routing unavailable: {error}",
        }