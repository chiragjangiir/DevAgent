# Pending REPL Commands

## ✅ /compact [focus on X] — SHIPPED Phase 32
Targeted context compaction: compress history but keep content related to a given topic.
`compress_session()` in `session/compressor.py` now accepts a `focus` param injected into the summary prompt.

## ✅ /fast [off] — SHIPPED Phase 32
Toggle fast mode — swaps to the `cheap` router tier model; `/fast off` restores the original provider/model.
State tracked in `_fast_mode`, `_pre_fast_provider`, `_pre_fast_model` on `DevAgentSession`.

## /batch
Apply a change across multiple files in parallel (fan-out sub-agents per file).
Implementation: parse a task + glob from the command, spin up worktree-isolated sub-agents, merge results.

## /branch
Fork the current conversation into an independent branch (save snapshot, allow diverging edits).
Implementation: duplicate session events into a new session_id; `/branch list` shows branches; `/branch switch N` restores.

## /background
Detach the current session as a background daemon (keep running after terminal closes).
Implementation: serialize session state; launch a detached subprocess; `/status` polls it via IPC.

## ✅ /recap [N] — SHIPPED Phase 34
Print last N messages (default 5) from session history so the user can re-orient after a long
break. Reads events from DB, filters to user/assistant content, renders with ruler separators.

## /theme / /keybindings
UI customisation — colour themes and key rebindings for prompt_toolkit.
Implementation: theme registry in config; prompt_toolkit KeyBindings override.
