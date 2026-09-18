"""Append-only evidence, journaled sealing and transactional control-plane state."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path

from nexus_atom_core import Artifact, Event, Experiment, Goal, TaskResult, canonical


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "state.sqlite", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS goals(id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, data TEXT NOT NULL, sha TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pending_seals(id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, data TEXT NOT NULL, sha TEXT NOT NULL);
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

    def checkpoint(self, goal: Goal, state: dict, *, event: Event | None = None):
        """Commit checkpoint and an optional task event in one SQLite transaction."""
        if event is not None and event.goal_id != goal.id:
            raise ValueError("Checkpoint event belongs to another goal")
        with self.db:
            updated = self.db.execute(
                "UPDATE goals SET state=? WHERE id=?", (json.dumps(state, allow_nan=False), goal.id)
            )
            if updated.rowcount != 1:
                raise KeyError(goal.id)
            if event is not None:
                self.db.execute("INSERT INTO events(data) VALUES(?)", (event.model_dump_json(),))

    def emit(self, event: Event):
        with self.db:
            self.db.execute("INSERT INTO events(data) VALUES(?)", (event.model_dump_json(),))

    def directory(self, experiment_id: str) -> Path:
        path = self.root / "experiments" / experiment_id
        if path.is_symlink() or path.resolve().parent != (self.root / "experiments").resolve():
            raise ValueError("Invalid experiment ID or symlinked directory")
        return path

    def snapshot(self, experiment_id: str) -> tuple[Artifact, ...]:
        """Capture current files, excluding Git internals and sealing metadata."""
        directory = self.directory(experiment_id)
        return tuple(
            Artifact.capture(path, directory)
            for path in sorted(directory.rglob("*"))
            if path.is_file()
            and not path.is_symlink()
            and ".git" not in path.relative_to(directory).parts
            and path != directory / "metadata.json"
            and not (path.parent == directory and path.name.startswith(".atom-seal-"))
            and not (path.parent == directory / "_atom_report" and path.name.startswith(".report-"))
        )

    def recorded_results(self, goal_id: str, experiment_id: str) -> tuple[TaskResult, ...]:
        """Latest terminal result for each recorded task; retries remain in events."""
        results = {}
        for event in self.events():
            if (
                event["goal_id"] == goal_id
                and event.get("experiment_id") == experiment_id
                and event["kind"] == "task.finished"
            ):
                result = TaskResult.model_validate(event["payload"])
                results[result.task_id] = result
        return tuple(results.values())

    @staticmethod
    def _decode_record(row) -> Experiment:
        data = row["data"].encode()
        if hashlib.sha256(data).hexdigest() != row["sha"]:
            raise ValueError(f"Experiment record corrupted: {row['id']}")
        experiment = Experiment.model_validate_json(data)
        if (
            experiment.id != row["id"]
            or experiment.goal != row["goal_id"]
            or canonical(experiment) != data
        ):
            raise ValueError(f"Experiment record identity corrupted: {row['id']}")
        return experiment

    def _verify_artifacts(self, experiment: Experiment):
        if any(
            not artifact.verify(self.directory(experiment.id)) for artifact in experiment.artifacts
        ):
            raise ValueError(f"Experiment artifact corrupted: {experiment.id}")

    @staticmethod
    def _sync_directory(directory: Path):
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _publish_metadata(self, experiment: Experiment):
        """Atomically publish a flushed file without replacing existing evidence."""
        directory = self.directory(experiment.id)
        directory.mkdir(parents=True, exist_ok=True)
        metadata = directory / "metadata.json"
        data = canonical(experiment)
        if metadata.is_symlink():
            raise ValueError("Experiment metadata cannot be a symlink")
        if metadata.exists():
            if metadata.read_bytes() != data:
                raise ValueError("Experiment evidence is immutable")
            return
        descriptor, name = tempfile.mkstemp(prefix=".atom-seal-", dir=directory)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fchmod(output.fileno(), 0o444)
                os.fsync(output.fileno())
            try:
                # A hard link publishes the complete file atomically and refuses to overwrite.
                os.link(temporary, metadata)
            except FileExistsError:
                if metadata.is_symlink() or metadata.read_bytes() != data:
                    raise ValueError("Experiment evidence is immutable") from None
            self._sync_directory(directory)
        finally:
            temporary.unlink(missing_ok=True)

    def _commit_seal(self, experiment: Experiment):
        """Move the durable intent to the ledger after metadata publication."""
        with self.db:
            row = self.db.execute(
                "SELECT * FROM pending_seals WHERE id=?", (experiment.id,)
            ).fetchone()
            if row is None or self._decode_record(row) != experiment:
                raise ValueError("Sealing intent missing or changed")
            existing = self.db.execute(
                "SELECT * FROM experiments WHERE id=?", (experiment.id,)
            ).fetchone()
            if existing is not None and self._decode_record(existing) != experiment:
                raise ValueError("Experiment already sealed with different content")
            self.db.execute(
                "INSERT OR IGNORE INTO experiments VALUES(?,?,?,?)",
                (row["id"], row["goal_id"], row["data"], row["sha"]),
            )
            self.db.execute("DELETE FROM pending_seals WHERE id=?", (experiment.id,))

    def seal(self, experiment: Experiment):
        """Journal exact evidence before publishing it; safe to retry after a crash.

        Call under Store.lock when coordinating with controller execution. Files of
        a completed experiment are never silently recreated or overwritten.
        """
        data = canonical(experiment)
        digest = hashlib.sha256(data).hexdigest()
        existing = self.db.execute(
            "SELECT * FROM experiments WHERE id=?", (experiment.id,)
        ).fetchone()
        if existing is not None:
            if self._decode_record(existing) != experiment:
                raise ValueError("Experiment already sealed with different content")
            self._verify_metadata(existing)
            self._verify_artifacts(experiment)
            return
        self._verify_artifacts(experiment)
        with self.db:
            pending = self.db.execute(
                "SELECT * FROM pending_seals WHERE id=?", (experiment.id,)
            ).fetchone()
            if pending is not None and self._decode_record(pending) != experiment:
                raise ValueError("Experiment sealing intent already has different content")
            self.db.execute(
                "INSERT OR IGNORE INTO pending_seals VALUES(?,?,?,?)",
                (experiment.id, experiment.goal, data.decode(), digest),
            )
        self._publish_metadata(experiment)
        self._commit_seal(experiment)

    def reconcile_seals(self, goal_id: str) -> tuple[str, ...]:
        """Finish journaled file/ledger commits; no capability or evaluator is rerun.

        The controller invokes this while holding its lock. Corruption fails closed;
        read-only history/service calls never invoke recovery implicitly.
        """
        rows = self.db.execute(
            "SELECT * FROM pending_seals WHERE goal_id=? ORDER BY rowid", (goal_id,)
        ).fetchall()
        completed = []
        for row in rows:
            experiment = self._decode_record(row)
            self._verify_artifacts(experiment)
            self._publish_metadata(experiment)
            self._commit_seal(experiment)
            completed.append(experiment.id)
        return tuple(completed)

    def _verify_metadata(self, row):
        path = self.directory(row["id"]) / "metadata.json"
        if (
            path.is_symlink()
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha"]
        ):
            raise ValueError(f"Experiment metadata corrupted: {row['id']}")

    def history(self, goal_id: str) -> tuple[Experiment, ...]:
        result = []
        for row in self.db.execute(
            "SELECT * FROM experiments WHERE goal_id=? ORDER BY rowid", (goal_id,)
        ):
            experiment = self._decode_record(row)
            self._verify_metadata(row)
            self._verify_artifacts(experiment)
            result.append(experiment)
        return tuple(result)

    def events(self) -> list[dict]:
        return [
            Event.model_validate_json(row[0]).model_dump(mode="json")
            for row in self.db.execute("SELECT data FROM events ORDER BY seq")
        ]
