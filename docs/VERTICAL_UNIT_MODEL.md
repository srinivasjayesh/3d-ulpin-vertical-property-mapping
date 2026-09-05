# Vertical and Unit Model

A building footprint is extruded from ground Z to roof Z. Floors divide that height equally: floor height = building height / floor count. This is a visualization model, not a surveyed plan.

Hyderabad floor IDs use a SHA-256 digest of source/location fields. Manhattan floor IDs are deterministic snapshot IDs; units split an oriented footprint into up to eight strips per floor. Mumbai strata use the MUM02_SOURCE_STRATA version and are flagged synthetic/source-derived.

Topology checks cover duplicate IDs, positive area/volume, floor closure, unit containment and overlaps. They do not prove architectural, structural or cadastral correctness.

No source currently supplies reliable basement count, depth or floor geometry. The Hyderabad/Manhattan below-ground view is a labelled B1/B2 demonstration; Mumbai has zero basement records.
