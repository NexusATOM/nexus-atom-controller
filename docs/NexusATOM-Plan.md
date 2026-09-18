I would modify the architecture after reading the official Earth Modeling Nexus description. The big-picture goal is broader than an autonomous GEOS development framework.

NASA describes Nexus as a **unified modeling framework** spanning process models, global Earth-system models, data assimilation, scientific computing, observations, advanced analysis/prediction, and ultimately actionable products. Its initial core modeling portfolio explicitly includes **GEOS, ModelE, LIS, ISSM, and ECCO**, while Scientific Computing provides HPC, code modernization, data interfaces, visualization, and AI/ML capabilities. ([NASA Science][1])

That suggests **Nexus-ATOM should become the autonomous software/science orchestration layer across Earth Modeling Nexus**, not merely a collection of model-specific coding agents.

Below is the plan I would give Codex as the project specification.

---

# Nexus-ATOM

## Autonomous Technology for Orchestrated Modeling

### Project vision

**Nexus-ATOM is an extensible, goal-driven agentic framework for autonomous development, execution, integration, optimization, and scientific evaluation of Earth-system models.**

ATOM sits above individual modeling systems and agent runtimes. A scientist or engineer expresses a high-level objective; ATOM decomposes that objective, discovers appropriate capabilities, delegates work to specialized agents, executes workflows on computing resources, evaluates results against deterministic software and scientific criteria, and iterates until the objective is achieved or an explicit stopping condition is reached.

The long-term interaction should look like:

```bash
atom run \
  "Optimize GEOS for GPUs to achieve at least 3x speedup
   while preserving numerical and scientific validity."
```

But eventually also:

```bash
atom run \
  "Run GEOS and ECCO experiments to investigate
   atmosphere-ocean response to X."
```

or:

```bash
atom run \
  "Assess the impact of these new observations across
   the appropriate Nexus modeling systems."
```

The first case is autonomous software engineering.

The second is autonomous model orchestration.

The third begins to approach autonomous Earth-system science.

That trajectory aligns well with Nexus's stated emphasis on integrating NASA's modeling capabilities and Scientific Computing's role in modernization, data interfaces, AI/ML, simulations, and uncertainty characterization. ([NASA Science][1])

---

# 1. Architectural principles

Codex should preserve these from the beginning.

**1. Goals, not prompts, are the primary abstraction.**

The user specifies what they want accomplished.

**2. Agents propose; evaluators decide.**

An LLM cannot declare scientific or software success.

**3. Models expose capabilities.**

The central controller should not contain GEOS/ECCO/LIS-specific logic.

**4. Agent frameworks are execution backends.**

ATOM should be able to use NOOA, coding agents, local models, hosted models, and future frameworks.

**5. Scientific models are plugins.**

GEOS, ECCO, LIS, ISSM, ModelE, etc. implement common ATOM contracts.

**6. Experiments are immutable evidence.**

Every autonomous attempt produces a reproducible experiment record.

**7. State is structured.**

Conversation history is not authoritative project state.

**8. HPC is a first-class subsystem.**

Slurm, allocations, environments, modules, GPUs, job monitoring, and resource budgets cannot be incidental shell commands.

**9. Scientific validation is first-class.**

Build success and unit tests are insufficient for scientific software.

**10. ATOM should support both software-development workflows and scientific workflows.**

This is the most important expansion from our previous design.

---

# 2. Repository ecosystem

I recommend starting with **six repositories**.

```text
Nexus-ATOM
│
├── nexus-atom-core
│
├── nexus-atom-controller
│
├── nexus-atom-agents
│
├── nexus-atom-hpc
│
├── nexus-atom-science
│
└── nexus-atom-geos
```

Then:

```text
Phase II
│
├── nexus-atom-ecco
├── nexus-atom-lis
├── nexus-atom-issm
└── nexus-atom-modele
```

Those five correspond directly to the core model capabilities NASA currently identifies for the initial Nexus integration effort. ([NASA Science][2])

Later:

```text
nexus-atom-data
nexus-atom-observations
nexus-atom-assimilation
nexus-atom-ui
```

I would **not create all of those now**.

---

# 3. `nexus-atom-core`

### Purpose

Define the ATOM protocol.

It should have almost no operational intelligence and no dependencies on GEOS, Slurm, NOOA, etc.

```text
nexus-atom-core/
├── src/nexus_atom_core/
│   ├── goal.py
│   ├── task.py
│   ├── plan.py
│   ├── capability.py
│   ├── plugin.py
│   ├── artifact.py
│   ├── experiment.py
│   ├── evaluation.py
│   ├── evaluator.py
│   ├── event.py
│   ├── budget.py
│   ├── resource.py
│   ├── provenance.py
│   └── exceptions.py
├── tests/
├── pyproject.toml
└── README.md
```

Core types:

```python
Goal
Plan
Task
TaskGraph

Capability
CapabilityRegistry
Plugin

Experiment
Artifact
Evaluation
Evaluator

ResourceRequest
Budget

Event
Provenance
```

Example:

```python
Goal(
    objective="maximize_gpu_speedup",
    target={
        "speedup": 3.0,
    },
    constraints=[
        "build_passes",
        "numerical_validation_passes",
        "science_validation_passes",
    ],
)
```

---

# 4. `nexus-atom-controller`

This is the **autonomous control plane**.

```text
nexus-atom-controller/
├── planner/
├── orchestrator/
├── scheduler/
├── executor/
├── registry/
├── task_graph/
├── state/
├── memory/
├── experiments/
├── checkpoints/
├── recovery/
├── budgets/
├── policy/
├── tracing/
├── cli/
└── service/
```

It implements:

```text
                 GOAL
                   │
                   ▼
                OBSERVE
                   │
                   ▼
                 PLAN
                   │
                   ▼
                EXECUTE
                   │
                   ▼
               EVALUATE
                   │
          ┌────────┴────────┐
          │                 │
      goal unmet         goal met
          │                 │
          ▼                 ▼
        LEARN             FINISH
          │
          ▼
        REPLAN
          │
          └──────► EXECUTE
```

Core loop:

```python
while True:

    state = await observe()

    if goal.satisfied(state):
        return finish()

    if budget.exhausted():
        return stop("budget_exhausted")

    plan = await planner.plan(
        goal=goal,
        state=state,
        capabilities=registry.capabilities(),
    )

    task = scheduler.select(plan)

    result = await executor.execute(task)

    evaluation = await evaluate(result)

    state.record(
        task,
        result,
        evaluation,
    )

    if evaluation.failed:
        await recovery.respond(evaluation)
```

The controller must know **nothing about GEOS compilation**.

---

# 5. `nexus-atom-agents`

This repository abstracts agent runtimes and models.

```text
nexus-atom-agents/
├── runtimes/
│   ├── base.py
│   ├── nooa.py
│   ├── openai.py
│   └── local.py
│
├── routing/
│   ├── router.py
│   ├── capability.py
│   └── policy.py
│
├── context/
├── tools/
├── prompts/
└── tests/
```

Contract:

```python
class AgentRuntime:

    async def execute(
        self,
        task: Task,
        context: AgentContext,
        capabilities: list[Capability],
    ) -> AgentResult:
        ...
```

This lets ATOM do:

```text
                  ATOM
                   │
             Agent Router
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
     NOOA       Coding       Local
                 Agent       Model
       │           │           │
       ▼           ▼           ▼
   Model A      Model B      Model C
```

Your `labs-OO-Agents` work can therefore become one runtime/backend rather than something ATOM forks and permanently couples itself to.

---

# 6. `nexus-atom-hpc`

Scientific computing is explicitly an enabling capability within Nexus, including HPC, analytics, data services, visualization, modernization, and AI/ML. That warrants a dedicated ATOM subsystem rather than burying Slurm calls inside GEOS agents. ([NASA Science][1])

```text
nexus-atom-hpc/
├── scheduler/
│   ├── base.py
│   ├── slurm.py
│   └── local.py
│
├── systems/
│   ├── base.py
│   └── discover.py
│
├── jobs/
├── environments/
├── resources/
├── modules/
├── containers/
├── monitoring/
├── accounting/
└── tests/
```

Capabilities:

```python
allocate()
submit()
status()
wait()
cancel()

run()

stdout()
stderr()

resources()
usage()
```

Resource model:

```python
ResourceRequest(
    nodes=1,
    cpus=12,
    gpus=1,
    gpu_type="A100",
    memory="128GB",
    walltime="01:00:00",
)
```

---

# 7. `nexus-atom-science`

This is the biggest change I would make from our earlier architecture.

Scientific evaluation should **not live inside GEOS**.

GEOS can provide model-specific diagnostics, but ATOM needs reusable scientific analysis infrastructure.

```text
nexus-atom-science/
├── evaluation/
├── diagnostics/
├── comparison/
├── statistics/
├── visualization/
├── uncertainty/
├── provenance/
├── datasets/
└── tests/
```

Common concepts:

```python
ScientificMetric
ScientificDiagnostic
ScientificComparison
ValidationSuite
PlotArtifact
DatasetArtifact
UncertaintyEstimate
```

Generic operations:

```python
compare_fields()
calculate_bias()
calculate_rmse()
calculate_conservation()
compare_distributions()
compare_timeseries()
generate_maps()
generate_profiles()
generate_diagnostics()
```

Model plugins supply model-specific meaning.

---

# 8. `nexus-atom-geos`

GEOS becomes ATOM's first model plugin.

```text
nexus-atom-geos/
│
├── plugin.py
│
├── config/
│
├── repositories/
│   ├── registry.py
│   ├── geosgcm.py
│   ├── geosfvdycore.py
│   ├── mapl.py
│   └── ...
│
├── capabilities/
│   ├── build.py
│   ├── run.py
│   ├── profile.py
│   ├── benchmark.py
│   ├── validate.py
│   ├── optimize.py
│   └── diagnose.py
│
├── agents/
│   ├── architecture.py
│   ├── fortran.py
│   ├── cuda.py
│   ├── build.py
│   ├── debugging.py
│   ├── performance.py
│   └── science.py
│
├── evaluators/
│   ├── build.py
│   ├── numerical.py
│   ├── performance.py
│   └── scientific.py
│
├── diagnostics/
│   ├── atmosphere.py
│   ├── dynamics.py
│   ├── conservation.py
│   └── plots.py
│
├── workflows/
│   ├── gpu_port.py
│   ├── optimize.py
│   ├── regression.py
│   └── debug.py
│
└── knowledge/
```

---

# 9. Model plugin contract

This contract is extremely important.

GEOS should implement something like:

```python
class GEOSPlugin(ModelPlugin):

    name = "geos"

    def capabilities(self):
        return [
            Build(),
            Run(),
            Profile(),
            Benchmark(),
            Validate(),
            Optimize(),
        ]
```

ECCO later implements:

```python
class ECCOPlugin(ModelPlugin):

    name = "ecco"

    def capabilities(self):
        return [
            Build(),
            Run(),
            EstimateState(),
            Validate(),
            DiagnoseOcean(),
        ]
```

LIS could expose:

```text
build
run
land_simulation
hydrology_diagnostics
validation
```

ISSM:

```text
build
run
ice_simulation
sea_level_projection
validation
```

ModelE:

```text
build
run
climate_simulation
diagnostics
validation
```

The controller doesn't care about the implementation.

---

# 10. Capabilities are more important than agents

This is another adjustment I'd make.

Don't let this become:

```text
GEOSAgent
ECCOAgent
LISAgent
```

Instead expose:

```text
GEOS
 ├── build
 ├── run
 ├── profile
 ├── optimize
 ├── validate
 └── forecast
```

Agents are one way of implementing capabilities.

A capability can be:

```text
deterministic Python
shell command
workflow
agent
external service
another ATOM capability
```

For example:

```python
class BuildGEOS(Capability):

    async def execute(self, request):
        # deterministic
```

versus:

```python
class OptimizeGEOS(Capability):

    agent = GEOSOptimizationAgent
```

That distinction will save you architectural pain later.

---

# 11. First flagship workflow: autonomous GEOS modernization

This should be the first thing Codex builds toward.

Input:

```bash
atom run \
  --system geos \
  "Achieve >=3x GPU acceleration while preserving
   numerical and scientific validity."
```

Internally:

```text
                       GOAL >=3×
                           │
                           ▼
                    Inspect repositories
                           │
                           ▼
                     Build baseline
                           │
                           ▼
                    Benchmark CPU/GPU
                           │
                           ▼
                        Profile
                           │
                           ▼
                 Identify bottlenecks
                           │
                           ▼
                 Generate hypotheses
                           │
                           ▼
                   Select experiment
                           │
                           ▼
                      Modify code
                           │
                           ▼
                         Build
                           │
                      ┌────┴────┐
                    FAIL       PASS
                      │          │
                    Debug       Run
                                 │
                            ┌────┴────┐
                          FAIL       PASS
                            │          │
                          Debug    Validate
                                       │
                       ┌───────────────┼──────────────┐
                       ▼               ▼              ▼
                    Numeric          Science      Performance
                       │               │              │
                       └───────────────┼──────────────┘
                                       ▼
                                    Evaluate
                                       │
                                best candidate?
                                   │       │
                                  NO      YES
                                   │       │
                                 reject  promote
                                           │
                                      target >=3×?
                                       │        │
                                      NO       YES
                                       │        │
                                   reprofile   DONE
                                       │
                                       └── LOOP
```

This formalizes the process you've already been manually exercising during the GEOS GPU modernization work.

---

# 12. Experiment model

Every attempt becomes:

```python
Experiment(
    id="E0042",

    goal="G0001",
    parent="E0037",

    hypothesis=
        "Repeated state-boundary pressure calculations "
        "are limiting GPU performance.",

    tasks=[...],

    code_changes=[...],

    artifacts=[...],

    evaluation=...,
)
```

Directory:

```text
E0042/
├── metadata.json
│
├── source/
│   ├── commits.json
│   └── diff.patch
│
├── build/
│   └── build.log
│
├── execution/
│   ├── stdout.log
│   └── stderr.log
│
├── performance/
│   ├── profile.json
│   ├── timings.csv
│   └── plots/
│
├── numerical/
│   ├── comparison.json
│   └── plots/
│
├── science/
│   ├── metrics.json
│   └── plots/
│
└── evaluation.json
```

---

# 13. Experiment ledger

Structured state:

| Experiment | Change         | Speedup | Numerics | Science | Status   |
| ---------- | -------------- | ------: | -------- | ------- | -------- |
| E001       | CPU baseline   |   1.00× | PASS     | PASS    | baseline |
| E002       | initial GPU    |   1.76× | PASS     | PASS    | valid    |
| E003       | optimization A |   2.03× | PASS     | PASS    | promoted |
| E004       | optimization B |   2.31× | FAIL     | —       | rejected |
| E005       | corrected B    |   2.26× | PASS     | PASS    | promoted |

This becomes the planner's memory.

Not:

```text
"Earlier in the conversation we tried..."
```

---

# 14. Git/worktree architecture

Every experiment gets an isolated workspace:

```text
ATOM workspace

baseline/
│
├── GEOSgcm
├── GEOSfvdycore
└── MAPL

experiments/
├── E0041/
├── E0042/
└── E0043/
```

ATOM maintains:

```python
best_valid_candidate
latest_candidate
baseline
```

Promote only when evaluators approve.

---

# 15. Evaluator architecture

This is central to trustworthy autonomy.

```text
Evaluator
│
├── SoftwareEvaluator
│    ├── compilation
│    ├── tests
│    └── sanitizers
│
├── NumericalEvaluator
│    ├── checkpoint comparison
│    ├── tolerances
│    └── reproducibility
│
├── Science
```

[1]: https://science.nasa.gov/earth-science/earth-modeling-nexus/?utm_source=chatgpt.com "Earth Modeling Nexus - NASA Science"
[2]: https://science.nasa.gov/earth-science/research/enabling-capabilities/?utm_source=chatgpt.com "Enabling Capabilities - NASA Science"
