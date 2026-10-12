from __future__ import annotations

import pytest

from genetic_algorithm import (
    GeneticAlgorithmError,
    brute_force_exact,
    generate_initial_population,
    nearest_neighbor,
    order_crossover,
    route_distance,
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
        run_genetic_algorithm("START", [], matrix, GAParameters())


def test_ga_handles_one_destination_closed_tour():
    _, destinations, matrix = fixture_problem()
    ids = [destinations[0].location_id]
    result = run_genetic_algorithm("START", ids, matrix, GAParameters(population_size=4, generations=3))
    assert result.best_route == ["START", ids[0], "START"]
    assert result.best_distance == matrix[("START", ids[0])].distance_km + matrix[(ids[0], "START")].distance_km


def test_nearest_neighbor_returns_closed_tour():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations]
    route, distance = nearest_neighbor("START", ids, matrix)
    assert route[0] == "START"
    assert route[-1] == "START"
    assert set(route[1:-1]) == set(ids)
    assert distance > 0


def test_route_distance_includes_return_to_start_leg():
    matrix = {
        ("START", "A"): RouteMeasurement("START", "A", 2, 1, "mock", utc_now_iso(), "mock", ""),
        ("A", "B"): RouteMeasurement("A", "B", 3, 1, "mock", utc_now_iso(), "mock", ""),
        ("B", "START"): RouteMeasurement("B", "START", 5, 1, "mock", utc_now_iso(), "mock", ""),
    }
    assert route_distance(["A", "B"], "START", matrix) == 10


def test_route_distance_empty_chromosome_is_zero():
    assert route_distance([], "START", {}) == 0.0


def test_invalid_matrix_distance_is_rejected():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations[:2]]
    matrix[("START", ids[0])] = RouteMeasurement("START", ids[0], float("nan"), 1, "mock", utc_now_iso(), "mock", "")
    with pytest.raises(GeneticAlgorithmError):
        run_genetic_algorithm("START", ids, matrix, GAParameters(population_size=4, generations=3))


def test_negative_matrix_distance_is_rejected():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations[:2]]
    matrix[("START", ids[0])] = RouteMeasurement("START", ids[0], -1, 1, "mock", utc_now_iso(), "mock", "")
    with pytest.raises(GeneticAlgorithmError):
        run_genetic_algorithm("START", ids, matrix, GAParameters(population_size=4, generations=3))


def test_ga_returns_closed_tour():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations[:3]]
    result = run_genetic_algorithm("START", ids, matrix, GAParameters(population_size=20, generations=20))
    assert result.best_route[0] == "START"
    assert result.best_route[-1] == "START"
    assert set(result.best_route[1:-1]) == set(ids)


def test_brute_force_exact_returns_closed_tour():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations[:2]]
    result = brute_force_exact("START", ids, matrix)
    assert result is not None
    route, distance = result
    assert route[0] == "START"
    assert route[-1] == "START"
    assert set(route[1:-1]) == set(ids)
    assert distance > 0


def test_brute_force_exact_finds_expected_small_optimum():
    ids = ["A", "B", "C"]
    distances = {
        ("START", "A"): 1,
        ("START", "B"): 9,
        ("START", "C"): 9,
        ("A", "B"): 1,
        ("A", "C"): 9,
        ("B", "A"): 9,
        ("B", "C"): 1,
        ("C", "A"): 9,
        ("C", "B"): 9,
        ("A", "START"): 9,
        ("B", "START"): 9,
        ("C", "START"): 1,
    }
    matrix = {
        edge: RouteMeasurement(edge[0], edge[1], distance, 1, "mock", utc_now_iso(), "mock", "")
        for edge, distance in distances.items()
    }
    route, distance = brute_force_exact("START", ids, matrix)
    assert route == ["START", "A", "B", "C", "START"]
    assert distance == 4


def test_ga_nearest_neighbor_and_exact_use_same_closed_tour_objective():
    _, destinations, matrix = fixture_problem()
    ids = [loc.location_id for loc in destinations[:3]]
    params = GAParameters(population_size=30, generations=20, random_seed=11)

    ga = run_genetic_algorithm("START", ids, matrix, params)
    nearest_route, nearest_distance = nearest_neighbor("START", ids, matrix)
    exact = brute_force_exact("START", ids, matrix)

    assert exact is not None
    for route, distance in [(ga.best_route, ga.best_distance), (nearest_route, nearest_distance), exact]:
        assert route[0] == "START"
        assert route[-1] == "START"
        assert set(route[1:-1]) == set(ids)
        assert validate_round_trip(route, "START", ids, matrix, distance).is_valid


def test_route_distance_rejects_negative_return_leg():
    matrix = {
        ("START", "A"): RouteMeasurement("START", "A", 2, 1, "mock", utc_now_iso(), "mock", ""),
        ("A", "START"): RouteMeasurement("A", "START", -1, 1, "mock", utc_now_iso(), "mock", ""),
    }
    with pytest.raises(GeneticAlgorithmError):
        route_distance(["A"], "START", matrix)
