# Command Flow

How every CLI command is wired and what actually runs under the hood.

---

## Typer dispatch

```mermaid
flowchart TD
    ENTRY[python -m devagent\nor devagent binary]
    TYPER[Typer app\ncli.py]

    INIT[devagent init]
    CONFIG[devagent config]
    INDEX[devagent index]
    RUN[devagent / devagent run]
    IMPLEMENT[devagent implement URL]
    REVIEW[devagent review URL]
    TRIAGE[devagent triage REPO]
    FIX_CI[devagent fix-ci URL]
    ONBOARD[devagent onboard]
    WATCH[devagent watch]
    SESSION_SUB[devagent session]
    DOCTOR[devagent doctor]
    SERVE[devagent serve]
    SEARCH[devagent search QUERY]
    REPORTS[devagent reports]

    ENTRY --> TYPER
    TYPER --> INIT
    TYPER --> CONFIG
    TYPER --> INDEX
    TYPER --> RUN
    TYPER --> IMPLEMENT
    TYPER --> REVIEW
    TYPER --> TRIAGE
    TYPER --> FIX_CI
    TYPER --> ONBOARD
    TYPER --> WATCH
    TYPER --> SESSION_SUB
    TYPER --> DOCTOR
    TYPER --> SERVE
    TYPER --> SEARCH
    TYPER --> REPORTS
```

---

## `devagent init`

```mermaid
flowchart TD
    INIT_CMD[devagent init]
    EXISTING{existing config?}
    SHOW_EXISTING[show current values as defaults]
    WIZARD[Multi-step Rich wizard\nPrompt.ask + Confirm.ask]
    PROVIDER[Step 1: LLM provider\nollama / groq / anthropic / openai / gemini]
    MODEL[Step 2: model name]
    CREDS[Step 3: base_url or api_key]
    GH[Step 4: GitHub token]
    SEARCH_PROV[Step 5: search provider\nsearchx / brave]
    SEARCH_KEY[Step 6: search API key]
    VAL_LLM[_validate_ollama or check api_key non-empty]
    VAL_SEARCH[_validate_brave_key or _validate_searchx_key]
    VAL_GH[_validate_github_token\nGET /user with token]
    BUILD_CFG[Build DevAgentConfig\nall fields populated]
    SAVE[save_config\nwrite TOML to config path]
    PANEL[Success panel\nconfig path + provider + model]

    INIT_CMD --> EXISTING
    EXISTING -->|yes| SHOW_EXISTING
    EXISTING -->|no| WIZARD
    SHOW_EXISTING --> WIZARD
    WIZARD --> PROVIDER --> MODEL --> CREDS --> GH --> SEARCH_PROV --> SEARCH_KEY
    SEARCH_KEY --> VAL_LLM
    VAL_LLM --> VAL_SEARCH
    VAL_SEARCH --> VAL_GH
    VAL_GH --> BUILD_CFG
    BUILD_CFG --> SAVE
    SAVE --> PANEL
```

---

## `devagent config`

```mermaid
flowchart LR
    CONFIG_CMD[devagent config]
    FLAG{flag?}
    SHOW[--show\nload_config → Rich Table\nall fields, api_key masked]
    SET[--set key=value\ndot-notation: llm.provider=anthropic]
    VALIDATE_KEY[validate known keys\nllm.provider in allowed list\nllm.temperature in 0.0-2.0]
    COERCE[type coerce\nfloat/int if current type is float/int]
    SAVE[setattr + save_config]

    CONFIG_CMD --> FLAG
    FLAG -->|--show| SHOW
    FLAG -->|--set| SET
    SET --> VALIDATE_KEY
    VALIDATE_KEY --> COERCE
    COERCE --> SAVE
```

---

## `devagent index`

```mermaid
flowchart TD
    INDEX_CMD[devagent index]
    FLAGS{flags?}
    STATUS_FLAG[--status\nget_index_status + get_changed_files_count]
    CLEAR_FLAG[--clear\nConfirm + clear_project_index]
    DETECT[detect_project_root\nwalk up for .git / pyproject.toml / etc]
    ENSURE[ensure_dirs\n.devagent/ + .codeprism/ structure]
    MCP_SERVER[Launch MCP server subprocess\ndevagent.mcp.servers.code_search.server]
    STDIO[stdio_client transport]
    CALL[session.call_tool\n"index_codebase"\nproject_root + incremental]
    RESULT[JSON: files_indexed, chunks_created,\nfiles_skipped, duration_seconds]
    TABLE[Show summary Rich Table]

    INDEX_CMD --> FLAGS
    FLAGS -->|--status| STATUS_FLAG
    FLAGS -->|--clear| CLEAR_FLAG
    FLAGS -->|default| DETECT
    DETECT --> ENSURE
    ENSURE --> MCP_SERVER
    MCP_SERVER --> STDIO
    STDIO --> CALL
    CALL --> RESULT
    RESULT --> TABLE
```

---

## `devagent run` (interactive session)

```mermaid
flowchart TD
    RUN_CMD[devagent run\nor bare devagent]
    OPTS[Optional: --resume ID\n--model MODEL\n--project PATH\n--max-tokens N]
    CFG[load_config]
    PROJECT[detect_project_root]
    SESSION_INIT[DevAgentSession.__init__\nagent/flows.py]
    CP_INIT[Try CodePrismClient\nskip if not indexed]
    LLM_INIT[LLMClient from config]
    ROUTER_INIT[MultiModelRouter if router config present]
    REGISTRY_INIT[Build ToolRegistry\nregister all tools + security_gate]
    MEMORY_INIT[MemoryBlock.load\nfrom SQLite]
    BUDGET_INIT[TokenBudget\nmax_tokens from config or flag]
    RESUME{--resume?}
    NEW_S[SessionManager.new]
    LOAD_S[SessionManager.resume]
    REPL[interactive_repl\nRich prompt loop]

    RUN_CMD --> OPTS
    OPTS --> CFG --> PROJECT
    PROJECT --> SESSION_INIT
    SESSION_INIT --> CP_INIT
    SESSION_INIT --> LLM_INIT
    SESSION_INIT --> ROUTER_INIT
    SESSION_INIT --> REGISTRY_INIT
    SESSION_INIT --> MEMORY_INIT
    SESSION_INIT --> BUDGET_INIT
    BUDGET_INIT --> RESUME
    RESUME -->|yes| LOAD_S
    RESUME -->|no| NEW_S
    NEW_S --> REPL
    LOAD_S --> REPL
```

---

## `devagent implement / review / triage / fix-ci`

These all follow the same pattern — they differ only in the system prompt and GitHub API calls.

```mermaid
flowchart TD
    CMD[devagent implement URL]
    PARSE_URL[parse_github_url\nextract owner + repo + number]
    CFG[load_config]
    PROJECT[detect_project_root]
    SESSION[DevAgentSession\nwith GitHub token in env]
    FETCH{what to fetch}
    FETCH_ISSUE[GET /repos/owner/repo/issues/N\ntitle + body + labels]
    FETCH_PR[GET /repos/owner/repo/pulls/N/files\ndiff hunks]
    FETCH_ISSUES[GET /repos/owner/repo/issues\nall open issues]
    FETCH_CI[GET /repos/owner/repo/actions/runs/ID/logs\nfailed step logs]
    PROMPT[Build task-specific system prompt\n+ fetched content]
    AGENT[AgentLoop.run\nmulti-step task execution]
    OUTPUT[Changes on disk / comments posted]

    CMD --> PARSE_URL --> CFG --> PROJECT --> SESSION
    SESSION --> FETCH
    FETCH -->|implement| FETCH_ISSUE
    FETCH -->|review| FETCH_PR
    FETCH -->|triage| FETCH_ISSUES
    FETCH -->|fix-ci| FETCH_CI
    FETCH_ISSUE --> PROMPT
    FETCH_PR --> PROMPT
    FETCH_ISSUES --> PROMPT
    FETCH_CI --> PROMPT
    PROMPT --> AGENT --> OUTPUT
```

---

## `devagent session` sub-commands

```mermaid
flowchart LR
    SESSION_APP[devagent session]
    LIST[list --limit N\nSessionManager.list → Rich Table]
    SHOW[show SESSION_ID\nload events + token totals → Rich display]
    DELETE[delete SESSION_ID\nConfirm.ask → SessionManager.delete]

    SESSION_APP --> LIST
    SESSION_APP --> SHOW
    SESSION_APP --> DELETE
```

---

## `devagent watch`

```mermaid
flowchart TD
    WATCH_CMD[devagent watch]
    FLAGS{flags?}

    NO_FLAGS[Show usage hint]
    REPO_ARG[--repo owner/repo\n_watch_register\nwrite to watcher.db]
    START_F[--start\n_watch_start\nWatcherScheduler.start\nasync loop forever]
    STATUS_F[--status\n_watch_run_once\nWatcherScheduler.run_once]
    STOP_F[--stop\n_watch_stop\ndeactivate_repo in DB]
    LIST_F[--list\n_watch_list\nlist_watched_repos → Rich Table]
    REPORT_F[--report\n_watch_report\nget_all_analyses → render]
    SHOW_F[--show N\n_watch_show\nget_analysis for issue N → render]

    WATCH_CMD --> FLAGS
    FLAGS -->|none| NO_FLAGS
    FLAGS -->|--repo| REPO_ARG
    FLAGS -->|--start| START_F
    FLAGS -->|--status| STATUS_F
    FLAGS -->|--stop| STOP_F
    FLAGS -->|--list| LIST_F
    FLAGS -->|--report| REPORT_F
    FLAGS -->|--show N| SHOW_F
```

---

## `devagent serve`

```mermaid
flowchart TD
    SERVE_CMD[devagent serve\n--host 127.0.0.1\n--port 7331]
    CFG[load_config if exists\nNone otherwise]
    PROJECT[detect_project_root]
    CP[Try CodePrismClient]
    HTTP[stdlib HTTPServer\nbind host:port]
    HANDLER[RequestHandler\nparse path → dispatch]
    ROUTES{path?}
    H[/api/health → version JSON]
    S[/api/status → config + index state]
    SE[/api/sessions → last 20]
    SE_ID[/api/sessions/ID → full session]
    T[/api/tools → tool definitions]
    GS[/api/graph/stats → graph metrics]
    GF[/api/graph/files → file map]
    CORS[CORS headers on all responses]

    SERVE_CMD --> CFG --> PROJECT --> CP --> HTTP
    HTTP --> HANDLER
    HANDLER --> ROUTES
    ROUTES --> H
    ROUTES --> S
    ROUTES --> SE
    ROUTES --> SE_ID
    ROUTES --> T
    ROUTES --> GS
    ROUTES --> GF
    H --> CORS
    S --> CORS
    SE --> CORS
    T --> CORS
    GS --> CORS
    GF --> CORS
```

---

## `devagent onboard`

```mermaid
flowchart TD
    ONBOARD_CMD[devagent onboard]
    PROJECT[detect_project_root]
    CP_CHECK{CodePrism\nindexed?}
    NOT_INDEXED[Panel: run codeprism index PATH]
    STATS[cp.get_stats\nnode count, edge count, etc.]
    FILE_MAP[cp.get_file_map\nentries sorted by symbol count]
    COUPLED[Per file: cp.get_module_summary\n+ cp.get_impact\nfor HIGH/CRITICAL severity symbols]
    TEST_GAPS[Per file: check test_coverage_file\nis None + has public_api]
    TABLE1[Rich table: Knowledge Graph metrics]
    TABLE2[Rich table: Top 20 files by symbol count]
    TABLE3[Rich table: Most-coupled symbols]
    LIST[Bullet list: files with no test coverage]

    ONBOARD_CMD --> PROJECT --> CP_CHECK
    CP_CHECK -->|no| NOT_INDEXED
    CP_CHECK -->|yes| STATS
    STATS --> TABLE1
    TABLE1 --> FILE_MAP
    FILE_MAP --> TABLE2
    TABLE2 --> COUPLED
    COUPLED --> TABLE3
    TABLE3 --> TEST_GAPS
    TEST_GAPS --> LIST
```
