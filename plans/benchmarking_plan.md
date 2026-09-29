# DevAgent Benchmarking Plan

> Scope: B3 (native task set), B4 (cost-to-correctness sweep), B5 (CI canary)
> Status: **Complete — Phase 17 shipped**

---

## Overview

Three complementary benchmarks that together give a complete picture of DevAgent's
real-world performance:

| ID | Name | Primary question | LLM required? | Runs in CI? |
|---|---|---|---|---|
| B3 | Native task set | "Can DevAgent solve real dev tasks?" | Yes (--live) or No (--dry) | No (too slow) |
| B4 | Cost-to-correctness sweep | "Which config gives the best value?" | Yes | No |
| B5 | Canary | "Did this PR break anything?" | No (mock mode) | Yes |

---

## B3 — Native Task Set

### Task format

Each task in `benchmarks/tasks/task_set.json` follows this schema:

```json
{
  "id": "bug-fix-001",
  "category": "bug_fix",
  "difficulty": "easy",
  "description": "What the user types to the agent",
  "fixture_project": "sample_project",
  "oracle_check": "python -m pytest tests/test_math.py -q",
  "oracle_pass_exit_code": 0,
  "expected_files_touched": ["src/math_utils.py"],
  "max_iterations": 10,
  "timeout_sec": 60,
  "tags": ["python", "pytest"]
}
```

### Fixture project

`benchmarks/fixtures/sample_project/` — a tiny Python project with intentional bugs,
missing features, and a security issue. Each task references this project.
The runner copies it to a temp dir before each task run so state never bleeds.

### CLI

```bash
devagent bench native                                # all tasks, dry-run (mock LLM)
devagent bench native --live                         # real LLM required
devagent bench native --category bug_fix             # filter by category
devagent bench native --difficulty easy              # filter by difficulty
devagent bench native --output json > results.json   # machine-readable output
```

### Metrics reported

| Metric | Description |
|---|---|
| `pass_rate` | % of tasks where oracle passes |
| `avg_iterations` | Average tool-call iterations per task |
| `avg_cost_usd` | Average LLM cost per task (live mode only) |
| `avg_duration_sec` | Average wall-clock time per task |
| Per-category breakdown | pass_rate split by category and difficulty |

---

## B4 — Cost-to-Correctness Sweep

Answers: *"At what cost does correctness plateau?"*

```bash
devagent bench sweep --params model,iterations
devagent bench sweep --params model,iterations,effort --tasks 10
```

### Parameter grid (defaults)

```json
{
  "model": ["ollama/qwen2.5-coder:7b", "anthropic/claude-haiku-4-5"],
  "max_iterations": [10, 30, 50],
  "effort": ["low", "high", "max"]
}
```

### Output

Rich table comparing `pass_rate` vs `avg_cost_usd` for each combination.
Results saved to `benchmarks/results/sweep_TIMESTAMP.json`.

---

## B5 — CI Canary

Runs on every PR. Must complete in < 3 minutes. Never requires a real LLM.

### What it tests

The canary runs three categories of checks:

1. **Framework checks** — tool registration, config loading, session lifecycle.
   These are pure Python assertions with no agent loop.

2. **Mock-agent tasks** — the existing `bench_security.py` and `bench_tasks.py`
   scripts already use mock LLM responses. The canary runs them as subprocess calls
   and checks exit codes.

3. **Oracle dry-run** — 5 easy tasks from `benchmarks/tasks/canary.json` run
   with `--dry` flag. The runner applies a pre-defined "patch" (stored in the
   task JSON) and verifies the oracle passes. Tests the evaluation framework,
   not the LLM.

### Pass threshold

`pass_rate >= 0.80` → exit 0 (CI green)
`pass_rate < 0.80` → exit 1 (CI red)

### CLI

```bash
devagent bench canary                    # exit 0/1 based on pass threshold
devagent bench canary --threshold 0.9    # stricter threshold
```

### GitHub Actions

`.github/workflows/canary.yml` runs on every PR to `main`. No API keys needed.

---

## Module structure

```
devagent/bench/
  __init__.py
  runner.py      # BenchRunner: load tasks, copy fixture, run, evaluate
  oracle.py      # OracleEvaluator: run oracle_check, return pass/fail
  report.py      # BenchReport: Rich table + JSON output
  sweep.py       # SweepRunner: parameter grid over BenchRunner

benchmarks/
  tasks/
    task_set.json        # B3: 20 full tasks
    canary.json          # B5: 5 dry-run tasks + framework checks manifest
  fixtures/
    sample_project/      # fixture project for task execution
  results/               # gitignored — local output only
  bench_security.py      # existing (used by canary)
  bench_tasks.py         # existing (used by canary)
  bench_token_usage.py   # existing (used by canary)

.github/workflows/
  canary.yml             # B5: runs devagent bench canary on every PR
```

---

## Implementation order

1. Fixture project + task_set.json (B3 data layer)
2. `devagent/bench/oracle.py` + `runner.py` (execution engine)
3. `devagent/bench/report.py` (output)
4. `devagent/bench/sweep.py` (B4)
5. CLI commands wired into `devagent/cli.py`
6. canary.json + `.github/workflows/canary.yml` (B5)
7. Tests

---

## What was NOT in scope for Phase 17 (deferred to future)

- SWE-bench integration (B1) — future work
- RIGORBENCH (B2) — future work
- ~~Multi-language tasks (non-Python fixture projects)~~ — **shipped**: JS and Go fixtures added in PR #23
- ~~Automated leaderboard / result publishing~~ — **shipped**: `devagent bench leaderboard` + CI auto-update in PR #28

## Completed work summary

Phase 17 is fully shipped. All core B3/B4/B5 infrastructure is live:

- **24-task set**: Python (20), JavaScript (2), Go (2) — with oracle-verified pass/fail
- **Live benchmark scores**: gpt-oss:20b 21/24 (87.5%), llama3.2:3b 9/20 (45%)
- **Leaderboard**: `devagent bench leaderboard` command + CI auto-update of LEADERBOARD.md
- **CI persistence**: bench-persist.yml saves every run to the `bench-results` branch
- **History**: `devagent bench history [--remote]` for cross-run trend tracking
- **3 repaired tasks**: code-review-001 (timeout), refactor-002 (false premise), test-write-002 (import + verification pattern)
