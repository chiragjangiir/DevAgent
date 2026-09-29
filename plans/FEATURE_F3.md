# SpecSync — Feature Implementation Guide: F3 (Repo Health Monitor)

> **For the AI code editor reading this file:**
> This document describes one feature to be added to an already working SpecSync codebase that has completed Phases 1–6 as described in `PROJECT.md`, and also has F4 (URL input) and F2 (Chat interface) implemented as described in `FEATURES_F4_F2.md`. Read `PROJECT.md` first to understand the full existing architecture. Read `FEATURES_F4_F2.md` to understand what F4 and F2 added. This file describes only what is NEW or CHANGED for F3. Do not rewrite existing working code unless explicitly instructed here.

---

## Context — What Already Exists

The codebase already has:

- `specsync/cli.py` — all commands including `analyze`, `chat`, `index`, `search`, `reports`, `init`, `doctor`, `config`
- `specsync/agents/pipeline.py` — `run_pipeline()` that runs SpecParserAgent + CodeInventoryAgent + GapReportAgent
- `specsync/core/models.py` — all Pydantic models including `GapReport`, `PipelineState`
- `specsync/core/storage.py` — all path resolution using `platformdirs`
- `specsync/core/config.py` — `SpecSyncConfig`, `load_config()`, `save_config()`
- `specsync/mcp/manager.py` — `MCPManager` that launches all 5 MCP servers
- `specsync/mcp/clients/github_client.py` — `get_issue()`, `get_pull_request()`
- `specsync/output/terminal.py` — Rich rendering functions
- `specsync/output/markdown.py` — saves `.md` and `.json` report files
- `specsync/chat/session.py` — `ChatSession` (from F2)
- `specsync/core/url_parser.py` — `parse_github_url()` (from F4)

F3 adds a new top-level capability: watching a GitHub repository for new issues, automatically analysing each one against the indexed codebase, and surfacing cross-issue conflicts — situations where two open issues will both touch the same files.

---

## FEATURE F3 — Repo Health Monitor

### What it does in plain terms

You point SpecSync at a GitHub repository. From that point on, whenever you run `specsync watch --status` or whenever the background scheduler fires, SpecSync:

1. Fetches all GitHub issues opened since the last check
2. For each new issue, runs the spec parsing and code inventory agents (not the full pipeline — skips the report formatting step for speed)
3. Stores the `RequirementMap` for each issue in SQLite
4. Detects cross-issue conflicts: if issue A and issue B both touch `auth/session.py`, that is flagged
5. Produces a health report showing: new issues analysed, complexity of each, and any cross-issue file overlaps

The watch command has two modes:

**On-demand mode** (`specsync watch --status`): runs the check right now, shows results, exits.

**Scheduled mode** (`specsync watch --start`): starts a background scheduler that checks on a configurable interval (default: every 30 minutes). Runs as a foreground process — the terminal stays open. Press Ctrl+C to stop.

---

### New terminal commands F3 adds

```
# Register a repo to watch (one-time setup per repo)
specsync watch --repo owner/repo

# Run a check right now and show results
specsync watch --status
specsync watch --status --repo owner/repo     # explicit repo

# Start the background scheduler (foreground process)
specsync watch --start
specsync watch --start --interval 30m         # every 30 minutes (default)
specsync watch --start --interval 1h          # every hour
specsync watch --start --interval 6h          # every 6 hours

# Show all issues analysed so far for this repo
specsync watch --report
specsync watch --report --repo owner/repo

# Show analysis for a specific issue the watcher found
specsync watch --show 142

# Stop watching a repo
specsync watch --stop
specsync watch --stop --repo owner/repo

# List all currently watched repos
specsync watch --list
```

---

### What the output looks like

**`specsync watch --status` output:**

```
  SpecSync Repo Health Monitor
  Repo: myorg/backend  ·  Last checked: 2 hours ago

  Checking for new issues since 2025-01-15 14:30...

  ✓ Fetched 3 new issues

  Analysing issues...
  ✓ Issue #143  "Add password reset flow"              [████████░░] analysing...
  ✓ Issue #144  "Rate limit the /api/auth endpoint"    [████████░░] analysing...
  ✓ Issue #145  "Add admin user management"            [████████░░] analysing...

  ─────────────────────────────────────────────────────
  HEALTH REPORT  ·  myorg/backend  ·  3 new issues
  ─────────────────────────────────────────────────────

  Issue #143  Add password reset flow
    Complexity:  Medium  (2 conflicts, 4 requirements)
    Files:       auth/session.py, auth/routes.py, models/user.py
    ⚠ Conflict:  auth/session.py also touched by #144 — coordinate

  Issue #144  Rate limit the /api/auth endpoint
    Complexity:  Low  (0 conflicts, 2 requirements)
    Files:       api/middleware.py, auth/routes.py
    ⚠ Overlap:   auth/routes.py also touched by #143 — coordinate

  Issue #145  Add admin user management
    Complexity:  High  (3 conflicts, 7 requirements, 12 files affected)
    Files:       models/user.py, admin/, api/routes/admin.py (+9 more)

  ─────────────────────────────────────────────────────
  CROSS-ISSUE CONFLICTS

  ⚠ auth/session.py    touched by #143 and #144 — assign to same developer or coordinate
  ⚠ auth/routes.py     touched by #143 and #144 — review together before starting

  ─────────────────────────────────────────────────────
  Next check scheduled: in 28 minutes
  Run 'specsync watch --show 143' for full analysis of any issue
```

**`specsync watch --show 142` output:**

Renders the full stored gap report for issue #142 using the existing `render_gap_report()` function from `specsync/output/terminal.py`. Then offers to start a chat session:

```
  Full analysis for Issue #142 is shown above.
  Run 'specsync chat --report issue-142-watcher' to discuss it in chat.
```

---

### Architecture — how F3 fits into SpecSync

F3 introduces three new concepts:

**1. WatchedRepo** — a repo registered for monitoring, stored in SQLite
**2. WatcherAnalysis** — a lightweight analysis result stored per issue (not a full GapReport — just the RequirementMap and file impact summary)
**3. CrossIssueConflict** — a detected overlap between two issues' file impact sets

F3 does NOT store full `GapReport` objects for watcher-discovered issues by default — that would be slow and storage-heavy for repos with many issues. It stores a `WatcherAnalysis` which is a lighter structure. However, when the user runs `specsync watch --show 142`, it re-runs the full pipeline on that specific issue and saves a full report (using the existing pipeline and output system).

---

### New files created by F3

```
specsync/
  watcher/
    __init__.py
    scheduler.py          ← APScheduler-based background scheduler
    checker.py            ← WatcherChecker — fetches new issues, runs analysis
    conflict_detector.py  ← CrossIssueConflictDetector — finds file overlaps
    storage.py            ← SQLite operations for watcher data
  output/
    watcher_renderer.py   ← Rich rendering for watch --status and --report output
tests/
  test_watcher_storage.py
  test_conflict_detector.py
  test_watcher_checker.py
```

Changes to existing files:

```
specsync/cli.py                  ← add watch command with all subflags
specsync/core/models.py          ← add WatchedRepo, WatcherAnalysis, CrossIssueConflict models
specsync/core/storage.py         ← add watcher storage path helpers
specsync/core/config.py          ← add watcher config section
```

---

### Storage — where F3 data lives

F3 stores everything in the existing SpecSync data directory:

```
%LOCALAPPDATA%\specsync\
  └── watcher\
      ├── watcher.db                    ← SQLite: watched repos, analyses, conflicts
      └── reports\
          └── {owner}-{repo}\
              ├── issue-142-watcher.json   ← lightweight WatcherAnalysis JSON
              └── issue-142-watcher.md     ← only if --show was run (full report)
```

The `watcher.db` is a single SQLite database for all watched repos. It is separate from the per-project `specsync.db` files — the watcher is repo-centric, not project-centric.

Add to `specsync/core/storage.py`:

```python
def get_watcher_db_path() -> Path:
    """Returns path to the watcher SQLite database."""
    return get_data_dir() / "watcher" / "watcher.db"

def get_watcher_reports_dir(owner: str, repo: str) -> Path:
    """Returns path to watcher reports for a specific repo."""
    return get_data_dir() / "watcher" / "reports" / f"{owner}-{repo}"
```

---

### Data Models — add to `specsync/core/models.py`

Add these Pydantic models to the existing models file:

```python
class IssueComplexity(str, Enum):
    LOW = "low"         # 0 conflicts, ≤3 requirements
    MEDIUM = "medium"   # 1-2 conflicts OR 4-6 requirements
    HIGH = "high"       # 3+ conflicts OR 7+ requirements OR 10+ files affected

class WatchedRepo(BaseModel):
    owner: str
    repo: str                           # just the repo name, not "owner/repo"
    registered_at: datetime
    last_checked_at: datetime | None = None
    check_interval_minutes: int = 30
    is_active: bool = True
    issue_filters: list[str] = []       # label filters e.g. ["feature", "enhancement"]
                                        # empty list = analyse all issues

class WatcherAnalysis(BaseModel):
    """Lightweight analysis stored per issue by the watcher.
    Not a full GapReport — stores only what's needed for health reporting
    and cross-issue conflict detection."""
    owner: str
    repo: str
    issue_number: int
    issue_title: str
    issue_url: str
    analysed_at: datetime
    requirements_count: int
    conflicts_count: int
    complexity: IssueComplexity
    touched_files: list[str]            # all files the issue's requirements map to
    conflicted_files: list[str]         # subset of touched_files that have conflicts
    requirement_summaries: list[dict]   # lightweight: [{id, description, status, files}]
    full_report_available: bool = False # True if --show has been run for this issue

class CrossIssueConflict(BaseModel):
    """A file that is touched by two or more open issues simultaneously."""
    file_path: str
    issue_numbers: list[int]            # issues that all touch this file
    issue_titles: dict[int, str]        # {issue_number: title} for display
    severity: Literal["high", "medium", "low"]
    # high: file is CONFLICTED in at least one of the issues
    # medium: file is PARTIALLY_EXISTS or EXTEND in multiple issues
    # low: file is touched (any status) by multiple issues
    detected_at: datetime

class WatchHealthReport(BaseModel):
    """The full health report generated by a watcher check run."""
    owner: str
    repo: str
    check_run_at: datetime
    new_issues_count: int
    new_analyses: list[WatcherAnalysis]
    cross_issue_conflicts: list[CrossIssueConflict]
    total_watched_issues: int           # all issues ever analysed for this repo
    next_check_at: datetime | None = None
```

---

### Config — add watcher section to `specsync/core/config.py`

Add a `WatcherConfig` model and include it in `SpecSyncConfig`:

```python
class WatcherConfig(BaseModel):
    default_interval_minutes: int = 30
    max_issues_per_check: int = 20      # safety limit — never analyse more than 20 new issues per run
    default_labels: list[str] = []      # empty = all issues
    notify_on_cross_conflict: bool = True
    skip_closed_issues: bool = True

class SpecSyncConfig(BaseModel):
    # ... existing fields ...
    watcher: WatcherConfig = WatcherConfig()
```

Add to `config.toml` schema:

```toml
[watcher]
default_interval_minutes = 30
max_issues_per_check = 20
default_labels = []          # e.g. ["feature", "enhancement"] to filter
notify_on_cross_conflict = true
skip_closed_issues = true
```

---

### Implementation — `specsync/watcher/storage.py`

This module handles all SQLite operations for the watcher. Uses `aiosqlite` consistent with the rest of the project.

**SQLite Schema — `watcher.db`:**

```sql
CREATE TABLE IF NOT EXISTS watched_repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    last_checked_at TEXT,
    check_interval_minutes INTEGER NOT NULL DEFAULT 30,
    is_active INTEGER NOT NULL DEFAULT 1,
    issue_filters TEXT NOT NULL DEFAULT '[]',   -- JSON array of label strings
    UNIQUE(owner, repo)
);

CREATE TABLE IF NOT EXISTS watcher_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    issue_title TEXT NOT NULL,
    issue_url TEXT NOT NULL,
    analysed_at TEXT NOT NULL,
    requirements_count INTEGER NOT NULL,
    conflicts_count INTEGER NOT NULL,
    complexity TEXT NOT NULL,
    touched_files TEXT NOT NULL,        -- JSON array of file paths
    conflicted_files TEXT NOT NULL,     -- JSON array of file paths
    requirement_summaries TEXT NOT NULL, -- JSON array
    full_report_available INTEGER NOT NULL DEFAULT 0,
    UNIQUE(owner, repo, issue_number)
);

CREATE TABLE IF NOT EXISTS cross_issue_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    file_path TEXT NOT NULL,
    issue_numbers TEXT NOT NULL,        -- JSON array of integers
    issue_titles TEXT NOT NULL,         -- JSON object {number: title}
    severity TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0  -- 1 when one of the issues is closed
);

CREATE TABLE IF NOT EXISTS check_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    run_at TEXT NOT NULL,
    new_issues_count INTEGER NOT NULL,
    cross_conflicts_count INTEGER NOT NULL,
    duration_seconds REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyses_repo ON watcher_analyses(owner, repo);
CREATE INDEX IF NOT EXISTS idx_analyses_issue ON watcher_analyses(owner, repo, issue_number);
CREATE INDEX IF NOT EXISTS idx_conflicts_repo ON cross_issue_conflicts(owner, repo);
CREATE INDEX IF NOT EXISTS idx_conflicts_file ON cross_issue_conflicts(owner, repo, file_path);
```

**Functions to implement in `storage.py`:**

```python
async def init_watcher_db() -> None:
    """Creates the watcher.db and all tables if they don't exist."""

async def register_repo(owner: str, repo: str, interval_minutes: int, labels: list[str]) -> WatchedRepo:
    """Inserts or updates a watched repo record. Idempotent."""

async def get_watched_repo(owner: str, repo: str) -> WatchedRepo | None:
    """Returns the WatchedRepo if registered, None otherwise."""

async def list_watched_repos() -> list[WatchedRepo]:
    """Returns all active watched repos."""

async def update_last_checked(owner: str, repo: str, checked_at: datetime) -> None:
    """Updates last_checked_at for a repo after a successful check run."""

async def deactivate_repo(owner: str, repo: str) -> None:
    """Marks a repo as inactive (stop watching). Does not delete data."""

async def save_analysis(analysis: WatcherAnalysis) -> None:
    """Saves a WatcherAnalysis. If the issue_number already exists for this repo,
    updates it (idempotent — safe to re-analyse the same issue)."""

async def get_analysis(owner: str, repo: str, issue_number: int) -> WatcherAnalysis | None:
    """Returns stored analysis for a specific issue."""

async def get_all_analyses_for_repo(owner: str, repo: str) -> list[WatcherAnalysis]:
    """Returns all stored analyses for a repo, sorted by issue_number descending."""

async def get_analysed_issue_numbers(owner: str, repo: str) -> set[int]:
    """Returns the set of issue numbers already analysed. Used to find new issues."""

async def save_cross_conflicts(conflicts: list[CrossIssueConflict]) -> None:
    """Saves detected cross-issue conflicts. Replaces existing conflicts for the same repo
    (re-computed fresh each check run)."""

async def get_cross_conflicts(owner: str, repo: str) -> list[CrossIssueConflict]:
    """Returns all current cross-issue conflicts for a repo."""

async def mark_full_report_available(owner: str, repo: str, issue_number: int) -> None:
    """Sets full_report_available = True for an issue after --show is run."""

async def log_check_run(owner: str, repo: str, new_issues: int,
                         conflicts: int, duration: float) -> None:
    """Appends a check run record for audit/history purposes."""
```

---

### Implementation — `specsync/watcher/checker.py`

This is the core logic of F3. `WatcherChecker` performs a single check run for one repo.

```python
import asyncio
import time
from datetime import datetime, timezone
from specsync.core.config import SpecSyncConfig
from specsync.core.models import WatchedRepo, WatcherAnalysis, IssueComplexity
from specsync.mcp.manager import MCPManager
from specsync.agents.spec_parser import SpecParserAgent
from specsync.agents.code_inventory import CodeInventoryAgent
from specsync.watcher.storage import (
    get_analysed_issue_numbers, save_analysis, update_last_checked, log_check_run
)

class WatcherChecker:
    def __init__(self, config: SpecSyncConfig, project_root: Path):
        self.config = config
        self.project_root = project_root

    async def run_check(
        self,
        watched_repo: WatchedRepo,
        progress_callback=None    # optional: callable(issue_number, issue_title, status)
    ) -> list[WatcherAnalysis]:
        """
        Runs one check cycle for a watched repo.
        Returns list of new WatcherAnalysis objects created this run.
        """
        start_time = time.monotonic()
        new_analyses = []

        async with MCPManager(self.config, self.project_root) as manager:
            # Step 1: Find new issues
            new_issues = await self._fetch_new_issues(manager, watched_repo)

            if not new_issues:
                await update_last_checked(watched_repo.owner, watched_repo.repo, datetime.now(timezone.utc))
                return []

            # Step 2: Analyse each new issue (respect max_issues_per_check limit)
            issues_to_analyse = new_issues[:self.config.watcher.max_issues_per_check]

            for issue in issues_to_analyse:
                if progress_callback:
                    progress_callback(issue["number"], issue["title"], "analysing")

                analysis = await self._analyse_issue(manager, watched_repo, issue)
                if analysis:
                    await save_analysis(analysis)
                    new_analyses.append(analysis)

                    if progress_callback:
                        progress_callback(issue["number"], issue["title"], "done")

            # Step 3: Update last checked timestamp
            await update_last_checked(
                watched_repo.owner,
                watched_repo.repo,
                datetime.now(timezone.utc)
            )

            # Step 4: Log the check run
            duration = time.monotonic() - start_time
            await log_check_run(
                watched_repo.owner, watched_repo.repo,
                len(new_analyses), 0, duration   # conflict count updated by caller
            )

        return new_analyses

    async def _fetch_new_issues(self, manager: MCPManager, watched_repo: WatchedRepo) -> list[dict]:
        """
        Fetches GitHub issues opened since last_checked_at.
        Returns list of issue dicts: {number, title, body, url, labels, created_at}
        """
        github = manager.github

        # Get all issues since last check
        since = watched_repo.last_checked_at
        issues = await github.list_issues(
            owner=watched_repo.owner,
            repo=watched_repo.repo,
            state="open",
            since=since,                    # GitHub API: issues updated/created since this datetime
            labels=watched_repo.issue_filters if watched_repo.issue_filters else None
        )

        # Filter to only truly NEW issues (not just updated ones)
        if since:
            issues = [i for i in issues if i["created_at"] >= since.isoformat()]

        # Remove already-analysed issues (handles reruns gracefully)
        analysed_numbers = await get_analysed_issue_numbers(
            watched_repo.owner, watched_repo.repo
        )
        new_issues = [i for i in issues if i["number"] not in analysed_numbers]

        return new_issues

    async def _analyse_issue(
        self,
        manager: MCPManager,
        watched_repo: WatchedRepo,
        issue: dict
    ) -> WatcherAnalysis | None:
        """
        Runs SpecParserAgent + CodeInventoryAgent for one issue.
        Returns WatcherAnalysis. Does NOT run GapReportAgent (for speed).
        Returns None if analysis fails — watcher continues with next issue.
        """
        try:
            # Build minimal PipelineState for this issue
            from specsync.core.models import PipelineState
            state = PipelineState(
                raw_spec=f"{issue['title']}\n\n{issue['body'] or ''}",
                spec_source="github_issue",
                issue_number=issue["number"],
                project_root=str(self.project_root),
                github_repo=f"{watched_repo.owner}/{watched_repo.repo}",
                resource_type="issue"
            )

            # Run SpecParserAgent
            spec_parser = SpecParserAgent(manager, self.config)
            state = await spec_parser.run(state)

            if not state.requirements:
                # Issue has no extractable requirements — skip
                return None

            # Run CodeInventoryAgent
            code_inventory = CodeInventoryAgent(manager, self.config)
            state = await code_inventory.run(state)

            # Build WatcherAnalysis from the state
            return self._build_analysis(watched_repo, issue, state)

        except Exception as e:
            # Log the failure but don't crash the whole check run
            import structlog
            log = structlog.get_logger()
            log.warning(
                "watcher_analysis_failed",
                issue_number=issue["number"],
                error=str(e)
            )
            return None

    def _build_analysis(
        self,
        watched_repo: WatchedRepo,
        issue: dict,
        state: "PipelineState"
    ) -> WatcherAnalysis:
        """Builds a WatcherAnalysis from a completed PipelineState."""
        # Collect all files touched across all requirements
        touched_files = set()
        conflicted_files = set()
        conflicts_count = 0

        for req_analysis in state.requirement_map:
            touched_files.update(req_analysis.matched_files)
            if req_analysis.status == "CONFLICTED":
                conflicts_count += 1
                conflicted_files.update(req_analysis.matched_files)
                if req_analysis.conflict_details:
                    conflicted_files.update(req_analysis.conflict_details.affected_files)

        # Determine complexity
        req_count = len(state.requirements)
        files_count = len(touched_files)
        if conflicts_count >= 3 or req_count >= 7 or files_count >= 10:
            complexity = IssueComplexity.HIGH
        elif conflicts_count >= 1 or req_count >= 4:
            complexity = IssueComplexity.MEDIUM
        else:
            complexity = IssueComplexity.LOW

        # Build lightweight requirement summaries
        req_summaries = [
            {
                "id": ra.requirement.id,
                "description": ra.requirement.description,
                "status": ra.status,
                "files": ra.matched_files[:5]  # cap at 5 files per requirement for storage
            }
            for ra in state.requirement_map
        ]

        return WatcherAnalysis(
            owner=watched_repo.owner,
            repo=watched_repo.repo,
            issue_number=issue["number"],
            issue_title=issue["title"],
            issue_url=issue.get("url", f"https://github.com/{watched_repo.owner}/{watched_repo.repo}/issues/{issue['number']}"),
            analysed_at=datetime.now(timezone.utc),
            requirements_count=req_count,
            conflicts_count=conflicts_count,
            complexity=complexity,
            touched_files=sorted(touched_files),
            conflicted_files=sorted(conflicted_files),
            requirement_summaries=req_summaries,
            full_report_available=False
        )
```

---

### Implementation — add `list_issues` to GitHub MCP client

The watcher needs to list issues since a given date. Add this method to `specsync/mcp/clients/github_client.py`:

```python
async def list_issues(
    self,
    owner: str,
    repo: str,
    state: str = "open",
    since: datetime | None = None,
    labels: list[str] | None = None
) -> list[dict]:
    """
    Lists issues for a repo. Returns list of issue dicts.
    Uses GitHub MCP's list_issues tool.
    """
    args = {
        "owner": owner,
        "repo": repo,
        "state": state,
    }
    if since:
        args["since"] = since.isoformat()
    if labels:
        args["labels"] = ",".join(labels)

    result = await self.mcp_client.call_tool("list_issues", args)

    # GitHub MCP returns issues as a list of dicts
    # Each dict has: number, title, body, url, labels, state, created_at, updated_at
    return result if isinstance(result, list) else []
```

---

### Implementation — `specsync/watcher/conflict_detector.py`

This module computes cross-issue conflicts from a set of `WatcherAnalysis` objects.

```python
from datetime import datetime, timezone
from specsync.core.models import WatcherAnalysis, CrossIssueConflict

class CrossIssueConflictDetector:

    def detect(self, analyses: list[WatcherAnalysis]) -> list[CrossIssueConflict]:
        """
        Given all WatcherAnalysis objects for a repo, finds files
        that are touched by more than one issue.

        Returns a list of CrossIssueConflict objects, one per
        conflicted file.
        """
        if len(analyses) < 2:
            return []

        # Build file → [analyses that touch it] mapping
        file_to_analyses: dict[str, list[WatcherAnalysis]] = {}
        for analysis in analyses:
            for file_path in analysis.touched_files:
                if file_path not in file_to_analyses:
                    file_to_analyses[file_path] = []
                file_to_analyses[file_path].append(analysis)

        # Find files touched by more than one issue
        conflicts = []
        for file_path, touching_analyses in file_to_analyses.items():
            if len(touching_analyses) < 2:
                continue

            # Determine severity
            severity = self._compute_severity(file_path, touching_analyses)

            conflict = CrossIssueConflict(
                file_path=file_path,
                issue_numbers=[a.issue_number for a in touching_analyses],
                issue_titles={a.issue_number: a.issue_title for a in touching_analyses},
                severity=severity,
                detected_at=datetime.now(timezone.utc)
            )
            conflicts.append(conflict)

        # Sort: high severity first, then by number of issues touching the file
        conflicts.sort(
            key=lambda c: (
                {"high": 0, "medium": 1, "low": 2}[c.severity],
                -len(c.issue_numbers)
            )
        )

        return conflicts

    def _compute_severity(
        self,
        file_path: str,
        touching_analyses: list[WatcherAnalysis]
    ) -> str:
        """
        Severity rules:
        - HIGH: the file appears in conflicted_files of at least one analysis
          (meaning it already has an internal conflict) AND is touched by 2+ issues
        - MEDIUM: file is touched by 2+ issues but not in any conflicted_files,
          but appears in at least 2 issues' matched files for EXTEND or PARTIAL status
        - LOW: file is touched by 2+ issues with no other signals
        """
        # Check if file is a conflicted file in any analysis
        for analysis in touching_analyses:
            if file_path in analysis.conflicted_files:
                return "high"

        # Check if it's a non-trivial touch (extension, not just a reuse)
        extension_count = 0
        for analysis in touching_analyses:
            for req_summary in analysis.requirement_summaries:
                if file_path in req_summary.get("files", []):
                    if req_summary["status"] in ("PARTIALLY_EXISTS", "EXTEND", "CONFLICTED"):
                        extension_count += 1
                        break

        if extension_count >= 2:
            return "medium"

        return "low"
```

---

### Implementation — `specsync/watcher/scheduler.py`

Manages the background scheduling using `APScheduler`. Add `APScheduler` to the project dependencies.

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from rich.console import Console
from specsync.core.config import SpecSyncConfig
from specsync.core.models import WatchedRepo
from specsync.watcher.checker import WatcherChecker
from specsync.watcher.conflict_detector import CrossIssueConflictDetector
from specsync.watcher.storage import (
    list_watched_repos, save_cross_conflicts, get_all_analyses_for_repo
)
from specsync.output.watcher_renderer import render_health_report

console = Console()

class WatcherScheduler:
    def __init__(self, config: SpecSyncConfig, project_root: Path, interval_minutes: int):
        self.config = config
        self.project_root = project_root
        self.interval_minutes = interval_minutes
        self.scheduler = AsyncIOScheduler()
        self.checker = WatcherChecker(config, project_root)
        self.conflict_detector = CrossIssueConflictDetector()

    async def start(self) -> None:
        """
        Starts the scheduler. Runs a check immediately on start,
        then on the configured interval. Blocks until Ctrl+C.
        """
        # Run immediately on start
        await self._run_all_repos()

        # Schedule recurring checks
        self.scheduler.add_job(
            self._run_all_repos,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id="repo_health_check",
            replace_existing=True
        )
        self.scheduler.start()

        console.print(
            f"[dim]Watcher running. Checking every {self.interval_minutes} minutes. "
            f"Press Ctrl+C to stop.[/dim]"
        )

        try:
            # Keep the event loop alive
            import asyncio
            while True:
                await asyncio.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown(wait=False)
            console.print("\n[dim]Watcher stopped.[/dim]")

    async def run_once(self) -> None:
        """Runs a single check for all watched repos and exits."""
        await self._run_all_repos()

    async def _run_all_repos(self) -> None:
        """Runs the check for every active watched repo."""
        watched_repos = await list_watched_repos()

        if not watched_repos:
            console.print("[dim]No repos being watched. Run 'specsync watch --repo owner/repo' to start.[/dim]")
            return

        for watched_repo in watched_repos:
            await self._run_for_repo(watched_repo)

    async def _run_for_repo(self, watched_repo: WatchedRepo) -> None:
        """Runs the full check cycle for one repo."""
        from rich.progress import Progress, SpinnerColumn, TextColumn

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            task = progress.add_task(
                f"Checking {watched_repo.owner}/{watched_repo.repo}...",
                total=None
            )

            def update_progress(issue_number, issue_title, status):
                progress.update(
                    task,
                    description=f"Analysing #{issue_number}: {issue_title[:40]}..."
                )

            new_analyses = await self.checker.run_check(
                watched_repo,
                progress_callback=update_progress
            )

        if not new_analyses:
            console.print(
                f"[dim]{watched_repo.owner}/{watched_repo.repo}: "
                f"no new issues since last check.[/dim]"
            )
            return

        # Detect cross-issue conflicts across all analyses for this repo
        all_analyses = await get_all_analyses_for_repo(watched_repo.owner, watched_repo.repo)
        conflicts = self.conflict_detector.detect(all_analyses)
        await save_cross_conflicts(conflicts)

        # Build and render health report
        from specsync.core.models import WatchHealthReport
        from datetime import datetime, timezone
        health_report = WatchHealthReport(
            owner=watched_repo.owner,
            repo=watched_repo.repo,
            check_run_at=datetime.now(timezone.utc),
            new_issues_count=len(new_analyses),
            new_analyses=new_analyses,
            cross_issue_conflicts=conflicts,
            total_watched_issues=len(all_analyses),
        )

        render_health_report(health_report)
```

---

### Implementation — `specsync/output/watcher_renderer.py`

Rich rendering for the watcher output.

```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from specsync.core.models import WatchHealthReport, WatcherAnalysis, CrossIssueConflict, IssueComplexity

console = Console()

def render_health_report(report: WatchHealthReport) -> None:
    """Renders the full health report after a check run."""

    console.print()
    console.print(Panel(
        f"[bold]HEALTH REPORT[/bold]  ·  "
        f"{report.owner}/{report.repo}  ·  "
        f"{report.new_issues_count} new issue{'s' if report.new_issues_count != 1 else ''}",
        border_style="cyan"
    ))

    if not report.new_analyses:
        console.print("[dim]  No new issues to report.[/dim]")
        return

    # New issues table
    table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    table.add_column("Issue", style="bold", width=8)
    table.add_column("Title", width=40)
    table.add_column("Complexity", width=10)
    table.add_column("Requirements", width=14)
    table.add_column("Conflicts", width=10)
    table.add_column("Files touched", width=14)

    for analysis in report.new_analyses:
        complexity_color = {
            IssueComplexity.LOW: "green",
            IssueComplexity.MEDIUM: "yellow",
            IssueComplexity.HIGH: "red"
        }[analysis.complexity]

        table.add_row(
            f"#{analysis.issue_number}",
            analysis.issue_title[:38] + ("…" if len(analysis.issue_title) > 38 else ""),
            f"[{complexity_color}]{analysis.complexity.value.capitalize()}[/{complexity_color}]",
            str(analysis.requirements_count),
            str(analysis.conflicts_count) if analysis.conflicts_count == 0
                else f"[red]{analysis.conflicts_count}[/red]",
            str(len(analysis.touched_files))
        )

    console.print(table)

    # Cross-issue conflicts section
    if report.cross_issue_conflicts:
        console.print()
        console.print(Panel(
            "[bold]CROSS-ISSUE CONFLICTS[/bold]  —  "
            "these files are touched by multiple open issues",
            border_style="yellow"
        ))

        for conflict in report.cross_issue_conflicts:
            severity_color = {"high": "red", "medium": "yellow", "low": "dim"}[conflict.severity]
            issue_refs = " and ".join(
                f"#{num}" for num in conflict.issue_numbers
            )
            console.print(
                f"  [{severity_color}]⚠[/{severity_color}]  "
                f"[bold]{conflict.file_path}[/bold]  "
                f"touched by {issue_refs}  "
                f"[dim]({conflict.severity} severity)[/dim]"
            )

        console.print()
        console.print(
            "[dim]  Tip: Assign cross-conflict files to the same developer, "
            "or coordinate before starting work.[/dim]"
        )

    console.print()
    console.print(
        f"[dim]  Run 'specsync watch --show {{issue_number}}' for full analysis of any issue.[/dim]"
    )
    console.print(
        f"[dim]  Run 'specsync watch --report' to see all analysed issues.[/dim]"
    )


def render_watched_repos(repos: list) -> None:
    """Renders the list of watched repos for 'specsync watch --list'."""
    if not repos:
        console.print("[dim]No repos currently being watched.[/dim]")
        console.print("[dim]Run 'specsync watch --repo owner/repo' to start watching a repo.[/dim]")
        return

    table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    table.add_column("Repo", width=30)
    table.add_column("Status", width=10)
    table.add_column("Interval", width=12)
    table.add_column("Last checked", width=20)
    table.add_column("Filters", width=20)

    for repo in repos:
        last_checked = (
            repo.last_checked_at.strftime("%Y-%m-%d %H:%M") if repo.last_checked_at
            else "Never"
        )
        filters = ", ".join(repo.issue_filters) if repo.issue_filters else "All issues"
        status = "[green]Active[/green]" if repo.is_active else "[dim]Stopped[/dim]"

        table.add_row(
            f"{repo.owner}/{repo.repo}",
            status,
            f"Every {repo.check_interval_minutes}m",
            last_checked,
            filters
        )

    console.print(table)


def render_all_analyses(analyses: list[WatcherAnalysis], owner: str, repo: str) -> None:
    """Renders all stored analyses for 'specsync watch --report'."""
    if not analyses:
        console.print(f"[dim]No issues analysed yet for {owner}/{repo}.[/dim]")
        return

    console.print()
    console.print(Panel(
        f"[bold]All Analysed Issues[/bold]  ·  {owner}/{repo}  ·  {len(analyses)} total",
        border_style="dim"
    ))

    table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    table.add_column("Issue", width=8)
    table.add_column("Title", width=45)
    table.add_column("Complexity", width=10)
    table.add_column("Conflicts", width=10)
    table.add_column("Full report", width=12)

    for analysis in analyses:
        complexity_color = {
            IssueComplexity.LOW: "green",
            IssueComplexity.MEDIUM: "yellow",
            IssueComplexity.HIGH: "red"
        }[analysis.complexity]

        has_report = "[green]✓[/green]" if analysis.full_report_available else "[dim]—[/dim]"

        table.add_row(
            f"#{analysis.issue_number}",
            analysis.issue_title[:43] + ("…" if len(analysis.issue_title) > 43 else ""),
            f"[{complexity_color}]{analysis.complexity.value.capitalize()}[/{complexity_color}]",
            str(analysis.conflicts_count) if analysis.conflicts_count == 0
                else f"[red]{analysis.conflicts_count}[/red]",
            has_report
        )

    console.print(table)
    console.print(
        "[dim]  Run 'specsync watch --show ISSUE_NUMBER' for full analysis.[/dim]"
    )
```

---

### Implementation — `specsync/cli.py` — the `watch` command

Add the `watch` command to `cli.py`. This is a single Typer command with multiple option flags that determine its behavior:

```python
@app.command()
def watch(
    repo: Annotated[Optional[str], typer.Option("--repo", "-r",
        help="GitHub repo to watch as owner/repo")] = None,
    status: Annotated[bool, typer.Option("--status",
        help="Run a check right now and show results")] = False,
    start: Annotated[bool, typer.Option("--start",
        help="Start background scheduler (foreground process)")] = False,
    stop: Annotated[bool, typer.Option("--stop",
        help="Stop watching a repo")] = False,
    list_repos: Annotated[bool, typer.Option("--list",
        help="List all watched repos")] = False,
    report: Annotated[bool, typer.Option("--report",
        help="Show all analysed issues for a repo")] = False,
    show: Annotated[Optional[int], typer.Option("--show",
        help="Show full analysis for a specific issue number")] = None,
    interval: Annotated[str, typer.Option("--interval",
        help="Check interval: 30m, 1h, 6h, 12h, 24h")] = "30m",
    labels: Annotated[Optional[str], typer.Option("--labels",
        help="Comma-separated label filters e.g. 'feature,enhancement'")] = None,
):
    """Monitor a GitHub repo for new issues and detect cross-issue conflicts."""
    config = _load_config_or_exit()
    project_root = _detect_project_root_or_exit()

    # Parse interval string
    interval_minutes = _parse_interval(interval)

    # Route to the correct behavior based on flags
    if list_repos:
        asyncio.run(_watch_list())
        return

    if stop:
        if not repo:
            console.print("[red]Specify --repo owner/repo to stop watching.[/red]")
            raise typer.Exit(1)
        asyncio.run(_watch_stop(repo))
        return

    if show is not None:
        owner, repo_name = _parse_repo_or_infer(repo, project_root)
        asyncio.run(_watch_show(owner, repo_name, show, config, project_root))
        return

    if report:
        owner, repo_name = _parse_repo_or_infer(repo, project_root)
        asyncio.run(_watch_report(owner, repo_name))
        return

    if status:
        owner, repo_name = _parse_repo_or_infer(repo, project_root)
        asyncio.run(_watch_run_once(owner, repo_name, config, project_root))
        return

    if start:
        asyncio.run(_watch_start(config, project_root, interval_minutes))
        return

    # Default: if --repo provided without other flags, register it
    if repo:
        label_list = [l.strip() for l in labels.split(",")] if labels else []
        asyncio.run(_watch_register(repo, interval_minutes, label_list))
        return

    # No flags provided — show help
    console.print(
        "[dim]Usage: specsync watch --repo owner/repo    (to start watching)[/dim]\n"
        "[dim]       specsync watch --status              (to check now)[/dim]\n"
        "[dim]       specsync watch --list                (to list watched repos)[/dim]\n"
        "[dim]       specsync watch --help                (for all options)[/dim]"
    )
```

**Private helper functions for the watch command:**

```python
async def _watch_register(repo_str: str, interval_minutes: int, labels: list[str]) -> None:
    """Registers a repo for watching."""
    from specsync.watcher.storage import init_watcher_db, register_repo
    owner, repo_name = _split_repo_string(repo_str)
    await init_watcher_db()
    watched = await register_repo(owner, repo_name, interval_minutes, labels)
    console.print(
        f"[green]✓[/green] Now watching [bold]{owner}/{repo_name}[/bold]  "
        f"·  checking every {interval_minutes} minutes"
    )
    console.print(
        f"[dim]Run 'specsync watch --status' to run the first check now.[/dim]"
    )

async def _watch_run_once(owner: str, repo: str, config: SpecSyncConfig, project_root: Path) -> None:
    """Runs a single check cycle."""
    from specsync.watcher.storage import init_watcher_db, get_watched_repo
    from specsync.watcher.scheduler import WatcherScheduler
    await init_watcher_db()
    watched_repo = await get_watched_repo(owner, repo)
    if not watched_repo:
        console.print(f"[red]{owner}/{repo} is not being watched.[/red]")
        console.print(f"[dim]Run 'specsync watch --repo {owner}/{repo}' to register it.[/dim]")
        return
    scheduler = WatcherScheduler(config, project_root, watched_repo.check_interval_minutes)
    await scheduler.run_once()

async def _watch_start(config: SpecSyncConfig, project_root: Path, interval_minutes: int) -> None:
    """Starts the background scheduler."""
    from specsync.watcher.storage import init_watcher_db
    from specsync.watcher.scheduler import WatcherScheduler
    await init_watcher_db()
    scheduler = WatcherScheduler(config, project_root, interval_minutes)
    await scheduler.start()   # blocks until Ctrl+C

async def _watch_list() -> None:
    """Lists all watched repos."""
    from specsync.watcher.storage import init_watcher_db, list_watched_repos
    from specsync.output.watcher_renderer import render_watched_repos
    await init_watcher_db()
    repos = await list_watched_repos()
    render_watched_repos(repos)

async def _watch_stop(repo_str: str) -> None:
    """Deactivates a watched repo."""
    from specsync.watcher.storage import init_watcher_db, deactivate_repo
    owner, repo_name = _split_repo_string(repo_str)
    await init_watcher_db()
    await deactivate_repo(owner, repo_name)
    console.print(f"[green]✓[/green] Stopped watching [bold]{owner}/{repo_name}[/bold]")
    console.print("[dim]Historical analysis data is preserved.[/dim]")

async def _watch_report(owner: str, repo: str) -> None:
    """Shows all analyses for a repo."""
    from specsync.watcher.storage import init_watcher_db, get_all_analyses_for_repo
    from specsync.output.watcher_renderer import render_all_analyses
    await init_watcher_db()
    analyses = await get_all_analyses_for_repo(owner, repo)
    render_all_analyses(analyses, owner, repo)

async def _watch_show(
    owner: str, repo: str, issue_number: int,
    config: SpecSyncConfig, project_root: Path
) -> None:
    """
    Shows full analysis for a specific watcher-discovered issue.
    If full report already exists (JSON saved), loads and renders it.
    If not, re-runs the full pipeline for that issue and saves the report.
    """
    from specsync.watcher.storage import init_watcher_db, get_analysis, mark_full_report_available
    await init_watcher_db()

    analysis = await get_analysis(owner, repo, issue_number)
    if not analysis:
        console.print(
            f"[red]Issue #{issue_number} has not been analysed by the watcher yet.[/red]"
        )
        console.print(
            f"[dim]Run 'specsync watch --status' to check for new issues first.[/dim]"
        )
        return

    # Check if full report JSON already exists
    from specsync.core.storage import get_watcher_reports_dir
    reports_dir = get_watcher_reports_dir(owner, repo)
    report_json = reports_dir / f"issue-{issue_number}-watcher.json"

    if report_json.exists() and analysis.full_report_available:
        # Load and render existing full report
        from specsync.core.models import GapReport
        from specsync.output.terminal import render_gap_report
        gap_report = GapReport.model_validate_json(report_json.read_text())
        render_gap_report(gap_report)
    else:
        # Run full pipeline for this issue
        console.print(
            f"[dim]Generating full analysis for #{issue_number}... "
            f"(this may take 30-60 seconds)[/dim]"
        )
        async with MCPManager(config, project_root) as manager:
            from specsync.agents.pipeline import run_pipeline
            gap_report = await run_pipeline(
                config=config,
                mcp_manager=manager,
                inputs={
                    "spec_source": "github_issue",
                    "issue_number": issue_number,
                    "github_repo": f"{owner}/{repo}",
                    "project_root": str(project_root)
                }
            )
        # Save full report
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_json.write_text(gap_report.model_dump_json())
        await mark_full_report_available(owner, repo, issue_number)

        from specsync.output.terminal import render_gap_report
        from specsync.output.markdown import save_gap_report
        render_gap_report(gap_report)
        md_path = reports_dir / f"issue-{issue_number}-watcher.md"
        save_gap_report(gap_report, md_path)

    # Offer chat
    console.print()
    console.print(
        f"[dim]To discuss this analysis: "
        f"specsync chat --report issue-{issue_number}-watcher[/dim]"
    )
```

**`_parse_interval` helper:**

```python
def _parse_interval(interval_str: str) -> int:
    """Converts interval string to minutes. Supports: 30m, 1h, 6h, 12h, 24h."""
    interval_str = interval_str.strip().lower()
    if interval_str.endswith("m"):
        return int(interval_str[:-1])
    elif interval_str.endswith("h"):
        return int(interval_str[:-1]) * 60
    else:
        # Assume minutes if no unit
        return int(interval_str)
```

**`_parse_repo_or_infer` helper:**

```python
def _parse_repo_or_infer(repo: str | None, project_root: Path) -> tuple[str, str]:
    """
    Returns (owner, repo_name).
    If repo is provided as "owner/repo", splits it.
    If not provided, infers from the git remote of project_root.
    """
    if repo:
        return _split_repo_string(repo)

    # Infer from git remote
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        remote_url = result.stdout.strip()
        # Handle: git@github.com:owner/repo.git or https://github.com/owner/repo.git
        if "github.com" in remote_url:
            from specsync.core.url_parser import parse_github_url
            # Normalize to https URL for parsing
            if remote_url.startswith("git@"):
                remote_url = remote_url.replace("git@github.com:", "https://github.com/")
            if remote_url.endswith(".git"):
                remote_url = remote_url[:-4]
            # Add a fake issue number to make it parseable
            parsed = parse_github_url(remote_url + "/issues/1")
            return parsed.owner, parsed.repo
    except Exception:
        pass

    console.print(
        "[red]Could not infer GitHub repo from git remote. "
        "Use --repo owner/repo explicitly.[/red]"
    )
    raise typer.Exit(1)

def _split_repo_string(repo_str: str) -> tuple[str, str]:
    """Splits 'owner/repo' into ('owner', 'repo')."""
    parts = repo_str.strip().split("/")
    if len(parts) != 2:
        console.print(f"[red]Invalid repo format: '{repo_str}'. Use 'owner/repo'.[/red]")
        raise typer.Exit(1)
    return parts[0], parts[1]
```

---

### Add `APScheduler` to dependencies

Add to `pyproject.toml` dependencies:

```toml
"apscheduler>=3.10.0",
```

---

### Tests

**`tests/test_watcher_storage.py`:**

```python
import pytest
import asyncio
from datetime import datetime, timezone
from specsync.watcher.storage import (
    init_watcher_db, register_repo, get_watched_repo,
    list_watched_repos, deactivate_repo, save_analysis,
    get_analysis, get_analysed_issue_numbers
)

# Use a temporary database path for tests
# Override get_watcher_db_path in conftest.py to return a tmp_path

@pytest.mark.asyncio
async def test_register_and_retrieve_repo(watcher_db):
    watched = await register_repo("myorg", "backend", 30, [])
    assert watched.owner == "myorg"
    assert watched.repo == "backend"
    assert watched.check_interval_minutes == 30

@pytest.mark.asyncio
async def test_register_idempotent(watcher_db):
    await register_repo("myorg", "backend", 30, [])
    await register_repo("myorg", "backend", 60, ["feature"])  # update
    repo = await get_watched_repo("myorg", "backend")
    assert repo.check_interval_minutes == 60  # updated

@pytest.mark.asyncio
async def test_deactivate_repo(watcher_db):
    await register_repo("myorg", "backend", 30, [])
    await deactivate_repo("myorg", "backend")
    repos = await list_watched_repos()
    assert len(repos) == 0  # list_watched_repos returns only active

@pytest.mark.asyncio
async def test_save_and_retrieve_analysis(watcher_db, sample_watcher_analysis):
    await save_analysis(sample_watcher_analysis)
    retrieved = await get_analysis("myorg", "backend", 142)
    assert retrieved is not None
    assert retrieved.issue_number == 142
    assert retrieved.issue_title == sample_watcher_analysis.issue_title

@pytest.mark.asyncio
async def test_get_analysed_issue_numbers(watcher_db, sample_watcher_analysis):
    await save_analysis(sample_watcher_analysis)
    numbers = await get_analysed_issue_numbers("myorg", "backend")
    assert 142 in numbers
```

**`tests/test_conflict_detector.py`:**

```python
from specsync.watcher.conflict_detector import CrossIssueConflictDetector
from specsync.core.models import WatcherAnalysis, IssueComplexity
from datetime import datetime, timezone

def make_analysis(issue_number: int, touched_files: list, conflicted_files: list = None):
    return WatcherAnalysis(
        owner="myorg", repo="backend",
        issue_number=issue_number,
        issue_title=f"Issue {issue_number}",
        issue_url=f"https://github.com/myorg/backend/issues/{issue_number}",
        analysed_at=datetime.now(timezone.utc),
        requirements_count=2,
        conflicts_count=len(conflicted_files or []),
        complexity=IssueComplexity.LOW,
        touched_files=touched_files,
        conflicted_files=conflicted_files or [],
        requirement_summaries=[]
    )

def test_no_conflicts_when_no_overlap():
    detector = CrossIssueConflictDetector()
    analyses = [
        make_analysis(1, ["auth/login.py", "auth/session.py"]),
        make_analysis(2, ["api/routes.py", "models/user.py"]),
    ]
    conflicts = detector.detect(analyses)
    assert len(conflicts) == 0

def test_detects_file_overlap():
    detector = CrossIssueConflictDetector()
    analyses = [
        make_analysis(1, ["auth/session.py", "auth/login.py"]),
        make_analysis(2, ["auth/session.py", "api/routes.py"]),
    ]
    conflicts = detector.detect(analyses)
    assert len(conflicts) == 1
    assert conflicts[0].file_path == "auth/session.py"
    assert set(conflicts[0].issue_numbers) == {1, 2}

def test_high_severity_when_conflicted_file():
    detector = CrossIssueConflictDetector()
    analyses = [
        make_analysis(1, ["auth/session.py"], conflicted_files=["auth/session.py"]),
        make_analysis(2, ["auth/session.py"]),
    ]
    conflicts = detector.detect(analyses)
    assert conflicts[0].severity == "high"

def test_three_issues_touching_same_file():
    detector = CrossIssueConflictDetector()
    analyses = [
        make_analysis(1, ["auth/session.py"]),
        make_analysis(2, ["auth/session.py"]),
        make_analysis(3, ["auth/session.py"]),
    ]
    conflicts = detector.detect(analyses)
    assert len(conflicts) == 1
    assert len(conflicts[0].issue_numbers) == 3

def test_single_analysis_no_conflicts():
    detector = CrossIssueConflictDetector()
    analyses = [make_analysis(1, ["auth/session.py"])]
    conflicts = detector.detect(analyses)
    assert len(conflicts) == 0
```

**`tests/test_watcher_checker.py`:**

Use mocked MCP clients. Test that `_build_analysis` produces correct complexity scores and correctly populates `touched_files` and `conflicted_files` from a mock PipelineState.

---

### Add `watcher_db` fixture to `tests/conftest.py`

```python
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch

@pytest.fixture
async def watcher_db(tmp_path):
    """Provides a temporary watcher database for tests."""
    db_path = tmp_path / "watcher.db"
    with patch("specsync.watcher.storage.get_watcher_db_path", return_value=db_path):
        from specsync.watcher.storage import init_watcher_db
        await init_watcher_db()
        yield db_path

@pytest.fixture
def sample_watcher_analysis():
    from specsync.core.models import WatcherAnalysis, IssueComplexity
    from datetime import datetime, timezone
    return WatcherAnalysis(
        owner="myorg",
        repo="backend",
        issue_number=142,
        issue_title="Add OAuth2 login with Google",
        issue_url="https://github.com/myorg/backend/issues/142",
        analysed_at=datetime.now(timezone.utc),
        requirements_count=4,
        conflicts_count=1,
        complexity=IssueComplexity.MEDIUM,
        touched_files=["auth/session.py", "auth/routes.py", "models/user.py"],
        conflicted_files=["auth/session.py"],
        requirement_summaries=[],
        full_report_available=False
    )
```

---

### F3 Verification

F3 is complete when all of the following work:

**Register and list:**
```
specsync watch --repo myorg/backend
specsync watch --list
```
Shows the repo in the list with status Active.

**On-demand check:**
```
specsync watch --status --repo myorg/backend
```
Fetches new issues, analyses them, shows health report with complexity and cross-issue conflicts.

**Scheduled mode:**
```
specsync watch --start --interval 1h
```
Runs a check immediately, prints results, then stays alive. Ctrl+C stops it cleanly without traceback.

**Show full analysis:**
```
specsync watch --show 142
```
First run: runs full pipeline, renders full gap report, saves JSON.
Second run: loads existing JSON, renders without re-running pipeline.

**Chat integration works:**
```
specsync chat --report issue-142-watcher
```
Opens chat session with the watcher-discovered issue's full report.

**Stop watching:**
```
specsync watch --stop --repo myorg/backend
specsync watch --list
```
Repo no longer appears in list. Historical data preserved.

**Cross-issue conflict detection works:**
Two issues that both touch `auth/session.py` must appear in the CROSS-ISSUE CONFLICTS section of the health report.

**All tests pass:**
```
pytest tests/test_watcher_storage.py tests/test_conflict_detector.py -v
```

---

## Summary — Exact File Change List

### New files (create from scratch):
```
specsync/watcher/__init__.py
specsync/watcher/checker.py
specsync/watcher/conflict_detector.py
specsync/watcher/scheduler.py
specsync/watcher/storage.py
specsync/output/watcher_renderer.py
tests/test_watcher_storage.py
tests/test_conflict_detector.py
tests/test_watcher_checker.py
```

### Modified files (change only what is documented above):
```
specsync/cli.py                      ← add watch command and all helper functions
specsync/core/models.py              ← add WatchedRepo, WatcherAnalysis,
                                        CrossIssueConflict, WatchHealthReport,
                                        IssueComplexity
specsync/core/storage.py             ← add get_watcher_db_path,
                                        get_watcher_reports_dir
specsync/core/config.py              ← add WatcherConfig to SpecSyncConfig
specsync/mcp/clients/github_client.py ← add list_issues method
pyproject.toml                       ← add apscheduler>=3.10.0
tests/conftest.py                    ← add watcher_db and
                                        sample_watcher_analysis fixtures
```

### Files that must NOT be touched:
```
specsync/mcp/manager.py              ← unchanged
specsync/mcp/servers/               ← unchanged
specsync/agents/pipeline.py          ← unchanged
specsync/agents/spec_parser.py       ← unchanged
specsync/agents/code_inventory.py    ← unchanged
specsync/agents/gap_report.py        ← unchanged
specsync/core/llm.py                 ← unchanged
specsync/chat/                       ← unchanged (F2 code)
specsync/core/url_parser.py          ← unchanged (F4 code)
```

---

## Build Order

Build in this exact sequence:

1. `specsync/core/models.py` — add all new models (WatchedRepo, WatcherAnalysis, CrossIssueConflict, WatchHealthReport, IssueComplexity)
2. `specsync/core/storage.py` — add watcher path helpers
3. `specsync/core/config.py` — add WatcherConfig
4. `specsync/watcher/storage.py` + SQLite schema — implement and test with `test_watcher_storage.py`
5. `specsync/watcher/conflict_detector.py` — implement and test with `test_conflict_detector.py`
6. `specsync/mcp/clients/github_client.py` — add `list_issues` method
7. `specsync/watcher/checker.py` — implement WatcherChecker
8. `specsync/output/watcher_renderer.py` — implement all render functions
9. `specsync/watcher/scheduler.py` — implement WatcherScheduler
10. `specsync/cli.py` — add watch command and all helper functions
11. `tests/conftest.py` — add fixtures
12. `tests/test_watcher_checker.py` — implement
13. `pyproject.toml` — add APScheduler
14. End-to-end verification: register a real repo, run --status, verify health report renders correctly
