from __future__ import annotations

from config import DATA_DIR, DEFAULT_ROUTING, ensure_directories
from data_loader import load_locations_csv
from distance_provider import OSRMDistanceProvider
from genetic_algorithm import nearest_neighbor, run_genetic_algorithm
from models import GAParameters, Location
from route_validation import validate_round_trip
from routing_client import OSRMRoutingClient


def main() -> None:
    ensure_directories()
    dataset = DATA_DIR / "discovered_locations.csv"
    if not dataset.exists():
        print("No real dataset found yet. Run the Streamlit app, use Discover Destinations, then save the discovered dataset.")
        return
    locations = load_locations_csv(dataset)
    start = Location("START", "Cagayan de Oro City Center", "Default CLI start", 8.475, 124.645, "User/demo configuration")
    selected = locations[: min(8, len(locations))]
    if len(selected) < 2:
        print("The saved real dataset needs at least two destinations.")
        return
    matrix, _ = OSRMDistanceProvider(OSRMRoutingClient(DEFAULT_ROUTING)).build_matrix([start] + selected)
    ids = [location.location_id for location in selected]
    baseline = nearest_neighbor("START", ids, matrix)
    result = run_genetic_algorithm("START", ids, matrix, GAParameters())
    validation = validate_round_trip(result.best_route, "START", ids, matrix, result.best_distance)
    print("Route:", " -> ".join(result.best_route))
    print(f"GA best-found distance: {result.best_distance:.3f} km")
    print(f"Nearest-neighbor distance: {baseline[1]:.3f} km")
    print("Validation:", "PASS" if validation.is_valid else validation.errors)


if __name__ == "__main__":
    main()
