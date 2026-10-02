# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.5.x (latest) | ✅ |
| 1.3.x | ✅ security fixes only |
| < 1.3 | ❌ |

Only the latest release and the previous minor version receive security fixes. Upgrade to the latest version before reporting a bug.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email **krishnatyagi2526@gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce (a minimal script or command sequence is ideal)
- The version of DevAgent you are running (`devagent --version`)
- Whether you have a proposed fix

You will receive an acknowledgement within **48 hours** and a resolution timeline within **7 days**. If a fix requires coordinated disclosure with a dependency maintainer, we will keep you updated.

We do not currently run a bug bounty programme, but we will credit you in the release notes and CHANGELOG unless you request otherwise.

## Scope

The following are in scope:

- **Security gate bypass** — a crafted tool argument that causes a write outside the project root to succeed
- **Path traversal** — `../` or absolute paths that escape `project_root` or declared `extra_dirs`
- **Secrets exposure** — the agent reading or exfiltrating credential files (`~/.ssh`, `.env`, `*.pem`, etc.)
- **Hook injection** — a crafted repo config that causes arbitrary code execution via DevAgent's hook system
- **Prompt injection** — tool output that hijacks the agent's behaviour in a way that causes data loss or unauthorised writes
- **Dependency CVE** — a known vulnerability in a pinned dependency that affects DevAgent users

The following are **out of scope**:

- Vulnerabilities that require the attacker to already have write access to the project root
- Issues in third-party LLM providers (Anthropic, OpenAI, Ollama, Gemini, Groq) — report those upstream
- Denial-of-service attacks that require local access to the machine running DevAgent
- Social engineering of maintainers

## Security design notes

DevAgent's primary security boundary is the **Security Gate** (`devagent/tools/security_gate.py`). Every write tool call passes through it before execution:

1. **Path containment** — the resolved write path must be inside `project_root` (or explicitly declared `extra_dirs`). The check uses `Path.is_relative_to`, not a string prefix, to prevent sibling-directory bypasses.
2. **Secrets scan** — the proposed file content is scanned for high-entropy strings, API key patterns, and known secret formats before writing.
3. **CVE scan** — changes to dependency files (`requirements*.txt`, `pyproject.toml`, etc.) trigger a dependency vulnerability check via CodePrism.
4. **Impact analysis** — CodePrism's impact graph is queried to surface high-blast-radius changes for human review.

The Security Gate is active by default and can only be disabled explicitly via `security.gate_enabled = false` in `devagent.toml`. Disabling it is not recommended in production.

## Disclosure timeline

| Day | Action |
|---|---|
| 0 | Report received; acknowledgement sent |
| 1–7 | Root cause confirmed; severity assessed |
| 7–30 | Fix developed and reviewed |
| 30 | Coordinated public disclosure; patched release published |

For critical vulnerabilities (CVSS ≥ 9.0) we target a fix within 7 days.
