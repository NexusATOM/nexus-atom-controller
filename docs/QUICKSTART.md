# Start with a small example

Run `atom demo` to see the orchestration loop without GEOS, a GPU, a scheduler account or an API key. It optimizes a tiny Python function that sums integers from zero through `n - 1`.

## Install

The full workspace gives you all packages and model examples:

```bash
git clone https://github.com/NexusATOM/nexus-atom-controller.git
python3 nexus-atom-controller/scripts/bootstrap.py --directory NexusATOM --ref main
source NexusATOM/.venv/bin/activate
```

Use Python 3.12 or 3.13. This creates an isolated virtual environment. The release default is `v0.1.0`; `--ref main` selects current development. The packages are on GitHub, not published to PyPI.

A minimal checkout needs only Core, Controller, HPC and Science. Clone those four repositories beside each other, create a virtual environment and install them together:

```bash
python -m pip install -e ./nexus-atom-core -e './nexus-atom-controller[demo]' \
  -e ./nexus-atom-hpc -e ./nexus-atom-science
```

## Run the whole process

```bash
atom demo --state .atom/toy
```

The demo executes three real experiments:

| Attempt | Code | Expected decision |
|---|---|---|
| Baseline | Loop over every integer | Correct, 1× baseline, target not met |
| Wrong candidate | `n * (n + 1) // 2` | Fast but incorrect; rejected |
| Correct candidate | `n * (n - 1) // 2` | Correct and fast; accepted if measured speedup reaches 3× |

Every attempt compiles the source and runs it in a separate local process through the HPC package. A monotonic application timer measures three trials after a warmup. The Science package compares multiple input/output pairs against the reference. Controller evaluators decide acceptance; a speedup cannot override incorrect results.

These are **prepared candidates**, so the run is reproducible and requires no agent provider. The demonstration illustrates a dramatic algorithmic simplification, not a GPU transformation. Timings vary by host and must never be reported as GEOS performance. Extremely unusual host conditions can leave the target unmet; ATOM then reports `budget_exhausted` rather than changing the criteria.

## Watch pause and resume

Use a different state directory if you already ran the previous command:

```bash
atom demo --state .atom/toy-resume --pause-after 1
atom demo --state .atom/toy-resume --resume
atom demo --state .atom/toy-resume --resume
```

The first command stops after the baseline with `budget_exhausted`; this is an intentional experiment-budget checkpoint, not a failed calculation. The second reopens the saved goal and runs the two remaining candidates. The third verifies the finished goal and returns without running tasks again.

`--pause-after` is the total allowed experiment count, not an additional number on each invocation. Use `--pause-after 2` to stop after the rejected candidate. An already completed directory requires `--resume`; a fresh directory starts a new goal.

## Inspect what was saved

The terminal prints the goal ID. Substitute it below:

```bash
atom status GOAL_ID --state .atom/toy
atom ledger GOAL_ID --state .atom/toy
atom events --state .atom/toy
atom serve --state .atom/toy --port 8765
```

Open `http://127.0.0.1:8765/goals/GOAL_ID` for a read-only JSON view. The report is `.atom/toy/demo-report.md` (also JSON). The state layout is:

```text
.atom/toy/
├── demo-goal.json           # immutable goal identity for the demo
├── demo-report.md          # human-readable summary, refreshed on resume
├── demo-report.json
├── state.sqlite            # goals, checkpoint, events and experiment ledger
└── experiments/<id>/
    ├── source/kernel.py    # exact candidate
    ├── source/worker.py    # benchmark/validation harness
    ├── jobs/build/         # actual compiler stdout/stderr
    ├── jobs/measure/       # actual run stdout/stderr
    ├── measurement.json    # raw output values and timing samples
    └── metadata.json       # sealed results, evaluations and artifact hashes
```

Do not edit files inside sealed experiments. Resume detects changed artifacts. You may inspect rejected source and logs without affecting the baseline or promoted candidate.

## Which repository did what?

* **Core** defined the goal, tasks, artifacts and evaluations.
* **Controller** planned attempts, enforced the budget, saved state, rejected the bad candidate and selected the best one.
* **HPC** compiled and executed local subprocesses and retained their logs.
* **Science** compared the candidate's numerical outputs to the reference.
* **Agents** was unnecessary because candidates were prepared; in a live workflow a configured runtime proposes them.
* **GEOS** was unnecessary because this example runs an ordinary Python kernel.

Continue with [the repository map](REPOSITORIES.md), [CLI and configuration](USAGE.md), [architecture](ARCHITECTURE.md), or [extension tutorial](EXTENDING.md).
