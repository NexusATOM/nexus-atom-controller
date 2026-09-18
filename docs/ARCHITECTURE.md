# Architecture

```text
Goal + Budget + Policy
          |
       Controller ---- SQLite state/events ---- verified experiment ledger
          |
       Planner (plugin, explicit task graphs, or custom)
          |
    DAG scheduler -> CapabilityRegistry -> trusted capability implementation
                                              |          |          |
                                          GEOS work   AgentRuntime   HPC jobs
                                              |          |          |
                                              +----- evidence ------+
                                                        |
                                               registered evaluators
                                                        |
                                         reject / retain / promote / finish
```

Core is the dependency root. Controller, Agents, HPC and Science depend on Core. GEOS depends on Core, Agents, HPC and Science. GEOS is discovered through `nexus_atom.plugins`; the controller has no GEOS import or compile command. GEOS integration tests depend on Controller without creating a runtime dependency cycle.

## State and evidence

`Store` persists goals, checkpoints, append-only events and sealed experiment records. SQLite transactions protect state transitions. A nonblocking file lock enforces one controller owner per storage directory. Completed experiments are immutable records checked against a metadata hash and artifact hashes; this is integrity detection, not tamper-proof remote storage. Keep the state database backed up alongside experiment directories.

A task completes only after its capability returns a matching task ID and valid artifact references. Failed dependencies block downstream execution. Execution is sequential in v0.1; independent DAG branches remain represented explicitly and can later be scheduled concurrently. Task timeouts cancel cooperative async capabilities; HPC adapters propagate cancellation to jobs/process groups. Synchronous third-party plugin code must not block the event loop.

Planner history is structured experiment evidence. Agent proposals, hypotheses and comments are not authoritative state. The GEOS planner sends previous evaluator failures to its configured runtime and retries from a clean baseline under the same budget. Prepared proposals execute once unless an explicit sequence supplies further plans.

Trusted evaluator implementations own approval. Goal constraints must resolve to registered evaluators before execution. Missing evidence, exceptions, nonfinite metrics and incomplete task graphs fail closed. All constraints must pass and every minimum target must be met before success. Promotion tracks Pareto nondecreasing target metrics rather than combining different units. The baseline pointer is the first validated experiment; GEOS additionally retains its measured CPU baseline inside each experiment.

## Recovery

A checkpoint marks active work before capability execution. A crash after sealing is reconciled from the immutable ledger. Other interruptions require explicit recovery; unfinished work is never silently repeated. Recovery preserves abandoned evidence, seals an interrupted record and lets the planner choose a new attempt. External Slurm jobs can survive a killed controller; inspect their durable receipts and reconcile/cancel them before recovery. A finished goal validates its historical evidence before returning success again.

## Workspaces and publication

GEOS imports the original mepo federation using the legacy repository registry and creates detached Git worktrees. Patch proposals identify full new file contents, repository-relative paths and original hashes. Dirty source and stale hashes are rejected. Site commands are trusted executable configuration and must target those isolated working directories. ATOM retains worktrees and diffs; promotion does not mutate upstream branches.

## Extension points

Implement a Core `Plugin` with unique capability names and evaluators. Register an entry point under `nexus_atom.plugins` to use CLI discovery. CLI plugins additionally implement `from_config`, `goal_constraints` and async `plan`; `demo` is optional. Python users can register any number of plugins and supply a custom Planner or `SequencePlanner`. `examples/multimodel.py` in the GEOS repo demonstrates a two-model goal. No physical coupling is implied by merely running both models.

A new agent framework implements `AgentRuntime`; routing is explicit. A new scheduler implements `Scheduler`. Scientific diagnostics use explicit units, alignment and weights; model-specific meaning and approved tolerances belong in the site/plugin policy.
