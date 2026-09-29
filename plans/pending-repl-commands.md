# Pending REPL Commands

## /compact [focus on X]
Targeted context compaction: compress history but keep content related to a given topic.
Current state: only auto-compact exists (compresses blindly when threshold exceeded).
Implementation: extend `session/compressor.py` to accept a `focus` hint injected into the summary prompt.

## /fast
Toggle fast mode (analogous to Claude Code's /fast — use a cheaper/faster model tier for the current session).
Implementation: swap `cfg.llm` to the `cheap` router tier; `/fast off` restores original.

## /batch
Apply a change across multiple files in parallel (fan-out sub-agents per file).
Implementation: parse a task + glob from the command, spin up worktree-isolated sub-agents, merge results.

## /branch
Fork the current conversation into an independent branch (save snapshot, allow diverging edits).
Implementation: duplicate session events into a new session_id; `/branch list` shows branches; `/branch switch N` restores.

## /background
Detach the current session as a background daemon (keep running after terminal closes).
Implementation: serialize session state; launch a detached subprocess; `/status` polls it via IPC.

## /recap
Re-read key files to warm the context cache after a long idle period.
Implementation: re-inject the last N tool results and key file reads as synthetic context.

## /theme / /keybindings
UI customisation — colour themes and key rebindings for prompt_toolkit.
Implementation: theme registry in config; prompt_toolkit KeyBindings override.
