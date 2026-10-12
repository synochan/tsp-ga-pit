# Demo Guide

Use these talking points for a 10-15 minute recorded demonstration. Do not present this as a transcript; the actual video should be recorded while running the program.

1. Introduce the GA route-ordering problem: one start, multiple destinations, return to the same start while minimizing road distance.
2. Explain the study area: Cagayan de Oro City with a configurable boundary and a default focus around Carmen/Upper Carmen.
3. Show the flexible `START` options: map click, address search, or coordinate entry.
4. Explain that `START` is temporary and is not permanently added to the destination dataset.
5. Show the GA destination selector and explain that selected destinations become the chromosome genes.
6. Open the discovery tab and explain that Overpass can retrieve source-reported OpenStreetMap POIs by category and radius.
7. Explain that OpenStreetMap POIs are not independently verified and should be reviewed before academic use.
8. Select at least two GA destinations so the algorithm has a meaningful ordering problem.
9. Explain routing data: the app uses real OSRM-compatible road distances and source-reported OpenStreetMap/Nominatim places.
10. Preview the number of directed measurements required.
11. Explain the Genetic Algorithm parameters: population, generations, crossover, mutation, tournament size, elitism, and seed.
12. Run an optimization.
13. Show that the route starts at `START`, visits every selected GA destination exactly once, and returns to `START`.
14. Compare the GA best-found distance with nearest neighbor.
15. Show the convergence graph and explain best-so-far tracking.
16. Show the animated map path and distinguish START, intermediate destinations, the return leg, and route line. If road geometry is unavailable, mention that the dashed line is illustrative.
17. Export the JSON report, ordered route CSV, distance matrix, and text summary.
18. Discuss limitations: approximate GA result, public provider limits, asymmetric road distances, incomplete routing, and dataset verification.
19. Mention future improvements: verified field collection, provider replacement, richer road geometry display, and parameter experiments.
