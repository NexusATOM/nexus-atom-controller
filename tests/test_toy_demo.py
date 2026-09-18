import json

import pytest

from nexus_atom_controller import Store
from nexus_atom_controller.examples.toy import run_demo


@pytest.mark.asyncio
async def test_demo_pause_reject_resume_and_idempotence(tmp_path, capsys):
    pytest.importorskip("nexus_atom_hpc")
    pytest.importorskip("nexus_atom_science")
    paused = await run_demo(tmp_path, pause_after=1)
    assert paused["status"] == "budget_exhausted"
    assert len(paused["experiments"]) == 1
    resumed = await run_demo(tmp_path, resume=True)
    assert resumed["status"] == "succeeded"
    assert [row["candidate"] for row in resumed["experiments"]] == ["baseline", "wrong", "correct"]
    assert resumed["experiments"][1]["correctness"] is False
    assert resumed["experiments"][1]["decision"] == "rejected"
    assert resumed["experiments"][2]["decision"] == "promoted"
    store = Store(tmp_path)
    before = store.goal(store.load_goal(resumed["goal_id"]))["usage"]
    store.close()
    assert (await run_demo(tmp_path, resume=True))["status"] == "succeeded"
    store = Store(tmp_path)
    assert store.goal(store.load_goal(resumed["goal_id"]))["usage"] == before
    store.close()
    assert json.loads((tmp_path / "demo-report.json").read_text())["goal_id"] == resumed["goal_id"]


@pytest.mark.asyncio
async def test_demo_reports_command_failure_without_losing_state(tmp_path, monkeypatch):
    from nexus_atom_core import TaskResult

    from nexus_atom_controller.examples.toy import Measure

    async def fail(self, task, context):
        return TaskResult(task_id=task.id, status="failed", error="Synthetic launch failure")

    monkeypatch.setattr(Measure, "execute", fail)
    report = await run_demo(tmp_path)
    assert report["status"] == "budget_exhausted"
    assert all(row["speedup"] is None for row in report["experiments"])
    assert all(row["decision"] == "rejected" for row in report["experiments"])
    assert "unavailable" in (tmp_path / "demo-report.md").read_text()
