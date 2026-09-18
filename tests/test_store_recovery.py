"""Exercise process-death boundaries, evidence retention and transactional state."""

import asyncio
import subprocess
import sys

import pytest
from nexus_atom_core import (
    Artifact,
    Capability,
    CapabilityRegistry,
    Evaluation,
    Event,
    Experiment,
    Goal,
    Plan,
    Plugin,
    Task,
    TaskGraph,
    TaskResult,
    Usage,
    canonical,
)

from nexus_atom_controller import Controller, SequencePlanner, Store


def fixture(store):
    goal = Goal(id="goal", objective="Preserve measured evidence", constraints=("test.check",))
    store.goal(goal)
    directory = store.directory("experiment")
    directory.mkdir(parents=True)
    path = directory / "output.txt"
    path.write_text("measurement")
    artifact = Artifact.capture(path, directory)
    task = Task(id="measure", capability="test.measure")
    result = TaskResult(task_id=task.id, status="succeeded", artifacts=(artifact,))
    experiment = Experiment(
        id="experiment",
        goal=goal.id,
        hypothesis="Measured result",
        tasks=(task,),
        results=(result,),
        artifacts=(artifact,),
        evaluations=(Evaluation(evaluator="test.check", passed=True),),
        status="valid",
    )
    return goal, experiment


@pytest.mark.parametrize("boundary", ["_publish_metadata", "_commit_seal"])
def test_real_process_death_during_seal_recovers_exact_record(tmp_path, boundary):
    store = Store(tmp_path)
    goal, experiment = fixture(store)
    seed = tmp_path / "seed.json"
    seed.write_bytes(canonical(experiment))
    store.close()
    script = """import os, sys
from pathlib import Path
from nexus_atom_core import Experiment
from nexus_atom_controller import Store
store = Store(Path(sys.argv[1]))
def crash(*args): os._exit(73)
setattr(store, sys.argv[2], crash)
with store.lock():
    store.seal(Experiment.model_validate_json((Path(sys.argv[1]) / 'seed.json').read_bytes()))
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), boundary],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert child.returncode == 73, child.stderr
    reopened = Store(tmp_path)
    metadata = reopened.directory(experiment.id) / "metadata.json"
    assert metadata.exists() == (boundary == "_commit_seal")
    before = metadata.stat().st_mtime_ns if metadata.exists() else None
    assert reopened.history(goal.id) == ()  # A read does not implicitly recover.
    with reopened.lock():
        assert reopened.reconcile_seals(goal.id) == (experiment.id,)
        assert reopened.reconcile_seals(goal.id) == ()
        reopened.seal(experiment)  # Idempotent after a completed commit.
    assert reopened.history(goal.id) == (experiment,)
    assert metadata.read_bytes() == canonical(experiment)
    if before is not None:
        assert metadata.stat().st_mtime_ns == before
    assert reopened.db.execute("SELECT COUNT(*) FROM pending_seals").fetchone()[0] == 0
    reopened.close()


def test_pending_seal_does_not_accept_changed_artifacts(tmp_path, monkeypatch):
    store = Store(tmp_path)
    goal, experiment = fixture(store)

    def crash(*args):
        raise OSError("interrupted publication")

    with monkeypatch.context() as patch:
        patch.setattr(store, "_publish_metadata", crash)
        with pytest.raises(OSError):
            store.seal(experiment)
    (store.directory(experiment.id) / "output.txt").write_text("changed")
    with pytest.raises(ValueError, match="artifact corrupted"):
        store.reconcile_seals(goal.id)
    assert store.history(goal.id) == ()
    store.close()


def test_metadata_conflict_is_not_overwritten(tmp_path):
    store = Store(tmp_path)
    goal, experiment = fixture(store)
    metadata = store.directory(experiment.id) / "metadata.json"
    metadata.write_text("conflicting evidence")
    with pytest.raises(ValueError, match="immutable"):
        store.seal(experiment)
    assert metadata.read_text() == "conflicting evidence"
    with pytest.raises(ValueError, match="immutable"):
        store.reconcile_seals(goal.id)
    store.close()


def test_ledger_payload_corruption_and_deleted_metadata_fail_closed(tmp_path):
    store = Store(tmp_path)
    goal, experiment = fixture(store)
    store.seal(experiment)
    with store.db:
        store.db.execute("UPDATE experiments SET data=? WHERE id=?", ("{}", experiment.id))
    with pytest.raises(ValueError, match="record corrupted"):
        store.history(goal.id)
    with store.db:
        store.db.execute(
            "UPDATE experiments SET data=? WHERE id=?",
            (canonical(experiment).decode(), experiment.id),
        )
    metadata = store.directory(experiment.id) / "metadata.json"
    metadata.unlink()
    with pytest.raises(ValueError, match="metadata corrupted"):
        store.seal(experiment)
    assert not metadata.exists()  # A sealed record is never silently reconstructed.
    store.close()


def test_checkpoint_event_transaction_rolls_back_both_writes(tmp_path):
    store = Store(tmp_path)
    goal, _ = fixture(store)
    original = store.goal(goal)
    store.db.execute(
        "CREATE TRIGGER reject_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'test interruption'); END"
    )
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError, match="test interruption"):
        store.checkpoint(
            goal,
            {**original, "usage": {"tokens": 123}},
            event=Event(kind="task.finished", goal_id=goal.id),
        )
    assert store.goal(goal) == original
    assert store.events() == []
    store.db.execute("DROP TRIGGER reject_event")
    store.checkpoint(
        goal,
        {**original, "usage": {"tokens": 123}},
        event=Event(kind="task.finished", goal_id=goal.id),
    )
    assert store.goal(goal)["usage"]["tokens"] == 123
    assert len(store.events()) == 1
    store.close()


class InterruptibleCapability(Capability):
    name = "test.work"

    def __init__(self):
        self.calls = []

    async def execute(self, task, context):
        self.calls.append(task.id)
        if task.id == "waiting":
            (context.directory / "partial.log").write_text("partial external work")
            raise asyncio.CancelledError()
        path = context.directory / "completed.txt"
        path.write_text("completed measurement")
        return TaskResult(
            task_id=task.id,
            status="succeeded",
            usage=Usage(tokens=7, gpu_seconds=3),
            artifacts=(Artifact.capture(path, context.directory),),
        )


class InterruptedPlugin(Plugin):
    name = "test"

    def __init__(self):
        self.work = InterruptibleCapability()

    def capabilities(self):
        return [self.work]


@pytest.mark.asyncio
@pytest.mark.parametrize("change_evidence", [False, True])
async def test_recovery_retains_results_budget_and_partial_logs(tmp_path, change_evidence):
    from nexus_atom_core import Evaluator

    class UnusedGate(Evaluator):
        name = "check"

        async def evaluate(self, goal, results, directory):
            raise AssertionError("Interrupted work must not be approved")

    class TestedPlugin(InterruptedPlugin):
        def evaluators(self):
            return [UnusedGate()]

    plugin = TestedPlugin()
    registry = CapabilityRegistry()
    registry.register(plugin)
    goal = Goal(objective="test interruption", constraints=("test.check",))
    plan = Plan(
        hypothesis="finish one task, then interrupt",
        graph=TaskGraph(
            tasks=(
                Task(id="completed", capability="test.work"),
                Task(id="waiting", capability="test.work", depends_on=("completed",)),
            )
        ),
    )
    store = Store(tmp_path)
    with pytest.raises(asyncio.CancelledError):
        await Controller(registry, SequencePlanner([plan]), store).run(goal)
    state = store.goal(goal)
    experiment_id = state["active"]["id"]
    assert state["usage"]["tokens"] == 7
    assert state["usage"]["gpu_seconds"] == 3
    assert state["usage"]["tasks"] == 2
    assert store.history(goal.id) == ()
    assert (await Controller(registry, SequencePlanner([plan]), store).run(goal))[
        "status"
    ] == "interrupted"
    if change_evidence:
        (store.directory(experiment_id) / "completed.txt").write_text("changed during interruption")
    store.close()
    reopened = Store(tmp_path)
    recovered = await Controller(registry, SequencePlanner([plan]), reopened).run(
        goal, recover_interrupted=True
    )
    (experiment,) = reopened.history(goal.id)
    assert recovered["status"] == "no_more_plans"
    assert recovered["best_valid_candidate"] is None
    assert recovered["latest_candidate"] == experiment_id
    assert recovered["usage"]["tokens"] == 7
    assert len(experiment.results) == 1
    assert experiment.results[0].task_id == "completed"
    assert experiment.status == "interrupted"
    assert not experiment.evaluations[0].passed
    assert {a.path for a in experiment.artifacts} == {"completed.txt", "partial.log"}
    assert experiment.provenance.parameters["tasks_without_terminal_result"] == ["waiting"]
    assert (
        any("changed or is missing" in reason for reason in experiment.evaluations[0].reasons)
        == change_evidence
    )
    assert plugin.work.calls == ["completed", "waiting"]  # No task silently replayed.
    (reopened.directory(experiment_id) / "partial.log").write_text("changed after sealing")
    with pytest.raises(ValueError, match="artifact corrupted"):
        reopened.history(goal.id)
    reopened.close()


@pytest.mark.asyncio
async def test_controller_finishes_pending_seal_without_repeating_execution(tmp_path, monkeypatch):
    from nexus_atom_core import Evaluator

    class Check(Evaluator):
        name = "check"

        async def evaluate(self, goal, results, directory):
            return Evaluation(
                evaluator=self.name,
                passed=(directory / "completed.txt").read_text() == "completed measurement",
            )

    class TestedPlugin(InterruptedPlugin):
        def evaluators(self):
            return [Check()]

    plugin = TestedPlugin()
    registry = CapabilityRegistry()
    registry.register(plugin)
    goal = Goal(objective="Recover the final sealed result", constraints=("test.check",))
    plan = Plan(
        hypothesis="Measured candidate",
        graph=TaskGraph(tasks=(Task(id="completed", capability="test.work"),)),
    )
    store = Store(tmp_path)

    def interrupt_commit(*args):
        raise OSError("process ended after metadata publication")

    with monkeypatch.context() as patch:
        patch.setattr(store, "_commit_seal", interrupt_commit)
        with pytest.raises(OSError):
            await Controller(registry, SequencePlanner([plan]), store).run(goal)
    interrupted = store.goal(goal)
    assert interrupted["status"] == "interrupted"
    assert interrupted["active"] is not None
    assert store.history(goal.id) == ()
    store.close()
    reopened = Store(tmp_path)
    # Completing journaled persistence does not need permission to repeat side effects.
    result = await Controller(registry, SequencePlanner([plan]), reopened).run(goal)
    assert result["status"] == "succeeded"
    assert result["active"] is None
    assert result["usage"]["tasks"] == 1
    assert result["usage"]["tokens"] == 7
    assert plugin.work.calls == ["completed"]
    (experiment,) = reopened.history(goal.id)
    assert experiment.status == "valid"
    assert result["best_valid_candidate"] == experiment.id
    reopened.close()
