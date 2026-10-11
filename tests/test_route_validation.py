from __future__ import annotations

from models import RouteMeasurement, utc_now_iso
from route_validation import validate_fixed_endpoint_route, validate_round_trip


def m(a: str, b: str, d: float) -> RouteMeasurement:
    return RouteMeasurement(a, b, d, 1.0, "test", utc_now_iso(), "test", "")


def matrix():
    return {
        ("START", "A"): m("START", "A", 1),
        ("A", "B"): m("A", "B", 2),
        ("B", "START"): m("B", "START", 3),
        ("START", "B"): m("START", "B", 4),
        ("B", "A"): m("B", "A", 5),
        ("A", "START"): m("A", "START", 6),
    }


def test_valid_round_trip_passes():
    result = validate_round_trip(["START", "A", "B", "START"], "START", ["A", "B"], matrix(), 6)
    assert result.is_valid
    assert result.recalculated_total_km == 6


def test_missing_destination_fails():
    result = validate_round_trip(["START", "A", "START"], "START", ["A", "B"], matrix())
    assert not result.is_valid
    assert any("Missing destinations" in error for error in result.errors)


def test_duplicate_destination_fails():
    result = validate_round_trip(["START", "A", "A", "START"], "START", ["A", "B"], matrix())
    assert not result.is_valid
    assert any("Duplicate destinations" in error for error in result.errors)


def test_incorrect_start_fails():
    result = validate_round_trip(["A", "B", "START"], "START", ["A", "B"], matrix())
    assert not result.is_valid
    assert any("start" in error.lower() for error in result.errors)


def test_missing_distance_fails():
    result = validate_round_trip(["START", "B", "A", "START"], "START", ["A", "B"], {})
    assert not result.is_valid
    assert any("Missing or invalid distance" in error for error in result.errors)


def test_total_mismatch_fails():
    result = validate_round_trip(["START", "A", "B", "START"], "START", ["A", "B"], matrix(), 99)
    assert not result.is_valid
    assert any("Reported total" in error for error in result.errors)


def test_fixed_endpoint_route_passes():
    route_matrix = matrix()
    route_matrix[("B", "END")] = m("B", "END", 3)
    result = validate_fixed_endpoint_route(["START", "A", "B", "END"], "START", "END", ["A", "B"], route_matrix, 6)
    assert result.is_valid


def test_fixed_endpoint_route_wrong_end_fails():
    result = validate_fixed_endpoint_route(["START", "A", "B", "START"], "START", "END", ["A", "B"], matrix())
    assert not result.is_valid
    assert any("end" in error.lower() for error in result.errors)
