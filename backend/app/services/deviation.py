import math
from datetime import datetime
from typing import Iterable, Sequence

ROUTE_DEVIATION_THRESHOLD_METERS = 125.0
ROUTE_DEVIATION_COOLDOWN_SECONDS = 60


def _projected_point(latitude: float, longitude: float, origin_latitude: float):
    scale = 111320.0
    return longitude * scale * math.cos(math.radians(origin_latitude)), latitude * scale


def point_to_segment_distance_meters(point: Sequence[float], start: Sequence[float], end: Sequence[float]) -> float:
    origin_latitude = (float(start[0]) + float(end[0]) + float(point[0])) / 3.0
    px, py = _projected_point(float(point[0]), float(point[1]), origin_latitude)
    ax, ay = _projected_point(float(start[0]), float(start[1]), origin_latitude)
    bx, by = _projected_point(float(end[0]), float(end[1]), origin_latitude)
    dx, dy = bx - ax, by - ay
    segment_length_squared = dx * dx + dy * dy
    if segment_length_squared == 0:
        return math.hypot(px - ax, py - ay)
    projection = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / segment_length_squared))
    return math.hypot(px - (ax + projection * dx), py - (ay + projection * dy))


def distance_to_route_meters(position: Sequence[float], route: Iterable[Sequence[float]]) -> float | None:
    points = list(route or [])
    if not position or len(position) < 2 or len(points) < 2:
        return None
    distances = [point_to_segment_distance_meters(position, points[index], points[index + 1]) for index in range(len(points) - 1)]
    return min(distances) if distances else None


def is_route_deviated(position: Sequence[float], route: Iterable[Sequence[float]], threshold_meters: float = ROUTE_DEVIATION_THRESHOLD_METERS) -> bool:
    distance = distance_to_route_meters(position, route)
    return distance is not None and distance > threshold_meters


def deviation_event_allowed(currently_deviated: bool, last_event: datetime | None, now: datetime, cooldown_seconds: float = ROUTE_DEVIATION_COOLDOWN_SECONDS) -> bool:
    return not currently_deviated or last_event is None or (now - last_event).total_seconds() >= cooldown_seconds