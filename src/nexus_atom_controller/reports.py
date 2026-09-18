"""Deterministic reports generated before sealing; never an alternative verdict."""

import csv
import io
import json
import os
import tempfile
from pathlib import Path

from nexus_atom_core import Experiment, Goal


def _cell(value) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def write_experiment_report(goal: Goal, experiment: Experiment, directory: Path) -> None:
    """Write reserved report files for an unsealed experiment.

    The engine includes these files in the artifact snapshot before seal journaling.
    Recovery may regenerate them only while an experiment is still unsealed.
    """
    if (directory / "metadata.json").exists() or (directory / "metadata.json").is_symlink():
        raise ValueError("Cannot rewrite reports for a sealed experiment")
    if any(
        artifact.path == "_atom_report" or artifact.path.startswith("_atom_report/")
        for result in experiment.results
        for artifact in result.artifacts
    ):
        raise ValueError("Task artifacts cannot use the reserved _atom_report directory")
    report_dir = directory / "_atom_report"
    if report_dir.is_symlink():
        raise ValueError("Report directory cannot be a symlink")
    report_dir.mkdir(parents=True, exist_ok=True)
    satisfied = experiment.status in {"valid", "baseline", "promoted"} and goal.satisfied(
        experiment.evaluations
    )
    evaluation = {
        "schema_version": 1,
        "goal": goal.model_dump(mode="json"),
        "experiment_id": experiment.id,
        "experiment_status": experiment.status,
        "goal_satisfied": satisfied,
        "evaluations": [item.model_dump(mode="json") for item in experiment.evaluations],
    }
    metrics = io.StringIO(newline="")
    writer = csv.writer(metrics)
    writer.writerow(("evaluator", "passed", "metric", "value", "minimum_target"))
    lines = [
        f"# Experiment {experiment.id}",
        "",
        f"Objective: {_cell(goal.objective)}",
        "",
        f"Hypothesis: {_cell(experiment.hypothesis)}",
        "",
        f"Status: **{experiment.status}**; goal satisfied: **{str(satisfied).lower()}**.",
        "",
        "These are recorded evaluator decisions, not independent scientific certification.",
        "",
        "| Evaluator | Decision | Reasons |",
        "|---|---|---|",
    ]
    for item in experiment.evaluations:
        lines.append(
            f"| {_cell(item.evaluator)} | {'PASS' if item.passed else 'FAIL'} | {_cell('; '.join(item.reasons))} |"
        )
        for name, value in sorted(item.metrics.items()):
            writer.writerow((item.evaluator, item.passed, name, value, goal.target.get(name, "")))
    lines += ["", "| Evaluator | Metric | Value | Minimum target |", "|---|---|---|---|"]
    for item in experiment.evaluations:
        for name, value in sorted(item.metrics.items()):
            lines.append(
                f"| {_cell(item.evaluator)} | {_cell(name)} | {value:.8g} | {goal.target.get(name, 'not set')} |"
            )
    lines += ["", "| Task | Capability | Result | Error |", "|---|---|---|---|"]
    results = {result.task_id: result for result in experiment.results}
    for task in experiment.tasks:
        result = results.get(task.id)
        lines.append(
            f"| {_cell(task.id)} | {_cell(task.capability)} | {result.status if result else 'not completed'} | {_cell(result.error or '') if result else ''} |"
        )
    lines += [
        "",
        "Machine-readable decisions: `evaluation.json`. Metrics and declared targets: `metrics.csv`.",
        "The experiment metadata manifest records hashes for this report and the underlying artifacts.",
        "",
    ]
    files = {
        "evaluation.json": json.dumps(evaluation, indent=2, allow_nan=False) + "\n",
        "metrics.csv": metrics.getvalue(),
        "summary.md": "\n".join(lines),
    }
    for name, content in files.items():
        descriptor, temporary = tempfile.mkstemp(prefix=".report-", dir=report_dir)
        try:
            with os.fdopen(descriptor, "w") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, report_dir / name)
        finally:
            Path(temporary).unlink(missing_ok=True)
    descriptor = os.open(report_dir, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
