"""Model-independent CLI; plugins own configuration, workflows and criteria."""

import argparse
import asyncio
import json
from pathlib import Path

from nexus_atom_core import Budget, CapabilityRegistry, Goal, Plan

from .discovery import PluginPlanner, discover_plugins
from .engine import Controller, SequencePlanner
from .planner_config import PlannerConfig, bind_planner_config
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="atom", description="Nexus ATOM goal-driven Earth-model orchestration"
    )
    parser.add_argument("--version", action="version", version="nexus-atom-controller 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plugins")
    demo = commands.add_parser("demo", help="Run the small offline optimization example")
    demo.add_argument("--state", type=Path, default=Path(".atom/toy"))
    demo.add_argument("--resume", action="store_true")
    demo.add_argument(
        "--pause-after", type=int, choices=(1, 2), help="Stop at a durable experiment checkpoint"
    )
    service = commands.add_parser("serve")
    service.add_argument("--state", type=Path, default=Path(".atom"))
    service.add_argument("--port", type=int, default=8765)
    for name in ("run", "resume"):
        sub = commands.add_parser(name)
        sub.add_argument("objective" if name == "run" else "goal_id")
        sub.add_argument("--system", required=True)
        sub.add_argument("--config", type=Path)
        sub.add_argument("--demo", action="store_true")
        sub.add_argument("--state", type=Path, default=Path(".atom"))
        planning = sub.add_mutually_exclusive_group()
        planning.add_argument("--plans", type=Path)
        planning.add_argument(
            "--planner-config",
            type=Path,
            help="JSON runtime planner configuration; saved with the goal",
        )
        sub.add_argument(
            "--budget", type=Path, help="JSON Budget; overrides individual CLI budget flags"
        )
        sub.add_argument("--target", action="append", default=[], metavar="METRIC=MINIMUM")
        sub.add_argument("--max-experiments", type=int, default=3)
        sub.add_argument("--max-tasks", type=int, default=100)
        sub.add_argument("--wall-seconds", type=float, default=3600)
        sub.add_argument("--recover-interrupted", action="store_true")
    for name in ("status", "ledger", "events"):
        sub = commands.add_parser(name)
        sub.add_argument("goal_id", nargs="?")
        sub.add_argument("--state", type=Path, default=Path(".atom"))
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            from .examples.toy import run_demo

            report = asyncio.run(
                run_demo(args.state, resume=args.resume, pause_after=args.pause_after)
            )
            return 0 if report["status"] == "succeeded" or args.pause_after else 2
        if args.command == "serve":
            from .service import serve

            serve(args.state, port=args.port)
            return 0
        if args.command == "plugins":
            print(
                json.dumps(
                    {name: point.value for name, point in discover_plugins().items()}, indent=2
                )
            )
            return 0
        store = Store(args.state)
        try:
            if args.command == "events":
                print(json.dumps(store.events(), indent=2))
                return 0
            if args.command in {"status", "ledger"}:
                if not args.goal_id:
                    parser.error("goal_id is required")
                goal = store.load_goal(args.goal_id)
                value = (
                    store.goal(goal)
                    if args.command == "status"
                    else [e.model_dump(mode="json") for e in store.history(goal.id)]
                )
                print(json.dumps(value, indent=2))
                return 0
            points = discover_plugins()
            if args.system not in points:
                raise ValueError(f"Plugin not installed: {args.system}")
            factory = points[args.system].load()
            if args.demo:
                if args.command == "resume":
                    raise ValueError(
                        "Resume a demo with its saved --config; do not recreate the baseline"
                    )
                plugin = factory.demo(args.state / "demo")
            elif args.config:
                plugin = factory.from_config(args.config.resolve())
            else:
                raise ValueError(
                    "Supply --config for site execution or --demo for synthetic examples"
                )
            registry = CapabilityRegistry()
            registry.register(plugin)
            targets = {}
            for raw in args.target:
                key, value = raw.split("=", 1)
                targets[key] = float(value)
            goal = (
                store.load_goal(args.goal_id)
                if args.command == "resume"
                else Goal(
                    objective=args.objective,
                    system=args.system,
                    target=targets,
                    constraints=plugin.goal_constraints(),
                )
            )
            if goal.system != args.system:
                raise ValueError("Resume system does not match persisted goal")
            runtime_config = bind_planner_config(
                store,
                goal,
                PlannerConfig.model_validate_json(args.planner_config.read_text())
                if args.planner_config
                else None,
                explicit_plans=bool(args.plans),
            )
            planner = (
                SequencePlanner(
                    [Plan.model_validate(p) for p in json.loads(args.plans.read_text())]
                )
                if args.plans
                else PluginPlanner(plugin)
            )
            if runtime_config is not None:
                planner = runtime_config.create(store.root / "planning" / goal.id)
            controller = Controller(
                registry,
                planner,
                store,
                Budget.model_validate_json(args.budget.read_text())
                if args.budget
                else Budget(
                    max_experiments=args.max_experiments,
                    max_tasks=args.max_tasks,
                    wall_seconds=args.wall_seconds,
                ),
            )
            result = asyncio.run(controller.run(goal, recover_interrupted=args.recover_interrupted))
            print(json.dumps({"goal_id": goal.id, **result}, indent=2))
            return 0 if result["status"] == "succeeded" else 2
        finally:
            store.close()
    except (ValueError, KeyError, RuntimeError, OSError) as exc:
        parser.exit(2, f"atom: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
