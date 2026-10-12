from __future__ import annotations

from models import GAResult, Location, RouteMeasurement
from route_validation import ValidationResult


def google_maps_url(location: Location) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={location.latitude:.6f},{location.longitude:.6f}"


def build_vertex_table(start: Location, destinations: list[Location]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, location in enumerate([start] + destinations):
        rows.append(
            {
                "vertex_label": f"V{index}",
                "location_id": location.location_id,
                "location_name": location.location_name,
                "role": "start_and_return" if index == 0 else "required_destination",
                "address_or_area": location.address_or_area,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "category": location.category,
                "source_name": location.source_name,
                "source_url": location.source_url,
                "google_maps_url": google_maps_url(location),
                "verification_status": location.verification_status,
            }
        )
    return rows


def build_directed_edge_table(
    nodes: list[Location],
    matrix: dict[tuple[str, str], RouteMeasurement],
) -> list[dict[str, object]]:
    by_id = {location.location_id: location for location in nodes}
    rows: list[dict[str, object]] = []
    for from_id in by_id:
        for to_id in by_id:
            if from_id == to_id:
                continue
            measurement = matrix.get((from_id, to_id))
            if measurement is None:
                rows.append(
                    {
                        "from_location_id": from_id,
                        "to_location_id": to_id,
                        "distance_km": None,
                        "duration_minutes": None,
                        "directed": True,
                        "travel_mode": "",
                        "data_source": "missing",
                        "is_assumed": "",
                        "notes": "No measurement available",
                    }
                )
                continue
            rows.append(
                {
                    "from_location_id": from_id,
                    "to_location_id": to_id,
                    "distance_km": measurement.distance_km,
                    "duration_minutes": measurement.duration_minutes,
                    "directed": True,
                    "travel_mode": measurement.travel_mode,
                    "data_source": measurement.source_name,
                    "source_url": measurement.source_url,
                    "measurement_date": measurement.measurement_date,
                    "is_assumed": measurement.is_assumed,
                    "from_cache": measurement.from_cache,
                    "notes": measurement.notes,
                }
            )
    return rows


def build_weight_matrix_table(
    nodes: list[Location],
    matrix: dict[tuple[str, str], RouteMeasurement],
) -> list[dict[str, object]]:
    node_ids = [location.location_id for location in nodes]
    rows: list[dict[str, object]] = []
    for from_id in node_ids:
        row: dict[str, object] = {"from_to_km": from_id}
        for to_id in node_ids:
            if from_id == to_id:
                row[to_id] = 0.0
            else:
                measurement = matrix.get((from_id, to_id))
                row[to_id] = None if measurement is None else round(measurement.distance_km, 6)
        rows.append(row)
    return rows


def build_route_edge_check(
    route: list[str],
    matrix: dict[tuple[str, str], RouteMeasurement],
) -> tuple[list[dict[str, object]], float]:
    rows: list[dict[str, object]] = []
    total = 0.0
    for step, (from_id, to_id) in enumerate(zip(route, route[1:]), start=1):
        measurement = matrix[(from_id, to_id)]
        total += measurement.distance_km
        rows.append(
            {
                "step": step,
                "from_location_id": from_id,
                "to_location_id": to_id,
                "distance_km": measurement.distance_km,
                "duration_minutes": measurement.duration_minutes,
                "running_total_km": total,
                "source_name": measurement.source_name,
                "is_assumed": measurement.is_assumed,
            }
        )
    return rows, total


def build_assignment_evidence_markdown(
    start: Location,
    destinations: list[Location],
    result: GAResult,
    validation: ValidationResult,
    baseline: tuple[list[str], float],
    exact: tuple[list[str], float] | None,
    route_total_check_km: float,
) -> str:
    exact_text = "not computed because the selected instance is above the configured brute-force limit"
    if exact is not None:
        exact_text = f"{exact[1]:.3f} km for route {' -> '.join(exact[0])}"
    validity = "PASS" if validation.is_valid else "FAIL: " + "; ".join(validation.errors)
    destination_list = "\n".join(
        f"- {location.location_id}: {location.location_name} ({location.address_or_area})"
        for location in destinations
    )
    return f"""# TSP Assignment Evidence

## Problem And Objective

Application: closed-tour route planning in Cagayan de Oro City using real source-reported map locations.

Starting location: {start.location_name} (`START`), {start.address_or_area}.

Required destinations:

{destination_list}

Objective: minimize total road distance in kilometers.

## Graph Model

The graph is a complete directed weighted graph over the selected start and destination vertices. Directed edges represent OSRM-compatible driving routes from one vertex to another. Edge weights are road distances in kilometers. Direction is used because road networks can contain one-way streets and turn restrictions, so A-to-B can differ from B-to-A.

Location data source: OpenStreetMap-derived discovery or user-selected coordinates. Google Maps URLs are included in the vertex export for map verification. Routing weights come from the configured OSRM-compatible service or the local routing cache.

## Genetic Algorithm Representation

Chromosome: a permutation of destination IDs only.

Fitness: `START -> chromosome destinations -> START` total distance.

Operators: random initial population, tournament selection, order crossover, swap mutation, elitism, and fixed-generation termination.

Optimality statement: the Genetic Algorithm is an approximate method. It does not prove global optimality. The brute-force reference is only computed for small instances.

## Result

Best-found route: {' -> '.join(result.best_route)}

Best-found distance: {result.best_distance:.3f} km

Independent recalculation from route edges: {route_total_check_km:.3f} km

Nearest-neighbor baseline: {baseline[1]:.3f} km for route {' -> '.join(baseline[0])}

Exact reference: {exact_text}

Validation: {validity}

## Limitations

OpenStreetMap places are source-reported and should be reviewed before field use. Public routing services can be rate-limited or unavailable. The GA result can vary with parameters and random seed, and should be described as best-found unless an exact reference is available for the same instance.
"""
