import csv
import json

import pytest
from nexus_atom_core import Evaluation, Experiment, Goal, Task

from nexus_atom_controller.reports import write_experiment_report


def test_report_preserves_decisions_and_unfinished_tasks(tmp_path):
    goal = Goal(objective="x", constraints=("science.check",), target={"speedup": 3})
    experiment = Experiment(
        goal=goal.id,
        hypothesis="x",
        tasks=(Task(id="run", capability="x"),),
        results=(),
        evaluations=(
            Evaluation(
                evaluator="science.check",
                passed=False,
                metrics={"speedup": 10},
                reasons=("wrong output",),
            ),
        ),
        status="interrupted",
    )
    write_experiment_report(goal, experiment, tmp_path)
    root = tmp_path / "_atom_report"
    assert not json.loads((root / "evaluation.json").read_text())["goal_satisfied"]
    assert "not completed" in (root / "summary.md").read_text()
    with (root / "metrics.csv").open() as stream:
        row = next(csv.DictReader(stream))
    assert row["minimum_target"] == "3.0"
    assert row["passed"] == "False"
    before = (root / "summary.md").read_bytes()
    write_experiment_report(goal, experiment, tmp_path)
    assert (root / "summary.md").read_bytes() == before
    (tmp_path / "metadata.json").write_text("sealed")
    with pytest.raises(ValueError, match="sealed"):
        write_experiment_report(goal, experiment, tmp_path)


def test_report_refuses_directory_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    run = tmp_path / "run"
    run.mkdir()
    (run / "_atom_report").symlink_to(outside, target_is_directory=True)
    goal = Goal(objective="x", constraints=("check",))
    experiment = Experiment(goal=goal.id, hypothesis="x", tasks=(), results=(), status="rejected")
    with pytest.raises(ValueError, match="symlink"):
        write_experiment_report(goal, experiment, run)
    assert not list(outside.iterdir())
