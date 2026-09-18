"""Validated, credential-free CLI configuration for optional proposal runtimes."""

from pathlib import Path
from typing import Literal

from nexus_atom_core import Contract
from pydantic import Field, model_validator

from .planning import RuntimePlanner


class PlannerConfig(Contract):
    runtime: Literal["local", "nooa", "openai"]
    model: str | None = None
    argv: tuple[str, ...] = ()
    capability_guidance: dict = Field(default_factory=dict)
    history_limit: int = Field(default=5, gt=0)
    max_output_tokens: int = Field(default=4096, gt=0)
    timeout_seconds: float = Field(default=120, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_backend(self):
        if self.runtime == "local":
            if not self.argv or any(not arg for arg in self.argv) or self.model is not None:
                raise ValueError("Local planning requires nonempty argv and no model")
        elif not self.model or not self.model.strip() or self.argv:
            raise ValueError("Provider planning requires an explicit model and no argv")
        return self

    def create(self, directory: Path) -> RuntimePlanner:
        try:
            from nexus_atom_agents import LocalRuntime, NOOARuntime, OpenAIRuntime

            if self.runtime == "local":
                runtime = LocalRuntime(self.argv, timeout=self.timeout_seconds)
            elif self.runtime == "nooa":
                # Fail before starting work if the selected optional dependency is absent.
                import nooa  # noqa: F401

                runtime = NOOARuntime(self.model)
            else:
                runtime = OpenAIRuntime(self.model, timeout=self.timeout_seconds)
        except ModuleNotFoundError as exc:
            raise ValueError(
                f"Planning runtime dependency missing: {exc.name}; install controller[agents] "
                "and the selected nexus-atom-agents provider extra"
            ) from exc
        return RuntimePlanner(
            runtime,
            directory,
            capability_guidance=self.capability_guidance,
            history_limit=self.history_limit,
            max_output_tokens=self.max_output_tokens,
            timeout_seconds=self.timeout_seconds,
        )


def bind_planner_config(store, goal, supplied: PlannerConfig | None, *, explicit_plans=False):
    """Persist the runtime choice and reuse it on resume; never silently replace it."""
    with store.lock():
        state = store.goal(goal)
        saved = state.get("planner_config")
        if saved is not None:
            if explicit_plans:
                raise ValueError("Saved runtime planner cannot be replaced by --plans")
            config = PlannerConfig.model_validate(saved)
            if supplied is not None and supplied != config:
                raise ValueError("Planner configuration differs from saved goal; create a new goal")
            return config
        if supplied is not None:
            if (
                state["active"]
                or store.history(goal.id)
                or any(event["goal_id"] == goal.id for event in store.events())
            ):
                raise ValueError("Cannot change planner after work has begun; create a new goal")
            state["planner_config"] = supplied.model_dump(mode="json")
            store.checkpoint(goal, state)
        return supplied
