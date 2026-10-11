from __future__ import annotations

import re
import time
from typing import Any

import requests

from config import DiscoverySettings
from data_loader import validate_coordinate
from models import Location, utc_now_iso


CATEGORY_FILTERS = {
    "pharmacies": [('amenity', 'pharmacy'), ('shop', 'chemist')],
    "schools": [('amenity', 'school'), ('amenity', 'college'), ('amenity', 'university')],
    "groceries": [('shop', 'supermarket'), ('shop', 'grocery'), ('shop', 'convenience')],
    "markets": [('amenity', 'marketplace')],
    "hospitals_clinics": [('amenity', 'hospital'), ('amenity', 'clinic'), ('amenity', 'doctors')],
    "government": [('office', 'government'), ('amenity', 'townhall'), ('amenity', 'post_office')],
    "courier": [('office', 'courier'), ('shop', 'copyshop')],
    "shopping": [('shop', 'mall'), ('amenity', 'marketplace')],
}


class DiscoveryError(RuntimeError):
    pass


def _safe_id(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")[:80]


class OverpassDiscoveryClient:
    def __init__(self, settings: DiscoverySettings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def discover(self, lat: float, lon: float, radius_m: int, categories: list[str], max_results: int | None = None) -> list[Location]:
        validate_coordinate(lat, lon)
        filters = []
        for category in categories:
            filters.extend(CATEGORY_FILTERS.get(category, []))
        if not filters:
            filters = CATEGORY_FILTERS["pharmacies"] + CATEGORY_FILTERS["schools"] + CATEGORY_FILTERS["groceries"]
        limit = max_results or self.settings.max_results
        accepted: list[Location] = []
        errors: list[str] = []

        # Small requests are much more reliable on shared public Overpass servers
        # than one large multi-category query.
        for key, value in filters:
            remaining = limit - len(accepted)
            if remaining <= 0:
                break
            node_query = self._query_for_filter(key, value, lat, lon, radius_m, remaining, include_ways=False)
            locations, query_errors = self._request_first_success(node_query, remaining)
            errors.extend(query_errors)
            accepted = deduplicate_by_proximity([*accepted, *locations])
            if len(accepted) >= limit:
                break

        if len(accepted) < max(2, min(limit, 5)):
            for key, value in filters:
                remaining = limit - len(accepted)
                if remaining <= 0:
                    break
                way_query = self._query_for_filter(key, value, lat, lon, radius_m, remaining, include_ways=True)
                locations, query_errors = self._request_first_success(way_query, remaining)
                errors.extend(query_errors)
                accepted = deduplicate_by_proximity([*accepted, *locations])
                if len(accepted) >= limit:
                    break

        if accepted:
            return accepted[:limit]
        raise DiscoveryError("All configured Overpass discovery attempts failed. " + "; ".join(errors[-8:]))

    def _query_for_filter(self, key: str, value: str, lat: float, lon: float, radius_m: int, limit: int, include_ways: bool) -> str:
        clauses = [f'node["{key}"="{value}"]["name"](around:{int(radius_m)},{lat},{lon});']
        if include_ways:
            clauses.append(f'way["{key}"="{value}"]["name"](around:{int(radius_m)},{lat},{lon});')
        return f"""
        [out:json][timeout:{int(self.settings.timeout_seconds)}];
        (
          {' '.join(clauses)}
        );
        out tags center {int(limit)};
        """

    def _request_first_success(self, query: str, limit: int) -> tuple[list[Location], list[str]]:
        headers = {"User-Agent": self.settings.user_agent}
        errors: list[str] = []
        urls = [self.settings.overpass_url, *self.settings.overpass_fallback_urls]
        for url in urls:
            try:
                response = self.session.post(url, data={"data": query}, headers=headers, timeout=self.settings.timeout_seconds + 5)
                if response.status_code == 429:
                    errors.append(f"{url}: rate limited")
                    continue
                if response.status_code >= 500:
                    errors.append(f"{url}: HTTP {response.status_code}")
                    continue
                if response.status_code >= 400:
                    errors.append(f"{url}: HTTP {response.status_code}")
                    continue
                payload = response.json()
                time.sleep(self.settings.request_delay_seconds)
                return self._parse(payload, limit), errors
            except requests.RequestException as exc:
                errors.append(f"{url}: {exc}")
        return [], errors

    def _parse(self, payload: dict[str, Any], limit: int) -> list[Location]:
        accepted: list[Location] = []
        seen_ids: set[str] = set()
        retrieved = utc_now_iso()
        for element in payload.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name")
            if not name:
                continue
            lat = element.get("lat") or element.get("center", {}).get("lat")
            lon = element.get("lon") or element.get("center", {}).get("lon")
            if lat is None or lon is None:
                continue
            lat_f, lon_f = validate_coordinate(lat, lon)
            source_id = f"osm_{element.get('type', 'node')}_{element.get('id')}"
            if source_id in seen_ids:
                continue
            seen_ids.add(source_id)
            category = tags.get("amenity") or tags.get("shop") or tags.get("office") or ""
            address = ", ".join(
                part for part in [tags.get("addr:housename"), tags.get("addr:street"), tags.get("addr:barangay"), tags.get("addr:city")] if part
            )
            accepted.append(
                Location(
                    location_id=_safe_id(source_id),
                    location_name=name,
                    address_or_area=address,
                    latitude=lat_f,
                    longitude=lon_f,
                    source_name="OpenStreetMap Overpass API",
                    source_url=f"https://www.openstreetmap.org/{element.get('type', 'node')}/{element.get('id')}",
                    verified_date=retrieved,
                    category=category,
                    verification_status="source-reported",
                )
            )
            if len(accepted) >= limit:
                break
        return deduplicate_by_proximity(accepted)


def deduplicate_by_proximity(locations: list[Location], threshold_degrees: float = 0.00003) -> list[Location]:
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
