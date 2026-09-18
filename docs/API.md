# nexus-atom-controller Python API

Public definitions below are generated from the shipped source. See USAGE.md and the README for runnable setup, semantics and limits. Contracts inherit strict extra-field rejection and finite-number validation where declared. Source links include the implementation for details.

## `nexus_atom_controller.cli`

Model-independent CLI; plugins own configuration, workflows and criteria.

### `main`

[Source](../src/nexus_atom_controller/cli.py#L16)

```python
def main(argv=None): ...
```

## `nexus_atom_controller.discovery`

### `discover_plugins`

[Source](../src/nexus_atom_controller/discovery.py#L6)

```python
def discover_plugins(): ...
```

### `PluginPlanner`

[Source](../src/nexus_atom_controller/discovery.py#L15)

```python
class PluginPlanner(Planner):
    def __init__(self, plugin): ...
    async def plan(self, goal, history, registry): ...
```

## `nexus_atom_controller.engine`

Observe/plan/execute/evaluate/learn loop with explicit failure boundaries.

### `PlanningResult`

[Source](../src/nexus_atom_controller/engine.py#L29)

Untrusted proposal plus runtime accounting, recorded before Plan validation.

```python
class PlanningResult(Contract):
    proposal: dict | None
    rationale: str
    runtime: str
    usage: Usage = Usage()
    evidence: dict = {}
```

### `Planner`

[Source](../src/nexus_atom_controller/engine.py#L39)

```python
class Planner(ABC):
    async def plan(self, goal: Goal, history: tuple[Experiment, ...], registry: CapabilityRegistry) -> Plan | PlanningResult | None: ...
    async def plan_with_budget(self, goal, history, registry, remaining: Budget): ...
```

### `SequencePlanner`

[Source](../src/nexus_atom_controller/engine.py#L51)

```python
class SequencePlanner(Planner):
    def __init__(self, plans: list[Plan]): ...
    async def plan(self, goal, history, registry): ...
```

### `Controller`

[Source](../src/nexus_atom_controller/engine.py#L60)

```python
class Controller():
    def __init__(self, registry: CapabilityRegistry, planner: Planner, store: Store, budget: Budget | None=None, *, allowed_capabilities: set[str] | None=None): ...
    async def run(self, goal: Goal, *, recover_interrupted: bool=False) -> dict: ...
```

## `nexus_atom_controller.examples.toy`

Offline optimization lab: measure, reject a wrong answer, accept a correct one.

This uses prepared candidates, actual Python execution and application timings.
It demonstrates software orchestration, not Earth-system science or LLM reasoning.

### `Measure`

[Source](../src/nexus_atom_controller/examples/toy.py#L56)

```python
class Measure(Capability):
    async def execute(self, task, context): ...
```

### `Correctness`

[Source](../src/nexus_atom_controller/examples/toy.py#L100)

```python
class Correctness(Evaluator):
    async def evaluate(self, goal, results, directory): ...
```

### `Performance`

[Source](../src/nexus_atom_controller/examples/toy.py#L129)

```python
class Performance(Evaluator):
    def __init__(self, store): ...
    async def evaluate(self, goal, results, directory): ...
```

### `ToyPlugin`

[Source](../src/nexus_atom_controller/examples/toy.py#L156)

```python
class ToyPlugin(Plugin):
    def __init__(self, store): ...
    def capabilities(self): ...
    def evaluators(self): ...
```

### `ToyPlanner`

[Source](../src/nexus_atom_controller/examples/toy.py#L169)

```python
class ToyPlanner(Planner):
    async def plan(self, goal, history, registry): ...
```

### `run_demo`

[Source](../src/nexus_atom_controller/examples/toy.py#L200)

```python
async def run_demo(root: Path, *, resume=False, pause_after: int | None=None): ...
```

## `nexus_atom_controller.planner_config`

Validated, credential-free CLI configuration for optional proposal runtimes.

### `PlannerConfig`

[Source](../src/nexus_atom_controller/planner_config.py#L12)

```python
class PlannerConfig(Contract):
    runtime: Literal['local', 'nooa', 'openai']
    model: str | None = None
    argv: tuple[str, ...] = ()
    capability_guidance: dict = Field(default_factory=dict)
    history_limit: int = Field(default=5, gt=0)
    max_output_tokens: int = Field(default=4096, gt=0)
    timeout_seconds: float = Field(default=120, gt=0, allow_inf_nan=False)
    def valid_backend(self): ...
    def create(self, directory: Path) -> RuntimePlanner: ...
```

### `bind_planner_config`

[Source](../src/nexus_atom_controller/planner_config.py#L58)

Persist the runtime choice and reuse it on resume; never silently replace it.

```python
def bind_planner_config(store, goal, supplied: PlannerConfig | None, *, explicit_plans=False): ...
```

## `nexus_atom_controller.planning`

Optional runtime-backed goal decomposition without provider imports in the engine.

### `RuntimePlanner`

[Source](../src/nexus_atom_controller/planning.py#L10)

Ask an AgentRuntime for a Plan; the controller validates and executes it.

capability_guidance supplies plugin-specific parameter conventions. History is
bounded by experiment count; source files and artifact contents are not read.

```python
class RuntimePlanner(Planner):
    def __init__(self, runtime, directory: Path, *, capability_guidance: dict | None=None, history_limit: int=5, max_output_tokens: int=4096, timeout_seconds: float=120): ...
    async def plan(self, goal, history, registry): ...
    async def plan_with_budget(self, goal, history, registry, remaining): ...
```

## `nexus_atom_controller.reports`

Deterministic reports generated before sealing; never an alternative verdict.

### `write_experiment_report`

[Source](../src/nexus_atom_controller/reports.py#L17)

Write reserved report files for an unsealed experiment.

The engine includes these files in the artifact snapshot before seal journaling.
Recovery may regenerate them only while an experiment is still unsealed.

```python
def write_experiment_report(goal: Goal, experiment: Experiment, directory: Path) -> None: ...
```

## `nexus_atom_controller.service`

Local read-only inspection API. Execution stays in the controlled CLI process.

### `serve`

[Source](../src/nexus_atom_controller/service.py#L11)

```python
def serve(root: Path, host='127.0.0.1', port=8765): ...
```

## `nexus_atom_controller.store`

Append-only evidence, journaled sealing and transactional control-plane state.

### `Store`

[Source](../src/nexus_atom_controller/store.py#L16)

```python
class Store():
    def __init__(self, root: Path): ...
    def close(self): ...
    def lock(self): ...
    def goal(self, goal: Goal) -> dict: ...
    def load_goal(self, goal_id: str) -> Goal: ...
    def checkpoint(self, goal: Goal, state: dict, *, event: Event | None=None): ...
    def emit(self, event: Event): ...
    def directory(self, experiment_id: str) -> Path: ...
    def snapshot(self, experiment_id: str) -> tuple[Artifact, ...]: ...
    def recorded_results(self, goal_id: str, experiment_id: str) -> tuple[TaskResult, ...]: ...
    def seal(self, experiment: Experiment): ...
    def reconcile_seals(self, goal_id: str) -> tuple[str, ...]: ...
    def history(self, goal_id: str) -> tuple[Experiment, ...]: ...
    def events(self) -> list[dict]: ...
```
