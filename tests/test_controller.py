import pytest
from nexus_atom_core import (
    Artifact,
    Budget,
    Capability,
    CapabilityRegistry,
    Evaluation,
    Evaluator,
    Goal,
    Plan,
    Plugin,
    Task,
    TaskGraph,
    TaskResult,
)

from nexus_atom_controller import Controller, SequencePlanner, Store


class Action(Capability):
    name = "test.run"

    def __init__(self):
        self.calls = 0

    async def execute(self, task, context):
        self.calls += 1
        path = context.directory / "evidence.txt"
        path.write_text(str(task.parameters.get("value", 0)))
        return TaskResult(
            task_id=task.id,
            status="succeeded",
            outputs={"passed": True},
            artifacts=(Artifact.capture(path, context.directory),),
        )


class Gate(Evaluator):
    name = "gate"

    async def evaluate(self, goal, results, directory):
        value = float((directory / "evidence.txt").read_text())
        return Evaluation(evaluator="gate", passed=value > 0, metrics={"speedup": value})


class TestPlugin(Plugin):
    __test__ = False
    name = "test"

    def __init__(self):
        self.action = Action()

    def capabilities(self):
        return [self.action]

    def evaluators(self):
        return [Gate()]


def setup(tmp_path, values):
    plugin = TestPlugin()
    registry = CapabilityRegistry()
    registry.register(plugin)
    plans = [
        Plan(
            hypothesis=f"Value {v}",
            graph=TaskGraph(tasks=(Task(capability="test.run", parameters={"value": v}),)),
        )
        for v in values
    ]
    return plugin, registry, SequencePlanner(plans), Store(tmp_path)


@pytest.mark.asyncio
async def test_replan_reject_promote_resume_and_tamper(tmp_path):
    plugin, registry, planner, store = setup(tmp_path, [-1, 1, 3])
    goal = Goal(objective="speed", constraints=("test.gate",), target={"speedup": 3})
    controller = Controller(registry, planner, store)
    state = await controller.run(goal)
    assert state["status"] == "succeeded"
    history = store.history(goal.id)
    assert [e.status for e in history] == ["rejected", "valid", "valid"]
    import json

    reports = [
        json.loads((store.directory(e.id) / "_atom_report/evaluation.json").read_text())
        for e in history
    ]
    assert [report["goal_satisfied"] for report in reports] == [False, False, True]
    assert all(any(a.path == "_atom_report/metrics.csv" for a in e.artifacts) for e in history)
    assert state["best_valid_candidate"] == history[-1].id
    assert (await controller.run(goal))["status"] == "succeeded"
    assert plugin.action.calls == 3
    (store.directory(history[0].id) / "evidence.txt").write_text("99")
    with pytest.raises(ValueError, match="corrupted"):
        await controller.run(goal)
    store.close()


@pytest.mark.asyncio
async def test_budget_does_not_claim_success(tmp_path):
    _, registry, planner, store = setup(tmp_path, [0, 3])
    goal = Goal(objective="speed", constraints=("test.gate",), target={"speedup": 3})
    state = await Controller(registry, planner, store, Budget(max_experiments=1)).run(goal)
    assert state["status"] == "budget_exhausted"
    assert state["best_valid_candidate"] is None
    store.close()


@pytest.mark.asyncio
async def test_interrupted_work_needs_explicit_recovery(tmp_path):
    _, registry, planner, store = setup(tmp_path, [3])
    goal = Goal(objective="speed", constraints=("test.gate",))
    state = store.goal(goal)
    state["active"] = {"id": "interrupted", "plan": planner.plans[0].model_dump(mode="json")}
    store.checkpoint(goal, state)
    assert (await Controller(registry, planner, store).run(goal))["status"] == "interrupted"
    recovered = await Controller(registry, planner, store).run(goal, recover_interrupted=True)
    assert recovered["status"] == "no_more_plans"
    assert store.history(goal.id)[0].status == "interrupted"
    store.close()


@pytest.mark.asyncio
async def test_failed_dependency_blocks_downstream(tmp_path):
    class Failing(Action):
        async def execute(self, task, context):
            raise RuntimeError("build failed")

    plugin = TestPlugin()
    plugin.action = Failing()
    registry = CapabilityRegistry()
    registry.register(plugin)
    plan = Plan(
        hypothesis="failing pipeline",
        graph=TaskGraph(
            tasks=(
                Task(id="a", capability="test.run"),
                Task(id="b", capability="test.run", depends_on=("a",)),
            )
        ),
    )
    store = Store(tmp_path)
    goal = Goal(objective="x", constraints=("test.gate",))
    result = await Controller(registry, SequencePlanner([plan]), store).run(goal)
    assert result["status"] == "no_more_plans"
    history = store.history(goal.id)
    assert len(history[0].results) == 1
    assert not history[0].evaluations[0].passed
    store.close()


@pytest.mark.asyncio
async def test_task_deadline_and_policy(tmp_path):
    import asyncio

    class Slow(Action):
        async def execute(self, task, context):
            await asyncio.sleep(1)

    plugin = TestPlugin()
    plugin.action = Slow()
    registry = CapabilityRegistry()
    registry.register(plugin)
    plan = Plan(
        hypothesis="timeout",
        graph=TaskGraph(tasks=(Task(capability="test.run", timeout_seconds=0.01),)),
    )
    store = Store(tmp_path)
    goal = Goal(objective="x", constraints=("test.gate",))
    with pytest.raises(PermissionError):
        await Controller(registry, SequencePlanner([plan]), store, allowed_capabilities=set()).run(
            goal
        )
    result = await Controller(registry, SequencePlanner([plan]), store).run(goal)
    assert result["status"] == "no_more_plans"
    assert "TimeoutError" in store.history(goal.id)[0].results[0].error
    store.close()


@pytest.mark.asyncio
async def test_overwritten_intermediate_evidence_fails_acceptance(tmp_path):
    plugin, registry, _, store = setup(tmp_path, [])
    plan = Plan(
        hypothesis="overwriting evidence",
        graph=TaskGraph(
            tasks=(
                Task(id="a", capability="test.run", parameters={"value": 1}),
                Task(id="b", capability="test.run", parameters={"value": 3}, depends_on=("a",)),
            )
        ),
    )
    goal = Goal(objective="x", constraints=("test.gate",))
    state = await Controller(registry, SequencePlanner([plan]), store).run(goal)
    assert state["status"] == "no_more_plans"
    assert state["best_valid_candidate"] is None
    store.close()
