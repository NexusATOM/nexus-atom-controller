"""Append-only experiment evidence and transactional control-plane state."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from nexus_atom_core import Event, Experiment, Goal, canonical


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "state.sqlite", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS goals(id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, data TEXT NOT NULL, sha TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def lock(self):
        import fcntl

        with (self.root / ".lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Another controller owns this state directory") from exc
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def goal(self, goal: Goal) -> dict:
        row = self.db.execute("SELECT spec,state FROM goals WHERE id=?", (goal.id,)).fetchone()
        if row:
            if json.loads(row["spec"]) != goal.model_dump(mode="json"):
                raise ValueError("Cannot change a persisted goal; create a new goal")
            return json.loads(row["state"])
        state = {
            "status": "pending",
            "usage": {},
            "baseline": None,
            "best_valid_candidate": None,
            "latest_candidate": None,
            "active": None,
            "score": None,
        }
        with self.db:
            self.db.execute(
                "INSERT INTO goals VALUES(?,?,?)",
                (goal.id, goal.model_dump_json(), json.dumps(state)),
            )
        return state

    def load_goal(self, goal_id: str) -> Goal:
        row = self.db.execute("SELECT spec FROM goals WHERE id=?", (goal_id,)).fetchone()
        if not row:
            raise KeyError(goal_id)
        return Goal.model_validate_json(row["spec"])

    def checkpoint(self, goal: Goal, state: dict):
        with self.db:
            self.db.execute(
                "UPDATE goals SET state=? WHERE id=?", (json.dumps(state, allow_nan=False), goal.id)
            )

    def emit(self, event: Event):
        with self.db:
            self.db.execute("INSERT INTO events(data) VALUES(?)", (event.model_dump_json(),))

    def directory(self, experiment_id: str) -> Path:
        path = self.root / "experiments" / experiment_id
        if path.resolve().parent != (self.root / "experiments").resolve():
            raise ValueError("Invalid experiment ID")
        return path

    def seal(self, experiment: Experiment):
        data = canonical(experiment)
        directory = self.directory(experiment.id)
        directory.mkdir(parents=True, exist_ok=True)
        metadata = directory / "metadata.json"
        if metadata.exists() and metadata.read_bytes() != data:
            raise ValueError("Experiment evidence is immutable")
        if not metadata.exists():
            with metadata.open("xb") as output:
                output.write(data)
        digest = hashlib.sha256(data).hexdigest()
        with self.db:
            old = self.db.execute(
                "SELECT sha FROM experiments WHERE id=?", (experiment.id,)
            ).fetchone()
            if old and old["sha"] != digest:
                raise ValueError("Experiment already sealed with different content")
            self.db.execute(
                "INSERT OR IGNORE INTO experiments VALUES(?,?,?,?)",
                (experiment.id, experiment.goal, data.decode(), digest),
            )
        metadata.chmod(0o444)

    def history(self, goal_id: str) -> tuple[Experiment, ...]:
        result = []
        for row in self.db.execute(
            "SELECT * FROM experiments WHERE goal_id=? ORDER BY rowid", (goal_id,)
        ):
            path = self.directory(row["id"]) / "metadata.json"
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha"]:
                raise ValueError(f"Experiment metadata corrupted: {row['id']}")
            experiment = Experiment.model_validate_json(row["data"])
            if any(not a.verify(path.parent) for a in experiment.artifacts):
                raise ValueError(f"Experiment artifact corrupted: {row['id']}")
            result.append(experiment)
        return tuple(result)

    def events(self) -> list[dict]:
        return [
            json.loads(row[0]) for row in self.db.execute("SELECT data FROM events ORDER BY seq")
        ]
