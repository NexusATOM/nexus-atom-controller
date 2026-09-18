# Add a capability and evaluator

A plugin exposes work; an evaluator independently checks its evidence. The following minimal implementation uses only Core and Controller. Save it as `hello_atom.py` and run it with the installed workspace interpreter:

```python
import asyncio
from pathlib import Path
from nexus_atom_core import (
    Artifact, Capability, CapabilityRegistry, Evaluation, Evaluator, Goal,
    Plan, Plugin, Task, TaskGraph, TaskResult,
)
from nexus_atom_controller import Controller, SequencePlanner, Store

class WriteEvidence(Capability):
    name = "hello.write"
    async def execute(self, task, context):
        path = context.directory / "answer.txt"
        path.write_text("42\n")
        return TaskResult(task_id=task.id, status="succeeded",
                          artifacts=(Artifact.capture(path, context.directory),))

class CheckEvidence(Evaluator):
    name = "correct"
    async def evaluate(self, goal, results, directory):
        passed = (directory / "answer.txt").read_text() == "42\n"
        return Evaluation(evaluator=self.name, passed=passed,
                          evidence=("answer.txt",))

class HelloPlugin(Plugin):
    name = "hello"
    def capabilities(self): return [WriteEvidence()]
    def evaluators(self): return [CheckEvidence()]

async def main():
    registry = CapabilityRegistry()
    registry.register(HelloPlugin())
    goal = Goal(objective="Write the correct answer", constraints=("hello.correct",))
    plan = Plan(hypothesis="Write and independently verify 42",
                graph=TaskGraph(tasks=(Task(capability="hello.write"),)))
    store = Store(Path(".atom/hello"))
    try:
        state = await Controller(registry, SequencePlanner([plan]), store).run(goal)
        print(goal.id, state["status"])
    finally:
        store.close()

asyncio.run(main())
```

`TaskResult.status` means the capability ran. It does not mean the goal succeeded. Returning `outputs={"passed": True}` cannot bypass `CheckEvidence`; only the registered evaluator approves its constraint.

## Add a CLI plugin

Register your factory in `pyproject.toml`:

```toml
[project.entry-points."nexus_atom.plugins"]
hello = "my_package.plugin:HelloPlugin"
```

The CLI factory also needs:

* `from_config(path)` to validate your plugin-specific configuration and return an instance;
* `goal_constraints()` returning fully qualified registry evaluator names;
* async `plan(goal, history, registry)` returning a Core Plan or `None` when no hypotheses remain;
* optional `demo(directory)` to prepare a synthetic example.

Use history as evidence-backed planner memory. Do not infer success from conversation text. Avoid unbounded subprocesses, synchronous long-running work in the event loop, unreported paid calls and implicit network access. Respect `ExecutionContext.remaining`, and produce artifact paths inside the experiment directory.

## Integrate an agent or scheduler

An agent adapter implements `AgentRuntime.execute` and returns a proposal. The consuming capability validates its structure, target files and source hashes before applying it. Do not let the agent supply its own final evaluator verdict.

An HPC adapter implements `Scheduler.submit`, `status` and `cancel`; the base class supplies wait/run helpers. Cancellation must stop external work, and successful submission must never be confused with successful execution. Record stable job receipts for recovery.

Science extensions should require explicit units, alignment, weights and approved thresholds. A generic numerical equality check is not automatically a domain-science acceptance criterion.
