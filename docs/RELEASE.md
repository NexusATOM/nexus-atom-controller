# Release verification

Install all six local packages into one clean Python 3.12/3.13 environment. Install developer extras, GEOS/Agents NOOA extras for legacy tests, and optional Science NetCDF/plot extras for integration coverage.

```bash
python -m pytest --import-mode=importlib ../nexus-atom-*/tests
ruff check ../nexus-atom-*/src ../nexus-atom-*/tests
ruff format --check ../nexus-atom-*/src ../nexus-atom-*/tests
python -m build
```

Build each repository's wheel and sdist. Install all six wheels into a fresh environment, then run `atom plugins`, GEOS's `--demo`, the four model examples, and `examples/multimodel.py`. Verify saved experiment hashes with `atom ledger` and resume a finished GEOS demo using its saved site config. Synthetic performance is not GEOS performance.

CI repeats checks on Linux/Python 3.12 and 3.13. Tagged releases should use matching tags across repositories. `scripts/bootstrap.py` defaults to `v0.1.0`; the cross-repository development CI follows main so each change is tested with current sibling APIs.

Discover acceptance is tracked separately in IMPLEMENTATION.md. Offline CI cannot establish allocation permission, site module compatibility, GPU speedup, GEOS science validity or live model-provider behavior.
