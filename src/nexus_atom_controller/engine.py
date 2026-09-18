"""Observe/plan/execute/evaluate/learn loop with explicit failure boundaries."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod

from nexus_atom_core import (
    Budget,
    CapabilityRegistry,
    Evaluation,
    Event,
    ExecutionContext,
    Experiment,
    Goal,
    Plan,
    Provenance,
    TaskResult,
    Usage,
    uid,
)

from .store import Store


class Planner(ABC):
    @abstractmethod
    async def plan(
        self, goal: Goal, history: tuple[Experiment, ...], registry: CapabilityRegistry
    ) -> Plan | None:
        """None means no remaining hypothesis, never success."""


class SequencePlanner(Planner):
    def __init__(self, plans: list[Plan]):
        self.plans = plans

    async def plan(self, goal, history, registry):
        index = len(history)
        return self.plans[index] if index < len(self.plans) else None


class Controller:
    def __init__(
        self,
        registry: CapabilityRegistry,
        planner: Planner,
        store: Store,
        budget: Budget | None = None,
        *,
        allowed_capabilities: set[str] | None = None,
    ):
        self.registry, self.planner, self.store = registry, planner, store
        self.budget = budget or Budget()
        self.allowed = allowed_capabilities

    async def run(self, goal: Goal, *, recover_interrupted: bool = False) -> dict:
        with self.store.lock():
            return await self._run(goal, recover_interrupted)

    async def _run(self, goal: Goal, recover: bool) -> dict:
        state = self.store.goal(goal)
        self.store.reconcile_seals(goal.id)
        history = self.store.history(goal.id)
        # A crash after sealing but before checkpointing is reconciled from evidence.
        if state["active"]:
            sealed = next((e for e in history if e.id == state["active"]["id"]), None)
            if sealed:
                self._record_candidate(goal, state, sealed)
                state["active"] = None
                self.store.checkpoint(goal, state)
            elif not recover:
                return {
                    **state,
                    "status": "interrupted",
                    "reason": "Explicit recovery required; running work is never replayed silently",
                }
            else:
                active = state["active"]
                plan = Plan.model_validate(active["plan"])
                results = self.store.recorded_results(goal.id, active["id"])
                task_ids = {task.id for task in plan.graph.tasks}
                if any(result.task_id not in task_ids for result in results):
                    raise ValueError("Recorded recovery result references an unknown task")
                reasons = [
                    "Interrupted experiment; unfinished execution is not assumed to have stopped."
                ]
                for result in results:
                    for artifact in result.artifacts:
                        if not artifact.verify(self.store.directory(active["id"])):
                            reasons.append(
                                f"Recorded task artifact changed or is missing: {result.task_id}: {artifact.path}"
                            )
                experiment = Experiment(
                    id=active["id"],
                    goal=goal.id,
                    parent=state["best_valid_candidate"],
                    hypothesis=plan.hypothesis,
                    tasks=plan.graph.tasks,
                    results=results,
                    artifacts=self.store.snapshot(active["id"]),
                    evaluations=(
                        Evaluation(
                            evaluator="controller.recovery", passed=False, reasons=tuple(reasons)
                        ),
                    ),
                    provenance=Provenance(
                        parameters={
                            "plan_id": plan.id,
                            "recovery": "recorded terminal task results and current artifact snapshot",
                            "tasks_without_terminal_result": sorted(
                                task_ids - {result.task_id for result in results}
                            ),
                        }
                    ),
                    status="interrupted",
                )
                self.store.seal(experiment)
                self._record_candidate(goal, state, experiment)
                state["active"] = None
                self.store.checkpoint(goal, state)
                history = self.store.history(goal.id)
        if state["status"] == "succeeded":
            return state
        started = time.monotonic()
        prior = Usage.model_validate(state["usage"])
        usage = prior

        def save(event: Event | None = None):
            nonlocal usage
            usage = usage.model_copy(
                update={"wall_seconds": prior.wall_seconds + time.monotonic() - started}
            )
            state["usage"] = usage.model_dump(mode="json")
            self.store.checkpoint(goal, state, event=event)

        while True:
            save()
            if self.budget.exhausted(usage):
                state["status"] = "budget_exhausted"
                save()
                return state
            try:
                plan = await asyncio.wait_for(
                    self.planner.plan(goal, history, self.registry),
                    max(0.001, self.budget.wall_seconds - usage.wall_seconds),
                )
            except TimeoutError:
                state["status"] = "budget_exhausted"
                save()
                return state
            if plan is None:
                state["status"] = "no_more_plans"
                save()
                return state
            for task in plan.graph.tasks:
                self.registry.get(task.capability)
                if self.allowed is not None and task.capability not in self.allowed:
                    raise PermissionError(f"Capability forbidden by policy: {task.capability}")
            # Constraints select trusted evaluator implementations, not task-supplied verdicts.
            evaluators = [(name, self.registry.evaluator(name)) for name in goal.constraints]
            experiment_id = uid()
            directory = self.store.directory(experiment_id)
            directory.mkdir(parents=True)
            state["status"] = "running"
            state["active"] = {"id": experiment_id, "plan": plan.model_dump(mode="json")}
            usage = usage.model_copy(update={"experiments": usage.experiments + 1})
            save()
            self.store.emit(
                Event(
                    kind="experiment.started",
                    goal_id=goal.id,
                    experiment_id=experiment_id,
                    payload={"plan": plan.model_dump(mode="json")},
                )
            )
            results: dict[str, TaskResult] = {}
            interrupted = False
            try:
                while len(results) < len(plan.graph.tasks):
                    completed = {
                        key for key, value in results.items() if value.status == "succeeded"
                    }
                    ready = [t for t in plan.graph.ready(completed) if t.id not in results]
                    if not ready:
                        break
                    task = ready[0]
                    for attempt in range(task.max_retries + 1):
                        save()
                        # Experiment count reserves a slot; only other limits apply within it.
                        running_usage = usage.model_copy(update={"experiments": 0})
                        if self.budget.exhausted(running_usage):
                            interrupted = True
                            break
                        timeout = min(
                            task.timeout_seconds, self.budget.wall_seconds - usage.wall_seconds
                        )
                        usage = usage.model_copy(update={"tasks": usage.tasks + 1})
                        save()
                        context = ExecutionContext(
                            goal=goal,
                            experiment_id=experiment_id,
                            directory=directory,
                            previous_results=results,
                            remaining=self.budget.model_copy(
                                update={
                                    "max_tokens": max(0, self.budget.max_tokens - usage.tokens),
                                    "max_cost": max(0, self.budget.max_cost - usage.cost),
                                    "max_gpu_seconds": max(
                                        0, self.budget.max_gpu_seconds - usage.gpu_seconds
                                    ),
                                    "wall_seconds": max(
                                        0, self.budget.wall_seconds - usage.wall_seconds
                                    ),
                                    "max_tasks": max(0, self.budget.max_tasks - usage.tasks),
                                    "max_experiments": max(
                                        0, self.budget.max_experiments - usage.experiments
                                    ),
                                }
                            ),
                        )
                        self.store.emit(
                            Event(
                                kind="task.started",
                                goal_id=goal.id,
                                experiment_id=experiment_id,
                                payload={"task": task.id, "attempt": attempt},
                            )
                        )
                        try:
                            result = await asyncio.wait_for(
                                self.registry.get(task.capability).execute(task, context), timeout
                            )
                            if result.task_id != task.id:
                                raise ValueError("Capability returned a mismatched task ID")
                            if any(not a.verify(directory) for a in result.artifacts):
                                raise ValueError("Capability returned invalid evidence")
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            result = TaskResult(
                                task_id=task.id,
                                status="failed",
                                error=f"{type(exc).__name__}: {exc}",
                            )
                        usage = usage.model_copy(
                            update={
                                "tokens": usage.tokens + result.usage.tokens,
                                "cost": usage.cost + result.usage.cost,
                                "gpu_seconds": usage.gpu_seconds + result.usage.gpu_seconds,
                            }
                        )
                        results[task.id] = result
                        save(
                            Event(
                                kind="task.finished",
                                goal_id=goal.id,
                                experiment_id=experiment_id,
                                payload=result.model_dump(mode="json"),
                            )
                        )
                        if result.status == "succeeded":
                            break
                    if interrupted:
                        break
                evaluations = []
                if len(results) == len(plan.graph.tasks) and all(
                    r.status == "succeeded" and all(a.verify(directory) for a in r.artifacts)
                    for r in results.values()
                ):
                    for name, evaluator in evaluators:
                        try:
                            remaining_time = max(
                                0.001,
                                self.budget.wall_seconds
                                - (prior.wall_seconds + time.monotonic() - started),
                            )
                            evaluated = await asyncio.wait_for(
                                evaluator.evaluate(goal, tuple(results.values()), directory),
                                remaining_time,
                            )
                            # Evaluator's registry identity is authoritative.
                            evaluations.append(evaluated.model_copy(update={"evaluator": name}))
                        except Exception as exc:
                            evaluations.append(
                                Evaluation(
                                    evaluator=name,
                                    passed=False,
                                    reasons=(f"{type(exc).__name__}: {exc}",),
                                )
                            )
                else:
                    evaluations = [
                        Evaluation(
                            evaluator=name,
                            passed=False,
                            reasons=("Task graph did not complete successfully",),
                        )
                        for name, _ in evaluators
                    ]
                artifacts = self.store.snapshot(experiment_id)
                valid = bool(evaluations) and all(e.passed for e in evaluations)
                experiment = Experiment(
                    id=experiment_id,
                    goal=goal.id,
                    parent=state["best_valid_candidate"],
                    hypothesis=plan.hypothesis,
                    tasks=plan.graph.tasks,
                    results=tuple(results.values()),
                    artifacts=artifacts,
                    evaluations=tuple(evaluations),
                    provenance=Provenance(parameters={"plan_id": plan.id}),
                    status="interrupted" if interrupted else ("valid" if valid else "rejected"),
                )
                self.store.seal(experiment)
                self._record_candidate(goal, state, experiment)
                state["active"] = None
                save()
                self.store.emit(
                    Event(
                        kind="experiment.finished",
                        goal_id=goal.id,
                        experiment_id=experiment_id,
                        payload={
                            "status": experiment.status,
                            "goal_satisfied": state["status"] == "succeeded",
                        },
                    )
                )
                history = self.store.history(goal.id)
                if state["status"] == "succeeded":
                    return state
            except BaseException:
                state["status"] = "interrupted"
                save()
                raise

    def _record_candidate(self, goal: Goal, state: dict, experiment: Experiment):
        state["latest_candidate"] = experiment.id
        valid = (
            experiment.status in {"valid", "baseline", "promoted"}
            and bool(experiment.evaluations)
            and all(e.passed for e in experiment.evaluations)
        )
        metrics = {key: value for e in experiment.evaluations for key, value in e.metrics.items()}
        # All target dimensions must weakly improve; avoid mixing unrelated units in a sum.
        score = {key: metrics.get(key, float("-inf")) for key in goal.target}
        if valid and all(value != float("-inf") for value in score.values()):
            if state["baseline"] is None:
                state["baseline"] = experiment.id
            if state["score"] is None or all(score[k] >= state["score"][k] for k in score):
                state["best_valid_candidate"], state["score"] = experiment.id, score
        state["status"] = (
            "succeeded" if valid and goal.satisfied(experiment.evaluations) else "running"
        )
