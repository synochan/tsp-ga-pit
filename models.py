from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Location:
    location_id: str
    location_name: str
    address_or_area: str
    latitude: float
    longitude: float
    source_name: str = ""
    source_url: str = ""
    verified_date: str = ""
    category: str = ""
    verification_status: str = "unverified"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RouteMeasurement:
    from_location_id: str
    to_location_id: str
    distance_km: float
    duration_minutes: float | None
    travel_mode: str
    measurement_date: str
    source_name: str
    source_url: str
    is_assumed: bool = False
    notes: str = ""
    from_cache: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GAParameters:
    population_size: int = 100
    generations: int = 300
    crossover_probability: float = 0.85
    mutation_probability: float = 0.10
    tournament_size: int = 3
    elitism_count: int = 2
    random_seed: int | None = 42


@dataclass(frozen=True)
class GAResult:
    best_route: list[str]
    best_distance: float
    history: list[float]
    generations_run: int
    runtime_seconds: float
    parameters: GAParameters


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
