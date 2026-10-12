from __future__ import annotations

import json
import time

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from assignment_artifacts import (
    build_assignment_evidence_markdown,
    build_directed_edge_table,
    build_route_edge_check,
    build_vertex_table,
    build_weight_matrix_table,
)
from config import DATA_DIR, DEFAULT_DISCOVERY, DEFAULT_ROUTING, DEFAULT_STUDY_AREA, OUTPUT_DIR, RoutingSettings, ensure_directories
from data_loader import load_locations_csv, save_distance_matrix_csv, save_locations_csv, validate_coordinate
from discovery import CATEGORY_FILTERS, DiscoveryError, OverpassDiscoveryClient
from distance_provider import OSRMDistanceProvider
from genetic_algorithm import brute_force_exact, nearest_neighbor, run_genetic_algorithm
from geocoding import GeocodingError, NominatimGeocoder, discover_places_by_category
from graph_visualization import plot_convergence
from map_visualization import build_route_map
from models import GAParameters, Location, utc_now_iso
from route_validation import validate_round_trip
from routing_client import OSRMRoutingClient, RoutingError


ensure_directories()
DISCOVERED_PATH = DATA_DIR / "discovered_locations.csv"


def _load_real_locations() -> list[Location]:
    if DISCOVERED_PATH.exists():
        try:
            return _make_unique_location_ids(load_locations_csv(DISCOVERED_PATH))
        except Exception:
            # Older generated files may contain duplicate IDs. Repair them on load
            # so the selector has stable, unique row identities.
            df = pd.read_csv(DISCOVERED_PATH).fillna("")
            repaired: list[Location] = []
            for row in df.to_dict("records"):
                try:
                    lat, lon = validate_coordinate(row.get("latitude"), row.get("longitude"))
                except Exception:
                    continue
                repaired.append(
                    Location(
                        location_id=str(row.get("location_id", "")).strip(),
                        location_name=str(row.get("location_name", "")).strip() or "Unnamed location",
                        address_or_area=str(row.get("address_or_area", "")).strip(),
                        latitude=lat,
                        longitude=lon,
                        source_name=str(row.get("source_name", "")).strip(),
                        source_url=str(row.get("source_url", "")).strip(),
                        verified_date=str(row.get("verified_date", "")).strip(),
                        category=str(row.get("category", "")).strip(),
                        verification_status=str(row.get("verification_status", "source-reported")).strip() or "source-reported",
                    )
                )
            repaired = _make_unique_location_ids(repaired)
            if repaired:
                save_locations_csv(repaired, DISCOVERED_PATH)
            return repaired
    return []


def _location_df(locations: list[Location]) -> pd.DataFrame:
    if not locations:
        return pd.DataFrame()
    return pd.DataFrame([location.as_dict() for location in locations])


def _copy_location_with_id(location: Location, location_id: str) -> Location:
    return Location(
        location_id=location_id,
        location_name=location.location_name,
        address_or_area=location.address_or_area,
        latitude=location.latitude,
        longitude=location.longitude,
        source_name=location.source_name,
        source_url=location.source_url,
        verified_date=location.verified_date,
        category=location.category,
        verification_status=location.verification_status,
    )


def _make_unique_location_ids(locations: list[Location]) -> list[Location]:
    seen: dict[str, int] = {}
    unique_locations: list[Location] = []
    for index, location in enumerate(locations, start=1):
        base_id = (location.location_id or f"location_{index}").strip() or f"location_{index}"
        count = seen.get(base_id, 0) + 1
        seen[base_id] = count
        location_id = base_id if count == 1 else f"{base_id}_{count}"
        unique_locations.append(_copy_location_with_id(location, location_id))
    return unique_locations


def _set_locations(locations: list[Location], auto_select_count: int = 10) -> None:
    unique_locations = _make_unique_location_ids(locations)
    st.session_state.locations = unique_locations
    st.session_state.selected_ids = [loc.location_id for loc in unique_locations[: min(auto_select_count, len(unique_locations))]]
    st.session_state.pop("last_matrix", None)
    st.session_state.pop("last_result", None)


def _set_start(location: Location) -> None:
    st.session_state.start = location
    st.session_state.pop("last_matrix", None)
    st.session_state.pop("last_result", None)


def _selected_locations() -> list[Location]:
    selected_ids = st.session_state.get("selected_ids", [])
    return [loc for loc in st.session_state.locations if loc.location_id in selected_ids]


def _ordered_locations(start: Location, destinations: list[Location], route: list[str]) -> list[Location]:
    by_id = {"START": start}
    by_id.update({location.location_id: location for location in destinations})
    return [by_id[location_id] for location_id in route if location_id in by_id]


def _assignment_tables(start: Location, selected: list[Location], matrix):
    nodes = [start] + selected
    return {
        "vertices": build_vertex_table(start, selected),
        "directed_edges": build_directed_edge_table(nodes, matrix),
        "weight_matrix_km": build_weight_matrix_table(nodes, matrix),
    }


def _create_report(result, validation, selected, start, matrix, baseline, exact, cached):
    tables = _assignment_tables(start, selected, matrix)
    route_edge_check, route_total_check_km = build_route_edge_check(result.best_route, matrix)
    return {
        "generated_at": utc_now_iso(),
        "data_mode": "REAL_OSM_OSRM_DATA",
        "route_model": "closed_tour_start_to_destinations_to_start",
        "problem_context": {
            "application": "Closed-tour route planning in Cagayan de Oro City",
            "objective": "Minimize total directed road distance in kilometers",
            "graph_type": "Complete directed weighted graph over START and selected destinations",
            "algorithm": "Genetic Algorithm for Traveling Salesperson Problem",
        },
        "routing_cache_hit": cached,
        "start": start.as_dict(),
        "selected_destinations": [loc.as_dict() for loc in selected],
        "ga_parameters": result.parameters.__dict__,
        "best_found_route": result.best_route,
        "best_found_distance_km": result.best_distance,
        "independent_route_total_check_km": route_total_check_km,
        "route_edge_recalculation": route_edge_check,
        "validation": validation.__dict__,
        "nearest_neighbor": {"route": baseline[0], "distance_km": baseline[1]},
        "exact_reference": None if exact is None else {"route": exact[0], "distance_km": exact[1]},
        "assignment_tables": tables,
        "distance_measurements": [measurement.as_dict() for measurement in matrix.values()],
        "attribution": "Locations, map tiles, and routing data are derived from OpenStreetMap contributors through the configured Overpass, Nominatim, and OSRM-compatible services.",
    }


st.set_page_config(page_title="Cagayan de Oro TSP GA", layout="wide")
st.title("Real-Data TSP Route Optimizer for Cagayan de Oro")
st.caption("Pick one START, select at least two GA destinations, then let the Genetic Algorithm build a closed tour that returns to START.")

if "locations" not in st.session_state:
    st.session_state.locations = _load_real_locations()
if "selected_ids" not in st.session_state:
    st.session_state.selected_ids = []
if "start" not in st.session_state:
    st.session_state.start = None
st.session_state.pop("end", None)
if "last_result" in st.session_state and len(st.session_state.last_result) != 10:
    st.session_state.pop("last_result", None)
    st.session_state.pop("last_matrix", None)

with st.sidebar:
    st.header("Real Routing")
    osrm_url = st.text_input("OSRM base URL", DEFAULT_ROUTING.base_url)
    st.caption("The public OSRM demo server can be rate-limited. For repeated experiments, use your own OSRM-compatible provider.")
    animate_route = st.toggle("Animate orange route line", value=True)

    st.header("GA Settings")
    population_size = st.number_input("Population size", 2, 1000, 100)
    generations = st.number_input("Generations", 0, 5000, 300)
    crossover_probability = st.slider("Crossover probability", 0.0, 1.0, 0.85)
    mutation_probability = st.slider("Mutation probability", 0.0, 1.0, 0.10)
    tournament_size = st.number_input("Tournament size", 1, int(population_size), 3)
    elitism_count = st.number_input("Elitism count", 0, int(population_size), 2)
    random_seed = st.number_input("Random seed", 0, 999999, 42)

start_done = st.session_state.start is not None
destinations_done = len(st.session_state.locations) >= 2
selection_done = len(st.session_state.selected_ids) >= 2
st.progress((int(start_done) + int(destinations_done) + int(selection_done)) / 3)
st.write(
    f"Workflow: {'START selected' if start_done else 'choose START'} -> "
    f"{'real destinations loaded' if destinations_done else 'load real destinations'} -> "
    f"{'GA destinations selected' if selection_done else 'select at least 2 GA destinations'} -> "
    "return to START"
)

tabs = st.tabs(["1. Start", "2. GA Destinations", "3. Run GA", "4. Export"])

with tabs[0]:
    st.subheader("Choose START")
    st.info("Click inside the blue Cagayan de Oro study box, search a place, or enter coordinates. The final route returns to this same START.")
    start_map = build_route_map(
        st.session_state.start,
        _selected_locations(),
    )
    map_event = st_folium(start_map, height=480, width=None, key="start_map")
    if map_event and map_event.get("last_clicked"):
        clicked = map_event["last_clicked"]
        try:
            lat, lon = validate_coordinate(clicked["lat"], clicked["lng"])
            if DEFAULT_STUDY_AREA.contains(lat, lon):
                _set_start(Location("START", "Selected start point", "Map click", lat, lon, "User map click"))
                st.success(f"START selected at {lat:.6f}, {lon:.6f}. Next: select GA destinations.")
            else:
                st.error("That point is outside the configured study area. Click inside the blue box.")
        except Exception as exc:
            st.error(str(exc))

    col1, col2 = st.columns(2)
    with col1:
        with st.form("coordinate_start"):
            st.write("START coordinates")
            lat = st.number_input("Latitude", value=DEFAULT_STUDY_AREA.center_lat, format="%.6f")
            lon = st.number_input("Longitude", value=DEFAULT_STUDY_AREA.center_lon, format="%.6f")
            if st.form_submit_button("Use As START"):
                try:
                    lat_f, lon_f = validate_coordinate(lat, lon)
                    if DEFAULT_STUDY_AREA.contains(lat_f, lon_f):
                        _set_start(Location("START", "Selected start point", "Manual coordinates", lat_f, lon_f, "User input"))
                        st.success("START selected.")
                    else:
                        st.error("Coordinates are outside the configured study area.")
                except Exception as exc:
                    st.error(str(exc))
    with col2:
        st.write("Current START")
        if st.session_state.start:
            start = st.session_state.start
            st.success(f"{start.location_name} ({start.latitude:.6f}, {start.longitude:.6f})")
            if st.button("Clear START"):
                st.session_state.start = None
                st.session_state.pop("last_matrix", None)
                st.session_state.pop("last_result", None)
                st.rerun()
        else:
            st.warning("No START selected yet.")

    with st.form("geocode_point"):
        st.write("Or search a place for START")
        query = st.text_input("Example: Cogon Market, Cagayan de Oro")
        submitted = st.form_submit_button("Search Place")
    if submitted and query:
        try:
            st.session_state.geocode_matches = NominatimGeocoder(DEFAULT_DISCOVERY).search(query)
        except GeocodingError as exc:
            st.error(str(exc))
    matches = st.session_state.get("geocode_matches", [])
    if matches:
        chosen = st.selectbox("Confirm result", matches, format_func=lambda item: f"{item.location_name} - {item.address_or_area}")
        if st.button("Use Search Result As START"):
            if DEFAULT_STUDY_AREA.contains(chosen.latitude, chosen.longitude):
                _set_start(Location("START", chosen.location_name, chosen.address_or_area, chosen.latitude, chosen.longitude, chosen.source_name, chosen.source_url))
                st.success("START selected.")
            else:
                st.error("Selected result is outside the configured study area.")

with tabs[1]:
    st.subheader("Select GA Destinations")
    st.info("These blue markers are the chromosome genes. Select at least two real places so the Genetic Algorithm can optimize the closed tour from START back to START.")
    center_source = st.radio("Discovery center", ["Use START location", "Use Cagayan de Oro default center"], horizontal=True)
    if center_source == "Use START location" and st.session_state.start:
        center_lat = st.session_state.start.latitude
        center_lon = st.session_state.start.longitude
    else:
        center_lat = DEFAULT_STUDY_AREA.center_lat
        center_lon = DEFAULT_STUDY_AREA.center_lon

    col1, col2, col3 = st.columns(3)
    with col1:
        radius = st.slider("Search radius", 500, 5000, 1000, step=500)
    with col2:
        max_results = st.slider("Maximum locations", 5, 30, 10)
    with col3:
        categories = st.multiselect("Categories", list(CATEGORY_FILTERS.keys()), default=["pharmacies", "schools"])

    if st.button("Find Real Destinations From OpenStreetMap", type="primary"):
        discovery_notes: list[str] = []
        try:
            with st.spinner("Contacting Overpass API and filtering named places..."):
                discovered = OverpassDiscoveryClient(DEFAULT_DISCOVERY).discover(center_lat, center_lon, radius, categories, max_results)
            source_label = "Overpass"
        except DiscoveryError as exc:
            discovery_notes.append(str(exc))
            st.warning("Overpass is unavailable or too slow right now. Trying Nominatim as a real-data fallback...")
            with st.spinner("Searching Nominatim for source-reported real places..."):
                discovered, fallback_warnings = discover_places_by_category(DEFAULT_DISCOVERY, DEFAULT_STUDY_AREA, categories, max_results)
            discovery_notes.extend(fallback_warnings)
            source_label = "Nominatim fallback"
        if discovered:
            _set_locations(discovered)
            save_locations_csv(st.session_state.locations, DISCOVERED_PATH)
            st.success(f"Loaded {len(discovered)} real OSM candidate GA destinations using {source_label}. Saved to data/discovered_locations.csv.")
            if discovery_notes:
                with st.expander("Discovery provider details"):
                    for note in discovery_notes[-10:]:
                        st.write(note)
        else:
            st.error("No real destinations could be loaded from Overpass or Nominatim. Try a smaller radius, fewer categories, or use the place-name backup below.")
            if discovery_notes:
                with st.expander("Discovery provider details"):
                    for note in discovery_notes[-10:]:
                        st.write(note)

    uploaded = st.file_uploader("Or import a previously saved real locations CSV", type=["csv"])
    if uploaded is not None:
        try:
            imported = load_locations_csv(uploaded)
            _set_locations(imported)
            st.success(f"Loaded {len(imported)} locations from CSV.")
        except Exception as exc:
            st.error(str(exc))

    with st.expander("Backup: add real places by name"):
        st.write("Use this if Overpass is slow. Enter up to 10 place names, one per line. Searches are sent to Nominatim with Cagayan de Oro added when needed.")
        names_text = st.text_area("Place names", placeholder="Mercury Drug Carmen\nGaisano City Carmen\nSM City CDO Uptown")
        if st.button("Search And Add These Places"):
            names = [line.strip() for line in names_text.splitlines() if line.strip()][:10]
            if not names:
                st.warning("Enter at least one place name.")
            else:
                geocoder = NominatimGeocoder(DEFAULT_DISCOVERY)
                added: list[Location] = []
                errors: list[str] = []
                with st.spinner("Searching Nominatim for the entered places..."):
                    for name in names:
                        query = name if "cagayan" in name.lower() else f"{name}, Cagayan de Oro, Philippines"
                        try:
                            matches = geocoder.search(query, limit=3)
                            match = next((item for item in matches if DEFAULT_STUDY_AREA.contains(item.latitude, item.longitude)), None)
                            if match is None:
                                errors.append(f"No in-area match for {name}")
                            else:
                                added.append(
                                    Location(
                                        location_id=f"nominatim_{len(st.session_state.locations) + len(added) + 1}",
                                        location_name=match.location_name,
                                        address_or_area=match.address_or_area,
                                        latitude=match.latitude,
                                        longitude=match.longitude,
                                        source_name=match.source_name,
                                        source_url=match.source_url,
                                        verified_date=utc_now_iso(),
                                        category="searched_place",
                                        verification_status="source-reported",
                                    )
                                )
                        except GeocodingError as exc:
                            errors.append(f"{name}: {exc}")
                existing_keys = {(round(loc.latitude, 6), round(loc.longitude, 6), loc.location_name.lower()) for loc in st.session_state.locations}
                unique_added = []
                for location in added:
                    key = (round(location.latitude, 6), round(location.longitude, 6), location.location_name.lower())
                    if key not in existing_keys:
                        unique_added.append(location)
                        existing_keys.add(key)
                if unique_added:
                    _set_locations([*st.session_state.locations, *unique_added])
                if st.session_state.locations:
                    save_locations_csv(st.session_state.locations, DISCOVERED_PATH)
                if unique_added:
                    st.success(f"Added {len(unique_added)} source-reported real places.")
                if errors:
                    st.warning("; ".join(errors))

    locations = st.session_state.locations
    if locations:
        st.write(f"{len(locations)} candidate GA destinations loaded.")
        valid_ids = {loc.location_id for loc in locations}
        st.session_state.selected_ids = [loc_id for loc_id in st.session_state.selected_ids if loc_id in valid_ids]
        selector_df = pd.DataFrame(
            [
                {
                    "Select": loc.location_id in st.session_state.selected_ids,
                    "Name": loc.location_name,
                    "Category": loc.category,
                    "Area / Address": loc.address_or_area,
                    "Latitude": loc.latitude,
                    "Longitude": loc.longitude,
                    "location_id": loc.location_id,
                }
                for loc in locations
            ]
        )
        edited_df = st.data_editor(
            selector_df,
            key="ga_destination_selector",
            use_container_width=True,
            hide_index=True,
            disabled=["Name", "Category", "Area / Address", "Latitude", "Longitude", "location_id"],
            column_config={
                "Select": st.column_config.CheckboxColumn("Use in GA", help="Blue marker destination included in the GA route."),
                "location_id": None,
            },
        )
        st.session_state.selected_ids = edited_df.loc[edited_df["Select"], "location_id"].tolist()
        select_cols = st.columns(2)
        with select_cols[0]:
            if st.button("Select first 10"):
                st.session_state.selected_ids = [loc.location_id for loc in locations[: min(10, len(locations))]]
                st.rerun()
        with select_cols[1]:
            if st.button("Clear GA selection"):
                st.session_state.selected_ids = []
                st.rerun()
        selected = _selected_locations()
        st.dataframe(_location_df(selected), use_container_width=True)
        if len(selected) >= 2:
            st.success(f"{len(selected)} GA destinations selected. Next: Run GA.")
        else:
            st.warning("Select at least two GA destinations. With fewer than two, there is no meaningful GA ordering problem.")
    else:
        st.warning("No real destinations loaded yet. Click the discovery button above.")

with tabs[2]:
    st.subheader("Calculate Road Distances And Run The Genetic Algorithm")
    selected = _selected_locations()
    start = st.session_state.start
    if not start:
        st.warning("Step 1 is not complete: choose a START first.")
    elif len(selected) < 2:
        st.warning("Step 2 is not complete: select at least two GA destinations.")
    else:
        node_count = len(selected) + 1
        measurement_count = node_count * (node_count - 1)
        st.info(f"Ready. The GA will optimize {len(selected)} destination stops and return to START using {measurement_count} directed road-distance measurements.")
        if st.button("Run Genetic Algorithm", type="primary"):
            try:
                params = GAParameters(int(population_size), int(generations), crossover_probability, mutation_probability, int(tournament_size), int(elitism_count), int(random_seed))
                routing_client = OSRMRoutingClient(RoutingSettings(base_url=osrm_url))
                provider = OSRMDistanceProvider(routing_client)
                route_nodes = [start] + selected
                with st.spinner("Getting real road distances from OSRM..."):
                    matrix, cache_hit = provider.build_matrix(route_nodes)
                destination_ids = [loc.location_id for loc in selected]
                with st.spinner("Running nearest-neighbor baseline and Genetic Algorithm..."):
                    baseline_started = time.perf_counter()
                    baseline = nearest_neighbor("START", destination_ids, matrix)
                    baseline_runtime = time.perf_counter() - baseline_started
                    result = run_genetic_algorithm("START", destination_ids, matrix, params)
                    exact = brute_force_exact("START", destination_ids, matrix, 8)
                    validation = validate_round_trip(result.best_route, "START", destination_ids, matrix, result.best_distance)
                road_geometries = None
                geometry_warning = ""
                if validation.is_valid:
                    try:
                        with st.spinner("Fetching road-following geometry and animation path for the map..."):
                            road_geometries = routing_client.route_geometry(_ordered_locations(start, selected, result.best_route))
                    except RoutingError as exc:
                        geometry_warning = f"Road geometry could not be fetched: {exc}. The map uses a dashed illustrative connection instead."
                st.session_state.last_matrix = matrix
                st.session_state.last_result = (result, validation, baseline, baseline_runtime, exact, selected, start, cache_hit, road_geometries, geometry_warning)
            except Exception as exc:
                st.error(str(exc))

    if "last_result" in st.session_state:
        result, validation, baseline, baseline_runtime, exact, selected, start, cache_hit, road_geometries, geometry_warning = st.session_state.last_result
        if validation.is_valid:
            st.success("Route validation passed: the route starts at START, visits selected stops once, and returns to START.")
        else:
            st.error("Route validation failed: " + "; ".join(validation.errors))
        metrics = st.columns(4)
        metrics[0].metric("Best route distance", f"{result.best_distance:.3f} km")
        metrics[1].metric("Nearest-neighbor distance", f"{baseline[1]:.3f} km")
        metrics[2].metric("GA runtime", f"{result.runtime_seconds:.3f} s")
        metrics[3].metric("Routing cache", "Hit" if cache_hit else "Fresh")
        diff = result.best_distance - baseline[1]
        pct = "N/A" if baseline[1] == 0 else f"{(diff / baseline[1]) * 100:.2f}%"
        st.write({"absolute_difference_km": round(diff, 6), "percent_difference_vs_baseline": pct, "baseline_runtime_seconds": round(baseline_runtime, 6)})
        if exact:
            st.info(f"Exact small-instance reference: {exact[1]:.3f} km")
        st.write("Best-found route:", " -> ".join(result.best_route))
        route_edge_check, route_total_check_km = build_route_edge_check(result.best_route, st.session_state.last_matrix)
        st.write(f"Independent edge-weight recalculation: {route_total_check_km:.3f} km")
        with st.expander("Assignment evidence: graph model, weights, and route check"):
            nodes = [start] + selected
            st.write("Vertex labels and source details")
            st.dataframe(pd.DataFrame(build_vertex_table(start, selected)), use_container_width=True)
            st.write("Directed distance matrix in kilometers")
            st.dataframe(pd.DataFrame(build_weight_matrix_table(nodes, st.session_state.last_matrix)), use_container_width=True)
            st.write("Best-route edge-by-edge recalculation")
            st.dataframe(pd.DataFrame(route_edge_check), use_container_width=True)
        st.pyplot(plot_convergence(result.history))
        if geometry_warning:
            st.warning(geometry_warning)
        route_map = build_route_map(
            start,
            selected,
            ordered_route=result.best_route,
            road_geometries=road_geometries,
            illustrative_fallback=road_geometries is None,
            animate_route=animate_route,
        )
        st_folium(route_map, height=560, width=None, key="result_map")

with tabs[3]:
    st.subheader("Export Real-Data Results")
    if "last_result" not in st.session_state:
        st.info("Run the Genetic Algorithm before exporting results.")
    else:
        result, validation, baseline, _, exact, selected, start, cache_hit, _, _ = st.session_state.last_result
        matrix = st.session_state.last_matrix
        report = _create_report(result, validation, selected, start, matrix, baseline, exact, cache_hit)
        tables = report["assignment_tables"]
        route_edge_check = report["route_edge_recalculation"]
        evidence_md = build_assignment_evidence_markdown(
            start,
            selected,
            result,
            validation,
            baseline,
            exact,
            report["independent_route_total_check_km"],
        )
        st.download_button("Download route report JSON", json.dumps(report, indent=2), "route_report.json", "application/json")
        ordered = pd.DataFrame({"visit_order": range(len(result.best_route)), "location_id": result.best_route})
        st.download_button("Download ordered route CSV", ordered.to_csv(index=False), "ordered_route.csv", "text/csv")
        st.download_button("Download selected locations CSV", _location_df([start] + selected).to_csv(index=False), "selected_locations.csv", "text/csv")
        matrix_df = pd.DataFrame([measurement.as_dict() for measurement in matrix.values()])
        st.download_button("Download distance matrix CSV", matrix_df.to_csv(index=False), "distance_matrix.csv", "text/csv")
        st.download_button("Download assignment vertex table CSV", pd.DataFrame(tables["vertices"]).to_csv(index=False), "assignment_vertices.csv", "text/csv")
        st.download_button("Download assignment edge table CSV", pd.DataFrame(tables["directed_edges"]).to_csv(index=False), "assignment_directed_edges.csv", "text/csv")
        st.download_button("Download assignment weight matrix CSV", pd.DataFrame(tables["weight_matrix_km"]).to_csv(index=False), "assignment_weight_matrix_km.csv", "text/csv")
        st.download_button("Download route recalculation CSV", pd.DataFrame(route_edge_check).to_csv(index=False), "route_edge_recalculation.csv", "text/csv")
        st.download_button("Download assignment evidence Markdown", evidence_md, "assignment_evidence.md", "text/markdown")
        history_df = pd.DataFrame({"generation": range(len(result.history)), "best_distance_km": result.history})
        st.download_button("Download convergence CSV", history_df.to_csv(index=False), "convergence_history.csv", "text/csv")
        summary = f"""TSP Genetic Algorithm Route Summary
Data mode: REAL_OSM_OSRM_DATA
Route model: closed tour, START -> selected destinations -> START
Route: {' -> '.join(result.best_route)}
Best-found distance: {result.best_distance:.3f} km
Independent recalculation: {report["independent_route_total_check_km"]:.3f} km
Nearest-neighbor distance: {baseline[1]:.3f} km
Validation: {'PASS' if validation.is_valid else 'FAIL'}
Generated at: {utc_now_iso()}
"""
        st.download_button("Download plain-text summary", summary, "route_summary.txt", "text/plain")
        if st.button("Save exports to output folder"):
            save_locations_csv([start] + selected, OUTPUT_DIR / "selected_locations.csv")
            save_distance_matrix_csv(matrix, OUTPUT_DIR / "distance_matrix.csv")
            pd.DataFrame(tables["vertices"]).to_csv(OUTPUT_DIR / "assignment_vertices.csv", index=False)
            pd.DataFrame(tables["directed_edges"]).to_csv(OUTPUT_DIR / "assignment_directed_edges.csv", index=False)
            pd.DataFrame(tables["weight_matrix_km"]).to_csv(OUTPUT_DIR / "assignment_weight_matrix_km.csv", index=False)
            pd.DataFrame(route_edge_check).to_csv(OUTPUT_DIR / "route_edge_recalculation.csv", index=False)
            (OUTPUT_DIR / "route_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            (OUTPUT_DIR / "assignment_evidence.md").write_text(evidence_md, encoding="utf-8")
            (OUTPUT_DIR / "route_summary.txt").write_text(summary, encoding="utf-8")
            st.success(f"Saved files in {OUTPUT_DIR}")

st.caption("OpenStreetMap attribution applies to OSM-derived places, routing, geocoding, and map tiles. Public services can rate-limit requests.")
