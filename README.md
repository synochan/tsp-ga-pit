# Closed-Tour TSP Route Optimization Using a Genetic Algorithm

This project is a complete Python application for a university Genetic Algorithm route-optimization assignment in Cagayan de Oro City, Philippines. It lets a user choose one temporary starting point, select real GA destinations, build a directed road-distance matrix, run a Genetic Algorithm to choose the visit order, compare it with nearest neighbor, validate the route, visualize it with an animated path, and export reports.

The start is fixed during one optimization run. The chromosome contains only selected destination IDs, for example `[C, A, D, B]`, and the complete closed tour is `START -> C -> A -> D -> B -> START`. At least two destinations are required so the Genetic Algorithm has a meaningful ordering problem.

There is no separate `END` selector in the current version. The selected `START` is also the final return point, which keeps the project aligned with the classic closed-tour TSP requirement.

## Why This Is A TSP

The route must start at one location, visit every selected destination exactly once, and return to the same start while minimizing total distance. This is the classic closed-tour Traveling Salesperson Problem. Road distances can be asymmetric because one-way roads and routing restrictions may make A-to-B different from B-to-A.

## Why Use A Genetic Algorithm

Exact enumeration grows factorially as destinations increase. A Genetic Algorithm is suitable for a demonstration because it searches many route permutations without trying every possible tour. It returns a best-found approximate solution, not a guaranteed global optimum unless an exact reference is separately computed for that small instance.

## Algorithm

- Chromosome: a permutation of selected destination IDs only.
- Fitness: complete route distance from `START` through the chromosome and back to `START`.
- Initial population: random valid permutations.
- Selection: tournament selection.
- Crossover: order crossover, preserving each destination exactly once.
- Mutation: swap mutation.
- Elitism: the best individuals are copied into the next generation.
- Termination: fixed number of generations.
- Tracking: best-so-far distance is stored for every generation and plotted.

Different random seeds and parameter choices may produce different best-found routes.

## Assignment Deliverables Covered

The assignment file asks for a real-life TSP application, graph model, weighted data table, Python execution, output verification, and a conclusion about optimality. This project supports those requirements directly:

- Real-life application: route planning over selected Cagayan de Oro locations.
- Vertices: `START` plus every selected destination.
- Edges: complete directed road-routing measurements between every pair of selected vertices.
- Weights: road distance in kilometers from OSRM-compatible routing data.
- Labeled graph evidence: the app exports `assignment_vertices.csv`, `assignment_directed_edges.csv`, and `assignment_weight_matrix_km.csv`.
- Verification evidence: the app exports `route_edge_recalculation.csv`, which independently adds the best-route edge weights and checks the reported total.
- Optimality statement: the GA is approximate; brute force is only used as a small-instance reference when the selected destination count is within the configured limit.

## Real Data Sources

The app is real-data-first. It discovers candidate destinations from OpenStreetMap through Overpass, searches place names through Nominatim when requested, and calculates directed road distances with an OSRM-compatible routing API. It stores routing results in a local SQLite cache so changing GA parameters does not re-request the same road-distance matrix.

These external services may receive the queried coordinates or place names. Respect their usage policies and use conservative request settings.

## Architecture

- `app.py`: Streamlit UI.
- `main.py`: command-line run using a previously saved real discovered dataset.
- `assignment_artifacts.py`: assignment evidence tables and Markdown summary helpers.
- `genetic_algorithm.py`: GA, nearest neighbor, and optional brute-force exact reference.
- `routing_client.py`: OSRM-compatible table and route geometry client with cache.
- `distance_provider.py`: OSRM distance provider.
- `discovery.py`: Overpass POI discovery.
- `geocoding.py`: Nominatim search.
- `data_loader.py`: CSV validation and saving.
- `route_validation.py`: independent route verification.
- `map_visualization.py`: Folium map.
- `graph_visualization.py`: convergence plot and optional graph helper.
- `ASSIGNMENT_CHECKLIST.md`: quick map from assignment requirements to project files and exports.
- `tests/`: pytest tests with mocked routing responses, so tests do not depend on a live public API.

## Windows Setup

```powershell
cd C:\Users\Merocel\Desktop\Coding\TSP-PIT\carmen_tsp_ga
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `python` points to a non-Windows/MSYS interpreter on your machine, use the full path to your installed Windows Python executable when creating the virtual environment.

## Run The App

```powershell
cd C:\Users\Merocel\Desktop\Coding\TSP-PIT\carmen_tsp_ga
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

## Command-Line Run

```powershell
cd C:\Users\Merocel\Desktop\Coding\TSP-PIT\carmen_tsp_ga
python main.py
```

`main.py` expects `data/discovered_locations.csv`, which is created by the Streamlit discovery workflow.

## Run Tests

```powershell
cd C:\Users\Merocel\Desktop\Coding\TSP-PIT\carmen_tsp_ga
pytest
```

Tests do not require internet access. Routing-client tests use mocked responses.

## Real-World Dataset Workflow

1. Open the Streamlit app.
2. In `1. Start`, click the map to set `START`. You can also search or enter coordinates.
3. In `2. GA Destinations`, click `Find Real Destinations From OpenStreetMap`.
4. Review the loaded candidates and select at least two GA destinations. These selected places are the genes in the GA chromosome.
5. In `3. Run GA`, click `Run Genetic Algorithm`.
6. Review the validation result, route distance, nearest-neighbor comparison, convergence graph, and animated map. The displayed route must start at `START`, visit every selected destination once, and return to `START`.
7. In `4. Export`, download or save the report files.

Do not treat OpenStreetMap POIs as independently verified real-world business records. If a field is unavailable, the app leaves it blank or marks the location as source-reported/unverified.

## Route Validation

The final route is independently checked to confirm:

- it starts at `START`;
- it returns to `START`;
- every required destination appears exactly once;
- no unselected destination appears;
- every edge has a finite non-negative distance;
- the reported total matches a separate recalculation.

If validation fails, the UI does not present the route as successful.

## Exports

The app can download:

- route report JSON;
- ordered route CSV;
- selected location dataset CSV;
- distance matrix CSV;
- assignment vertex table CSV;
- assignment directed edge table CSV;
- assignment distance matrix CSV;
- route edge recalculation CSV;
- assignment evidence Markdown;
- convergence history CSV;
- plain-text summary.

It can also save generated files to `output/`.

## Limitations

The OSRM public demo server and public OpenStreetMap services are not production SLA services. Live discovery/routing can fail due to network access, rate limits, provider downtime, or unsupported coordinates. Public services should be replaced with a suitable configured provider for serious or repeated experiments.

The exact brute-force reference is intentionally limited to small instances because factorial search grows rapidly.

## References

- OSRM project documentation: https://project-osrm.org/docs/
- OpenStreetMap: https://www.openstreetmap.org/
- Overpass API: https://wiki.openstreetmap.org/wiki/Overpass_API
- Nominatim usage policy: https://operations.osmfoundation.org/policies/nominatim/
- Streamlit: https://docs.streamlit.io/
- Folium: https://python-visualization.github.io/folium/
