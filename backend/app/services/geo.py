"""
Google Maps road-routing utilities.

Uses Google Routes API to calculate:
- actual road route
- road distance
- ETA
- optimized waypoint order
- road-following polyline

Falls back to the existing Haversine + nearest-neighbour route
if Google Routes API is unavailable.
"""

import math
import os
import requests
from typing import List, Tuple
from dotenv import load_dotenv

load_dotenv()


AVG_SPEED_KMPH = 25.0


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


def _google_waypoint(lat, lng):
    return {
        "location": {
            "latLng": {
                "latitude": lat,
                "longitude": lng,
            }
        }
    }


def _google_route(start, stops):
    """
    Calculate an actual driving route using Google Routes API.
    """

    api_key = os.getenv("GOOGLE_ROUTES_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GOOGLE_ROUTES_API_KEY is not configured."
        )

    if not stops:
        return {
            "order": [],
            "total_distance_km": 0.0,
            "legs": [],
            "polyline": [],
        }

    url = (
        "https://routes.googleapis.com/"
        "directions/v2:computeRoutes"
    )

    origin = _google_waypoint(
        start[0],
        start[1],
    )

    # Google Routes API requires a destination.
    # We use the last supplied stop as destination.
    destination = _google_waypoint(
        stops[-1]["lat"],
        stops[-1]["lng"],
    )

    intermediates = [
        _google_waypoint(
            stop["lat"],
            stop["lng"],
        )
        for stop in stops[:-1]
    ]

    body = {
        "origin": origin,
        "destination": destination,
        "intermediates": intermediates,
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "polylineQuality": "HIGH_QUALITY",
        "polylineEncoding": "GEO_JSON_LINESTRING",
        "optimizeWaypointOrder": True,
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "routes.distanceMeters,"
            "routes.duration,"
            "routes.polyline.geoJsonLinestring,"
            "routes.optimizedIntermediateWaypointIndex"
        ),
    }

    response = requests.post(
        url,
        json=body,
        headers=headers,
        timeout=20,
    )

    if not response.ok:
        raise RuntimeError(
            f"Google Routes API error "
            f"{response.status_code}: {response.text}"
        )

    data = response.json()

    routes = data.get("routes", [])

    if not routes:
        raise RuntimeError(
            "Google Routes API returned no routes."
        )

    route = routes[0]

    distance_meters = route.get(
        "distanceMeters",
        0,
    )

    duration_string = route.get(
        "duration",
        "0s",
    )

    duration_seconds = float(
        duration_string.rstrip("s")
    )

    optimized_indexes = route.get(
        "optimizedIntermediateWaypointIndex",
        [],
    )

    print("GOOGLE OPTIMIZED INDEXES:", optimized_indexes)

    # Original stop ordering:
    # intermediates + destination
    #
    # Example:
    # stops = [A, B, C]
    #
    # Google optimizes intermediates [A, B]
    # and destination C remains the final point.
    # Google returns indexes only for intermediate waypoints.
# Ignore invalid indexes such as -1.
        # Google returns indexes only for intermediate waypoints.
    # Ignore invalid indexes such as -1.
    valid_indexes = [
        i
        for i in optimized_indexes
        if 0 <= i < len(stops) - 1
    ]

    if valid_indexes:
        ordered_stops = [
            stops[i]
            for i in valid_indexes
        ]

        # Destination remains the final stop.
        ordered_stops.append(stops[-1])

    else:
        # If Google does not provide a usable optimization,
        # preserve the original stop order.
        ordered_stops = stops

    order = [
        stop["id"]
        for stop in ordered_stops
    ]

    legs = []

    # Google gives overall route duration/distance.
    # For individual stop ETA we calculate cumulative
    # distance between the ordered stops using the
    # road route's overall duration proportionally.
    #
    # The actual route itself comes from Google.
    cumulative_distance = 0.0

    points = [
        (start[0], start[1])
    ] + [
        (
            stop["lat"],
            stop["lng"],
        )
        for stop in ordered_stops
    ]

    segment_distances = []

    for i in range(len(points) - 1):
        segment = haversine_km(
            *points[i],
            *points[i + 1],
        )

        segment_distances.append(segment)
        cumulative_distance += segment

    total_google_km = distance_meters / 1000.0

    cumulative_haversine = 0.0
    cumulative_eta = 0.0

    for i, stop in enumerate(ordered_stops):

        cumulative_haversine += segment_distances[i]

        if cumulative_distance > 0:
            fraction = (
                cumulative_haversine
                / cumulative_distance
            )
        else:
            fraction = 0

        cumulative_eta = (
            duration_seconds
            * fraction
            / 60.0
        )

        legs.append({
            "stop_id": stop["id"],
            "distance_km": round(
                segment_distances[i],
                3,
            ),
            "eta_minutes": round(
                cumulative_eta,
                1,
            ),
        })

    # GeoJSON coordinates returned by Google
    # are [longitude, latitude].
    geojson = (
        route
        .get("polyline", {})
        .get("geoJsonLinestring", {})
    )

    coordinates = geojson.get(
        "coordinates",
        [],
    )

    # MapView expects [latitude, longitude].
    polyline = [
        [coord[1], coord[0]]
        for coord in coordinates
        if len(coord) >= 2
    ]

    return {
        "order": order,
        "total_distance_km": round(
            total_google_km,
            3,
        ),
        "legs": legs,
        "polyline": polyline,
    }


def _fallback_route(start, stops):
    """
    Fallback route if Google API cannot be reached.
    """

    if not stops:
        return {
            "order": [],
            "total_distance_km": 0.0,
            "legs": [],
            "polyline": [],
        }

    remaining = stops[:]

    route_ids = []

    route_points = [start]

    current = start

    while remaining:

        nxt = min(
            remaining,
            key=lambda s: haversine_km(
                *current,
                s["lat"],
                s["lng"],
            ),
        )

        route_ids.append(nxt["id"])

        route_points.append(
            (
                nxt["lat"],
                nxt["lng"],
            )
        )

        current = (
            nxt["lat"],
            nxt["lng"],
        )

        remaining.remove(nxt)

    legs = []

    cumulative_km = 0.0

    cumulative_min = 0.0

    for i in range(
        len(route_points) - 1
    ):

        distance = haversine_km(
            *route_points[i],
            *route_points[i + 1],
        )

        cumulative_km += distance

        cumulative_min += (
            distance
            / AVG_SPEED_KMPH
            * 60
        )

        legs.append({
            "stop_id": route_ids[i],
            "distance_km": round(
                distance,
                3,
            ),
            "eta_minutes": round(
                cumulative_min,
                1,
            ),
        })

    return {
        "order": route_ids,
        "total_distance_km": round(
            cumulative_km,
            3,
        ),
        "legs": legs,
        "polyline": [
            list(point)
            for point in route_points
        ],
    }


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
        print(
            "GOOGLE ROUTES: calculating "
            "real road route..."
        )

        result = _google_route(
            start,
            stops,
        )

        print(
            "GOOGLE ROUTES: "
            f"{result['total_distance_km']} km"
        )

        return result

    except Exception as error:

        print(
            "GOOGLE ROUTES FAILED: "
            f"{error}"
        )

        print(
            "FALLBACK: using "
            "straight-line routing."
        )

        return _fallback_route(
            start,
            stops,
        )