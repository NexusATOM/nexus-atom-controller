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
