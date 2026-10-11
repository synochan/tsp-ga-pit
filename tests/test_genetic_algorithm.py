from __future__ import annotations

import pytest

from genetic_algorithm import (
    GeneticAlgorithmError,
    generate_initial_population,
    nearest_neighbor,
    order_crossover,
    run_genetic_algorithm,
    swap_mutation,
    tournament_selection,
)
from models import GAParameters, Location, RouteMeasurement, utc_now_iso
from route_validation import validate_round_trip


def fixture_problem():
    start = Location("START", "Start", "", 8.475, 124.645)
    destinations = [
        Location("A", "A", "", 8.48, 124.63),
        Location("B", "B", "", 8.49, 124.64),
        Location("C", "C", "", 8.47, 124.62),
        Location("D", "D", "", 8.46, 124.65),
    ]
    nodes = [start] + destinations
    matrix = {}
    for i, origin in enumerate(nodes):
        for j, destination in enumerate(nodes):
            if origin.location_id == destination.location_id:
                continue
            distance = abs(i - j) + 1 + (0.1 if i > j else 0)
            matrix[(origin.location_id, destination.location_id)] = RouteMeasurement(
                origin.location_id,
                destination.location_id,
                distance,
                distance * 2,
                "mock-road",
                utc_now_iso(),
                "mock routing provider",
                "",
            )
    return start, destinations, matrix


def test_population_generation_creates_valid_permutations():
    import random

    population = generate_initial_population(["A", "B", "C"], 20, random.Random(1))
    assert len(population) == 20
    assert all(sorted(individual) == ["A", "B", "C"] for individual in population)


def test_tournament_selection_returns_valid_individual():
    import random

    population = [["A", "B"], ["B", "A"]]
    selected = tournament_selection(population, [10.0, 5.0], 2, random.Random(1))
    assert sorted(selected) == ["A", "B"]


def test_order_crossover_preserves_every_destination_once():
    import random

    child = order_crossover(["A", "B", "C", "D"], ["D", "C", "B", "A"], random.Random(2))
    assert sorted(child) == ["A", "B", "C", "D"]
    assert len(set(child)) == 4


def test_swap_mutation_preserves_permutation():
    import random

    mutated = swap_mutation(["A", "B", "C"], random.Random(3))
    assert sorted(mutated) == ["A", "B", "C"]


def test_fixed_seed_is_reproducible():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations]
    params = GAParameters(population_size=30, generations=50, random_seed=7)
    first = run_genetic_algorithm("START", ids, matrix, params)
    second = run_genetic_algorithm("START", ids, matrix, params)
    assert first.best_route == second.best_route
    assert first.best_distance == second.best_distance
    assert first.history == second.history


def test_ga_handles_small_valid_instance_and_validates_route():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations[:2]]
    result = run_genetic_algorithm("START", ids, matrix, GAParameters(population_size=10, generations=10))
    validation = validate_round_trip(result.best_route, "START", ids, matrix, result.best_distance)
    assert validation.is_valid


def test_ga_rejects_invalid_input():
    _, destinations, matrix = fixture_problem()
    with pytest.raises(GeneticAlgorithmError):
        run_genetic_algorithm("START", [destinations[0].location_id], matrix, GAParameters())


def test_nearest_neighbor_returns_closed_tour():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations]
    route, distance = nearest_neighbor("START", ids, matrix)
    assert route[0] == "START"
    assert route[-1] == "START"
    assert set(route[1:-1]) == set(ids)
    assert distance > 0


def test_ga_supports_fixed_end_route():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations[:3]]
    result = run_genetic_algorithm("START", ids, matrix, GAParameters(population_size=20, generations=20), end_id="D")
    assert result.best_route[0] == "START"
    assert result.best_route[-1] == "D"
    assert set(result.best_route[1:-1]) == set(ids)


def test_nearest_neighbor_supports_fixed_end_route():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations[:2]]
    route, distance = nearest_neighbor("START", ids, matrix, end_id="D")
    assert route[0] == "START"
    assert route[-1] == "D"
    assert set(route[1:-1]) == set(ids)
    assert distance > 0
