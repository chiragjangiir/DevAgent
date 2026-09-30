# Pending REPL Commands

## ✅ /compact [focus on X] — SHIPPED Phase 32
Targeted context compaction: compress history but keep content related to a given topic.
`compress_session()` in `session/compressor.py` now accepts a `focus` param injected into the summary prompt.

## ✅ /fast [off] — SHIPPED Phase 32
Toggle fast mode — swaps to the `cheap` router tier model; `/fast off` restores the original provider/model.
State tracked in `_fast_mode`, `_pre_fast_provider`, `_pre_fast_model` on `DevAgentSession`.

## ✅ /batch — SHIPPED Phase 37
Apply a change across multiple files in parallel (fan-out sub-agents per file).
Syntax: `/batch <task> -- <glob>`. Uses `ThreadPoolExecutor(max_workers=4)`; each worker spins up
a `DevAgentSession(bare=True)` and calls `run_message`. Results shown in a Rich table.

## ✅ /branch — SHIPPED Phase 36
Snapshot the current session to a new branch session (all events copied).
User resumes with `devagent run --resume <id>`. Uses `store.copy_session_events(from, to)`.

## ✅ /background — SHIPPED Phase 38
Detach a task as a long-running background subprocess (survives terminal close).
`/background <task>` launches `devagent do <task>` via `subprocess.Popen` with
`DETACHED_PROCESS` (Windows) / `start_new_session=True` (Unix). stdout+stderr go to
`.devagent/bg_<id>.log`; state persisted in `.devagent/bg_<id>.json`.
`/background` (no args) lists all jobs and their live PID status.

## ✅ /recap [N] — SHIPPED Phase 34
Print last N messages (default 5) from session history so the user can re-orient after a long
break. Reads events from DB, filters to user/assistant content, renders with ruler separators.

## ✅ /theme — SHIPPED Phase 36
4 themes: default, dracula, monokai, solarized. Stored in `cfg.ui.theme` (new `UIConfig`).
`/theme <name>` hot-swaps by recreating the PromptSession with a `prompt_toolkit.styles.Style`.

## ✅ /keybindings — SHIPPED Phase 42
Shows a keyboard shortcut reference table in the REPL.
F1 and F2 are wired as custom `prompt_toolkit` `KeyBindings`:
F1 sets the buffer to `/help`, F2 to `/status`, and both call `validate_and_handle()`
so the command runs immediately.
