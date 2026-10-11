from __future__ import annotations

import math
from dataclasses import dataclass, field

from models import RouteMeasurement


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    recalculated_total_km: float | None = None


def recalculate_route_distance(route: list[str], matrix: dict[tuple[str, str], RouteMeasurement]) -> float:
    total = 0.0
    for from_id, to_id in zip(route, route[1:]):
        measurement = matrix.get((from_id, to_id))
        if measurement is None or not math.isfinite(measurement.distance_km) or measurement.distance_km < 0:
            raise ValueError(f"Missing or invalid distance for {from_id} -> {to_id}")
        total += measurement.distance_km
    return total


def validate_round_trip(
    route: list[str],
    start_id: str,
    required_destination_ids: list[str],
    matrix: dict[tuple[str, str], RouteMeasurement],
    reported_total_km: float | None = None,
    tolerance_km: float = 1e-6,
) -> ValidationResult:
    errors: list[str] = []
    if len(route) < 3:
        errors.append("Route must contain a start, at least one destination, and return to start.")
    if not route or route[0] != start_id:
        errors.append("Route does not start at the selected start.")
    if not route or route[-1] != start_id:
        errors.append("Route does not return to the selected start.")

    middle = route[1:-1]
    required = set(required_destination_ids)
    if set(middle) != required:
        missing = sorted(required - set(middle))
        extra = sorted(set(middle) - required)
        if missing:
            errors.append(f"Missing destinations: {', '.join(missing)}")
        if extra:
            errors.append(f"Unselected destinations in route: {', '.join(extra)}")
    duplicates = sorted({location_id for location_id in middle if middle.count(location_id) > 1})
    if duplicates:
        errors.append(f"Duplicate destinations: {', '.join(duplicates)}")

    recalculated_total = None
    try:
        recalculated_total = recalculate_route_distance(route, matrix)
    except ValueError as exc:
        errors.append(str(exc))

    if reported_total_km is not None and recalculated_total is not None:
        if not math.isfinite(reported_total_km) or abs(reported_total_km - recalculated_total) > tolerance_km:
            errors.append("Reported total does not match independent recalculation.")

    return ValidationResult(not errors, errors, recalculated_total)


def validate_fixed_endpoint_route(
    route: list[str],
    start_id: str,
    end_id: str,
    required_destination_ids: list[str],
    matrix: dict[tuple[str, str], RouteMeasurement],
    reported_total_km: float | None = None,
    tolerance_km: float = 1e-6,
) -> ValidationResult:
    errors: list[str] = []
    if len(route) < 2:
        errors.append("Route must contain a start and an end.")
    if not route or route[0] != start_id:
        errors.append("Route does not start at the selected start.")
    if not route or route[-1] != end_id:
        errors.append("Route does not end at the selected end.")

    middle = route[1:-1]
    required = set(required_destination_ids)
    if start_id in middle:
        errors.append("Start appears in the middle of the route.")
    if end_id in middle:
        errors.append("End appears in the middle of the route.")
    if set(middle) != required:
        missing = sorted(required - set(middle))
        extra = sorted(set(middle) - required)
        if missing:
            errors.append(f"Missing destinations: {', '.join(missing)}")
        if extra:
            errors.append(f"Unselected destinations in route: {', '.join(extra)}")
    duplicates = sorted({location_id for location_id in middle if middle.count(location_id) > 1})
    if duplicates:
        errors.append(f"Duplicate destinations: {', '.join(duplicates)}")

    recalculated_total = None
    try:
        recalculated_total = recalculate_route_distance(route, matrix)
    except ValueError as exc:
        errors.append(str(exc))

    if reported_total_km is not None and recalculated_total is not None:
        if not math.isfinite(reported_total_km) or abs(reported_total_km - recalculated_total) > tolerance_km:
            errors.append("Reported total does not match independent recalculation.")

    return ValidationResult(not errors, errors, recalculated_total)
