# nexus-atom-controller Python API

Public definitions below are generated from the shipped source. See USAGE.md and the README for runnable setup, semantics and limits. Contracts inherit strict extra-field rejection and finite-number validation where declared. Source links include the implementation for details.

## `nexus_atom_controller.cli`

Model-independent CLI; plugins own configuration, workflows and criteria.

### `main`

[Source](../src/nexus_atom_controller/cli.py#L15)

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

[Source](../src/nexus_atom_controller/engine.py#L28)

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

[Source](../src/nexus_atom_controller/engine.py#L38)

```python
class Planner(ABC):
    async def plan(self, goal: Goal, history: tuple[Experiment, ...], registry: CapabilityRegistry) -> Plan | PlanningResult | None: ...
    async def plan_with_budget(self, goal, history, registry, remaining: Budget): ...
```

### `SequencePlanner`

[Source](../src/nexus_atom_controller/engine.py#L50)

```python
class SequencePlanner(Planner):
    def __init__(self, plans: list[Plan]): ...
    async def plan(self, goal, history, registry): ...
```

### `Controller`

[Source](../src/nexus_atom_controller/engine.py#L59)

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
