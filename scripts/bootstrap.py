"""Clone and install a matching ATOM workspace. Run with Python 3.12 or 3.13."""

import argparse
import subprocess
import sys
from pathlib import Path

REPOSITORIES = ("core", "controller", "agents", "hpc", "science", "geos")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path("NexusATOM"))
    parser.add_argument(
        "--ref", default="v0.1.0", help="Matching release tag; use main for development"
    )
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in REPOSITORIES:
        path = root / f"nexus-atom-{name}"
        if not path.exists():
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--branch",
                    args.ref,
                    f"https://github.com/NexusATOM/nexus-atom-{name}.git",
                    str(path),
                ],
                check=True,
            )
        elif not (path / ".git").exists():
            raise SystemExit(f"Refusing existing non-repository directory: {path}")
        else:
            print(f"Preserving existing checkout: {path}; verify its revision before using it")
    venv = root / ".venv"
    if not venv.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    python = venv / "bin/python"
    command = [str(python), "-m", "pip", "install"]
    for name in REPOSITORIES:
        extra = "[dev,nooa]" if args.dev and name == "geos" else "[dev]" if args.dev else ""
        command += ["-e", str(root / f"nexus-atom-{name}") + extra]
    subprocess.run(command, check=True)
    print(f"Run {venv}/bin/atom plugins")


if __name__ == "__main__":
    main()
