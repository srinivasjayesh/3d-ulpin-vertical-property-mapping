# Contributing

This is a research/hackathon prototype. Small, focused pull requests are welcome.

1. Create a virtual environment and install `requirements.txt`.
2. Run `python -m pytest -q` before opening a pull request.
3. Keep root scripts `01`–`21` byte-for-byte unchanged; extend the `pipeline/` scripts instead.
4. Do not commit credentials, local environments, caches, raw restricted datasets, or large raster/LAS/LAZ files.
5. Preserve source attribution and update `docs/DATA_LICENSES.md` when adding data.

Please describe any changes to data provenance, assumptions, or estimated/synthetic fields in the pull request.
