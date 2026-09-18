"""Offline optimization lab: measure, reject a wrong answer, accept a correct one.

This uses prepared candidates, actual Python execution and application timings.
It demonstrates software orchestration, not Earth-system science or LLM reasoning.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

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
    ResourceRequest,
    Task,
    TaskGraph,
    TaskResult,
)

from nexus_atom_controller.engine import Controller, Planner
from nexus_atom_controller.store import Store

KERNELS = {
    "baseline": "def compute(n):\n    total = 0\n    for i in range(n):\n        total += i\n    return total\n",
    "wrong": "def compute(n):\n    return n * (n + 1) // 2\n",
    "correct": "def compute(n):\n    return n * (n - 1) // 2\n",
}
WORKER = """import json
import time
from pathlib import Path
from kernel import compute
samples=[]
for trial in range(4):
    start=time.perf_counter_ns()
    for _ in range(200):
        result=compute(20000)
    elapsed=(time.perf_counter_ns()-start)/1e9
    if trial: samples.append(elapsed)
# Extra inputs catch a candidate that only hard-codes the benchmark answer.
values=[compute(n) for n in (0,1,2,17,20000)]
Path('measurement.json').write_text(json.dumps({'samples':samples,'values':values,
    'inputs':[0,1,2,17,20000], 'units':'integer sum', 'timing_scope':'200 calls, 1 warmup, 3 measured trials'}))
"""


class Measure(Capability):
    name = "toy.measure"
    description = "Build and measure a prepared synthetic integer-sum implementation"

    async def execute(self, task, context):
        from nexus_atom_hpc import JobSpec, LocalScheduler

        variant = task.parameters["variant"]
        source = context.directory / "source"
        source.mkdir()
        (source / "kernel.py").write_text(KERNELS[variant])
        (source / "worker.py").write_text(WORKER)
        scheduler = LocalScheduler()
        for operation, argv in (
            ("build", (sys.executable, "-m", "py_compile", "kernel.py", "worker.py")),
            ("measure", (sys.executable, "worker.py")),
        ):
            job, status = await scheduler.run(
                JobSpec(
                    argv=argv,
                    cwd=source,
                    output_directory=context.directory / "jobs" / operation,
                    resources=ResourceRequest(walltime="00:01:00"),
                )
            )
            if status.state != "succeeded":
                return TaskResult(
                    task_id=task.id,
                    status="failed",
                    error=f"{operation}: {status.state}: {scheduler.stderr(job)}",
                )
        measurement = json.loads((source / "measurement.json").read_text())
        measurement["variant"] = variant
        output = context.directory / "measurement.json"
        output.write_text(json.dumps(measurement, indent=2))
        print(f"  EXECUTE {variant}: compiled and measured 3 trials", flush=True)
        return TaskResult(
            task_id=task.id,
            status="succeeded",
            outputs={"variant": variant},
            artifacts=(Artifact.capture(output, context.directory),),
        )


class Correctness(Evaluator):
    name = "correctness"

    async def evaluate(self, goal, results, directory):
        from nexus_atom_science import DatasetArtifact, FieldData, Tolerance, compare_fields

        measured = json.loads((directory / "measurement.json").read_text())
        expected = [sum(range(n)) for n in measured["inputs"]]
        reference = DatasetArtifact(
            fields={"sum": FieldData(units="1", shape=(len(expected),), values=expected)}
        )
        candidate = DatasetArtifact(
            fields={"sum": FieldData(units="1", shape=(len(expected),), values=measured["values"])}
        )
        compared = compare_fields(reference, candidate, Tolerance(bitwise=True))
        print(
            f"  EVALUATE correctness: {'PASS' if compared.passed else 'FAIL — candidate rejected'}",
            flush=True,
        )
        return Evaluation(
            evaluator=self.name,
            passed=compared.passed,
            reasons=()
            if compared.passed
            else ("Incorrect integer sums; speed cannot override correctness.",),
            evidence=("measurement.json",),
        )


class Performance(Evaluator):
    name = "performance"

    def __init__(self, store):
        self.store = store

    async def evaluate(self, goal, results, directory):
        measured = json.loads((directory / "measurement.json").read_text())
        median = statistics.median(measured["samples"])
        history = self.store.history(goal.id)
        if history:
            baseline = json.loads(
                (self.store.directory(history[0].id) / "measurement.json").read_text()
            )
            baseline_seconds = statistics.median(baseline["samples"])
        else:
            baseline_seconds = median
        speedup = baseline_seconds / median
        print(f"  EVALUATE performance: {speedup:.2f}x measured speedup", flush=True)
        return Evaluation(
            evaluator=self.name,
            passed=True,
            metrics={"speedup": speedup},
            evidence=("measurement.json",),
        )


class ToyPlugin(Plugin):
    name = "toy"

    def __init__(self, store):
        self.store = store

    def capabilities(self):
        return [Measure()]

    def evaluators(self):
        return [Correctness(), Performance(self.store)]


class ToyPlanner(Planner):
    async def plan(self, goal, history, registry):
        variants = ("baseline", "wrong", "correct")
        if len(history) >= len(variants):
            return None
        variant = variants[len(history)]
        print(f"\nPLAN attempt {len(history) + 1}/3: {variant}", flush=True)
        if variant == "wrong":
            print(
                "  Hypothesis: a formula is faster — but this candidate has an off-by-one error.",
                flush=True,
            )
        if variant == "correct":
            print(
                "  LEARN: retain the formula approach and correct the failed numerical result.",
                flush=True,
            )
        return Plan(
            hypothesis=f"Prepared {variant} integer-sum candidate",
            graph=TaskGraph(
                tasks=(
                    Task(
                        capability="toy.measure",
                        parameters={"variant": variant},
                        timeout_seconds=60,
                    ),
                )
            ),
        )


async def run_demo(root: Path, *, resume=False, pause_after: int | None = None):
    try:
        import nexus_atom_hpc  # noqa: F401
        import nexus_atom_science  # noqa: F401
    except ImportError as exc:
        raise ValueError(
            "The demo requires nexus-atom-hpc and nexus-atom-science; install the controller demo extra with sibling packages"
        ) from exc
    root = root.resolve()
    store = Store(root)
    try:
        marker = root / "demo-goal.json"
        if resume:
            if not marker.exists():
                raise ValueError("No saved demo goal in this state directory")
            goal = Goal.model_validate_json(marker.read_text())
        else:
            if marker.exists():
                raise ValueError(
                    "Demo state already exists; use --resume or a new --state directory"
                )
            goal = Goal(
                objective="Make a small integer-sum kernel at least 3x faster without changing results",
                system="toy",
                constraints=("toy.correctness", "toy.performance"),
                target={"speedup": 3},
            )
            marker.write_text(goal.model_dump_json(indent=2))
        print("Nexus ATOM optimization lab — synthetic Python, no GEOS/GPU/API key", flush=True)
        print(f"Goal: {goal.objective}\nState: {root}\nGoal ID: {goal.id}", flush=True)
        registry = CapabilityRegistry()
        registry.register(ToyPlugin(store))
        budget = Budget(max_experiments=pause_after or 3, wall_seconds=120)
        result = await Controller(registry, ToyPlanner(), store, budget).run(goal)
        history = store.history(goal.id)
        rows = []
        print("\nEXPERIMENT LEDGER", flush=True)
        print("Candidate    Correctness    Speedup       Decision", flush=True)
        for experiment in history:
            variant = experiment.tasks[0].parameters["variant"]
            correctness = next(
                e for e in experiment.evaluations if e.evaluator == "toy.correctness"
            )
            speedup = next(
                e.metrics.get("speedup")
                for e in experiment.evaluations
                if e.evaluator == "toy.performance"
            )
            decision = (
                "promoted" if result["best_valid_candidate"] == experiment.id else experiment.status
            )
            row = {
                "candidate": variant,
                "correctness": correctness.passed,
                "speedup": speedup,
                "decision": decision,
                "experiment_id": experiment.id,
            }
            rows.append(row)
            measured_text = f"{speedup:.2f}x" if speedup is not None else "unavailable"
            print(
                f"{variant:12} {'PASS' if correctness.passed else 'FAIL':14} {measured_text:>10}    {decision}",
                flush=True,
            )
        report = {
            "goal_id": goal.id,
            "status": result["status"],
            "experiments": rows,
            "state": str(root),
            "note": "Prepared synthetic candidates. Measured speedups vary by host and are not GEOS/GPU results.",
        }
        (root / "demo-report.json").write_text(json.dumps(report, indent=2))
        lines = [
            "# ATOM small optimization example",
            "",
            report["note"],
            "",
            f"Goal: {goal.objective}",
            f"Status: **{result['status']}**",
            "",
            "| Candidate | Correctness | Measured speedup | Decision |",
            "|---|---|---:|---|",
        ]
        for row in rows:
            measured_text = (
                f"{row['speedup']:.2f}×" if row["speedup"] is not None else "unavailable"
            )
            lines.append(
                f"| {row['candidate']} | {'PASS' if row['correctness'] else 'FAIL'} | {measured_text} | {row['decision']} |"
            )
        lines += [
            "",
            "State is stored in `state.sqlite`. Each experiment retains source, build/run logs, raw timings and immutable evaluator evidence.",
            "",
            f"Resume: `atom demo --state {root} --resume`",
            "",
        ]
        (root / "demo-report.md").write_text("\n".join(lines))
        print(f"\nFINISH: {result['status']}\nReport: {root / 'demo-report.md'}", flush=True)
        return report
    finally:
        store.close()
