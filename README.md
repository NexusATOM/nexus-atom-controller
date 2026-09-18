# Nexus ATOM Controller

The model-independent control plane for **Autonomous Technology for Orchestrated Modeling**. A structured goal drives observe → plan → execute → evaluate → learn/replan until deterministic criteria pass or an explicit stopping condition is reached.

```bash
atom run --system geos --demo --state .atom/geos-demo --target speedup=1 \
  'Optimize a synthetic kernel while preserving its output'
atom run --system ecco --demo --state .atom/ecco-demo 'Exercise the ECCO plugin contract'
atom run --system lis --demo --state .atom/lis-demo 'Exercise the LIS plugin contract'
atom run --system issm --demo --state .atom/issm-demo 'Exercise the ISSM plugin contract'
atom run --system modele --demo --state .atom/modele-demo 'Exercise the ModelE plugin contract'
```

These demonstrations use synthetic data. They do not run the upstream Earth-system models or establish GEOS GPU acceleration. For actual GEOS execution use the [Discover guide](https://github.com/NexusATOM/nexus-atom-geos/blob/main/docs/DISCOVER.md).

The objective text records intent. Numeric acceptance criteria are supplied explicitly through `--target`; model plugins provide deterministic constraints and workflow planning. A configured agent runtime proposes source changes during GEOS optimization. Arbitrary natural-language Earth-science experiment design is not inferred from text alone.

```bash
atom status GOAL_ID --state .atom/geos-demo
atom ledger GOAL_ID --state .atom/geos-demo
atom events --state .atom/geos-demo
atom resume GOAL_ID --system geos --config .atom/geos-demo/demo/geos.yaml --state .atom/geos-demo
atom serve --state .atom/geos-demo --port 8765
```

The read-only loopback service exposes `/health`, `/goals/GOAL_ID` and `/goals/GOAL_ID/experiments`. Keep one active controller per state directory. SQLite stores goal state and append-only events; sealed experiment metadata and artifacts carry integrity hashes. The ledger is planner memory. Resume verifies historical evidence before skipping completed work. Interrupted work requires `--recover-interrupted`, which seals the abandoned experiment and starts a new attempt; inspect/cancel outstanding scheduler jobs first.

Use `--plans plans.json` for explicit serialized task graphs spanning multiple capabilities, or the Python `Controller` API with a registry containing multiple plugins and a custom `Planner`. CLI execution selects one plugin; cross-model workflows use the Python API. Policy allowlists, task deadlines/retries and experiment/task/wall/token/cost/GPU budgets are enforced by the controller and cooperating capabilities. Cost/token reporting from third-party runtimes is only as complete as their adapter; configure external provider limits too. `--budget budget.json` accepts the complete Core Budget schema.

Candidates are promoted only after all configured evaluators pass and target metrics weakly improve. Promotion is a durable pointer, not an upstream Git merge. No agent-generated boolean can replace a registered evaluator.

See [architecture](docs/ARCHITECTURE.md), [implementation status](docs/IMPLEMENTATION.md), [original specification](docs/NexusATOM-Plan.md), and [release verification](docs/RELEASE.md).

## Install

Python 3.12–3.13, Linux or macOS. The six packages are released together; they are not yet published to PyPI. Clone `nexus-atom-controller` and run its `scripts/bootstrap.py --directory ../NexusATOM` to clone the matching release and create a virtual environment. Use `--ref main --dev` for development. Existing checkouts are preserved.

From a workspace containing all six repositories:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ./nexus-atom-core -e ./nexus-atom-controller \
  -e ./nexus-atom-agents -e ./nexus-atom-hpc -e ./nexus-atom-science -e ./nexus-atom-geos
.venv/bin/atom plugins
```

Run package tests with `python -m pytest tests` after installing the `dev` extra and sibling dependencies. The GEOS legacy tests also require the `nooa` extra; GEOS integration tests require the controller. CI tests Python 3.12 and 3.13 and builds wheel/sdist artifacts. See the [architecture and implementation map](https://github.com/NexusATOM/nexus-atom-controller/blob/main/docs/ARCHITECTURE.md).

Apache-2.0. This is an independent implementation for model orchestration, not an official NASA model distribution or endorsement.
