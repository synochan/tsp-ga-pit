# Demo Guide

Use these talking points for a 10-15 minute recorded demonstration. Do not present this as a transcript; the actual video should be recorded while running the program.

1. Introduce the GA route-ordering problem: one start, multiple destinations, return to the same start while minimizing road distance.
2. Explain the study area: Cagayan de Oro City with a configurable boundary and a default focus around Carmen/Upper Carmen.
3. State clearly that the current app has no separate `END` point. The selected `START` is also the final return point.
4. Show the flexible `START` options: map click, address search, or coordinate entry.
5. Explain that `START` is temporary and is not permanently added to the destination dataset.
6. Show the GA destination selector and explain that selected destinations become the chromosome genes.
7. Open the discovery tab and explain that Overpass can retrieve source-reported OpenStreetMap POIs by category and radius.
8. Explain that OpenStreetMap POIs are not independently verified and should be reviewed before academic use.
9. Select at least two GA destinations so the algorithm has a meaningful ordering problem.
10. Explain routing data: the app uses real OSRM-compatible road distances and source-reported OpenStreetMap/Nominatim places.
11. Preview the number of directed measurements required.
12. Explain the Genetic Algorithm parameters: population, generations, crossover, mutation, tournament size, elitism, and seed.
13. Run an optimization.
14. Show that the route starts at `START`, visits every selected GA destination exactly once, and returns to `START`.
15. Compare the GA best-found distance with nearest neighbor.
16. Show the convergence graph and explain best-so-far tracking.
17. Show the animated map path and distinguish START, intermediate destinations, the return leg, and route line. If road geometry is unavailable, mention that the dashed line is illustrative.
18. Export the JSON report, ordered route CSV, distance matrix, and text summary.
19. Discuss limitations: approximate GA result, public provider limits, asymmetric road distances, incomplete routing, and dataset verification.
20. Mention future improvements: verified field collection, provider replacement, richer road geometry display, and parameter experiments.
