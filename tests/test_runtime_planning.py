import sys

import pytest
from nexus_atom_agents import AgentResult, LocalRuntime
from nexus_atom_core import (
    Budget,
    Capability,
    CapabilityRegistry,
    Evaluation,
    Evaluator,
    Goal,
    Plugin,
    TaskResult,
    Usage,
)

from nexus_atom_controller import Controller, RuntimePlanner, Store


class Run(Capability):
    name = "example.run"
    calls = 0

    async def execute(self, task, context):
        self.calls += 1
        return TaskResult(task_id=task.id, status="succeeded", outputs=task.parameters)


class Gate(Evaluator):
    name = "gate"

    async def evaluate(self, goal, results, directory):
        value = results[0].outputs["value"]
        return Evaluation(evaluator=self.name, passed=value >= 3, metrics={"speedup": value})


class Example(Plugin):
    name = "example"

    def __init__(self):
        self.run = Run()

    def capabilities(self):
        return [self.run]

    def evaluators(self):
        return [Gate()]


def components(tmp_path):
    plugin = Example()
    registry = CapabilityRegistry()
    registry.register(plugin)
    goal = Goal(objective="Reach 3x", constraints=("example.gate",), target={"speedup": 3})
    return plugin, registry, goal, Store(tmp_path / "state")


@pytest.mark.asyncio
async def test_local_runtime_replans_from_failed_evidence_and_resumes(tmp_path):
    script = tmp_path / "planner.py"
    script.write_text("""import json, sys
request = json.load(sys.stdin)
history = request["evidence"]["recent_experiments"]
if history:
    assert history[-1]["evaluations"][0]["passed"] is False
    assert history[-1]["evaluations"][0]["metrics"]["speedup"] == 1
value = 3 if history else 1
print(json.dumps({"proposal": {"hypothesis": "revise from evidence", "graph": {
    "tasks": [{"capability": "example.run", "parameters": {"value": value}}]}},
    "rationale": "Use prior measurements"}))
""")
    plugin, registry, goal, store = components(tmp_path)
    planner = RuntimePlanner(LocalRuntime((sys.executable, str(script))), tmp_path / "planning")
    controller = Controller(registry, planner, store, Budget(max_experiments=1))
    assert (await controller.run(goal))["status"] == "budget_exhausted"
    store.close()
    store = Store(tmp_path / "state")
    controller = Controller(registry, planner, store, Budget(max_experiments=3))
    assert (await controller.run(goal))["status"] == "succeeded"
    assert [e.status for e in store.history(goal.id)] == ["rejected", "valid"]
    assert (await controller.run(goal))["status"] == "succeeded"
    assert plugin.run.calls == 2
    rows = store.db.execute(
        "SELECT data FROM events WHERE data LIKE '%planning.finished%'"
    ).fetchall()
    assert len(rows) == 2
    store.close()


class FixedRuntime:
    def __init__(self, proposal, tokens=10):
        self.proposal, self.tokens = proposal, tokens

    async def execute(self, task, context, capabilities):
        assert context.max_output_tokens <= context.evidence["remaining_budget"]["max_tokens"]
        return AgentResult(
            proposal=self.proposal,
            rationale="test",
            runtime="fake",
            usage=Usage(tokens=self.tokens),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "proposal",
    [
        {"graph": {}},
        {
            "hypothesis": "cycle",
            "graph": {"tasks": [{"id": "a", "capability": "example.run", "depends_on": ["a"]}]},
        },
        {"hypothesis": "unknown", "graph": {"tasks": [{"capability": "unknown"}]}},
    ],
)
async def test_invalid_proposal_never_executes_and_usage_is_saved(tmp_path, proposal):
    plugin, registry, goal, store = components(tmp_path)
    planner = RuntimePlanner(FixedRuntime(proposal), tmp_path / "planning")
    with pytest.raises((ValueError, KeyError)):
        await Controller(registry, planner, store).run(goal)
    assert plugin.run.calls == 0
    assert store.goal(goal)["usage"]["tokens"] == 10
    assert store.history(goal.id) == ()
    store.close()


@pytest.mark.asyncio
async def test_planning_budget_exhaustion_and_stop_are_not_success(tmp_path):
    plugin, registry, goal, store = components(tmp_path)
    planner = RuntimePlanner(FixedRuntime({"stop": True}, tokens=10), tmp_path / "planning")
    state = await Controller(registry, planner, store, Budget(max_tokens=10)).run(goal)
    assert state["status"] == "budget_exhausted"
    state = await Controller(registry, planner, store, Budget(max_tokens=100)).run(goal)
    assert state["status"] == "no_more_plans"
    assert state["usage"]["tokens"] == 20
    assert plugin.run.calls == 0
    store.close()


@pytest.mark.asyncio
async def test_nooa_strategy_plans_a_real_controller_experiment(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    pytest.importorskip("nooa")
    from nexus_atom_agents import NOOARuntime
    from nooa.unifiedllm import FakeLLMClient
    from nooa.unifiedllm import registry as providers

    reply = {
        "proposal": {
            "hypothesis": "measure candidate",
            "graph": {"tasks": [{"capability": "example.run", "parameters": {"value": 3}}]},
        },
        "rationale": "supplied goal",
        "runtime": "nooa",
    }
    llm = FakeLLMClient.with_code_responses([json.dumps(reply)])
    monkeypatch.setattr(providers, "get_llm_client", lambda model: llm)
    plugin, registry, goal, store = components(tmp_path)
    planner = RuntimePlanner(NOOARuntime("test/fake"), tmp_path / "planning")
    result = await Controller(registry, planner, store).run(goal)
    assert result["status"] == "succeeded"
    assert plugin.run.calls == llm.call_count == 1
    store.close()
