# User Flow

Every path a user takes through DevAgent, from first install to complex GitHub workflows.

---

## First-time setup

```mermaid
flowchart TD
    START([User installs DevAgent\npipx install devagent])
    INIT[devagent init]

    STEP1{Choose LLM provider}
    OLLAMA[Ollama\nlocal, free]
    GROQ[Groq API]
    ANTHROPIC[Anthropic API]
    OPENAI[OpenAI API]
    GEMINI[Gemini API]

    STEP2[Enter model name\ndefault shown per provider]
    STEP3_OLL[Enter Ollama base URL\ndefault: localhost:11434]
    STEP3_CLOUD[Enter API key\nmasked input]
    STEP4[Enter GitHub token\noptional, for GitHub features]
    STEP5{Choose search provider}
    SEARCHX[SearchX\nfree 3K/day]
    BRAVE[Brave Search\npaid]
    STEP6_KEY[Enter search API key\noptional]
    VALIDATE[Validate LLM + GitHub + search]
    SAVE[Save config.toml]
    DONE([Ready to use])

    START --> INIT
    INIT --> STEP1
    STEP1 --> OLLAMA
    STEP1 --> GROQ
    STEP1 --> ANTHROPIC
    STEP1 --> OPENAI
    STEP1 --> GEMINI
    OLLAMA --> STEP2
    GROQ --> STEP2
    ANTHROPIC --> STEP2
    OPENAI --> STEP2
    GEMINI --> STEP2
    STEP2 --> STEP3_OLL
    STEP2 --> STEP3_CLOUD
    STEP3_OLL --> STEP4
    STEP3_CLOUD --> STEP4
    STEP4 --> STEP5
    STEP5 --> SEARCHX
    STEP5 --> BRAVE
    SEARCHX --> STEP6_KEY
    BRAVE --> STEP6_KEY
    STEP6_KEY --> VALIDATE
    VALIDATE --> SAVE
    SAVE --> DONE
```

---

## Codebase indexing

```mermaid
flowchart TD
    CD[cd /path/to/project]
    INDEX[devagent index]
    ROOT[detect_project_root\nlook for .git, pyproject.toml, etc.]
    MARKER{Marker found?}
    WARN[Warn: using current dir]
    MCP[Launch code_search MCP server\nstdio subprocess]
    TOOL_CALL[call index_codebase\nproject_root + incremental=True]
    PARSE[Parse source files\nAST + imports]
    STORE_GRAPH[Store in CodePrism graph\n.codeprism/ directory]
    SUMMARY[Show: files indexed, chunks, duration]
    STALE[devagent index --status\nshow changed files count]
    FULL[devagent index --full\nforce complete rebuild]

    CD --> INDEX
    INDEX --> ROOT
    ROOT --> MARKER
    MARKER -->|yes| MCP
    MARKER -->|no| WARN
    WARN --> MCP
    MCP --> TOOL_CALL
    TOOL_CALL --> PARSE
    PARSE --> STORE_GRAPH
    STORE_GRAPH --> SUMMARY

    INDEX -.->|--status| STALE
    INDEX -.->|--full| FULL
    FULL --> MCP
```

**When to re-index:** After significant code changes. Incremental mode (default) only re-parses changed files. Full re-index takes the same time as the first index.

---

## Interactive session flow

```mermaid
flowchart TD
    RUN[devagent  or  devagent run]
    CFG_CHECK{Config exists?}
    CFG_ERR[Error: run devagent init]
    SESSION_INIT[DevAgentSession.__init__\nload config, build tools, init budget]
    RESUME_CHECK{--resume flag?}
    NEW_SESSION[SessionManager.new\ncreate UUID session]
    LOAD_SESSION[SessionManager.resume\nload existing session]
    HEADER[Print session header\nID, model, provider]
    REPL[interactive_repl\nRich prompt loop]

    INPUT[User types message]
    EMPTY_EXIT{Empty message?}
    EXIT_CMD{/exit or /quit?}
    SPECIAL{Special command?}
    HANDLE_CMD[handle /help /session /memory /clear]
    AGENT_RUN[AgentLoop.run\nyield AgentEvents]
    RENDER[output/streaming.py\nrender events to terminal]
    NEXT_TURN[Ready for next message]
    CLOSE[SessionManager.close\nupdate timestamp]

    RUN --> CFG_CHECK
    CFG_CHECK -->|no| CFG_ERR
    CFG_CHECK -->|yes| SESSION_INIT
    SESSION_INIT --> RESUME_CHECK
    RESUME_CHECK -->|yes| LOAD_SESSION
    RESUME_CHECK -->|no| NEW_SESSION
    NEW_SESSION --> HEADER
    LOAD_SESSION --> HEADER
    HEADER --> REPL

    REPL --> INPUT
    INPUT --> EMPTY_EXIT
    EMPTY_EXIT -->|yes| CLOSE
    EMPTY_EXIT -->|no| EXIT_CMD
    EXIT_CMD -->|yes| CLOSE
    EXIT_CMD -->|no| SPECIAL
    SPECIAL -->|yes| HANDLE_CMD
    SPECIAL -->|no| AGENT_RUN
    HANDLE_CMD --> NEXT_TURN
    AGENT_RUN --> RENDER
    RENDER --> NEXT_TURN
    NEXT_TURN --> INPUT
    CLOSE --> END([Session saved to SQLite])
```

---

## Session resume flow

```mermaid
flowchart LR
    LIST[devagent session list\nshow last 20 sessions]
    PICK[User picks session ID prefix\ne.g. a1b2c3d4]
    RESUME[devagent run --resume a1b2c3d4]
    FIND[SessionManager.resume\nlook up full ID]
    LOAD_EVENTS[store.get_events\nfull message history]
    LOAD_MEM[MemoryBlock.load\nall memory key-value pairs]
    REPL[interactive_repl\nfull context restored]
    CONTINUE[User continues conversation\nagent has all prior context]

    LIST --> PICK
    PICK --> RESUME
    RESUME --> FIND
    FIND --> LOAD_EVENTS
    FIND --> LOAD_MEM
    LOAD_EVENTS --> REPL
    LOAD_MEM --> REPL
    REPL --> CONTINUE
```

The LLM doesn't "remember" the session — but all prior messages are replayed as context every turn via `build_messages()`. The memory block is separate: it's a compact injected prompt rather than full replay.

---

## GitHub workflow — implement an issue

```mermaid
flowchart TD
    CMD[devagent implement\nhttps://github.com/owner/repo/issues/42]
    PARSE[parse_github_url\nextract owner, repo, number]
    FETCH[GitHub API\nGET /repos/owner/repo/issues/42]
    ISSUE[Issue: title + body + labels]
    SESSION[New DevAgentSession\nprovider: anthropic or configured]
    PROMPT[System prompt: implement mode\ninclude issue title + body]
    LOOP[AgentLoop\nrun implementation]
    BRANCH[git checkout -b feat/issue-42]
    CODE[write_file / edit_file\nimplement the feature]
    TEST[_auto_test_after_write\nrun pytest on affected tests]
    PR_DRAFT[Draft PR description\ntitle + body from issue]
    DONE[Session ends\nChanges on disk, user reviews + commits]

    CMD --> PARSE
    PARSE --> FETCH
    FETCH --> ISSUE
    ISSUE --> SESSION
    SESSION --> PROMPT
    PROMPT --> LOOP
    LOOP --> BRANCH
    BRANCH --> CODE
    CODE --> TEST
    TEST -->|pass| PR_DRAFT
    TEST -->|fail| CODE
    PR_DRAFT --> DONE
```

---

## GitHub workflow — review a PR

```mermaid
flowchart TD
    CMD[devagent review\nhttps://github.com/owner/repo/pull/17]
    PARSE[parse_github_url]
    FETCH_DIFF[GitHub API\nGET /repos/owner/repo/pulls/17/files]
    DIFF[PR diff: changed files + hunks]
    SESSION[New DevAgentSession\nreviewing mode]
    LOOP[AgentLoop\nanalyse diff, read relevant files]
    FINDINGS[List of issues:\nbug, missing test, style, etc.]
    POST[GitHub API\nPOST /repos/owner/repo/pulls/17/comments\ninline review comment per finding]
    DONE[PR has inline review comments]

    CMD --> PARSE
    PARSE --> FETCH_DIFF
    FETCH_DIFF --> DIFF
    DIFF --> SESSION
    SESSION --> LOOP
    LOOP --> FINDINGS
    FINDINGS --> POST
    POST --> DONE
```

---

## Background watcher flow

```mermaid
flowchart TD
    REGISTER[devagent watch --repo owner/repo\n--interval 30m]
    DB[watcher.db\nInsert watched_repos row]
    STATUS[devagent watch --status\nrun a check immediately]
    START[devagent watch --start\nstart foreground scheduler loop]

    SCHEDULER[WatcherScheduler.start\nasync loop every interval_minutes]
    FETCH[GitHub API\nGET /repos/owner/repo/issues\n?state=open&since=last_check]
    NEW{New issues?}
    ANALYSE[WatcherChecker\nfor each new issue]
    AGENT_BRIEF[Lightweight agent session\nread issue + codebase graph]
    STORE_ANALYSIS[watcher.db\nInsert issue_analyses row]
    CONFLICT[ConflictDetector\ncheck against other open issues]
    STORE_CONFLICT[watcher.db\nInsert conflicts row]

    REPORT[devagent watch --report\nshow all analyses]
    SHOW[devagent watch --show 42\nfull analysis for issue #42]

    REGISTER --> DB
    DB --> STATUS
    DB --> START
    START --> SCHEDULER
    SCHEDULER --> FETCH
    FETCH --> NEW
    NEW -->|no| SCHEDULER
    NEW -->|yes| ANALYSE
    ANALYSE --> AGENT_BRIEF
    AGENT_BRIEF --> STORE_ANALYSIS
    STORE_ANALYSIS --> CONFLICT
    CONFLICT --> STORE_CONFLICT
    STORE_CONFLICT --> SCHEDULER

    REPORT --> DB
    SHOW --> DB
```

---

## Doctor / health check flow

```mermaid
flowchart LR
    DOCTOR[devagent doctor]
    CHECK_CFG{config.toml\nexists + parseable?}
    CHECK_LLM{ollama: can reach\n/api/tags + model available?\ncloud: api_key set?}
    CHECK_GH{GitHub token\n200 from /user?}
    CHECK_SEARCH{search API key\n200 from provider?}
    CHECK_NODE{node --version\nnpx --version}
    TABLE[Rich table\ngreen/red per row]

    DOCTOR --> CHECK_CFG
    CHECK_CFG --> CHECK_LLM
    CHECK_LLM --> CHECK_GH
    CHECK_GH --> CHECK_SEARCH
    CHECK_SEARCH --> CHECK_NODE
    CHECK_NODE --> TABLE
```
