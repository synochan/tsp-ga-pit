from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import requests

from config import CACHE_DIR, RoutingSettings, ensure_directories
from data_loader import validate_coordinate
from models import Location, RouteMeasurement, utc_now_iso


class RoutingError(RuntimeError):
    pass


class NoRouteError(RoutingError):
    pass


class RateLimitError(RoutingError):
    pass


class RoutingCache:
    def __init__(self, path: str | Path | None = None) -> None:
        ensure_directories()
        self.path = Path(path) if path else CACHE_DIR / "routing_cache.sqlite3"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS routes (
                    cache_key TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )

    def get(self, key: str, ttl_seconds: float) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT created_at, payload FROM routes WHERE cache_key = ?", (key,)).fetchone()
        if not row:
            return None
        if time.time() - float(row[0]) > ttl_seconds:
            return None
        return json.loads(row[1])

    def set(self, key: str, payload: dict[str, Any]) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "REPLACE INTO routes(cache_key, created_at, payload) VALUES (?, ?, ?)",
                (key, time.time(), json.dumps(payload)),
            )

    def clear(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM routes")


class OSRMRoutingClient:
    """Small OSRM-compatible client.

    OSRM URL coordinates are longitude,latitude. The table endpoint returns
    distances in meters and durations in seconds when annotations request them.
    """

    def __init__(self, settings: RoutingSettings, cache: RoutingCache | None = None) -> None:
        self.settings = settings
        self.cache = cache or RoutingCache()
        self.session = requests.Session()

    def _cache_key(self, locations: list[Location]) -> str:
        normalized = {
            "provider": self.settings.provider_name,
            "base_url": self.settings.base_url.rstrip("/"),
            "profile": self.settings.profile,
            "coordinates": [(loc.location_id, round(loc.latitude, 6), round(loc.longitude, 6)) for loc in locations],
        }
        return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode("utf-8")).hexdigest()

    def table(self, locations: list[Location]) -> tuple[dict[tuple[str, str], RouteMeasurement], bool]:
        if len(locations) < 2:
            raise RoutingError("At least two locations are required for routing.")
        for location in locations:
            validate_coordinate(location.latitude, location.longitude)

        ttl_seconds = self.settings.cache_ttl_days * 24 * 60 * 60
        cache_key = self._cache_key(locations)
        cached = self.cache.get(cache_key, ttl_seconds)
        if cached is not None:
            return self._parse_table_payload(cached, locations, from_cache=True), True

        coordinates = ";".join(f"{loc.longitude:.6f},{loc.latitude:.6f}" for loc in locations)
        url = f"{self.settings.base_url.rstrip('/')}/table/v1/{self.settings.profile}/{coordinates}"
        params = {"annotations": "distance,duration"}
        payload = self._request_json(url, params)
        self.cache.set(cache_key, payload)
        return self._parse_table_payload(payload, locations, from_cache=False), False

    def route_geometry(self, route_locations: list[Location]) -> list[list[tuple[float, float]]]:
        geometries: list[list[tuple[float, float]]] = []
        for origin, destination in zip(route_locations, route_locations[1:]):
            coordinates = f"{origin.longitude:.6f},{origin.latitude:.6f};{destination.longitude:.6f},{destination.latitude:.6f}"
            url = f"{self.settings.base_url.rstrip('/')}/route/v1/{self.settings.profile}/{coordinates}"
            payload = self._request_json(url, {"overview": "full", "geometries": "geojson"})
            routes = payload.get("routes")
            if not routes:
                raise NoRouteError(f"No route geometry for {origin.location_id} -> {destination.location_id}")
            coords = routes[0].get("geometry", {}).get("coordinates", [])
            geometries.append([(float(lat), float(lon)) for lon, lat in coords])
            time.sleep(self.settings.request_delay_seconds)
        return geometries

    def _request_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.settings.retry_count + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.settings.timeout_seconds)
                if response.status_code == 429:
                    raise RateLimitError("Routing provider rate limit was reached.")
                if 500 <= response.status_code < 600:
                    raise RoutingError(f"Routing provider server error: HTTP {response.status_code}")
                if response.status_code >= 400:
                    raise RoutingError(f"Routing provider rejected the request: HTTP {response.status_code}")
                payload = response.json()
                code = payload.get("code")
                if code not in {"Ok", None}:
                    if code == "NoRoute":
                        raise NoRouteError("Routing provider could not find a route.")
                    raise RoutingError(f"Routing provider returned code {code}")
                return payload
            except (requests.Timeout, requests.ConnectionError, RoutingError) as exc:
                last_error = exc
                if isinstance(exc, (RateLimitError, NoRouteError)):
                    raise
                if attempt >= self.settings.retry_count:
                    break
                time.sleep((2**attempt) * self.settings.request_delay_seconds)
        raise RoutingError(str(last_error) if last_error else "Routing request failed.")

    def _parse_table_payload(
        self,
        payload: dict[str, Any],
        locations: list[Location],
        from_cache: bool,
    ) -> dict[tuple[str, str], RouteMeasurement]:
        distances = payload.get("distances")
        durations = payload.get("durations")
        if not isinstance(distances, list) or not isinstance(durations, list):
            raise RoutingError("Routing table response is missing distances or durations.")
        matrix: dict[tuple[str, str], RouteMeasurement] = {}
        timestamp = utc_now_iso()
        for i, origin in enumerate(locations):
            for j, destination in enumerate(locations):
                if i == j:
                    continue
                try:
                    distance_m = distances[i][j]
                    duration_s = durations[i][j]
                except (IndexError, TypeError) as exc:
                    raise RoutingError("Routing table dimensions do not match requested locations.") from exc
                if distance_m is None:
                    raise NoRouteError(f"No route for {origin.location_id} -> {destination.location_id}")
                matrix[(origin.location_id, destination.location_id)] = RouteMeasurement(
                    from_location_id=origin.location_id,
                    to_location_id=destination.location_id,
                    distance_km=float(distance_m) / 1000.0,
                    duration_minutes=None if duration_s is None else float(duration_s) / 60.0,
                    travel_mode=self.settings.profile,
                    measurement_date=timestamp,
                    source_name=self.settings.provider_name,
                    source_url=self.settings.base_url,
                    is_assumed=False,
                    notes="OSRM-compatible table response",
                    from_cache=from_cache,
                )
        return matrix
