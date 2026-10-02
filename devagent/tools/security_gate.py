"""Security Gate — Phase 3 full implementation.

Every file write goes through three checks:
  1. Impact Scope Estimator  — cp_get_impact on the file's public API
  2. Security diff scan      — scan_diff (BLOCK/WARN/PASS)
  3. CVE check               — triggered when writing requirements/pyproject files

Confirmation behaviour:
  - BLOCK → always rejected, error returned to LLM
  - WARN  → confirm_fn() called; if None or returns True, write proceeds with warning note
  - PASS  → write proceeds silently

The security log (a plain list) is passed in at registry build time so the
CLI can display a summary at session end.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from devagent.codeprism.client import CodePrismClient

# The gate resolves the same path the write tools do, through the same rule:
# a second copy of a containment test is a copy that can disagree with the one
# that actually performs the write.
from devagent.tools.file_tools import _safe_resolve

# Files that trigger CVE dependency scanning
_DEP_FILES = re.compile(
    r"(requirements.*\.txt|setup\.py|setup\.cfg|pyproject\.toml"
    r"|package\.json|Pipfile|Pipfile\.lock|poetry\.lock)$",
    re.IGNORECASE,
)


def _read_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _impact_note(client: CodePrismClient, rel_path: str) -> str:
    """Run impact on the first public symbol; return a warning string or ''."""
    summary = client.get_module_summary(rel_path)
    if "error" in summary:
        return ""
    public_api = summary.get("public_api", [])
    if not public_api:
        return ""
    symbol_name = public_api[0]["name"]
    impact = client.get_impact(rel_path, symbol_name)
    if "error" in impact:
        return ""
    sev = impact.get("severity", "LOW")
    if sev not in ("HIGH", "CRITICAL"):
        return ""
    surface = impact.get("estimated_change_surface", 0)
    pub = " (PUBLIC API)" if impact.get("public_api_affected") else ""
    direct = [s["name"] for s in impact.get("direct_dependents", [])[:4]]
    tests = impact.get("affected_test_files", [])
    return (
        f"\n[impact] {sev}{pub}: editing {rel_path} affects {surface} dependent(s). "
        f"Direct: {', '.join(direct) or 'none'}. "
        f"Tests to re-run: {', '.join(tests[:3]) or 'none'}."
    )


def _cve_note(client: CodePrismClient, rel_path: str, content: str) -> str:
    """Run CVE check when writing a dependency file; return warning or ''."""
    if not _DEP_FILES.search(rel_path):
        return ""
    try:
        from codeprism.security import check_requirements_cve
        result = check_requirements_cve(content)
        if not result or not getattr(result, "vulnerable", None):
            return ""
        vuln = result.vulnerable[:5]
        names = ", ".join(getattr(v, "package", str(v)) for v in vuln)
        return (
            f"\n[cve_warn] {len(result.vulnerable)} vulnerable package(s) detected: {names}. "
            "Check https://osv.dev/ for details before shipping."
        )
    except Exception:
        return ""


def wrap_write_with_security(
    original_handler: Callable[[dict], str],
    client: CodePrismClient,
    project_root: str,
    operation: str,                              # "write" | "edit"
    security_log: list | None = None,           # caller-owned list, appended in place
    confirm_fn: Callable[[str], bool] | None = None,  # None = auto-allow WARN
    extra_dirs: list[str] | None = None,        # the same dirs the write tools were given
) -> Callable[[dict], str]:
    """Return a new handler that runs security checks before calling the original.

    extra_dirs: directories the underlying write tool may write to outside
                project_root. Pass the same list the registry received, or the
                gate would refuse paths the tool itself allows.
    """

    log = security_log if security_log is not None else []
    extra_roots = [Path(d).resolve() for d in (extra_dirs or [])]

    def secured_handler(args: dict) -> str:
        rel_path = args.get("path", "")
        # ── 0. Containment ───────────────────────────────────────────
        # Every check below runs against *this* path, so an escaping path has
        # to be refused here rather than scanned. `Path(root) / "../../etc/passwd"`
        # does not raise, it resolves outside the root: the impact estimate and
        # the CVE scan would then describe a file outside the project, and a
        # BLOCK/WARN verdict would be about the wrong file.
        try:
            abs_path = _safe_resolve(project_root, rel_path, extra_roots)
        except ValueError as exc:
            log.append({
                "action": "BLOCK",
                "file": rel_path,
                "reasons": str(exc),
            })
            return (
                f"[security_block] Write to {rel_path} blocked by security gate.\n"
                f"Issues: {exc}\n"
                "Fix the security issues and try again."
            )
        original_content = _read_safe(abs_path)

        # ── Reconstruct proposed content for diff ────────────────────
        if operation == "write":
            proposed_content = args.get("content", "")
        else:
            old_str = args.get("old_str", "")
            new_str = args.get("new_str", "")
            proposed_content = (
                original_content.replace(old_str, new_str, 1)
                if old_str else original_content
            )

        # ── 1. Impact Scope Estimator ────────────────────────────────
        impact_note = ""
        if client.is_indexed and abs_path.exists():
            impact_note = _impact_note(client, rel_path)

        # ── 2. Security diff scan ────────────────────────────────────
        security_note = ""
        if client.is_indexed and proposed_content:
            scan = client.scan_diff(original_content, proposed_content, rel_path)
            status = scan.get("status", "PASS")
            new_issues = scan.get("new_issues", [])

            if status == "BLOCK":
                reasons = "; ".join(
                    f"{i.get('severity','ISSUE')}: {i.get('description','')}"
                    for i in new_issues[:3]
                )
                log.append({
                    "action": "BLOCK",
                    "file": rel_path,
                    "reasons": reasons,
                })
                return (
                    f"[security_block] Write to {rel_path} blocked by security gate.\n"
                    f"Issues: {reasons}\n"
                    "Fix the security issues and try again."
                )

            if status == "WARN" and new_issues:
                reasons = "; ".join(
                    f"{i.get('severity','WARN')}: {i.get('description','')}"
                    for i in new_issues[:3]
                )
                warn_msg = (
                    f"[security_warn] Writing {rel_path} introduces potential issues:\n"
                    f"  {reasons}\n"
                    "Proceed? [y/N]: "
                )
                if confirm_fn is not None and not confirm_fn(warn_msg):
                    log.append({
                        "action": "REJECTED_BY_USER",
                        "file": rel_path,
                        "reasons": reasons,
                    })
                    return (
                        f"[security_rejected] Write to {rel_path} cancelled by user.\n"
                        f"Reason: {reasons}"
                    )
                log.append({
                    "action": "WARN",
                    "file": rel_path,
                    "reasons": reasons,
                    "confirmed": confirm_fn is not None,
                })
                security_note = f"\n[security_warn] {reasons}"

        # ── 3. CVE check for dependency files ────────────────────────
        cve_note = ""
        if client.is_indexed and proposed_content:
            cve_note = _cve_note(client, rel_path, proposed_content)
            if cve_note:
                log.append({"action": "CVE_WARN", "file": rel_path, "note": cve_note.strip()})

        # ── 4. Perform the actual write ───────────────────────────────
        result = original_handler(args)

        # ── 5. Record write in CodePrism session ──────────────────────
        if client.is_indexed and not result.startswith("[error]"):
            new_content = _read_safe(abs_path)
            client.record_write(rel_path, original_content, new_content)
            log.append({"action": "WRITE", "file": rel_path})

        return result + impact_note + security_note + cve_note

    return secured_handler


# ---------------------------------------------------------------------------
# Security log formatter (for /security command and session-end summary)
# ---------------------------------------------------------------------------

def format_security_report(log: list[dict]) -> str:
    if not log:
        return "No security events this session."

    blocks   = [e for e in log if e.get("action") == "BLOCK"]
    warns    = [e for e in log if e.get("action") == "WARN"]
    rejected = [e for e in log if e.get("action") == "REJECTED_BY_USER"]
    cves     = [e for e in log if e.get("action") == "CVE_WARN"]
    writes   = [e for e in log if e.get("action") == "WRITE"]

    lines = ["Security Gate — Session Report", "=" * 40]
    lines.append(f"  Writes recorded  : {len(writes)}")
    lines.append(f"  Blocked (BLOCK)  : {len(blocks)}")
    lines.append(f"  Warnings (WARN)  : {len(warns)}")
    lines.append(f"  Rejected by user : {len(rejected)}")
    lines.append(f"  CVE warnings     : {len(cves)}")

    if blocks:
        lines.append("\nBlocked writes:")
        for e in blocks:
            lines.append(f"  {e['file']}: {e.get('reasons', '')}")

    if warns:
        lines.append("\nWarnings (proceeded):")
        for e in warns:
            lines.append(f"  {e['file']}: {e.get('reasons', '')}")

    if cves:
        lines.append("\nCVE warnings:")
        for e in cves:
            lines.append(f"  {e['file']}: {e.get('note', '')}")

    return "\n".join(lines)
