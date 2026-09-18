# Audit against the submitted plan

Snapshot: 2026-09-18. This is a completion audit, not a declaration that every
requirement is finished. The supplied plan ends partway through section 15.
The repository layouts and code fragments are interpreted as architectural
examples; the behavior and named public concepts remain the requirements.

Evidence base: the six-package workspace through GEOS 0a87aa6 (agent migration, optional
specialist profiles, regression comparison, debug repair, proposal feedback, and accepted-candidate continuation), Controller ab80d0b plus parent-context delivery, Agents ada79d8,
Science 7e52eec, Core 5669d9a, and HPC e076bc8. The complete local suite passes 145 tests,
with the documented optional NetCDF warning. Plot tests cover aligned 1-D/2-D
rendering, failed-validation retention, sealing, and modified-artifact detection.
Profile tests cover repository/objective selection, scoped source/timing evidence,
citation rejection, and persisted configuration across session resume. The migrated
agent source history and five namespaced release tags are verified independently
of the old repository. Regression cases cover valid prepared patches, repeated-source
runs, wrong numerical outputs, failing baseline/candidate checks, and resume without
re-execution. Debug cases include a valid repair, an unreproduced or unrelated failure,
a bad repair, a protected harness edit, a changed reference, wrong scientific output,
and a scripted runtime retry using prior failure evidence. Public CLI run/resume were also exercised on the synthetic fixture.
Proposal feedback tests verify that the next attempt receives the exact failed patch,
large proposals are explicitly truncated, and hashes identify full sealed artifacts.
Continuation tests verify resume, accepted-parent reconstruction after rejection,
fixed original baseline measurements, cumulative file changes, corruption rejection,
and rejection of changed original commits. Timings in that test are scripted inputs,
not measured GEOS performance.
Passing tests below establish only the behavior they exercise.

## Architectural principles (section 1)

| Requirement | Current evidence | Assessment |
|---|---|---|
| Goals are primary | Core `Goal`; Controller `run`, CLI targets and constraints | Implemented. Natural-language-only policy inference remains unavailable. |
| Agents propose; evaluators decide | Engine resolves registered constraints and checks all targets; rejection tests | Implemented for configured trusted capabilities/evaluators. No process security boundary claimed. |
| Model capabilities; independent controller | Plugin registry, entry-point discovery; no GEOS imports in engine | Implemented. |
| Interchangeable agent frameworks | Agents `AgentRuntime`, NOOA/OpenAI/local adapters; Controller RuntimePlanner | Implemented interfaces and fake-provider/local integration tests; live provider quality unverified. |
| Models are plugins | GEOS and ECCO/LIS/ISSM/ModelE entry points | GEOS integration framework plus synthetic examples. Production secondary models deferred explicitly by section 2. |
| Immutable experimental evidence | Hash-checked metadata/artifacts; journaled seal; corruption and child-process crash tests | Integrity checks and recovery implemented. Mutable local storage is not tamper-proof. |
| Structured authoritative state | SQLite goal checkpoints, events, ledger, history feedback | Implemented; provider-call billing is not exactly-once across crashes. |
| HPC first-class | HPC JobSpec/Job/JobStatus, resource/environment configuration, Slurm adapter | Local execution verified; real Discover acceptance outstanding. |
| Scientific validation first-class | Science contracts/diagnostics; GEOS numerical/science gates | Generic mechanisms implemented; actual GEOS acceptance criteria and representative datasets still needed. |
| Software and scientific workflows | GEOS modernization and synthetic multi-plugin example | Framework support demonstrated; autonomous physical experiment design and coupled production runs not demonstrated. |

## Repositories and public contracts (sections 2–7)

| Requirement | Authoritative implementation | Assessment |
|---|---|---|
| Six Phase I repositories; packaging and documentation | Six public repositories listed in REPOSITORIES.md, README/USAGE/API and CI in each | Delivered and pushed; matching v0.1.0 tags plus documented later main changes. |
| Phase II model and later data/observations/assimilation/UI repositories | Plan explicitly says not to create all now; examples in GEOS | Deferred by the specification, not claimed implemented. |
| Goal, Plan, Task, TaskGraph | Core `contracts.py` | Implemented; DAG uniqueness/dependency/cycle checks. |
| Capability, CapabilityRegistry, Plugin | Core `contracts.py` | Implemented; unique registered names. |
| Experiment, Artifact, Evaluation, Evaluator | Core `contracts.py` | Implemented; artifact hashes and required evaluator identities. |
| ResourceRequest, Budget, Event, Provenance | Core `contracts.py` | Implemented; accounting completeness depends on backend. |
| Observe/plan/execute/evaluate/learn/replan | Controller `engine.py`, `planning.py`, `store.py` | Feedback loop implemented; learning is structured experiment feedback, not model training. |
| Scheduler, executor, registry, task graph | Controller engine plus Core registry/DAG | Sequential dependency scheduling; not distributed parallel scheduling. |
| State, memory, experiments, checkpoints, recovery | Store/history, seal journal, explicit interruption recovery | Implemented and failure-tested; external job reconciliation still requires site verification. |
| Budgets, policy, tracing | Engine budgets/allowed capabilities, structured events | Implemented application policy; hard financial/resource isolation not guaranteed. |
| CLI and service | `cli.py`, `service.py` | CLI run/resume/status/ledger/events/demo and read-only loopback service implemented. |
| AgentRuntime.execute and routing | Agents `runtime.py`; Controller `planner_config.py` | NOOA/OpenAI/local and explicit router present. Credentials supplied externally. |
| allocate, submit, status, wait, cancel, run | HPC `scheduler.py`, `slurm.py` | Implemented. allocate submits a payload-bearing job, not a detached interactive allocation. |
| stdout, stderr, resources, usage | HPC scheduler/backend methods | Implemented. Local resources is synchronous, Slurm resources asynchronous; interface harmonization remains useful. |
| Discover, environments, modules, containers, monitoring, accounting | HPC backends/configuration; GEOS DISCOVER.md | Configurable infrastructure and template delivered. Allocation/module/GPU settings and real scheduler behavior unverified. |
| ScientificMetric, ScientificDiagnostic, ScientificComparison, ValidationSuite | Science `fields.py` | Implemented with explicit finite data and policy. |
| PlotArtifact, DatasetArtifact, UncertaintyEstimate | Science `io.py`, `fields.py`, `statistics.py` | Implemented; uncertainty utility is seeded IID bootstrap, not a general climate uncertainty model. |
| compare_fields, calculate_bias, calculate_rmse, calculate_conservation | Science `fields.py` | Implemented; aligned fields and explicit weights required. |
| compare_distributions, compare_timeseries | Science `statistics.py` | Implemented and synthetic tests; scientific appropriateness is policy-owned. |
| generate_maps, generate_profiles, generate_diagnostics | Science `io.py` | Implemented. Maps are grid-index views, not geospatial regridding. |

## GEOS and flagship workflow (sections 8–11)

| Requirement | Evidence | Assessment |
|---|---|---|
| GEOS federation registry (GEOSgcm, GEOSfvdycore, MAPL, others) | Preserved `geos_agents.registry`, mepo import, isolated federation tests | Generic federation mechanism implemented, not separate hard-coded registry modules per repository. |
| build/run/profile/benchmark/validate/optimize/diagnose capabilities | `nexus_atom_geos.plugin` | Registered. In debug workflows, diagnose records the reproduced failure and reference/protected-file policy for repair; otherwise it performs numerical/science checks. General causal diagnosis remains unproven. |
| Architecture/Fortran/CUDA/build/debugging/performance/science specialists | Retained RepositoryAgent, ArchitectureAgent, CUDAAgent, ValidationAgent, PerformanceAgent, GEOSAgent | Built-in roles plus optional repository/objective ProfileSpecialistAgent reviews are implemented with explicit scoping and saved configuration. Fortran/build/debugging expertise may be configured as profiles; proven domain coverage for every named role is not established. |
| Atmosphere/dynamics/conservation diagnostics | Generic fields and conservation; configurable GEOS suite | No domain-complete atmosphere/dynamics diagnostic library or approved GEOS science policy demonstrated. |
| GPU-port and optimization workflows | `modernization_plan`, aliases | Shared lifecycle implemented; aliases do not prove a distinct GPU-port strategy. |
| Regression and debug workflows | `regression_plan`, `debug_plan` | Regression now compares baseline/candidate build, required software checks, numerical and science outputs using a prepared patch or unchanged-source repeated run. Debug now requires a specified failure, records diagnostics, applies a prepared/runtime repair, and verifies the same reproducer plus a hash-verified reference. Real GEOS debugging remains unverified. |
| Inspect, baseline build/run/benchmark/profile | Synthetic modernization test and recorded artifacts | Implemented. |
| Identify bottlenecks and generate/select hypotheses | Runtime receives source, timings, profiler excerpts and history | Evidence delivery implemented; model interpretation/selection quality unverified. No universal profiler parser. |
| Modify, build, run; debug after failure | Checked patches; task-failure feedback; synthetic compile-fail/repair integration test | Candidate repair loop demonstrated with scripted local proposals; live scientific debugging unverified. |
| Numerical/science/performance evaluation and promotion | Registered gates and best/latest pointers | Implemented for configured policies. |
| Reprofile when target unmet | Candidate profiling added after candidate benchmark; output enters later task-result feedback | Baseline and candidate profiling available. Default trials start from original source. Opt-in best-valid continuation reconstructs the accepted candidate from verified cumulative proposals and supplies its recorded profile/benchmark/validation evidence. Original baseline is remeasured each attempt. |
| Bare `atom run --system geos 'Achieve >=3x...'` | CLI requires site config or demo and explicit target | Not supported literally. Site configuration and acceptance policy cannot be safely guessed. |
| Actual >=3x GEOS GPU acceleration with scientific validity | No matched production GEOS experiment | Not demonstrated; Discover validation remains deferred per user direction. |

## Experiments, ledger, worktrees and evaluators (sections 12–15)

| Requirement | Evidence | Assessment |
|---|---|---|
| Experiment ID, goal, parent, hypothesis, tasks, code changes, artifacts, evaluation | Core Experiment; GEOS patch/proposal artifacts; Store | Implemented with code changes as artifacts rather than a separate contract field. |
| metadata.json; source commits/diff; build/run stdout/stderr | Sealed metadata; GEOS evidence/source-commits.json and patch files; jobs logs | Implemented with a different directory arrangement. |
| Profile JSON, timing CSV, numerical/science metrics, plots, evaluation JSON | Profile JSON, per-phase timing CSV; automatic controller Markdown/evaluation JSON/metric CSV; field data and optional Science plots | JSON/CSV/report exports implemented and sealed for new attempts; selected 1-D/2-D scientific comparison plots are generated during GEOS validation and sealed with the experiment. Model-specific selection and geographic diagnostics remain site-owned. |
| Experiment ledger as planner memory | Store history, CLI ledger, structured feedback | Implemented; demo table provides readable decisions. |
| Isolated experiment workspaces and source preservation | GEOSWorkspace/PatchManager, clean/stale/path checks, original-source regression tests | Implemented. |
| best_valid_candidate, latest_candidate, baseline | Controller checkpoints and promotion tests | Implemented; GEOS can opt into verified reconstruction of the selected parent. Default behavior does not change source. |
| Software compilation/tests/sanitizers | GEOS software_checks; geos.test/geos.sanitize; separate geos.tests/geos.sanitizers evaluators and software evidence requirements | Implemented as explicit configurable stages for both phases. Synthetic success/failure/omission tests pass; actual site sanitizer coverage remains unverified. Empty configuration means those checks were not required. |
| Numerical checkpoint comparison/tolerances/reproducibility | Field comparison, bitwise/tolerance options | Partial: generic arrays supported; actual GEOS restart/checkpoint reproducibility policy and experiments absent. |
| Scientific evaluator tree | Submitted section ends after `Science` | Earlier numerical/science/performance requirements implemented generically; no additional missing text assumed. |

## Remaining work that can proceed locally

1. Evaluate the implemented debug workflow against expert-curated real failures and approved reference/acceptance policies; synthetic reproduction and repair checks are implemented.
2. Exercise the newly implemented test/sanitizer stages with the actual model suites and instrumented commands when site tooling is available.
3. Extend configured comparison plots with model-specific diagnostics and appropriate geographic views when domain requirements are available.
4. Exercise opt-in best-valid continuation on representative GEOS modernization tasks. Local synthetic tests verify accumulation, resume, rejection, corrupted evidence, and original-source preservation; real model acceptance remains unverified.
5. Extend meaningful model diagnostics and examples without claiming untested physical validity.

Discover execution, model-specific acceptance criteria, live provider assessment,
and comparative research results require additional external evidence. They are
not inferred from local tests or from successful GitHub CI. The goal remains open.
