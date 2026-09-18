# Specification implementation and acceptance status

The source specification ended mid-section 15. This implementation completes the evaluator contract using the earlier explicit software, numerical, science and performance requirements. The six Phase I repositories are implemented; Phase II model examples are bundled without creating the later repositories the plan explicitly defers.

| Plan area | Implementation | Verification / boundary |
|---|---|---|
| 1–3 principles and protocol | Core contracts, finite metrics, DAG validation, artifacts/provenance, capability/evaluator registry | Unit tests; no vendor/model dependencies |
| 4 autonomous control plane | Controller loop, pluggable planning, dependency scheduler, executor, checkpoints/recovery, budgets/policy, SQLite events and ledger, CLI and read-only service | Failure, timeout, replan, resume, integrity and promotion tests, real process-death sealing tests, interrupted-result/log retention; sequential scheduling |
| 5 runtime abstraction | Local subprocess, OpenAI Responses, NOOA, explicit routing | Real local adapter tests, mocked hosted API contract, preserved NOOA tests; no paid/live API validation |
| 6 HPC | Local process supervision, Slurm submit/status/wait/cancel, resource/module/container settings, accounting and saved receipts | Real local process tests; fake Slurm transport tests; Discover run pending |
| 7 reusable science | Numeric comparisons, weighted conservation, diagnostics/suites, bias/RMSE, distributions, aligned time series, bootstrap intervals, NetCDF input, maps/profiles | Finite synthetic data and NetCDF/plot integration tests; physical interpretation and acceptance thresholds site-owned |
| 8–10 GEOS plugin/capabilities | Inspect/build/run/profile/benchmark/optimize/validate/diagnose, federation registry, retained NOOA specialists, target-limited patches | Full synthetic worktree lifecycle and inherited GEOS regression suite |
| 11 flagship modernization | Baseline → profile → proposal → candidate → three validation families/performance → promotion or replan | Synthetic baseline/candidate measured locally; actual GEOS GPU target not yet measured |
| 12–14 experiments and worktrees | Isolated source, policy and commit records, patch diff, build/run/profile logs, fresh fields, repeated timings, evaluation ledger and best/latest pointers | Source preservation, rejection, hash verification and restart tests |
| 15 evaluators | Registered software, numerical, science and performance evaluators; all constraints required | Invalid candidate cannot be promoted; missing/invalid evidence fails closed |
| Other model examples | ECCO state-estimation, LIS land, ISSM ice and ModelE climate toy capabilities; two-plugin example | Contract/orchestration examples only, not upstream models |

## Small model-independent example

`atom demo` demonstrates a measured baseline, rejection of a fast incorrect candidate, promotion of a correct candidate, durable checkpoints, and resume without re-execution. Its three source candidates are prepared, and it requires no GEOS, GPU or API key. It uses Core, Controller, HPC and Science directly. See QUICKSTART.md for the runnable walkthrough.

## Production acceptance still required

1. On Discover, supply and validate actual allocation/partition/GPU settings, modules, GEOS federation, baselibs, compiler flags and input/restart datasets.
2. Run baseline and candidate workloads on matched, documented configurations using synchronized application timing; retain repeated measurements and profiler output.
3. Have domain-approved numerical and scientific policies for the intended experiment. Exercise representative resolutions/decompositions, restart reproducibility, long-run drift and relevant conservation budgets.
4. Validate scheduler cancellation/accounting and restart recovery against the real site's Slurm configuration.
5. Exercise configured hosted/local model providers with authorized credentials and provider-side limits if autonomous proposals are desired.

No synthetic result satisfies these production checks. This is an implemented and locally tested framework release, not a claim that GEOS has already achieved 3x GPU speedup or scientific certification. Full arbitrary natural-language scientific experiment design, production Phase II adapters, data/observations/assimilation services and UI remain extension work; the supplied plan defers those repositories.

## Post-release agent planning on main

`RuntimePlanner` now connects the controller to a configured Agents runtime and
feeds recent experiment results/evaluations back into task-graph proposals. Plans
and stop requests are recorded with reported usage, then checked against the DAG
contract, capability registry and execution policy. A local subprocess test covers
rejection, restart and revision; a real NOOA strategy is tested with a fake provider.
This interface is available through Python and the CLI `--planner-config` option.
CLI runtime settings are persisted with the goal and restored on resume. Provider billing and live planning quality remain
subject to the boundaries in [Usage](USAGE.md#agent-driven-planning-python-api).
