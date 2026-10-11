from __future__ import annotations

import folium
from folium.plugins import AntPath

from config import DEFAULT_STUDY_AREA
from models import Location


def build_route_map(
    start: Location | None,
    destinations: list[Location],
    end: Location | None = None,
    ordered_route: list[str] | None = None,
    road_geometries: list[list[tuple[float, float]]] | None = None,
    illustrative_fallback: bool = False,
    animate_route: bool = False,
) -> folium.Map:
    study = DEFAULT_STUDY_AREA
    fmap = folium.Map(location=[study.center_lat, study.center_lon], zoom_start=study.default_zoom, control_scale=True)
    folium.Rectangle(
        bounds=[[study.min_lat, study.min_lon], [study.max_lat, study.max_lon]],
        color="#1f77b4",
        weight=1,
        fill=False,
        tooltip="Configured supported study area",
    ).add_to(fmap)
    by_id = {loc.location_id: loc for loc in destinations}
    if start:
        by_id[start.location_id] = start
        folium.Marker(
            [start.latitude, start.longitude],
            popup=f"START: {start.location_name}",
            tooltip="START",
            icon=folium.Icon(color="green", icon="play"),
        ).add_to(fmap)
    if end:
        by_id[end.location_id] = end
        folium.Marker(
            [end.latitude, end.longitude],
            popup=f"END: {end.location_name}",
            tooltip="END",
            icon=folium.Icon(color="red", icon="stop"),
        ).add_to(fmap)
    for location in destinations:
        if start and location.location_id == start.location_id:
            continue
        if end and location.location_id == end.location_id:
            continue
        folium.Marker(
            [location.latitude, location.longitude],
            popup=f"{location.location_name}<br>{location.address_or_area}",
            tooltip=location.location_name,
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(fmap)
    if road_geometries:
        for geometry in road_geometries:
            if animate_route:
                AntPath(
                    locations=geometry,
                    color="#e84a27",
                    pulse_color="#ffd166",
                    weight=6,
                    opacity=0.9,
                    delay=900,
                ).add_to(fmap)
            else:
                folium.PolyLine(geometry, color="#e84a27", weight=5, opacity=0.85).add_to(fmap)
    elif ordered_route:
        points = [(by_id[location_id].latitude, by_id[location_id].longitude) for location_id in ordered_route if location_id in by_id]
        if len(points) > 1:
            folium.PolyLine(
                points,
                color="#d95f02" if illustrative_fallback else "#e84a27",
                weight=4,
                opacity=0.75,
                dash_array="8,8" if illustrative_fallback else None,
                tooltip="Illustrative straight-line connection" if illustrative_fallback else "Route",
            ).add_to(fmap)
    return fmap
