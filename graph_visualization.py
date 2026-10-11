from __future__ import annotations

import matplotlib.pyplot as plt
import networkx as nx

from models import RouteMeasurement


def plot_convergence(history: list[float]):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(range(len(history)), history, color="#1f77b4", linewidth=2)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Best-so-far distance (km)")
    ax.set_title("Genetic Algorithm Convergence")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    return fig


def build_networkx_graph(matrix: dict[tuple[str, str], RouteMeasurement]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for (from_id, to_id), measurement in matrix.items():
        graph.add_edge(from_id, to_id, distance_km=measurement.distance_km)
    return graph
