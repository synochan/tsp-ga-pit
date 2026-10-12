from __future__ import annotations

import itertools
import math
import random
import time

from models import GAParameters, GAResult, RouteMeasurement


class GeneticAlgorithmError(ValueError):
    pass


def validate_parameters(params: GAParameters, destination_count: int) -> None:
    if destination_count < 1:
        raise GeneticAlgorithmError("At least one destination is required.")
    if params.population_size <= 0:
        raise GeneticAlgorithmError("Population size must be positive.")
    if params.generations < 0:
        raise GeneticAlgorithmError("Generations cannot be negative.")
    if not 0 <= params.crossover_probability <= 1:
        raise GeneticAlgorithmError("Crossover probability must be between 0 and 1.")
    if not 0 <= params.mutation_probability <= 1:
        raise GeneticAlgorithmError("Mutation probability must be between 0 and 1.")
    if params.tournament_size <= 0 or params.tournament_size > params.population_size:
        raise GeneticAlgorithmError("Tournament size must be between 1 and population size.")
    if params.elitism_count < 0 or params.elitism_count > params.population_size:
        raise GeneticAlgorithmError("Elitism count must be between 0 and population size.")


def validate_distance_matrix(
    start_id: str,
    destination_ids: list[str],
    matrix: dict[tuple[str, str], RouteMeasurement],
) -> None:
    nodes = [start_id] + destination_ids
    for from_id in nodes:
        for to_id in nodes:
            if from_id == to_id:
                continue
            measurement = matrix.get((from_id, to_id))
            if measurement is None:
                raise GeneticAlgorithmError(f"Missing distance for {from_id} -> {to_id}")
            if not math.isfinite(measurement.distance_km) or measurement.distance_km < 0:
                raise GeneticAlgorithmError(f"Invalid distance for {from_id} -> {to_id}")


def route_distance(
    chromosome: list[str],
    start_id: str,
    matrix: dict[tuple[str, str], RouteMeasurement],
) -> float:
    if not chromosome:
        return 0.0
    route = [start_id] + chromosome + [start_id]
    total = 0.0
    for from_id, to_id in zip(route, route[1:]):
        measurement = matrix.get((from_id, to_id))
        if measurement is None or not math.isfinite(measurement.distance_km):
            raise GeneticAlgorithmError(f"Missing or invalid distance for {from_id} -> {to_id}")
        total += measurement.distance_km
    return total


def generate_initial_population(destination_ids: list[str], population_size: int, rng: random.Random) -> list[list[str]]:
    population: list[list[str]] = []
    for _ in range(population_size):
        individual = destination_ids[:]
        rng.shuffle(individual)
        population.append(individual)
    return population


def tournament_selection(
    population: list[list[str]],
    distances: list[float],
    tournament_size: int,
    rng: random.Random,
) -> list[str]:
    indexes = rng.sample(range(len(population)), tournament_size)
    best_index = min(indexes, key=lambda index: distances[index])
    return population[best_index][:]


def order_crossover(parent1: list[str], parent2: list[str], rng: random.Random) -> list[str]:
    if len(parent1) <= 1:
        return parent1[:]
    left, right = sorted(rng.sample(range(len(parent1)), 2))
    child: list[str | None] = [None] * len(parent1)
    child[left : right + 1] = parent1[left : right + 1]
    fill_values = [gene for gene in parent2 if gene not in child]
    fill_index = 0
    for index, value in enumerate(child):
        if value is None:
            child[index] = fill_values[fill_index]
            fill_index += 1
    return [str(gene) for gene in child]


def swap_mutation(individual: list[str], rng: random.Random) -> list[str]:
    mutated = individual[:]
    if len(mutated) > 1:
        first, second = rng.sample(range(len(mutated)), 2)
        mutated[first], mutated[second] = mutated[second], mutated[first]
    return mutated


def run_genetic_algorithm(
    start_id: str,
    destination_ids: list[str],
    matrix: dict[tuple[str, str], RouteMeasurement],
    params: GAParameters,
) -> GAResult:
    validate_parameters(params, len(destination_ids))
    validate_distance_matrix(start_id, destination_ids, matrix)
    rng = random.Random(params.random_seed)
    started = time.perf_counter()
    population = generate_initial_population(destination_ids, params.population_size, rng)
    best_route: list[str] | None = None
    best_distance = math.inf
    history: list[float] = []

    for _ in range(params.generations + 1):
        distances = [route_distance(individual, start_id, matrix) for individual in population]
        ranked = sorted(zip(distances, population), key=lambda item: item[0])
        if ranked[0][0] < best_distance:
            best_distance = ranked[0][0]
            best_route = ranked[0][1][:]
        history.append(best_distance)
        if len(history) > params.generations:
            break

        next_population = [individual[:] for _, individual in ranked[: params.elitism_count]]
        while len(next_population) < params.population_size:
            parent1 = tournament_selection(population, distances, params.tournament_size, rng)
            parent2 = tournament_selection(population, distances, params.tournament_size, rng)
            child = order_crossover(parent1, parent2, rng) if rng.random() < params.crossover_probability else parent1[:]
            if rng.random() < params.mutation_probability:
                child = swap_mutation(child, rng)
            next_population.append(child)
        population = next_population

    assert best_route is not None
    return GAResult(
        best_route=[start_id] + best_route + [start_id],
        best_distance=best_distance,
        history=history,
        generations_run=params.generations,
        runtime_seconds=time.perf_counter() - started,
        parameters=params,
    )


def nearest_neighbor(
    start_id: str,
    destination_ids: list[str],
    matrix: dict[tuple[str, str], RouteMeasurement],
) -> tuple[list[str], float]:
    validate_distance_matrix(start_id, destination_ids, matrix)
    if not destination_ids:
        return [start_id, start_id], 0.0
    unvisited = set(destination_ids)
    route = [start_id]
    current = start_id
    total = 0.0
    while unvisited:
        next_id = min(unvisited, key=lambda candidate: matrix[(current, candidate)].distance_km)
        total += matrix[(current, next_id)].distance_km
        route.append(next_id)
        unvisited.remove(next_id)
        current = next_id
    total += matrix[(current, start_id)].distance_km
    route.append(start_id)
    return route, total


def brute_force_exact(
    start_id: str,
    destination_ids: list[str],
    matrix: dict[tuple[str, str], RouteMeasurement],
    max_destinations: int = 8,
) -> tuple[list[str], float] | None:
    if len(destination_ids) > max_destinations:
        return None
    if not destination_ids:
        return [start_id, start_id], 0.0
    validate_distance_matrix(start_id, destination_ids, matrix)
    best_route: list[str] | None = None
    best_distance = math.inf
    for permutation in itertools.permutations(destination_ids):
        distance = route_distance(list(permutation), start_id, matrix)
        if distance < best_distance:
            best_distance = distance
            best_route = [start_id] + list(permutation) + [start_id]
    return (best_route or [], best_distance)
