from __future__ import annotations

from models import Location, RouteMeasurement
from routing_client import OSRMRoutingClient


class DistanceProvider:
    def build_matrix(self, locations: list[Location]) -> tuple[dict[tuple[str, str], RouteMeasurement], bool]:
        raise NotImplementedError


class OSRMDistanceProvider(DistanceProvider):
    def __init__(self, client: OSRMRoutingClient) -> None:
        self.client = client

    def build_matrix(self, locations: list[Location]) -> tuple[dict[tuple[str, str], RouteMeasurement], bool]:
        return self.client.table(locations)
