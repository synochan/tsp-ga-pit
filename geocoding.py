from __future__ import annotations

import time
from typing import Any

import requests

from config import DiscoverySettings, StudyArea
from data_loader import validate_coordinate
from models import Location


class GeocodingError(RuntimeError):
    pass


NOMINATIM_CATEGORY_QUERIES = {
    "pharmacies": ["pharmacy Cagayan de Oro Philippines"],
    "schools": ["school Cagayan de Oro Philippines"],
    "groceries": ["supermarket Cagayan de Oro Philippines", "grocery Cagayan de Oro Philippines"],
    "markets": ["public market Cagayan de Oro Philippines"],
    "hospitals_clinics": ["hospital Cagayan de Oro Philippines", "clinic Cagayan de Oro Philippines"],
    "government": ["government office Cagayan de Oro Philippines", "post office Cagayan de Oro Philippines"],
    "courier": ["courier Cagayan de Oro Philippines", "LBC Cagayan de Oro Philippines"],
    "shopping": ["shopping mall Cagayan de Oro Philippines"],
}


class NominatimGeocoder:
    def __init__(self, settings: DiscoverySettings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def search(self, query: str, limit: int = 5) -> list[Location]:
        if not query.strip():
            return []
        params = {"q": query, "format": "jsonv2", "addressdetails": "1", "limit": str(limit)}
        headers = {"User-Agent": self.settings.user_agent}
        try:
            response = self.session.get(self.settings.nominatim_url, params=params, headers=headers, timeout=self.settings.timeout_seconds)
        except requests.RequestException as exc:
            raise GeocodingError(str(exc)) from exc
        if response.status_code == 429:
            raise GeocodingError("Nominatim rate limit was reached.")
        if response.status_code >= 400:
            raise GeocodingError(f"Nominatim returned HTTP {response.status_code}")
        data: list[dict[str, Any]] = response.json()
        results: list[Location] = []
        for item in data:
            lat, lon = validate_coordinate(item.get("lat"), item.get("lon"))
            osm_type = item.get("osm_type", "place")
            osm_id = item.get("osm_id", len(results))
            results.append(
                Location(
                    location_id=f"geocode_{osm_type}_{osm_id}",
                    location_name=item.get("name") or item.get("display_name", "Geocoded result").split(",")[0],
                    address_or_area=item.get("display_name", ""),
                    latitude=lat,
                    longitude=lon,
                    source_name="OpenStreetMap Nominatim",
                    source_url="https://nominatim.openstreetmap.org/",
                    verification_status="source-reported",
                )
            )
        time.sleep(self.settings.request_delay_seconds)
        return results


def deduplicate_locations(locations: list[Location], threshold_degrees: float = 0.00003) -> list[Location]:
    kept: list[Location] = []
    for location in locations:
        duplicate = False
        for existing in kept:
            close = abs(location.latitude - existing.latitude) <= threshold_degrees and abs(location.longitude - existing.longitude) <= threshold_degrees
            same_name = location.location_name.strip().lower() == existing.location_name.strip().lower()
            if close and same_name:
                duplicate = True
                break
        if not duplicate:
            kept.append(location)
    return kept


def discover_places_by_category(
    settings: DiscoverySettings,
    study_area: StudyArea,
    categories: list[str],
    max_results: int,
) -> tuple[list[Location], list[str]]:
    geocoder = NominatimGeocoder(settings)
    accepted: list[Location] = []
    warnings: list[str] = []
    query_count = 0
    for category in categories or ["pharmacies", "schools", "groceries"]:
        for query in NOMINATIM_CATEGORY_QUERIES.get(category, []):
            if len(accepted) >= max_results or query_count >= 8:
                break
            query_count += 1
            try:
                matches = geocoder.search(query, limit=min(10, max_results))
            except GeocodingError as exc:
                warnings.append(f"{query}: {exc}")
                continue
            for match in matches:
                if not study_area.contains(match.latitude, match.longitude):
                    continue
                accepted.append(
                    Location(
                        location_id=f"nominatim_{match.location_id}",
                        location_name=match.location_name,
                        address_or_area=match.address_or_area,
                        latitude=match.latitude,
                        longitude=match.longitude,
                        source_name=match.source_name,
                        source_url=match.source_url,
                        verification_status="source-reported",
                        category=category,
                    )
                )
            accepted = deduplicate_locations(accepted)
        if len(accepted) >= max_results or query_count >= 8:
            break
    return accepted[:max_results], warnings
