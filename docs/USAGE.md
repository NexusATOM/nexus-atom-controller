# CLI, configuration and state

## Commands

| Command | Purpose |
|---|---|
| `atom demo [--state PATH] [--pause-after 1|2] [--resume]` | Small prepared optimization example; see QUICKSTART |
| `atom plugins` | List installed `nexus_atom.plugins` entry points |
| `atom run OBJECTIVE --system NAME --config FILE` | Start a new goal using a configured plugin |
| `atom run OBJECTIVE --system NAME --demo` | Use a model plugin's synthetic demonstration |
| `atom resume GOAL_ID --system NAME --config FILE` | Verify persisted evidence and continue a goal |
| `atom status GOAL_ID --state PATH` | Show checkpoint, usage and candidate pointers |
| `atom ledger GOAL_ID --state PATH` | Verify and print sealed experiments |
| `atom events --state PATH` | Print ordered structured execution events |
| `atom serve --state PATH [--port 8765]` | Serve read-only goal/experiment JSON on loopback |

Use `atom COMMAND --help` for argument syntax. The demo and service are optional entry points; normal controller execution depends only on Core plus your selected installed plugin.

## Goal acceptance

Objective text records intent. `--target METRIC=MINIMUM` supplies explicit numeric criteria, and the plugin supplies named evaluator constraints. Repeat `--target` for multiple metrics. For example, `--target speedup=3` requires measured speedup at least 3 in addition to every required evaluator passing. Maximum-error tolerances belong in evaluator configuration rather than being expressed as minimum targets.

Success requires a complete task graph, intact evidence, all constraints passing and all targets met. `no_more_plans`, `budget_exhausted`, `interrupted`, missing evidence and evaluator exceptions are not successful outcomes. Standard `run`/`resume` return exit 0 only on success and exit 2 otherwise. `demo --pause-after` intentionally returns 0 for its requested checkpoint, while reporting `budget_exhausted` accurately.

## Budgets and policy

`--max-experiments`, `--max-tasks` and `--wall-seconds` control the usual limits. `--budget FILE` overrides these with a complete Core Budget object:

```json
{
  "max_experiments": 5,
  "max_tasks": 100,
  "wall_seconds": 86400,
  "max_tokens": 100000,
  "max_cost": 100,
  "max_gpu_seconds": 72000
}
```

Budgets are totals for the goal, including earlier invocations, not fresh allowances each time you resume. Raising a limit permits further work. There is no automatic purchase of tokens or allocation time. Usage depends on adapter reporting; external/provider limits remain necessary for hard monetary guarantees. GEOS checks each requested GPU allocation against remaining GPU time before submission.

Python API users may supply `allowed_capabilities` to Controller. Tasks have individual deadlines and bounded retry counts; retry only idempotent operations. GEOS's default workflow does not automatically replay partially applied patches.

## Plans and plugins

The default planner comes from the selected plugin. `--plans FILE` instead accepts a JSON list of Core Plan objects. Each has a hypothesis and a validated task graph. Every task's capability must be registered. Explicit dependencies form a DAG; unknown IDs and cycles fail before execution. Current execution is sequential, including independent ready tasks.

The CLI loads one selected plugin. Multi-plugin orchestration uses the Python registry/Controller API; see EXTENDING and the GEOS `examples/multimodel.py` script. New CLI plugins implement configuration loading, goal constraints and planning in addition to the Core Plugin contract.

## State and recovery

The state directory contains `state.sqlite` and `experiments/`. A process lock prevents two controllers from writing the same directory concurrently. The ledger preserves each sealed experiment; goal checkpoints track current status, consumed budget and baseline/best/latest pointers. Terminal task events and their budget checkpoint are saved in one transaction.

Resume verifies historical metadata and artifact hashes. A completed goal returns without rerunning tasks. A goal stopped between experiments may continue after a budget increase. If it stopped during a task, inspect the recorded events and external job receipts first. `--recover-interrupted` seals the abandoned attempt with its recorded task results, current artifact hashes and partial logs, then permits a new isolated attempt. The recovery evaluation lists changed/missing task artifacts and identifies tasks without a terminal result; the abandoned attempt stays interrupted and cannot be promoted. This is not instruction-level or mid-task continuation. A crash during sealing is handled separately: the controller finishes the journaled metadata/ledger commit automatically on restart, without replaying execution. Read-only history and service calls never perform this reconciliation. If either the pending record or its artifacts changed, recovery fails for investigation.

Promotion updates a pointer only; it never automatically merges or pushes candidate source changes. Back up the database and experiment directories together. Keep site secrets out of logged environment settings and command arguments.

## Read-only service

`GET /health` reports service availability. `GET /goals/ID` returns a saved checkpoint. `GET /goals/ID/experiments` verifies and returns its ledger. The server accepts no execution/mutation endpoints and binds only to loopback. Use the CLI for authorized execution. The service is a local inspection facility, not a hardened multi-user deployment.

## Agent-driven planning (Python API)

`RuntimePlanner` connects an Agents runtime to the controller. Install the controller's
`agents` extra and the desired Agents provider extra (`nooa` or `openai`); local
JSON subprocess runtimes need no provider dependency. The engine still imports
only Core. The CLI's default remains the plugin's predefined workflow; select a runtime with `--planner-config` as described below.

```python
from pathlib import Path
from nexus_atom_agents import NOOARuntime
from nexus_atom_controller import Controller, RuntimePlanner, Store

# registry and goal are configured exactly as for a deterministic planner.
store = Store(Path(".atom/agent-goal"))
planner = RuntimePlanner(
    NOOARuntime("your-explicit-provider/model"),
    store.root / "planning",
    capability_guidance={
        "your_system.run": {"parameters": "Describe the plugin's accepted parameters here"}
    },
)
controller = Controller(registry, planner, store)
# In an async application: state = await controller.run(goal)
# Close store when the application is finished.
```

The request includes the immutable goal, remaining budget, Plan JSON schema,
registered capabilities, parameter guidance, and the last five experiments
(configurable). History includes task outputs and deterministic evaluations;
artifact files and source contents are not automatically read. Use guidance that
matches your plugin: capability descriptions alone do not define parameter schemas.
Provider-backed runs require credentials and may incur charges.

The runtime returns an `AgentResult` whose `proposal` is a Plan object, or exactly
`{"stop": true}`. A stop produces `no_more_plans`, never success. ATOM records the
request context, proposal, rationale, runtime and reported usage in a
`planning.finished` event before validating the Plan. Cyclic graphs, unknown
capabilities and policy-forbidden tasks cannot execute. Registered evaluators
still decide acceptance; the agent cannot change the goal's constraints or targets.

Reported planning tokens, cost and GPU time count toward the goal budget. Output
tokens and planning wall time are bounded. Input tokens can exceed the remaining
token allowance during one provider call; this is not a prepaid spending limit.
OpenAI reports token usage but does not calculate monetary cost here; NOOA usage
is currently supplied through the proposal response, and LocalRuntime does not
infer token or monetary usage. Configure provider-side spending limits where needed.
A crash during a provider call can leave its usage unrecorded and resume may make
another planning call. Exactly-once provider billing is not guaranteed. Completed
experiments and evaluation feedback persist and are supplied to replanning on resume.

Tests exercise a real local JSON subprocess that revises a rejected candidate after
restart, invalid graphs and accounting, budget exhaustion, and the real NOOA
strategy with a fake provider. These tests do not establish live model quality,
GEOS speedup or production science validity.

## Runtime planning from the CLI

`atom run` accepts `--planner-config PATH`, mutually exclusive with `--plans`.
For a local agent, create a JSON file such as:

```json
{
  "runtime": "local",
  "argv": ["/absolute/path/to/python", "/absolute/path/to/agent.py"],
  "history_limit": 5,
  "max_output_tokens": 4096,
  "timeout_seconds": 120,
  "capability_guidance": {}
}
```

The subprocess follows the Agents JSON protocol described above. Its working
directory is the goal's planning directory, so use absolute paths for script
arguments. No shell expansion is performed. Replace the runtime and argv with
`"runtime": "nooa", "model": "your-provider/model"` to select NOOA, or use
`"runtime": "openai"` with an explicit model. Provider credentials come from the
runtime environment; do not put credentials in argv, guidance or this config,
which is persisted in the state database and displayed by status commands.

```bash
atom run 'Evaluate a candidate using the configured scientific checks' \
  --system geos --config /absolute/path/to/geos.json \
  --planner-config /absolute/path/to/planner.json --state .atom/planned \
  --target speedup=3
atom resume GOAL_ID --system geos --config /absolute/path/to/geos.json \
  --state .atom/planned
```

This command requires an actual model configuration and suitable capability
parameter guidance. It does not promise that an arbitrary provider can solve
GEOS optimization from the objective alone. The plugin's fixed evaluators retain
acceptance authority. Use `--budget` to supply a full Budget JSON when controlling
token, monetary or GPU usage; the accounting limitations above still apply.

The validated planner configuration is saved with the goal before execution.
Resume automatically reuses it; resupplying an identical configuration is allowed,
but changing it or replacing it with `--plans` requires a new goal. The model's
`--config` must still be supplied on resume. Existing goals without saved runtime
configuration retain their previous planning behavior, and a runtime cannot be
attached after recorded work has begun. The standalone `atom demo` remains offline
and uses prepared candidates.

## Automatic experiment reports

New controller experiments include a reserved `_atom_report/` directory:

- `summary.md`: hypothesis, recorded status, whether the goal was satisfied,
  evaluator decisions/reasons, task outcomes and unfinished tasks.
- `evaluation.json`: schema version, fixed goal/targets, experiment identity,
  recorded status and evaluator results.
- `metrics.csv`: one row per evaluator metric, with its decision, measured value
  and declared minimum target when present. Different metric units are not summed.

Reports are generated before sealing and included in the same artifact-hash
manifest as the measured evidence. They also accompany explicit recovery of
interrupted attempts. Journal recovery reuses the already sealed report without
rerunning work. Editing a report after sealing fails history verification.
Existing sealed experiments remain unchanged and are not backfilled on resume.

`_atom_report` is reserved for the controller: plugins must not place task artifacts
there. Reports may be regenerated while an experiment is unsealed, but never after
metadata publication. They summarize configured evaluator decisions; a passing
report does not establish untested scientific validity. This export currently
provides JSON/CSV/Markdown, not a general plotting or interactive dashboard layer.


Capabilities receive the controller-selected best accepted experiment in
`ExecutionContext.parent_experiment`. This follows the same promotion policy as
the checkpoint's `best_valid_candidate` and survives resume through verified
ledger history. Plugins may opt into source continuation; the Controller itself
does not alter source trees. GEOS documents `continuation: best_valid` and keeps
its original scientific/performance reference while reconstructing candidates.
