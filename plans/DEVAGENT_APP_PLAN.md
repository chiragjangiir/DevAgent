# devagent-app — Complete Product Plan

> Internal planning document. Not for public distribution.

---

## Design Mandate

**UI is a first-class product decision.** The orchestrator and IDE must look as good as they work.
Competitors (Cursor, Windsurf, Zed) have beautiful UIs. DevAgent must match or exceed them.

### Core Design Principles

- **Dark-first.** Default dark theme. Light theme is a courtesy, not the primary experience.
- **Dense but not cluttered.** Show a lot of information (events, tokens, workers) without feeling noisy. Use subtle hierarchy: font weight, opacity, spacing — not color everywhere.
- **Motion with purpose.** Animate running states (pulsing nodes, streaming text), not chrome. Nothing spins for no reason.
- **Monospace where it matters.** Event feeds, tool call args, code — always monospace. UI chrome — Inter or Geist.
- **Depth.** Use blur, layering, subtle borders. Not flat/material — more like Linear or Vercel's design language.
- **Syntax highlighting everywhere.** Tool args, tool results, diff views — always color-coded.

### Color Palette (Dark Theme)

```
Background:   #0A0A0B  (near-black, not pure black)
Surface:      #111113  (cards, panels)
Border:       #1E1E21  (subtle separators)
Muted:        #3A3A3F  (disabled, placeholder)
Text:         #E8E8EB  (primary)
Text-dim:     #8A8A8F  (secondary, timestamps, labels)

Accent-blue:  #3B82F6  (running, active, links)
Accent-green: #22C55E  (done, success)
Accent-red:   #EF4444  (failed, error, block)
Accent-amber: #F59E0B  (warn, in-progress)
Accent-purple:#A855F7  (thinking, LLM text)

Gradient hero: linear-gradient(135deg, #1a1a2e 0%, #0f0f1a 50%, #0a0a0b 100%)
```

### Typography

```
UI chrome:      Geist Sans (or Inter) — 400/500/600 weights
Code/mono:      Geist Mono (or JetBrains Mono) — operator ligatures on
Sizes:          12px labels, 13px body, 14px primary, 16px headings
```

### Reference UIs to Study

- **Linear** — spacing, typography, list density, sidebar
- **Vercel dashboard** — card layouts, status indicators, metrics
- **Raycast** — command palette, search, keyboard-first interactions  
- **Warp terminal** — event streams, monospace blocks, diff highlighting
- **Langflow** — React Flow DAG styling, node design

---

## Repo Architecture Decision

**Separate repo: `devagent-app`** (not inside the Python `devagent` repo)

Why:
- Different tech stack (TypeScript/Rust vs Python)
- Different release cadence (app ships on GitHub Releases; CLI ships on PyPI)
- Different contributors (frontend dev can work without touching Python)
- Clean API contract between the two: `devagent serve` is the only interface

Stable contract: `devagent serve --port 7331` exposes REST + WebSocket. Breaking changes require API version bump.

---

## Full Repo Structure

```
devagent-app/
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                 # lint + typecheck + test on every PR
│   │   ├── release.yml            # build binaries + publish on git tag
│   │   └── ui-preview.yml         # build storybook on PR for visual review
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── PULL_REQUEST_TEMPLATE.md
│
├── apps/
│   │
│   ├── web/                       # React web app — the orchestrator UI
│   │   ├── src/
│   │   │   ├── main.tsx
│   │   │   ├── App.tsx            # router + providers
│   │   │   │
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── ActiveAgentsPanel.tsx
│   │   │   │   │   ├── MetricsSummary.tsx
│   │   │   │   │   └── RecentSessions.tsx
│   │   │   │   ├── Sessions/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── SessionRow.tsx
│   │   │   │   │   └── SessionFilters.tsx
│   │   │   │   ├── SessionDetail/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── EventStream.tsx
│   │   │   │   │   ├── MemoryPanel.tsx
│   │   │   │   │   ├── TokenChart.tsx
│   │   │   │   │   └── ToolCallInspector.tsx
│   │   │   │   ├── Orchestrate/
│   │   │   │   │   ├── index.tsx
│   │   │   │   │   ├── TaskDAG.tsx
│   │   │   │   │   ├── WorkerGrid.tsx
│   │   │   │   │   ├── WorkerCard.tsx
│   │   │   │   │   ├── FileLockMap.tsx
│   │   │   │   │   └── WaveProgress.tsx
│   │   │   │   └── Metrics/
│   │   │   │       ├── index.tsx
│   │   │   │       ├── TokenOverTime.tsx
│   │   │   │       ├── CostByModel.tsx
│   │   │   │       └── ToolCallHeatmap.tsx
│   │   │   │
│   │   │   ├── components/
│   │   │   │   ├── EventFeed/
│   │   │   │   │   ├── EventFeed.tsx
│   │   │   │   │   ├── EventItem.tsx
│   │   │   │   │   ├── ThinkingEvent.tsx
│   │   │   │   │   ├── ToolCallEvent.tsx
│   │   │   │   │   ├── ToolResultEvent.tsx
│   │   │   │   │   └── ErrorEvent.tsx
│   │   │   │   ├── TokenMeter.tsx
│   │   │   │   ├── CostBadge.tsx
│   │   │   │   ├── ModelBadge.tsx
│   │   │   │   ├── StatusDot.tsx
│   │   │   │   ├── SessionCard.tsx
│   │   │   │   ├── SecurityAlert.tsx
│   │   │   │   └── ConnectionStatus.tsx
│   │   │   │
│   │   │   ├── hooks/
│   │   │   │   ├── useSession.ts
│   │   │   │   ├── useSessions.ts
│   │   │   │   ├── useOrchestrateGraph.ts
│   │   │   │   ├── useMetrics.ts
│   │   │   │   └── useConnectionStatus.ts
│   │   │   │
│   │   │   ├── lib/
│   │   │   │   ├── api.ts
│   │   │   │   ├── ws.ts
│   │   │   │   ├── formatters.ts
│   │   │   │   └── constants.ts
│   │   │   │
│   │   │   └── stores/
│   │   │       ├── connection.store.ts
│   │   │       ├── sessions.store.ts
│   │   │       └── ui.store.ts
│   │   │
│   │   ├── public/
│   │   │   └── favicon.svg
│   │   ├── index.html
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   └── package.json
│   │
│   └── desktop/                   # Tauri desktop app
│       ├── src/                   # symlinked to apps/web/src
│       ├── src-tauri/
│       │   ├── src/
│       │   │   ├── main.rs
│       │   │   ├── devagent.rs    # manages devagent serve subprocess
│       │   │   ├── updater.rs
│       │   │   ├── tray.rs
│       │   │   └── commands.rs
│       │   ├── capabilities/
│       │   │   └── default.json
│       │   ├── icons/
│       │   ├── Cargo.toml
│       │   └── tauri.conf.json
│       ├── index.html
│       ├── vite.config.ts
│       └── package.json
│
├── packages/
│   │
│   ├── api-client/                # Shared TypeScript API client
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── client.ts          # REST client
│   │   │   ├── ws-manager.ts      # WebSocket manager (auto-reconnect, queue)
│   │   │   └── types.ts           # All shared TypeScript types
│   │   ├── tsconfig.json
│   │   └── package.json
│   │
│   └── ui/                        # Shared component library + Storybook
│       ├── src/
│       │   ├── index.ts
│       │   ├── EventFeed/
│       │   ├── TaskDAG/
│       │   ├── TokenMeter/
│       │   ├── SessionCard/
│       │   └── theme/             # design tokens: colors, spacing, typography
│       ├── .storybook/
│       ├── tsconfig.json
│       └── package.json
│
├── docs/
│   ├── api-contract.md
│   ├── contributing.md
│   └── screenshots/
│
├── pnpm-workspace.yaml
├── package.json                   # root scripts: dev, build, lint, test
├── .eslintrc.json
├── .prettierrc
├── tsconfig.base.json
└── README.md
```

---

## Tech Stack — Every Decision Justified

### Frontend

| Layer | Choice | Why not X |
|---|---|---|
| Framework | **React 18** | shadcn/ui and React Flow are React-first. Ecosystem size matters for niche libs. |
| Language | **TypeScript** | Type safety between API client ↔ UI catches an entire class of bugs. Non-negotiable. |
| Build tool | **Vite 5** | 10–50× faster HMR vs webpack. First-class TS. Works perfectly with Tauri. |
| Styling | **Tailwind CSS 3** | Utility-first = no CSS sprawl. Consistent tokens. Works with shadcn. |
| Component base | **shadcn/ui** | Not a package — you copy components in (full control). Built on Radix UI (accessible). Looks professional without a designer. |
| Server state | **TanStack Query v5** | Handles caching, loading/error states, background refetching. Eliminates 80% of async boilerplate. |
| Client state | **Zustand** | 1KB, simple API. No Redux ceremony. Perfect alongside TanStack Query. |
| Routing | **React Router v6** | Standard. Works in Tauri. |
| DAG viz | **React Flow v11** | Purpose-built for node-edge graphs. Interactive. Used by Langflow, n8n. Ideal for task DAGs. D3 would need 10× more code. |
| Charts | **Recharts** | React-native. Simple API. Good for token/cost charts. |
| CodePrism graph | **D3.js v7** | Force-directed physics simulation for organic graph layout. React Flow can't do this. |
| WebSocket | **Native WebSocket API** | No library needed. Custom WS manager handles reconnect logic. |
| Icons | **Lucide React** | Same icon set as shadcn/ui. Clean SVG. |
| Date formatting | **date-fns** | Lightweight. Tree-shakeable. |
| Testing | **Vitest + React Testing Library** | Vite-native (same config). RTL is the React standard. |
| Fonts | **Geist Sans + Geist Mono** | Vercel's open-source fonts. Excellent at small sizes. Ligatures. |

### Desktop

| Layer | Choice | Why |
|---|---|---|
| App shell | **Tauri v2** | ~10MB binary vs Electron's ~150MB. OS WebView (no bundled Chromium). Rust backend is memory-safe. Built-in updater + code signing hooks. |
| Rust crates | **tokio, serde_json, which, tauri-plugin-updater, tauri-plugin-notification, tauri-plugin-shell** | Standard Tauri ecosystem. |
| Process mgmt | Custom `devagent.rs` | Start/stop/restart devagent serve child process. Port discovery. Crash recovery. |

### Package Management

| Choice | Why |
|---|---|
| **pnpm** | Faster, better monorepo support, strict mode prevents phantom dependencies. |
| No Turborepo | Overkill for 2 apps + 2 packages. pnpm `--filter` handles build order. Add Turborepo if it grows beyond 10 packages. |

### IDE Phase

| Layer | Choice | Why |
|---|---|---|
| Code editor | **Monaco Editor** (`@monaco-editor/react`) | Same engine as VS Code. Best-in-class TypeScript/Python support. Rich API for decorations, diffs, inline hints. |
| Terminal | **xterm.js** | Standard. Fast. Used by VS Code, JupyterLab. WebGL renderer available. |
| LSP client | **`vscode-languageserver-protocol`** | Connects Monaco to pyright, tsserver, etc. |
| File tree | **@tanstack/react-virtual** + custom tree | Virtualizes 10,000+ files. Pre-built trees are all limited. |

---

## API Contract Between devagent and devagent-app

The Python `devagent` repo owns this contract. Breaking changes require a version bump.

### REST Endpoints

```
GET  /api/v1/status
     → { version, uptime_seconds, active_sessions, total_sessions }

GET  /api/v1/sessions?status=&project=&limit=&offset=
     → { sessions: Session[], total: int }

GET  /api/v1/sessions/{id}
     → Session (full detail)

DELETE /api/v1/sessions/{id}
     → { ok: true }

GET  /api/v1/sessions/{id}/events?from_seq=&limit=
     → { events: SessionEvent[], has_more: bool }

GET  /api/v1/sessions/{id}/memory
     → { facts: {key, value, created_at}[] }

POST /api/v1/sessions/{id}/approve
     → { ok: true }   (approves a pending write_file in permission-gate mode)

GET  /api/v1/orchestrate/{session_id}/graph
     → { nodes: TaskNode[], session_id, is_complete, has_failures }

GET  /api/v1/orchestrate/{session_id}/locks
     → { locks: FileLock[] }

GET  /api/v1/metrics?period=1h|24h|7d|30d
     → { total_tokens, total_cost_usd, sessions_count,
          by_model: {model, tokens, cost}[],
          by_hour: {hour, tokens, cost}[] }
```

### WebSocket Protocol (`/ws/v1/{session_id}`)

Server pushes newline-delimited JSON:

```json
// Standard event
{ "type": "event", "session_id": "s_abc", "seq": 42,
  "event_type": "thinking|tool_call|tool_result|final_answer|error|status",
  "data": { ... } }

// Orchestrate: task status change
{ "type": "graph_update", "session_id": "s_abc",
  "task_id": "t1", "status": "done", "result": "wrote payments/processor.py" }

// Orchestrate: file lock
{ "type": "lock_update", "session_id": "s_abc",
  "action": "acquired|released", "file_path": "payments/processor.py", "worker_id": "w-2" }

// Heartbeat (every 30s)
{ "type": "ping" }
// Client responds: { "type": "pong" }
```

### TypeScript Types (`packages/api-client/src/types.ts`)

```typescript
type SessionStatus = 'running' | 'completed' | 'error' | 'paused'
type TaskStatus    = 'pending' | 'running' | 'done' | 'failed'
type WorkerType    = 'implementer' | 'tester' | 'reviewer' | 'coordinator'

interface Session {
  id: string; project: string; model: string; provider: string
  title: string; status: SessionStatus
  created_at: number; updated_at: number
  token_input: number; token_output: number; cost_usd: number
  is_orchestrate: boolean; compressed_summary: string
}

interface SessionEvent {
  id: number; session_id: string; seq: number
  role: string; content: string
  tool_calls: ToolCall[]; tool_call_id: string; tool_name: string
  tokens_in: number; tokens_out: number; created_at: number
  event_type: 'thinking' | 'tool_call' | 'tool_result' | 'final_answer' | 'error' | 'status'
}

interface TaskNode {
  id: string; session_id: string; description: string
  worker_type: WorkerType; depends_on: string[]; status: TaskStatus
  result: string; output_files: string[]; assigned_session: string
  created_at: number; updated_at: number
}

interface FileLock {
  session_id: string; file_path: string; worker_id: string; locked_at: number
}

interface MetricsSummary {
  total_tokens: number; total_cost_usd: number
  sessions_count: number; active_sessions: number
  by_model: { model: string; tokens: number; cost_usd: number }[]
  by_hour: { hour: string; tokens: number; cost_usd: number }[]
}
```

---

## Phase App-1: Orchestrator Web App (5 weeks)

### Week 1 — Repo Setup + API Client + Shell

**Day 1–2: Repo bootstrap**
- `git init devagent-app`
- `pnpm-workspace.yaml` declaring `apps/*` and `packages/*`
- Shared `tsconfig.base.json` (strict, path aliases)
- Root `.eslintrc.json` (eslint-config-airbnb-typescript + prettier)
- Root `.prettierrc` (singleQuote, tabWidth 2, trailing comma)
- GitHub Actions `ci.yml`: lint + typecheck + test on every PR

**Day 3–4: `packages/api-client`**
- All TypeScript types from the API contract above
- REST client: configurable baseUrl, typed `get/post/del`, `ApiError` class
- WS manager:
  - `connect(sessionId)` → opens WebSocket to `/ws/v1/{sessionId}`
  - `subscribe(sessionId, handler)` / `unsubscribe(sessionId, handler)`
  - Auto-reconnect: exponential backoff 1s → 2s → 4s → 8s → max 30s
  - Message queue: buffers events during disconnect, flushes on reconnect
  - Heartbeat: ping every 30s, reconnect if no pong in 5s
  - Multiple simultaneous session subscriptions

**Day 5: `apps/web` scaffold**
- Vite + React 18 + TypeScript
- Tailwind CSS: `tailwind.config.ts` with the full design palette above
- shadcn/ui init: `components.json` pointing to `src/components/ui/`
- Geist font loaded from `@vercel/font` or self-hosted
- React Router v6: layout routes (`/`, `/sessions`, `/sessions/:id`, `/orchestrate/:id`, `/metrics`)
- Main layout: fixed sidebar (240px) + top bar (48px) + scrollable content
- Sidebar: DevAgent logo (top), nav items with active state, connection status (bottom)
- Top bar: page title, breadcrumb, model badge for active session
- `ConnectionStatus` component: green/red dot + "Reconnecting…" state
- TanStack Query setup: `queryClient` with 30s staleTime, retry 2

---

### Week 2 — Dashboard + Sessions List

**Dashboard page design:**

```
┌─ Sidebar ────────────┬─ Dashboard ─────────────────────────────────────────┐
│                      │  ┌── Active Agents ──────────────────────────────┐  │
│  ● DevAgent          │  │  ◌ sess_a4f  payments refactor   2m 34s  42k  │  │
│                      │  │  ◌ sess_b1c  fix CI test failure  45s  8.1k   │  │
│  ○ Dashboard         │  └───────────────────────────────────────────────┘  │
│  ○ Sessions          │                                                       │
│  ○ Metrics           │  ┌── Today ──────┐  ┌── This Week ─────────────┐   │
│                      │  │  184k tokens  │  │  2.4M tokens    $1.84    │   │
│                      │  │  $0.14        │  │  47 sessions             │   │
│  ────────────        │  └───────────────┘  └──────────────────────────┘   │
│  ● Connected         │                                                       │
└──────────────────────┴──────────────────────────────────────────────────────┘
```

- `ActiveAgentsPanel`: polls `/api/v1/status` every 5s. Shows each running session as a row: ID (monospace, first 8 chars), title (from first task), elapsed time, token count. Click row → navigate to `/sessions/{id}`.
- `MetricsSummary`: two cards — today and this week. Token count large, cost secondary.
- `RecentSessions`: last 10 sessions as `SessionCard` components. Each card shows:
  - Model badge (colour-coded: purple=ollama, orange=claude, green=openai)
  - Status dot with animation (pulsing blue if running)
  - Project name (from CWD basename)
  - First 80 chars of task title
  - Time ago + token count + cost
  - Hover: slight elevation, border brightens

**Sessions list page design:**

```
┌─ Sessions ───────────────────────────────────────────────────────────────┐
│  [Filter: all ▾]  [Project: all ▾]  [Date range: last 7d ▾]   Search…  │
│                                                                           │
│  sess_a4f2b  ◌ running   payments refactor   qwen2.5  2m 34s  42.1k    │
│  sess_c8d1a  ✓ done      add login tests     claude   4m 11s  91.3k    │
│  sess_e2f9c  ✗ failed    migrate db schema   qwen2.5  1m 02s  18.7k    │
│  ...                                                                      │
│                                              ← 1 2 3 4 5 →              │
└──────────────────────────────────────────────────────────────────────────┘
```

- Filter bar: status dropdown, project dropdown (populated from unique projects in DB), date range picker
- Sort by: created_at (default), token count, cost — click column header
- Pagination: 20 per page
- Click row → `/sessions/{id}`
- Keyboard: `j/k` to move between rows, `Enter` to open

---

### Week 3 — Session Detail

This is the most important screen. Design goals: information-dense, live, every event inspectable.

**Layout:**

```
┌─ Session Detail: sess_a4f2b ────────────────────────────────────────────────┐
│  ◌ running  qwen2.5-coder:32b  project: ~/code/payments  42.1k / $0.09     │
├─────────────────────────────────────────────┬───────────────────────────────┤
│  Event Stream                               │  Token Usage                  │
│                                             │  ████████████░░░░ 42.1k/100k  │
│  ◐ Thinking about the problem...            │                               │
│    "I need to first read the existing       │  Memory                       │
│     payment processor to understand..."    │  • project: payments-service  │
│                                             │  • framework: FastAPI         │
│  → read_file                                │  • test: pytest               │
│    path: "payments/processor.py"      [▸]  │                               │
│  ← 284 lines read                     [▸]  │  Session Info                 │
│                                             │  Started: 2m 34s ago          │
│  → write_file                               │  Events: 47                   │
│    path: "payments/processor.py"      [▸]  │  Tool calls: 12               │
│  ← File written successfully          [▸]  │  Model: qwen2.5-coder:32b     │
│                                             │  Provider: ollama             │
│  ◐ Thinking...                              │                               │
│    "Now I need to write tests for..."       └───────────────────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

**EventStream component:**
- TanStack Virtual for scrolling (handles 10,000+ events without jank)
- `ThinkingEvent`: dim purple text, italic, truncated to 3 lines by default, click to expand
- `ToolCallEvent`:
  - Tool name as coloured pill (`read_file` = blue, `write_file` = amber, `run_shell` = red, `search_codebase` = green)
  - Args preview: first key=value pair shown inline
  - `[▸]` expand button → collapsible JSON block with syntax highlighting
- `ToolResultEvent`: result preview (first 150 chars) + `[▸]` button → full result in right drawer
- `ErrorEvent`: red left border, error type as badge, message
- `SecurityAlertEvent`: amber or red background strip, lock icon, rule name, what was blocked
- Auto-scroll to bottom when live; shows "↓ N new events" banner if user has scrolled up
- Replay mode: for completed sessions, shows a scrubber (timeline slider at top)

**ToolCallInspector (right drawer):**
- Opens when clicking `[▸]` on any event
- Split view: left = args JSON, right = result JSON
- For `write_file`/`edit_file`: shows Monaco DiffEditor (old vs new content)
- For `run_shell`: shows output in terminal-style black box, ANSI colour support

**TokenChart:**
- Recharts AreaChart: cumulative tokens over time for this session
- X-axis: time since session start. Y-axis: token count
- Dashed horizontal line: budget limit (if set)
- Hover tooltip: exact event that happened at that moment
- Click a point → EventStream scrolls to that event

---

### Week 4 — Orchestrate View

Shown for sessions where `is_orchestrate = true`. Replaces the standard SessionDetail layout.

**Full-screen layout:**

```
┌─ Orchestrate: sess_a4f2b ───────────────────────────────────────────────────┐
│  Wave 2 of 3  [████████████░░░░░░░░] 62%   ◌ 3 running  ✓ 4 done          │
├──────────────────┬──────────────────────────────┬───────────────────────────┤
│  Task DAG        │  Worker Feeds                │  File Lock Map            │
│                  │                              │                           │
│  [coordinator]   │  ┌─ impl-A ──────────────┐  │  payments/processor.py   │
│      ↓           │  │  ◌ running            │  │    └─ worker impl-A       │
│  [impl-A] [impl-B]  │  → write_file          │  │                           │
│  [impl-C]        │  │    "processor.py"  ↓  │  │  payments/webhook.py     │
│      ↓           │  └───────────────────────┘  │    └─ worker impl-B       │
│   [tester]       │  ┌─ impl-B ──────────────┐  │                           │
│      ↓           │  │  ✓ done               │  │  tests/test_payment.py   │
│  [reviewer]      │  │  wrote webhook.py      │  │    (unlocked)            │
│                  │  └───────────────────────┘  │                           │
│                  │  ┌─ impl-C ──────────────┐  └───────────────────────────┘
│                  │  │  ◌ running  →think... │
│                  │  └───────────────────────┘
└──────────────────┴──────────────────────────────────────────────────────────┘
```

**TaskDAG (React Flow):**
- Node per TaskNode; edges from `depends_on`
- Node states:
  - `pending` → grey outline, dim text
  - `running` → blue border with CSS pulse glow animation
  - `done` → solid green fill, checkmark icon
  - `failed` → solid red fill, X icon
- Each node shows: worker_type badge (pill), description (truncated), output_files count
- Layout: `dagre` algorithm for automatic top-down DAG positioning
- Interactive: zoom, pan, click node → highlights the WorkerCard for that worker
- Mini-map in bottom-right corner for large DAGs

**WorkerGrid:**
- Grid of `WorkerCard` components (responsive: 1–3 columns based on width)
- Each `WorkerCard`:
  - Header: worker type badge + short task description + status dot
  - Coloured left border: blue=running, green=done, red=failed
  - Body: mini EventFeed (last 10 events) for that worker's session
  - Footer: token count + elapsed time
  - Click → expand to full SessionDetail overlay

**FileLockMap:**
- Right panel, compact list
- Per-file row: `path/to/file.py` + worker badge who holds it
- Currently-locked files: amber background
- Fades out released locks after 2 seconds with slide-out animation

**WaveProgress:**
- Top bar, full width
- "Wave 2 of 3" + progress bar
- Below: one line per active task in this wave

---

### Week 5 — Metrics + devagent Backend API + Polish

**Metrics page:**

```
┌─ Metrics ────────────────────────────────────────────────────────────────────┐
│  Period: [1h] [24h] [7d ✓] [30d]                                            │
│                                                                              │
│  ┌── Tokens Over Time ─────────────────────────────────────────────────┐   │
│  │   █                                                                  │   │
│  │  ██  █                                                               │   │
│  │ ███ ████  █    █                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌── Cost by Model ─────────────┐  ┌── Top Tools ──────────────────────┐  │
│  │  qwen2.5    ████████  $0.00  │  │  read_file    ██████████████  847  │  │
│  │  claude-3.5 ██████    $1.24  │  │  write_file   ████████        412  │  │
│  │  gpt-4o     ███       $0.67  │  │  run_shell    ██████          198  │  │
│  └──────────────────────────────┘  └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**devagent Python backend** (done this week, in the `devagent` repo):
- `devagent/api/__init__.py`
- `devagent/api/routes.py` — FastAPI router with all REST endpoints
- `devagent/api/ws.py` — WebSocket connection manager + event publisher
- `devagent/api/models.py` — Pydantic response models
- Wire `AgentLoop` to publish every `AgentEvent` to the WS publisher (after storing to DB)
- Wire `OrchestratorSession` to publish graph updates + lock updates
- `devagent serve` CLI command: `uvicorn` + FastAPI app on `--port` (default 7331)
- `devagent serve --open` flag: opens browser to `http://localhost:7331` after start

**Polish:**
- Keyboard shortcuts: `G` = Dashboard, `S` = Sessions, `M` = Metrics, `Esc` = close drawer
- Dark/light theme toggle in sidebar footer
- Empty states: clean illustration + CTA ("Run your first session with `devagent do '...'`")
- Error boundary: full-page fallback if React crashes
- `ConnectionStatus` banner at top when WebSocket disconnected, with manual reconnect button
- Responsive: works at 1280×720 minimum, breakpoints at 1440 and 1920
- Loading skeletons (not spinners) while data loads

---

## Phase App-2: Desktop App — Orchestrator (3–4 weeks)

The Tauri app wraps the exact same React frontend. Main addition: starts `devagent serve` automatically, no terminal needed.

### Week 1 — Tauri Foundation

**Init:**
```bash
pnpm create tauri-app apps/desktop --template react-ts
```

**`src-tauri/src/devagent.rs` — Process Manager:**

```rust
// State managed by Tauri AppState:
struct DevAgentState {
    child: Mutex<Option<Child>>,
    port: AtomicU16,
}

// Startup sequence:
// 1. Try to find devagent in PATH via `which::which("devagent")`
// 2. If not found, look for bundled sidecar at Resources/devagent
// 3. Pick random available port: bind TcpListener to :0, get assigned port, drop listener
// 4. Spawn: devagent serve --port {port} --no-browser
// 5. Pipe stdout/stderr to ~/.devagent/logs/serve.log
// 6. Poll GET /api/v1/status every 500ms until 200 OK (timeout 30s)
// 7. Store port in AppState, notify frontend via Tauri event
//
// On crash (exit code != 0):
// - Wait 2 seconds
// - Restart (count attempts)
// - After 3 crashes: emit "devagent-crashed" event to frontend, show dialog
//
// On app close (before_window_close hook):
// - Send SIGTERM to child
// - Wait 3s
// - SIGKILL if still alive
```

**`src-tauri/src/tray.rs`:**
```rust
// System tray:
// - Icon: DevAgent logo (monochrome)
// - macOS: menu bar icon
// - Windows: taskbar notification area
// Menu items:
//   "DevAgent" (title, disabled)
//   "Open"
//   "Active Sessions: N" (updated every 5s)
//   ---
//   "Restart Server"
//   "View Logs"
//   ---
//   "Quit"
// macOS dock badge: count of active sessions
```

**`src-tauri/src/commands.rs`:**
```rust
#[tauri::command] async fn get_devagent_port(state: State<DevAgentState>) -> u16
#[tauri::command] fn get_app_version() -> String   // from CARGO_PKG_VERSION
#[tauri::command] fn get_log_path() -> String      // ~/.devagent/logs/serve.log
#[tauri::command] async fn restart_devagent(state: State<DevAgentState>) -> Result<(), String>
#[tauri::command] async fn get_active_session_count(state: State<DevAgentState>) -> u32
```

**Frontend startup flow:**
```typescript
// apps/desktop/src/main.tsx
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'

// 1. Show loading screen: "Starting DevAgent server..."
// 2. Listen for 'devagent-ready' event from Rust
// 3. On ready: get port, configure api-client baseUrl, hide loading screen
// 4. Listen for 'devagent-crashed' event → show error dialog with "Restart" button
```

---

### Week 2 — Desktop-Specific UX

**Deep links (`devagent://`):**
- Registered in `tauri.conf.json` as URL scheme handler
- `devagent://session/sess_a4f2b` → open app, navigate to that session
- Used by: `devagent do "task"` CLI output can print this URL
- Used by: CI output can link to the session that fixed the PR

**Native notifications:**
```rust
// tauri-plugin-notification
// Fired when OrchestratorSession completes:
Notification::new("DevAgent")
    .title("Task complete")
    .body("payments module refactor: 14.2k tokens, $0.09")
    .show()?;
// Click notification → focus app window, navigate to session
```

**Settings window (`Cmd+,` / `Ctrl+,`):**
- Connection: port override, auto-start on system login
- Notifications: completed sessions, failed sessions, budget warnings
- Appearance: Dark / Light / System
- Updates: stable / beta channel

**Window management:**
- Remember size/position: `tauri-plugin-window-state`
- `Cmd+W`: close to tray (don't quit app)
- `Cmd+Q`: quit fully
- Always-on-top toggle: useful for monitoring while coding in another window

---

### Week 3 — Distribution Pipeline

**`.github/workflows/release.yml`:**

```yaml
name: Release
on:
  push:
    tags: ['v*']

jobs:
  build-web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - run: pnpm install && pnpm --filter web build
      - uses: actions/upload-artifact@v4
        with: { name: web-dist, path: apps/web/dist }

  build-desktop:
    needs: build-web
    strategy:
      fail-fast: false
      matrix:
        include:
          - platform: macos-latest
            target: universal-apple-darwin
            artifact: DevAgent_*.dmg
          - platform: windows-latest
            target: x86_64-pc-windows-msvc
            artifact: DevAgent_*_x64.msi
          - platform: ubuntu-22.04
            target: x86_64-unknown-linux-gnu
            artifact: DevAgent_*.AppImage
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with: { name: web-dist, path: apps/desktop/dist }
      - uses: pnpm/action-setup@v3
      - run: pnpm install
      - uses: dtolnay/rust-toolchain@stable
        with: { targets: ${{ matrix.target }} }
      - name: (macOS) Import signing cert
        if: matrix.platform == 'macos-latest'
        # ... import from APPLE_CERTIFICATE secret
      - name: Build
        run: pnpm tauri build --target ${{ matrix.target }}
      - name: Upload to Release
        uses: softprops/action-gh-release@v2
        with:
          files: apps/desktop/src-tauri/target/${{ matrix.target }}/release/bundle/**/${{ matrix.artifact }}
```

**Distribution targets after release.yml runs:**

| Platform | File | Size | Install |
|---|---|---|---|
| macOS universal | `DevAgent_1.0.0_universal.dmg` | ~45MB | Drag to Applications |
| Windows x64 | `DevAgent_1.0.0_x64.msi` | ~50MB | Double-click installer |
| Linux x64 | `DevAgent_1.0.0_amd64.AppImage` | ~55MB | `chmod +x && ./DevAgent*.AppImage` |
| Linux x64 | `DevAgent_1.0.0_amd64.deb` | ~40MB | `dpkg -i DevAgent*.deb` |

**Homebrew tap** (`futuresmart-ai/homebrew-tap`):
```ruby
cask "devagent" do
  version "1.0.0"
  url "https://github.com/futuresmart-ai/devagent-app/releases/download/v#{version}/DevAgent_#{version}_universal.dmg"
  name "DevAgent"
  desc "AI coding agent orchestrator"
  homepage "https://devagent.ai"
  app "DevAgent.app"
end
```

**winget** (PR to `microsoft/winget-pkgs`):
```yaml
PackageIdentifier: FutureSmart.DevAgent
PackageVersion: 1.0.0
PackageUrl: https://devagent.ai
Installers:
  - Architecture: x64
    InstallerUrl: .../DevAgent_1.0.0_x64.msi
    InstallerType: msi
```

**Auto-updater:**
- Tauri's built-in updater: checks GitHub Releases API on startup + every 24h
- Background download → "Update available — quit and restart to apply" notification
- No user action required for download, only for the restart

---

### Week 4 — Python Bundling

**The problem:** User downloads the app, no Python installed. `devagent` CLI isn't in PATH.

**Solution: PyInstaller sidecar bundled inside Tauri app**

Build pipeline step (added to `release.yml`, runs before Tauri build):
```yaml
- name: Build PyInstaller binary
  run: |
    pip install pyinstaller devagent
    pyinstaller --onefile --name devagent \
      --hidden-import devagent.api \
      $(python -c "import devagent; print(devagent.__file__.replace('__init__.py', ''))")/cli.py
    mkdir -p apps/desktop/src-tauri/binaries/
    cp dist/devagent apps/desktop/src-tauri/binaries/devagent-{platform}-{arch}
```

`devagent.rs` lookup order:
1. Check PATH for `devagent` (users with pip-installed version get their own)
2. Fall back to bundled sidecar at `{resourceDir}/devagent`

Final app sizes:
```
DevAgent.app/
  MacOS/DevAgent        ← Tauri Rust binary (1MB)
  MacOS/devagent        ← PyInstaller sidecar (40MB)
  Resources/            ← React frontend (2MB)
Total: ~45MB
```

This means: download, open, done. Zero terminal, zero Python install, zero config.

---

## Phase App-3: IDE Foundations (8–10 weeks)

The orchestrator evolves into an IDE. Same Tauri app, new panels.

### Week 1–2: File System + File Tree

**Layout change:** add a File Explorer sidebar (left of the existing sidebar, or replace it with a tabbed panel).

```
┌── Explorer ─┬── Editor ─────────────────────────────┬── Agent Panel ──┐
│  ▶ src/     │  src/auth.py  ×    tests/test_auth.py  │  ◌ sess_a4f2b  │
│    auth.py  │                                         │                 │
│    models.py│  1  from fastapi import Depends         │  > fix the     │
│  ▶ tests/   │  2  from .models import User            │    JWT expiry  │
│    conftest │  3                                       │    bug         │
│    test_auth│  4  def verify_token(                   │                 │
│  ▶ docs/    │  5    token: str,                       │  ◐ Thinking... │
│  requirements│ 6    db: Session = Depends(get_db)     │  → read_file   │
│  README.md  │  7  ) -> User:                          │    auth.py ✓   │
│             │  8    ...                               │  → write_file  │
└─────────────┴─────────────────────────────────────────┴────────────────┘
```

**File tree implementation:**
- `@tanstack/react-virtual` — renders only visible rows, handles 10,000+ files
- Recursive tree state in Zustand: `{ expanded: Set<string>, selected: string }`
- File icons: parse extension → map to SVG icon from `@vscode/codicons`
- Git status overlay: call `devagent/api` endpoint `GET /api/v1/project/git-status` (new endpoint)
  - Modified files: amber dot on icon
  - Untracked: green dot
  - Deleted: strikethrough
- Right-click context menu (Radix ContextMenu):
  - New File, New Folder, Rename, Delete, Copy Path, Copy Relative Path
  - "Ask DevAgent about this file" → opens agent panel with the file pre-loaded
- Keyboard: arrow keys to navigate, `Enter` to open, `Space` to expand/collapse
- Breadcrumb in top bar updates as you navigate

**Tauri file access:**
- `tauri-plugin-fs`: read, write, watch
- `tauri-plugin-dialog`: native folder picker
- Watch: `fs.watchImmediate(projectPath)` → emit `file-changed` event → update file tree + editor

---

### Week 3–4: Monaco Editor

**Setup:**
```typescript
import { Editor, DiffEditor } from '@monaco-editor/react'
import { loader } from '@monaco-editor/react'

// Self-host Monaco workers (no CDN) for offline use
loader.config({ paths: { vs: '/monaco-editor/min/vs' } })
```

**Editor config:**
```typescript
{
  theme: 'devagent-dark',           // custom theme matching app palette
  fontSize: 14,
  fontFamily: 'Geist Mono, JetBrains Mono, monospace',
  fontLigatures: true,
  minimap: { enabled: false },      // saves horizontal space
  wordWrap: 'on',                   // for markdown files
  formatOnSave: true,
  bracketPairColorization: { enabled: true },
  guides: { bracketPairs: true },
  scrollBeyondLastLine: false,
  renderLineHighlight: 'gutter',
  scrollbar: { verticalScrollbarSize: 6 },
}
```

**Custom `devagent-dark` Monaco theme:**
```typescript
monaco.editor.defineTheme('devagent-dark', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '5a5a6a', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'c792ea' },
    { token: 'string', foreground: 'c3e88d' },
    { token: 'number', foreground: 'f78c6c' },
    // ... full token set
  ],
  colors: {
    'editor.background': '#0A0A0B',
    'editor.foreground': '#E8E8EB',
    'editorLineNumber.foreground': '#3A3A3F',
    'editor.selectionBackground': '#264f78',
    'editorIndentGuide.background': '#1E1E21',
    // ...
  }
})
```

**Tab management:**
- Tab state in Zustand: `{ tabs: Tab[], activeTab: string }`
- `Tab`: `{ path, isDirty, scrollPosition, cursorPosition }`
- `Cmd+S` → save (Tauri `fs.writeFile`), clear `isDirty`
- `Cmd+W` → close tab, activate next
- Dirty indicator: orange dot on tab before filename
- Middle-click → close tab
- Drag to reorder tabs
- Tab overflow: scrollable tab strip with left/right buttons
- Right-click tab: Close, Close Others, Close All, Reveal in Explorer

**Split view:**
- Two editor panels side by side
- `Cmd+\` to split current file
- Drag divider to resize
- Each panel independent (different files, different cursor positions)

---

### Week 5–6: Agent Panel (IDE Context)

The agent panel from the orchestrator becomes a right sidebar in the IDE.

**Panel design:**

```
┌─ Agent ──────────────────────────────────────────┐
│  ◌ Session: fix JWT expiry bug     sess_a4f  [×] │
│                                                   │
│  ┌─ Events ──────────────────────────────────┐  │
│  │  ◐ Reading auth.py...                     │  │
│  │  → read_file "src/auth.py"          ✓ [▸] │  │
│  │  ◐ The issue is on line 47...             │  │
│  │  → write_file "src/auth.py"         ⊙ [▸] │  │  ← pending approval
│  │                                            │  │
│  │  ┌─ Proposed change ─────────────────┐   │  │
│  │  │  [Apply ✓]  [Skip ✗]  [Explain]   │   │  │
│  │  └───────────────────────────────────┘   │  │
│  └────────────────────────────────────────────┘  │
│                                                   │
│  ┌─ Ask DevAgent ────────────────────────────┐  │
│  │  fix the JWT token expiry to 24h...  [⏎]  │  │
│  └───────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

**Inline diff approval:**

When agent calls `write_file` and permission gate is active (Phase 10):
1. `write_file` event arrives via WebSocket with `status: "pending_approval"`
2. Agent panel shows "Proposed change" card with `[Apply] [Skip] [Explain]` buttons
3. The editor automatically opens `DiffEditor` for that file (old left, new right)
4. User clicks `[Apply]` → `POST /api/v1/sessions/{id}/approve` → devagent writes the file
5. Editor tab updates to show the saved file
6. `[Explain]` → sends "explain your reasoning for this change" message to the session

**Context injection:**
- When a file is open in the editor → auto-inject its path into new sessions as context
- Right-click in editor → "Ask DevAgent about this selection" → opens panel with selected text quoted

---

### Week 7–8: CodePrism Graph View

**Access:** Tab in left sidebar (Explorer | Git | Graph) or `Cmd+Shift+G`

**D3.js force simulation setup:**
```typescript
const simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(edges).id(d => d.id).distance(80))
  .force('charge', d3.forceManyBody().strength(-200))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collide', d3.forceCollide(30))

// Renderer: Canvas (not SVG) for 1000+ nodes without lag
// Uses d3-zoom for pan/zoom
```

**Node visual design:**
```
● file module    → circle #111113 border #3B82F6  (blue)
◆ class          → diamond #111113 border #A855F7  (purple)
▶ function       → triangle #111113 border #22C55E (green)
■ variable       → square #111113 border #8A8A8F   (grey)
```

**Edges:**
```
──►  imports/requires     solid line, grey
···► function calls       dashed line, dim
═══► class inheritance    thick solid, purple
```

**Interactions:**
- Hover node → tooltip: full path, symbol count, complexity score, last modified
- Click node → jump to file in Monaco, scroll to that symbol
- Click edge → agent panel shows "A calls B" explanation
- Right-click node → "Analyze impact" → calls `cp_get_impact` tool, shows result in agent panel
- Double-click → expand: show all symbols inside this file as child nodes
- `Cmd+F` → search nodes by name

**Session overlay:**
- When a session is active, nodes that were modified this session get a pulsing ring
- Click the ring → see what the agent did to that file

**Performance:**
- Default: file-level only (no symbol nodes) for repos > 100 files
- Expand a node to show its symbols
- Zoom level adapts detail: zoomed out = just dots; zoomed in = labels visible

---

## Phase App-4: Full IDE (8–10 weeks)

### Integrated Terminal

```typescript
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebglAddon } from '@xterm/addon-webgl'   // GPU rendering

// Tauri shell plugin spawns real shell:
// macOS/Linux: user's $SHELL (bash/zsh/fish)
// Windows: PowerShell 7 > PowerShell 5 > cmd
```

- Multiple terminal tabs
- `Cmd+\`` to toggle panel (same as VS Code)
- ANSI colour + 256-colour + 24-bit colour support
- Persistent history between sessions
- CWD syncs with currently open file's directory
- DevAgent shortcut: `Cmd+D` in terminal → runs `devagent do` with selected text

### Git Integration

**Source Control panel (left sidebar tab):**

```
┌─ Source Control ─────────────────────────────────────┐
│  main  [↑ 2]  [↓ 0]                    [Commit +]   │
│                                                       │
│  ▼ Staged Changes (3)                                │
│    M  src/auth.py                         [−]        │
│    M  tests/test_auth.py                  [−]        │
│    A  src/auth_utils.py                   [−]        │
│                                                       │
│  ▼ Changes (2)                                       │
│    M  src/models.py                       [+]        │
│    ?  src/temp.py                         [+]        │
│                                                       │
│  ┌─ Commit message ───────────────────────────────┐ │
│  │  fix JWT token expiry to 24h          [AI ✨]  │ │
│  └────────────────────────────────────────────────┘ │
│  [Commit]  [Commit & Push]                           │
└───────────────────────────────────────────────────────┘
```

- `[AI ✨]` button → calls devagent with the diff to generate a commit message
- Click modified file → opens DiffEditor in main pane
- Inline blame: hover a line → shows commit hash + author + time
- Branch switcher in status bar (bottom)
- `[↑ 2]` = commits ahead of remote → click → push

### DEVAGENT.md Editor

When DEVAGENT.md is open:
- Toggle between **Edit mode** (raw markdown in Monaco) and **Preview mode** (rendered)
- Preview shows sections: Project Overview, Tech Stack, Architecture, Conventions
- `[Regenerate]` button → calls `POST /api/v1/project/generate-devagent-md` (devagent analyzes codebase and rewrites it)
- Section headers are links: click to jump to that section in the editor

### Command Palette

`Cmd+Shift+P` → fuzzy search overlay:

```
┌─ Command Palette ──────────────────────────────────────┐
│  > ask devagent                                        │
│  ─────────────────────────────────────────────────     │
│  ◐ DevAgent: New Session                              │
│  ◐ DevAgent: Resume Session sess_a4f2b                │
│  ◐ DevAgent: Run /review                              │
│  ◐ DevAgent: Run /explain current file                │
│  📄 Open File...                                      │
│  ⚙ Open Settings                                     │
│  ⌨ Open Keyboard Shortcuts                           │
│  🌿 Git: Create Branch                               │
└────────────────────────────────────────────────────────┘
```

All DevAgent skills appear as commands. All editor actions. All git operations.

### Settings UI

Full settings at `Cmd+,`:

**Models:**
- Ollama URL (default http://localhost:11434)
- Anthropic API key (stored in OS keychain via Tauri `plugin-stronghold`)
- OpenAI API key
- Google API key
- Model router: which model for planning / coding / reviewing / quick

**Agent:**
- Max iterations per session
- Loop detection sensitivity
- Shell command timeout
- Auto-compress threshold

**Security Gate:**
- Enable/disable
- Block patterns (configurable regex list)
- Warn-only vs block mode

**Editor:**
- Font family, font size, line height
- Tab size, indent with spaces/tabs
- Word wrap, minimap, bracket pair colors
- Format on save, format on paste

**Keybindings:**
- Full keybinding editor (searchable, rebindable)
- Import/export as JSON

**Appearance:**
- Dark / Light / System
- Theme: DevAgent Dark, DevAgent Light, High Contrast, Monokai, (import VS Code theme)

---

## CI/CD Pipeline — Full Detail

### `ci.yml`

```yaml
name: CI
on: [push, pull_request]

jobs:
  lint-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - run: pnpm install --frozen-lockfile
      - run: pnpm run lint          # ESLint across all packages
      - run: pnpm run typecheck     # tsc --noEmit across all packages

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - run: pnpm install --frozen-lockfile
      - run: pnpm run test -- --coverage

  build-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - run: pnpm install --frozen-lockfile
      - run: pnpm --filter web build    # ensure production build succeeds

  storybook:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - run: pnpm install --frozen-lockfile
      - run: pnpm --filter @devagent/ui build-storybook
      # optionally: upload to Chromatic for visual diff
```

### `release.yml`

Triggered by `git tag v1.0.0 && git push --tags`:

```yaml
name: Release
on:
  push:
    tags: ['v*']

jobs:
  build-web:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.version.outputs.value }}
    steps:
      - uses: actions/checkout@v4
      - id: version
        run: echo "value=${GITHUB_REF_NAME#v}" >> $GITHUB_OUTPUT
      - uses: pnpm/action-setup@v3
      - run: pnpm install --frozen-lockfile
      - run: pnpm --filter web build
      - uses: actions/upload-artifact@v4
        with: { name: web-dist, path: apps/web/dist }

  build-pyinstaller:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-22.04, windows-latest, macos-latest]
    steps:
      - run: pip install pyinstaller devagent==${{ needs.build-web.outputs.version }}
      - run: pyinstaller --onefile --name devagent devagent_entry.py
      - uses: actions/upload-artifact@v4
        with: { name: devagent-bin-${{ matrix.os }}, path: dist/devagent* }

  build-desktop:
    needs: [build-web, build-pyinstaller]
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: macos-latest
            target: universal-apple-darwin
          - os: windows-latest
            target: x86_64-pc-windows-msvc
          - os: ubuntu-22.04
            target: x86_64-unknown-linux-gnu
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with: { name: web-dist, path: apps/desktop/dist }
      - uses: actions/download-artifact@v4
        with: { name: devagent-bin-${{ matrix.os }}, path: apps/desktop/src-tauri/binaries }
      - uses: pnpm/action-setup@v3
      - run: pnpm install --frozen-lockfile
      - uses: dtolnay/rust-toolchain@stable
        with: { targets: ${{ matrix.target }} }
      - run: pnpm tauri build --target ${{ matrix.target }}
      - uses: softprops/action-gh-release@v2
        with:
          files: apps/desktop/src-tauri/target/${{ matrix.target }}/release/bundle/**

  update-homebrew:
    needs: build-desktop
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { repository: futuresmart-ai/homebrew-tap, token: ${{ secrets.TAP_TOKEN }} }
      - run: |
          VERSION=${GITHUB_REF_NAME#v}
          SHA=$(shasum -a 256 path/to/dmg | awk '{print $1}')
          sed -i "s/version .*/version \"$VERSION\"/" Casks/devagent.rb
          sed -i "s/sha256 .*/sha256 \"$SHA\"/" Casks/devagent.rb
          git commit -am "devagent $VERSION" && git push
```

---

## Parallel Work Strategy — Exact Recommendation

### If working solo (one person):

```
Month 1:  App-1 Weeks 1-2   (repo + API client + shell)
          + devagent backend API (FastAPI routes + WS)     ← same mental model, do together

Month 2:  App-1 Weeks 3-5   (Session Detail + Orchestrate + Metrics + polish)

Month 3:  App-2 Weeks 1-2   (Tauri setup + desktop UX)
          + CLI Phase 10     (Hooks system)                 ← independent, start in background

Month 4:  App-2 Weeks 3-4   (distribution pipeline + Python bundling)
          + CLI Phase 10     (finish) + Phase 11 (Web Tools)

Month 5:  App-3 Weeks 1-4   (file tree + Monaco editor)
          + CLI Phase 12     (DEVAGENT.md + MEMORY.md)      ← IDE displays these

Month 6:  App-3 Weeks 5-8   (agent panel + graph view)
          + CLI Phase 13     (REPL depth / slash commands)

Month 7-9: App-4            (full IDE: terminal, git, settings)
           + CLI Phases 14-16 (effort, thinking, vision)
```

### If you add a frontend developer:

```
Frontend dev → App-1 → App-2 → App-3 → App-4  (continuous)
You (Python) → Phase 10 → 11 → 12 → 13 → 14 → 15 → 16
```

Sync points (30-min call):
- When a new API endpoint is needed: you add it, they consume it
- When CLI Phase 10 (hooks) lands: they add hook event display in the feed
- When CLI Phase 12 (DEVAGENT.md) lands: they add the settings editor

**Key rule: don't block App-1 on any CLI phase.** The orchestrator web app is immediately useful with devagent v0.4.0-dev (phases 0-9). It can show real sessions, real events, real orchestrate runs. Ship App-1 first.

---

## What to Start Right Now

1. Create `devagent-app` repo on GitHub (`futuresmart-ai/devagent-app` or `knight22-21/devagent-app`)
2. `pnpm create vite apps/web --template react-ts` inside it
3. Wire up Tailwind + shadcn/ui with the exact colour palette from the Design Mandate
4. Create `packages/api-client` with the TypeScript types from the API contract
5. Add the FastAPI routes to the Python `devagent` repo (no UI needed yet, just the endpoints)
6. Build the Dashboard page first — it's the simplest and confirms the whole stack works end-to-end
