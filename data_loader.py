from __future__ import annotations

import csv
import math
from pathlib import Path

import pandas as pd

from models import Location, RouteMeasurement


LOCATION_COLUMNS = [
    "location_id",
    "location_name",
    "address_or_area",
    "latitude",
    "longitude",
    "source_name",
    "source_url",
    "verified_date",
]

DISTANCE_COLUMNS = [
    "from_location_id",
    "to_location_id",
    "distance_km",
    "duration_minutes",
    "travel_mode",
    "measurement_date",
    "source_name",
    "source_url",
    "is_assumed",
    "notes",
]


class DataValidationError(ValueError):
    pass


def _finite_float(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DataValidationError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise DataValidationError(f"{field} must be finite")
    return number


def validate_coordinate(lat: object, lon: object) -> tuple[float, float]:
    latitude = _finite_float(lat, "latitude")
    longitude = _finite_float(lon, "longitude")
    if not -90 <= latitude <= 90:
        raise DataValidationError("latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise DataValidationError("longitude must be between -180 and 180")
    return latitude, longitude


def load_locations_csv(path: str | Path) -> list[Location]:
    df = pd.read_csv(path, dtype=str).fillna("")
    missing = [column for column in LOCATION_COLUMNS[:5] if column not in df.columns]
    if missing:
        raise DataValidationError(f"Missing location columns: {', '.join(missing)}")
    if df["location_id"].duplicated().any():
        raise DataValidationError("Duplicate location_id values are not allowed")

    locations: list[Location] = []
    for row in df.to_dict("records"):
        lat, lon = validate_coordinate(row["latitude"], row["longitude"])
        locations.append(
            Location(
                location_id=row["location_id"].strip(),
                location_name=row["location_name"].strip(),
                address_or_area=row.get("address_or_area", "").strip(),
                latitude=lat,
                longitude=lon,
                source_name=row.get("source_name", "").strip(),
                source_url=row.get("source_url", "").strip(),
                verified_date=row.get("verified_date", "").strip(),
                category=row.get("category", "").strip(),
                verification_status=row.get("verification_status", "unverified").strip() or "unverified",
            )
        )
    return locations


def save_locations_csv(locations: list[Location], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    columns = LOCATION_COLUMNS + ["category", "verification_status"]
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for location in locations:
            writer.writerow({column: location.as_dict().get(column, "") for column in columns})


def load_distance_matrix_csv(path: str | Path) -> dict[tuple[str, str], RouteMeasurement]:
    df = pd.read_csv(path, dtype=str).fillna("")
    missing = [column for column in DISTANCE_COLUMNS[:3] if column not in df.columns]
    if missing:
        raise DataValidationError(f"Missing distance columns: {', '.join(missing)}")

    matrix: dict[tuple[str, str], RouteMeasurement] = {}
    for row in df.to_dict("records"):
        distance = _finite_float(row["distance_km"], "distance_km")
        if distance < 0:
            raise DataValidationError("distance_km must not be negative")
        duration = None
        if row.get("duration_minutes", "") != "":
            duration = _finite_float(row["duration_minutes"], "duration_minutes")
            if duration < 0:
                raise DataValidationError("duration_minutes must not be negative")
        measurement = RouteMeasurement(
            from_location_id=row["from_location_id"].strip(),
            to_location_id=row["to_location_id"].strip(),
            distance_km=distance,
            duration_minutes=duration,
            travel_mode=row.get("travel_mode", "driving"),
            measurement_date=row.get("measurement_date", ""),
            source_name=row.get("source_name", ""),
            source_url=row.get("source_url", ""),
            is_assumed=str(row.get("is_assumed", "")).lower() in {"true", "1", "yes"},
            notes=row.get("notes", ""),
        )
        matrix[(measurement.from_location_id, measurement.to_location_id)] = measurement
    return matrix


def save_distance_matrix_csv(matrix: dict[tuple[str, str], RouteMeasurement], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=DISTANCE_COLUMNS + ["from_cache"])
        writer.writeheader()
        for measurement in matrix.values():
            writer.writerow(measurement.as_dict())
