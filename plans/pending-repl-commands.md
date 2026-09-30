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

## /background
Detach the current session as a background daemon (keep running after terminal closes).
Implementation: serialize session state; launch a detached subprocess; `/status` polls it via IPC.

## ✅ /recap [N] — SHIPPED Phase 34
Print last N messages (default 5) from session history so the user can re-orient after a long
break. Reads events from DB, filters to user/assistant content, renders with ruler separators.

## ✅ /theme — SHIPPED Phase 36
4 themes: default, dracula, monokai, solarized. Stored in `cfg.ui.theme` (new `UIConfig`).
`/theme <name>` hot-swaps by recreating the PromptSession with a `prompt_toolkit.styles.Style`.

## /keybindings
Custom key rebindings for prompt_toolkit via `~/.claude/keybindings.json` style config.
Deferred — low priority relative to other features.
