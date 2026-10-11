from __future__ import annotations

import pytest

from data_loader import DataValidationError, load_distance_matrix_csv, load_locations_csv


def test_valid_locations_csv_loads(tmp_path):
    path = tmp_path / "locations.csv"
    path.write_text(
        "location_id,location_name,address_or_area,latitude,longitude\nA,Place,Area,8.1,124.1\n",
        encoding="utf-8",
    )
    locations = load_locations_csv(path)
    assert locations[0].location_id == "A"


def test_missing_required_location_columns_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("location_id,location_name\nA,Place\n", encoding="utf-8")
    with pytest.raises(DataValidationError):
        load_locations_csv(path)


def test_invalid_coordinates_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "location_id,location_name,address_or_area,latitude,longitude\nA,Place,Area,999,124.1\n",
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError):
        load_locations_csv(path)


def test_duplicate_ids_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "location_id,location_name,address_or_area,latitude,longitude\nA,One,Area,8.1,124.1\nA,Two,Area,8.2,124.2\n",
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError):
        load_locations_csv(path)


def test_negative_distance_rejected(tmp_path):
    path = tmp_path / "dist.csv"
    path.write_text(
        "from_location_id,to_location_id,distance_km,duration_minutes\nA,B,-1,2\n",
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError):
        load_distance_matrix_csv(path)


def test_nan_distance_rejected(tmp_path):
    path = tmp_path / "dist.csv"
    path.write_text(
        "from_location_id,to_location_id,distance_km,duration_minutes\nA,B,nan,2\n",
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError):
        load_distance_matrix_csv(path)
