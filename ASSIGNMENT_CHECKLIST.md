# Assignment Checklist

This project was checked against `Performance_Innovative_Task_TSP (1).docx`.

## Required Model

- Closed-tour TSP: `START -> selected destinations -> START`.
- Every selected destination is visited exactly once.
- Objective: minimize total road distance in kilometers.
- Graph type: complete directed weighted graph.
- Vertices: selected `START` and all selected GA destinations.
- Edges: directed driving connections between every pair of vertices.
- Weights: OSRM-compatible road distances in kilometers.

## Where To Find Evidence

- Algorithm implementation: `genetic_algorithm.py`.
- Independent route validation: `route_validation.py`.
- Real location dataset: `data/discovered_locations.csv`.
- Streamlit app and exports: `app.py`.
- Command-line execution: `main.py`.
- Assignment evidence helpers: `assignment_artifacts.py`.
- Tests: `tests/`.

## Export Files For Submission

After running the app and clicking `Save exports to output folder`, use:

- `output/selected_locations.csv`
- `output/distance_matrix.csv`
- `output/assignment_vertices.csv`
- `output/assignment_directed_edges.csv`
- `output/assignment_weight_matrix_km.csv`
- `output/route_edge_recalculation.csv`
- `output/weighted_graph.png`
- `output/route_report.json`
- `output/assignment_evidence.md`
- `output/route_summary.txt`

## Presentation Notes

In the video, show an actual app run: choose `START`, select real destinations, run the GA, show the route output, open the assignment evidence tables, and export the files. State clearly that the Genetic Algorithm provides a best-found approximate route unless the small-instance brute-force reference is shown for the same selected locations.
