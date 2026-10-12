from __future__ import annotations

import json

import pandas as pd

from assignment_artifacts import build_directed_edge_table, build_route_edge_check, build_vertex_table, build_weight_matrix_table
from config import DATA_DIR, DEFAULT_ROUTING, ensure_directories
from data_loader import load_locations_csv, save_distance_matrix_csv, save_locations_csv
from distance_provider import OSRMDistanceProvider
from genetic_algorithm import nearest_neighbor, run_genetic_algorithm
from graph_visualization import plot_weighted_graph
from models import GAParameters, Location, utc_now_iso
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
    route_edge_check, route_total_check_km = build_route_edge_check(result.best_route, matrix)
    print("Route:", " -> ".join(result.best_route))
    print(f"GA best-found distance: {result.best_distance:.3f} km")
    print(f"Independent recalculation: {route_total_check_km:.3f} km")
    print(f"Nearest-neighbor distance: {baseline[1]:.3f} km")
    print("Validation:", "PASS" if validation.is_valid else validation.errors)

    output_dir = DATA_DIR.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes = [start] + selected
    save_locations_csv(nodes, output_dir / "selected_locations.csv")
    save_distance_matrix_csv(matrix, output_dir / "distance_matrix.csv")
    pd.DataFrame(build_vertex_table(start, selected)).to_csv(output_dir / "assignment_vertices.csv", index=False)
    pd.DataFrame(build_directed_edge_table(nodes, matrix)).to_csv(output_dir / "assignment_directed_edges.csv", index=False)
    pd.DataFrame(build_weight_matrix_table(nodes, matrix)).to_csv(output_dir / "assignment_weight_matrix_km.csv", index=False)
    pd.DataFrame(route_edge_check).to_csv(output_dir / "route_edge_recalculation.csv", index=False)
    plot_weighted_graph(nodes, matrix).savefig(output_dir / "weighted_graph.png", dpi=180, bbox_inches="tight")
    report = {
        "generated_at": utc_now_iso(),
        "route_model": "closed_tour_start_to_destinations_to_start",
        "objective": "Minimize total directed road distance in kilometers",
        "best_found_route": result.best_route,
        "best_found_distance_km": result.best_distance,
        "independent_route_total_check_km": route_total_check_km,
        "validation": validation.__dict__,
        "nearest_neighbor": {"route": baseline[0], "distance_km": baseline[1]},
    }
    (output_dir / "route_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Assignment evidence files saved to {output_dir}")


if __name__ == "__main__":
    main()
