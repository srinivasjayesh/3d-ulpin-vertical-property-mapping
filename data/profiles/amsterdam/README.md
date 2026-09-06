# Amsterdam Centrum benchmark

This profile is designed for reproducible open-data regeneration. It does not
ship downloaded source data or fabricate records when the downloads are absent.

Recommended source stack:

- PDOK BAG for building and address geometry.
- PDOK BGT for large-scale topography and roads.
- PDOK Kadastrale Kaart / Kadastrale Percelen for parcel context.
- AHN open raster and point-cloud products for terrain and height evidence.
- PDOK RGB orthophoto for image context.
- CBS/PDOK administrative areas for the Amsterdam Centrum boundary.

Source catalogue: https://www.pdok.nl/datasets
AHN open data: https://www.ahn.nl/open-data

The downloaded files must be reviewed against their current provider terms
before redistribution. The local BAG and cadastral extracts are intentionally
ignored by Git until that review is complete. Building floors and apartment
units remain unavailable until an approved floor plan, BIM model, or reviewed
survey is supplied.