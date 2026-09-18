# Troubleshooting

| Symptom | Meaning and action |
|---|---|
| `atom: command not found` | Activate the workspace virtual environment or use `.venv/bin/atom` |
| `No matching distribution found for nexus-atom-*` | Packages are not on PyPI; install sibling GitHub checkouts together with the bootstrap script |
| Plugin not installed | Run `atom plugins`; install the package providing its entry point |
| Demo directory already exists | Use `atom demo --resume --state ...`, or choose a new directory |
| `budget_exhausted` after `--pause-after 1` | Expected checkpoint; resume without `--pause-after` |
| `no_more_plans` | Prepared candidates are exhausted before all goal criteria pass; inspect the ledger rather than assuming success |
| `interrupted` | Work was active when execution stopped; inspect events and outstanding external jobs before explicit recovery |
| Another controller owns this directory | Stop or wait for the owner; use separate state directories for independent goals |
| Pending seal conflict | An interrupted metadata write has evidence inconsistent with its sealing journal; preserve the directory and investigate rather than overwriting it |
| Artifact/metadata corrupted | Evidence differs from its saved hash; restore the original backup or investigate the change; do not silently rewrite the ledger |
| Goal ID missing | Use the ID printed at creation and the same `--state` directory |
| Slurm submission succeeds but goal fails | Inspect actual job exit state, logs, fresh data/timing output and evaluator reasons; a job ID is not evidence of completion |
| GPU budget exceeded | Requested allocation exceeds remaining GPU-seconds; choose appropriate resources or deliberately raise the total budget |
| Science alignment error | Field sets, metadata, units, shapes, dimensions, coordinates or weights differ; correct the experimental comparison |
| NOOA/provider failure | Install the appropriate runtime extra and configure the explicit provider/model and credential environment; offline examples need none |

See repository-specific guides for precise error contracts. Reproduce problems using a minimal synthetic case where possible, and report package versions, platform and the relevant redacted event/evaluation records.
