# Contributing

Use a branch, add tests for changed behavior, and run pytest, Ruff and package builds. Changes to Core contracts must be checked against all sibling packages. Preserve evaluator independence: model-generated conclusions are not acceptance evidence. Use synthetic fixtures in CI; do not commit credentials, site profiles, proprietary model inputs or production output datasets.

Report which workflows were actually run. Distinguish offline transport tests and synthetic examples from Discover/GEOS acceptance runs. Keep public APIs and the implementation status document accurate.

From the workspace directory containing all six checkouts, regenerate public API references with `python nexus-atom-controller/scripts/generate_api_docs.py` and check relative Markdown links with `python nexus-atom-controller/scripts/check_docs.py`. Keep README/USAGE descriptions and examples aligned with the implementation; generated signatures alone are not sufficient documentation. Run the standalone demo with a fresh state directory and exercise its pause/resume path when changing controller behavior.
