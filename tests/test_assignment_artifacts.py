from __future__ import annotations

from assignment_artifacts import build_route_edge_check, build_vertex_table, build_weight_matrix_table
from models import Location, RouteMeasurement, utc_now_iso


def m(a: str, b: str, d: float) -> RouteMeasurement:
    return RouteMeasurement(a, b, d, 1.0, "driving", utc_now_iso(), "test", "")


def test_vertex_table_labels_start_and_destinations():
    start = Location("START", "Start", "Area", 8.1, 124.1, "manual")
    destinations = [Location("A", "A", "Area", 8.2, 124.2, "osm")]

    rows = build_vertex_table(start, destinations)

    assert rows[0]["vertex_label"] == "V0"
    assert rows[0]["role"] == "start_and_return"
    assert rows[1]["role"] == "required_destination"
    assert "google.com/maps" in rows[1]["google_maps_url"]


def test_weight_matrix_uses_zero_diagonal_and_directed_weights():
    nodes = [
        Location("START", "Start", "", 8.1, 124.1),
        Location("A", "A", "", 8.2, 124.2),
    ]
    matrix = {
        ("START", "A"): m("START", "A", 2.5),
        ("A", "START"): m("A", "START", 3.5),
    }

    rows = build_weight_matrix_table(nodes, matrix)

    assert rows[0]["START"] == 0.0
    assert rows[0]["A"] == 2.5
    assert rows[1]["START"] == 3.5


def test_route_edge_check_recalculates_total():
    matrix = {
        ("START", "A"): m("START", "A", 2.0),
        ("A", "START"): m("A", "START", 3.0),
    }

    rows, total = build_route_edge_check(["START", "A", "START"], matrix)

    assert total == 5.0
    assert rows[-1]["running_total_km"] == 5.0
