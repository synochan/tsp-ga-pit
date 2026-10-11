from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / ".cache"


@dataclass(frozen=True)
class StudyArea:
    name: str = "Cagayan de Oro City, Philippines"
    min_lat: float = 8.35
    max_lat: float = 8.55
    min_lon: float = 124.55
    max_lon: float = 124.75
    center_lat: float = 8.475
    center_lon: float = 124.645
    default_zoom: int = 13

    def contains(self, lat: float, lon: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon


@dataclass(frozen=True)
class RoutingSettings:
    provider_name: str = "OSRM demo server"
    base_url: str = "https://router.project-osrm.org"
    profile: str = "driving"
    timeout_seconds: float = 15.0
    retry_count: int = 2
    request_delay_seconds: float = 1.0
    cache_ttl_days: int = 30


@dataclass(frozen=True)
class DiscoverySettings:
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_fallback_urls: tuple[str, ...] = (
        "https://lz4.overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.osm.jp/api/interpreter",
    )
    nominatim_url: str = "https://nominatim.openstreetmap.org/search"
    user_agent: str = "carmen-tsp-ga-student-project/1.0"
    timeout_seconds: float = 10.0
    request_delay_seconds: float = 1.0
    max_results: int = 12


DEFAULT_STUDY_AREA = StudyArea()
DEFAULT_ROUTING = RoutingSettings()
DEFAULT_DISCOVERY = DiscoverySettings()


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
