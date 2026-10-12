from __future__ import annotations

import matplotlib.pyplot as plt
import networkx as nx

from models import Location
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


def plot_weighted_graph(
    nodes: list[Location],
    matrix: dict[tuple[str, str], RouteMeasurement],
    max_full_nodes: int = 7,
):
    graph = nx.DiGraph()
    node_ids = [node.location_id for node in nodes]
    labels = {node.location_id: f"V{index}\n{node.location_id}" for index, node in enumerate(nodes)}
    for index, node in enumerate(nodes):
        graph.add_node(node.location_id, label=labels[node.location_id], is_start=index == 0)

    sampled = len(nodes) > max_full_nodes
    for from_id in node_ids:
        outgoing = [
            (to_id, matrix[(from_id, to_id)].distance_km)
            for to_id in node_ids
            if from_id != to_id and (from_id, to_id) in matrix
        ]
        if sampled:
            outgoing = sorted(outgoing, key=lambda item: item[1])[:2]
        for to_id, distance in outgoing:
            graph.add_edge(from_id, to_id, distance_km=distance)

    fig, ax = plt.subplots(figsize=(9, 6))
    pos = nx.circular_layout(graph)
    colors = ["#2ca25f" if graph.nodes[node]["is_start"] else "#3182bd" for node in graph.nodes]
    nx.draw_networkx_nodes(graph, pos, node_color=colors, node_size=1250, edgecolors="#1f2933", linewidths=1.0, ax=ax)
    nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8, font_color="white", ax=ax)
    nx.draw_networkx_edges(
        graph,
        pos,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=12,
        width=1.2,
        alpha=0.55,
        connectionstyle="arc3,rad=0.08",
        edge_color="#4b5563",
        ax=ax,
    )
    edge_labels = {(u, v): f"{data['distance_km']:.1f} km" for u, v, data in graph.edges(data=True)}
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=7, label_pos=0.35, ax=ax)
    title_suffix = "nearest outgoing edges shown; full matrix is the source of truth" if sampled else "all directed edges shown"
    ax.set_title(f"Directed Weighted TSP Graph ({title_suffix})")
    ax.text(
        0.01,
        0.01,
        "Green = START/return point. Blue = required destination. Edge weights are directed road distances in km.",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
    )
    ax.axis("off")
    fig.tight_layout()
    return fig
