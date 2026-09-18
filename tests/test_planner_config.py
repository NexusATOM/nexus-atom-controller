import json
import sys
from types import SimpleNamespace

import pytest
from nexus_atom_core import Capability, Evaluation, Evaluator, Goal, Plugin, TaskResult

from nexus_atom_controller import Store
from nexus_atom_controller.cli import main
from nexus_atom_controller.planner_config import PlannerConfig, bind_planner_config


class Action(Capability):
    name = "example.run"

    async def execute(self, task, context):
        return TaskResult(task_id=task.id, status="succeeded", outputs=task.parameters)


class Check(Evaluator):
    name = "check"

    async def evaluate(self, goal, results, directory):
        return Evaluation(evaluator=self.name, passed=results[0].outputs["value"] == 3)


class Example(Plugin):
    name = "example"

    @classmethod
    def from_config(cls, path):
        return cls()

    def capabilities(self):
        return [Action()]

    def evaluators(self):
        return [Check()]

    def goal_constraints(self):
        return ("example.check",)


@pytest.mark.parametrize(
    "data",
    [
        {"runtime": "nooa"},
        {"runtime": "local", "argv": []},
        {"runtime": "openai", "model": "x", "argv": ["x"]},
        {"runtime": "local", "argv": ["python"], "api_key": "not-allowed"},
        {"runtime": "local", "argv": ["python"], "timeout_seconds": float("nan")},
    ],
)
def test_reject_invalid_or_secret_configuration(data):
    with pytest.raises(ValueError):
        PlannerConfig.model_validate(data)


def test_cli_runtime_resume_uses_saved_configuration(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "nexus_atom_controller.cli.discover_plugins",
        lambda: {"example": SimpleNamespace(load=lambda: Example)},
    )
    script = tmp_path / "propose.py"
    script.write_text("""import json,sys
request=json.load(sys.stdin)
history=request["evidence"]["recent_experiments"]
if history:
    assert history[-1]["evaluations"][0]["passed"] is False
value=3 if history else 1
print(json.dumps({"proposal":{"hypothesis":"revise using evidence","graph":{"tasks":[
    {"capability":"example.run","parameters":{"value":value}}]}},"rationale":"test"}))
""")
    config = tmp_path / "planner.json"
    config.write_text(json.dumps({"runtime": "local", "argv": [sys.executable, str(script)]}))
    state = tmp_path / "state"
    common = [
        "--system",
        "example",
        "--config",
        str(tmp_path / "model.json"),
        "--state",
        str(state),
    ]
    assert (
        main(
            [
                "run",
                "pass the check",
                *common,
                "--planner-config",
                str(config),
                "--max-experiments",
                "1",
            ]
        )
        == 2
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "budget_exhausted"
    goal_id = result["goal_id"]
    config.unlink()
    assert main(["resume", goal_id, *common]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "succeeded"
    assert result["planner_config"]["runtime"] == "local"
    with pytest.raises(SystemExit):
        main(["resume", goal_id, *common, "--plans", str(tmp_path / "plans.json")])
    assert "cannot be replaced" in capsys.readouterr().err
    store = Store(state)
    events_before = len(store.events())
    store.close()
    assert main(["resume", goal_id, *common]) == 0
    store = Store(state)
    assert len(store.events()) == events_before
    store.close()


def test_saved_configuration_cannot_change(tmp_path):
    store = Store(tmp_path)
    goal = Goal(objective="x", constraints=("example.check",))
    first = PlannerConfig(runtime="local", argv=("python", "agent.py"))
    assert bind_planner_config(store, goal, first) == first
    assert bind_planner_config(store, goal, None) == first
    with pytest.raises(ValueError, match="differs"):
        bind_planner_config(store, goal, PlannerConfig(runtime="nooa", model="provider/model"))
    store.close()


def test_cannot_attach_runtime_after_existing_planning_event(tmp_path):
    from nexus_atom_core import Event

    store = Store(tmp_path)
    goal = Goal(objective="x", constraints=("example.check",))
    store.goal(goal)
    store.emit(Event(kind="planning.finished", goal_id=goal.id, payload={}))
    with pytest.raises(ValueError, match="after work has begun"):
        bind_planner_config(store, goal, PlannerConfig(runtime="local", argv=("python",)))
    assert "planner_config" not in store.goal(goal)
    store.close()
