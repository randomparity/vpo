#!/usr/bin/env python3
"""Documentation-code sync enforcement (V2).

Checks for documentation drift, co-change violations, metadata compliance,
and release-note presence. Designed for use in pre-commit hooks and CI.

Usage::

    python scripts/check_doc_sync.py --check <check> [options]

Checks: schema, index, cochange, metadata, release-note, all

Exit codes (bitmask):
    1  - schema drift
    2  - co-change violation
    4  - index issue
    8  - metadata violation
    16 - release-note violation
    32 - invalid CI skip / unauthorized exemption
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

# =============================================================================
# Exit code constants
# =============================================================================

EXIT_SCHEMA = 1
EXIT_COCHANGE = 2
EXIT_INDEX = 4
EXIT_METADATA = 8
EXIT_RELEASE_NOTE = 16
EXIT_INVALID_CI_SKIP = 32

# =============================================================================
# Configuration (embedded, organized by check)
# =============================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_RULES = {
    # Where to read the canonical schema version from code
    "version_source": "src/vpo/policy/loader.py",
    "version_pattern": r"SCHEMA_VERSION\s*=\s*(\d+)",
    # Directories to scan for schema version references in docs
    "doc_directories": ["docs/"],
    # Files/patterns excluded from schema version checks
    "exclude_files": [
        "docs/usage/v11-migration.md",
        "docs/decisions/*",
    ],
    # YAML code block pattern for schema_version: N
    "yaml_version_re": r"schema_version:\s*(\d+)",
    # Prose version reference pattern (e.g., "V12", "V13")
    "prose_version_re": r"\bV(\d+)\b",
    # Minimum version to flag in prose (ignore V1, V2, etc.)
    "prose_min_version": 10,
    # Marker to scope prose version checks
    "marker": "<!-- DOCSYNC:SCHEMA_VERSION -->",
}

INDEX_RULES = {
    # Index file to check
    "index_file": "docs/INDEX.md",
    # Directories whose .md files must be indexed
    "tracked_directories": [
        "docs/usage/",
        "docs/design/",
        "docs/overview/",
        "docs/decisions/",
        "docs/internals/",
    ],
    # Marker to exempt a file from index checks
    "exempt_marker": "<!-- DOCSYNC:INDEX_EXEMPT -->",
    # Files always excluded from index checks (relative to repo root)
    "exclude_files": [
        "docs/design/DESIGN_INDEX.md",
    ],
}

COCHANGE_RULES = [
    {
        "code_globs": [
            "src/vpo/policy/types.py",
            "src/vpo/policy/types/*.py",
            "src/vpo/policy/loader.py",
            "src/vpo/policy/pydantic_models.py",
            "src/vpo/policy/pydantic_models/*.py",
        ],
        "required_docs": ["docs/usage/policies.md"],
        "category": "policy",
        "reason": "Policy schema/types/loader changes affect policy authoring docs",
    },
    {
        "code_globs": [
            "src/vpo/policy/conditions.py",
            "src/vpo/workflow/skip_conditions.py",
        ],
        "required_docs": ["docs/usage/conditional-policies.md"],
        "category": "policy",
        "reason": "Conditional policy behavior is user-facing",
    },
    {
        "code_globs": [
            "src/vpo/executor/transcode.py",
            "src/vpo/policy/transcode.py",
        ],
        "required_docs": ["docs/usage/transcode-policy.md"],
        "category": "transcode",
        "reason": "Transcode behavior/policy semantics are user-facing",
    },
    {
        "code_globs": ["src/vpo/cli/*.py"],
        "required_docs": ["docs/usage/cli-usage.md"],
        "category": "cli",
        "reason": "CLI commands/options/help are user-facing",
    },
    {
        "code_globs": ["src/vpo/plugin/*.py"],
        "required_docs": ["docs/plugins.md"],
        "category": "plugin",
        "reason": "Plugin behavior/configuration is user-facing",
    },
    {
        "code_globs": ["src/vpo/server/ui/routes.py"],
        "required_docs": ["docs/api-webui.md"],
        "category": "ui",
        "reason": "UI/API route behavior is user-facing",
    },
    {
        "code_globs": ["src/vpo/db/schema.py"],
        "required_docs": ["docs/design/design-database.md"],
        "category": "db",
        "reason": "Database schema changes may need operator docs updates",
    },
]

# Paths excluded from co-change analysis
COCHANGE_EXCLUDES = [
    "tests/**",
    "**/conftest.py",
    "scripts/**",
]

METADATA_RULES = {
    "required_trailer": "Docs-Impact",
    "valid_values": ["required", "none"],
    "reason_trailer": "Docs-Reason",
}

EXEMPTION_RULES = {
    "env_var": "DOC_SYNC_EXEMPTION",
    "valid_labels": ["docs-impact-exempt"],
}


# =============================================================================
# Git helpers
# =============================================================================


def get_changed_files(*, staged: bool = False, base: str | None = None) -> list[str]:
    """Return list of changed file paths relative to repo root."""
    if staged:
        cmd = ["git", "diff", "--cached", "--name-only"]
    elif base:
        cmd = ["git", "diff", "--name-only", f"{base}...HEAD"]
    else:
        # Default: diff against origin/main
        cmd = ["git", "diff", "--name-only", "origin/main...HEAD"]

    try:
        result = subprocess.run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if result.returncode != 0:
            return []
        return [f for f in result.stdout.strip().splitlines() if f]
    except (OSError, subprocess.SubprocessError):
        return []


# =============================================================================
# Check A: Schema version drift
# =============================================================================


def get_code_schema_version() -> int | None:
    """Read the canonical schema version from source code."""
    source_path = REPO_ROOT / SCHEMA_RULES["version_source"]
    if not source_path.exists():
        return None
    text = source_path.read_text()
    m = re.search(SCHEMA_RULES["version_pattern"], text)
    return int(m.group(1)) if m else None


def _is_excluded_from_schema(filepath: str) -> bool:
    """Check if a file is excluded from schema version checks."""
    for exc in SCHEMA_RULES["exclude_files"]:
        if fnmatch.fnmatch(filepath, exc) or filepath == exc:
            return True
    return False


def check_schema() -> list[dict]:
    """Check for schema version drift in docs."""
    failures = []
    code_version = get_code_schema_version()
    if code_version is None:
        failures.append(
            {
                "check": "schema",
                "severity": "error",
                "code": "SCHEMA_VERSION_NOT_FOUND",
                "message": (
                    f"Cannot read schema version from {SCHEMA_RULES['version_source']}"
                ),
            }
        )
        return failures

    yaml_re = re.compile(SCHEMA_RULES["yaml_version_re"])
    prose_re = re.compile(SCHEMA_RULES["prose_version_re"])
    min_prose = SCHEMA_RULES["prose_min_version"]

    for doc_dir in SCHEMA_RULES["doc_directories"]:
        full_dir = REPO_ROOT / doc_dir
        if not full_dir.is_dir():
            continue
        for md_file in full_dir.rglob("*.md"):
            rel_path = str(md_file.relative_to(REPO_ROOT))
            if _is_excluded_from_schema(rel_path):
                continue

            try:
                lines = md_file.read_text().splitlines()
            except OSError:
                continue

            in_code_block = False
            for line_num, line in enumerate(lines, 1):
                # Track fenced code blocks
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_code_block = not in_code_block

                if in_code_block:
                    # YAML schema_version in code blocks
                    m = yaml_re.search(line)
                    if m:
                        found_ver = int(m.group(1))
                        if found_ver != code_version:
                            failures.append(
                                {
                                    "check": "schema",
                                    "severity": "error",
                                    "code": "SCHEMA_YAML_DRIFT",
                                    "message": (
                                        f"{rel_path}:{line_num}: "
                                        f"schema_version: {found_ver} "
                                        f"(expected {code_version})"
                                    ),
                                    "file": rel_path,
                                    "line": line_num,
                                    "found_version": found_ver,
                                    "expected_version": code_version,
                                }
                            )
                else:
                    # Prose version references outside code blocks
                    for pm in prose_re.finditer(line):
                        found_ver = int(pm.group(1))
                        if found_ver >= min_prose and found_ver != code_version:
                            # Allow V11 references in migration context
                            if found_ver == 11 and "migration" in rel_path.lower():
                                continue
                            # Allow "V10 and earlier" type references
                            if found_ver < code_version - 1:
                                continue
                            failures.append(
                                {
                                    "check": "schema",
                                    "severity": "error",
                                    "code": "SCHEMA_PROSE_DRIFT",
                                    "message": (
                                        f"{rel_path}:{line_num}: "
                                        f"prose reference V{found_ver} "
                                        f"(current is V{code_version})"
                                    ),
                                    "file": rel_path,
                                    "line": line_num,
                                    "found_version": found_ver,
                                    "expected_version": code_version,
                                }
                            )

    return failures


# =============================================================================
# Check B: Index completeness
# =============================================================================


def _is_excluded_from_index(filepath: str) -> bool:
    """Check if a file is excluded from index checks."""
    for exc in INDEX_RULES["exclude_files"]:
        if fnmatch.fnmatch(filepath, exc) or filepath == exc:
            return True
    return False


def check_index() -> list[dict]:
    """Check that all tracked docs are referenced in INDEX.md."""
    failures = []
    index_path = REPO_ROOT / INDEX_RULES["index_file"]
    if not index_path.exists():
        failures.append(
            {
                "check": "index",
                "severity": "error",
                "code": "INDEX_FILE_MISSING",
                "message": f"{INDEX_RULES['index_file']} not found",
            }
        )
        return failures

    index_text = index_path.read_text()
    exempt_marker = INDEX_RULES["exempt_marker"]

    for tracked_dir in INDEX_RULES["tracked_directories"]:
        full_dir = REPO_ROOT / tracked_dir
        if not full_dir.is_dir():
            continue
        for md_file in full_dir.rglob("*.md"):
            rel_path = str(md_file.relative_to(REPO_ROOT))
            if _is_excluded_from_index(rel_path):
                continue

            # Check for exempt marker in the file itself
            try:
                file_text = md_file.read_text()
            except OSError:
                continue
            if exempt_marker in file_text:
                continue

            # Check if file is referenced in INDEX.md
            # Match both relative-to-docs paths and full paths
            rel_to_docs = str(md_file.relative_to(REPO_ROOT / "docs"))
            if rel_to_docs not in index_text and rel_path not in index_text:
                failures.append(
                    {
                        "check": "index",
                        "severity": "error",
                        "code": "INDEX_MISSING_ENTRY",
                        "message": (
                            f"{rel_path} is not referenced "
                            f"in {INDEX_RULES['index_file']}"
                        ),
                        "file": rel_path,
                    }
                )

    return failures


# =============================================================================
# Check C: Co-change enforcement
# =============================================================================


def _is_cochange_excluded(filepath: str) -> bool:
    """Check if a file should be excluded from co-change analysis."""
    for pattern in COCHANGE_EXCLUDES:
        if fnmatch.fnmatch(filepath, pattern):
            return True
    return False


def _match_cochange_rules(
    changed_files: list[str],
) -> list[dict]:
    """Match changed files against co-change rules. Returns list of violations."""
    changed_set = set(changed_files)
    # Filter out excluded files
    code_files = [f for f in changed_files if not _is_cochange_excluded(f)]

    violations = []
    for rule in COCHANGE_RULES:
        matched_code = []
        for code_file in code_files:
            for glob_pattern in rule["code_globs"]:
                if fnmatch.fnmatch(code_file, glob_pattern):
                    matched_code.append(code_file)
                    break

        if not matched_code:
            continue

        # Check if required docs are in changed set
        missing_docs = [d for d in rule["required_docs"] if d not in changed_set]
        if missing_docs:
            violations.append(
                {
                    "check": "cochange",
                    "severity": "error",
                    "code": "COCHANGE_MISSING_DOC",
                    "message": (
                        f"Changed {rule['category']} code requires docs update: "
                        f"{', '.join(missing_docs)}"
                    ),
                    "changed_files": matched_code,
                    "required_docs": missing_docs,
                    "changed_docs": [
                        d for d in rule["required_docs"] if d in changed_set
                    ],
                    "category": rule["category"],
                    "reason": rule["reason"],
                }
            )

    return violations


def check_cochange(*, staged: bool = False, base: str | None = None) -> list[dict]:
    """Check co-change requirements between code and docs."""
    changed_files = get_changed_files(staged=staged, base=base)
    if not changed_files:
        return []
    return _match_cochange_rules(changed_files)


# =============================================================================
# Check D: Metadata enforcement
# =============================================================================


def parse_metadata_from_text(text: str) -> dict[str, str | None]:
    """Parse Docs-Impact and Docs-Reason trailers from text."""
    result: dict[str, str | None] = {
        "docs_impact": None,
        "docs_reason": None,
    }
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^Docs-Impact:\s*(.+)$", line, re.IGNORECASE)
        if m:
            result["docs_impact"] = m.group(1).strip().lower()
        m = re.match(r"^Docs-Reason:\s*(.+)$", line, re.IGNORECASE)
        if m:
            result["docs_reason"] = m.group(1).strip()
    return result


def check_metadata(
    *,
    commit_msg_file: str | None = None,
    pr_body_file: str | None = None,
    staged: bool = False,
    base: str | None = None,
    ci: bool = False,
) -> list[dict]:
    """Check Docs-Impact / Docs-Reason metadata presence and validity."""
    failures = []

    # Read metadata from available sources
    metadata: dict[str, str | None] = {"docs_impact": None, "docs_reason": None}

    sources_checked = []
    if commit_msg_file:
        path = Path(commit_msg_file)
        if path.exists():
            text = path.read_text()
            metadata = parse_metadata_from_text(text)
            sources_checked.append("commit-msg")

    if pr_body_file and metadata["docs_impact"] is None:
        path = Path(pr_body_file)
        if path.exists():
            text = path.read_text()
            metadata = parse_metadata_from_text(text)
            sources_checked.append("pr-body")

    if not sources_checked:
        # No source to check — skip silently unless in CI
        if ci:
            failures.append(
                {
                    "check": "metadata",
                    "severity": "error",
                    "code": "NO_METADATA_SOURCE",
                    "message": (
                        "No commit message or PR body provided for metadata check"
                    ),
                }
            )
        return failures

    # Validate Docs-Impact presence
    if metadata["docs_impact"] is None:
        failures.append(
            {
                "check": "metadata",
                "severity": "error",
                "code": "MISSING_DOCS_IMPACT",
                "message": "Missing Docs-Impact trailer (expected: required|none)",
            }
        )
        return failures

    # Validate Docs-Impact value
    if metadata["docs_impact"] not in METADATA_RULES["valid_values"]:
        failures.append(
            {
                "check": "metadata",
                "severity": "error",
                "code": "INVALID_DOCS_IMPACT",
                "message": (
                    f"Invalid Docs-Impact value: '{metadata['docs_impact']}' "
                    f"(expected: {', '.join(METADATA_RULES['valid_values'])})"
                ),
            }
        )
        return failures

    # If none, require Docs-Reason
    if metadata["docs_impact"] == "none" and not metadata["docs_reason"]:
        failures.append(
            {
                "check": "metadata",
                "severity": "error",
                "code": "MISSING_DOCS_REASON",
                "message": "Docs-Impact: none requires a Docs-Reason trailer",
            }
        )

    # CI cross-check: if cochange says docs required but metadata says none
    if ci and metadata["docs_impact"] == "none":
        cochange_violations = check_cochange(staged=staged, base=base)
        if cochange_violations:
            exemption = os.environ.get(EXEMPTION_RULES["env_var"], "")
            if exemption not in EXEMPTION_RULES["valid_labels"]:
                failures.append(
                    {
                        "check": "metadata",
                        "severity": "error",
                        "code": "METADATA_COCHANGE_CONFLICT",
                        "message": (
                            "Docs-Impact: none but co-change rules "
                            "require docs updates. Add docs or apply "
                            "'docs-impact-exempt' label."
                        ),
                        "cochange_categories": list(
                            {v["category"] for v in cochange_violations}
                        ),
                    }
                )

    return failures


# =============================================================================
# Check E: Release-note enforcement
# =============================================================================


def check_release_note(*, staged: bool = False, base: str | None = None) -> list[dict]:
    """Check that a release-note fragment exists for user-visible changes."""
    failures = []
    changed_files = get_changed_files(staged=staged, base=base)
    if not changed_files:
        return []

    # Check if any cochange rules fire
    cochange_violations = _match_cochange_rules(changed_files)
    if not cochange_violations:
        return []

    # Check for changelog fragment
    has_fragment = any(
        f.startswith("changelog.d/") and f.endswith(".md") for f in changed_files
    )
    if not has_fragment:
        categories = list({v["category"] for v in cochange_violations})
        failures.append(
            {
                "check": "release-note",
                "severity": "error",
                "code": "MISSING_RELEASE_NOTE",
                "message": (
                    f"User-visible changes ({', '.join(categories)}) require a "
                    "release note fragment in changelog.d/*.md"
                ),
                "categories": categories,
            }
        )

    return failures


# =============================================================================
# Output formatters
# =============================================================================


def format_text(
    failures: list[dict],
    warnings: list[dict],
    checks_run: list[str],
    exemption_active: bool,
    exemption_source: str | None,
) -> str:
    """Format results as human-readable text."""
    lines = []
    if not failures and not warnings:
        lines.append(f"Doc sync checks passed: {', '.join(checks_run)}")
        return "\n".join(lines)

    for f in failures:
        prefix = f"ERROR [{f['check']}]"
        lines.append(f"{prefix} {f['message']}")

    for w in warnings:
        prefix = f"WARNING [{w['check']}]"
        lines.append(f"{prefix} {w['message']}")

    if exemption_active:
        lines.append(f"NOTE: Exemption active via {exemption_source}")

    n_errors = len(failures)
    n_warnings = len(warnings)
    lines.append(f"\n{n_errors} error(s), {n_warnings} warning(s)")
    return "\n".join(lines)


def format_json(
    failures: list[dict],
    warnings: list[dict],
    checks_run: list[str],
    exemption_active: bool,
    exemption_source: str | None,
) -> str:
    """Format results as machine-readable JSON."""
    output = {
        "ok": len(failures) == 0,
        "checks_run": checks_run,
        "failures": failures,
        "warnings": warnings,
        "exemptions": {
            "active": exemption_active,
            "source": exemption_source,
        },
    }
    return json.dumps(output, indent=2)


def format_github(
    failures: list[dict],
    warnings: list[dict],
    checks_run: list[str],
    exemption_active: bool,
    exemption_source: str | None,
) -> str:
    """Format results as GitHub Actions annotations."""
    lines = []
    for f in failures:
        file_part = f"file={f['file']}" if "file" in f else ""
        line_part = f",line={f['line']}" if "line" in f else ""
        loc = f" {file_part}{line_part}" if file_part else ""
        lines.append(f"::error{loc}::[{f['check']}] {f['message']}")

    for w in warnings:
        file_part = f"file={w['file']}" if "file" in w else ""
        line_part = f",line={w['line']}" if "line" in w else ""
        loc = f" {file_part}{line_part}" if file_part else ""
        lines.append(f"::warning{loc}::[{w['check']}] {w['message']}")

    if exemption_active:
        lines.append(f"::notice::Doc-sync exemption active via {exemption_source}")

    if not failures and not warnings:
        lines.append(f"::notice::Doc sync checks passed: {', '.join(checks_run)}")

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================


def compute_exit_code(failures: list[dict]) -> int:
    """Compute bitmask exit code from failures."""
    code = 0
    check_to_bit = {
        "schema": EXIT_SCHEMA,
        "cochange": EXIT_COCHANGE,
        "index": EXIT_INDEX,
        "metadata": EXIT_METADATA,
        "release-note": EXIT_RELEASE_NOTE,
        "ci-skip": EXIT_INVALID_CI_SKIP,
    }
    for f in failures:
        check = f.get("check", "")
        if check in check_to_bit:
            code |= check_to_bit[check]
        elif f.get("code") == "INVALID_CI_SKIP":
            code |= EXIT_INVALID_CI_SKIP
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Documentation-code sync enforcement (V2)"
    )
    parser.add_argument(
        "--check",
        required=True,
        help="Check to run: schema|index|cochange|metadata|release-note|all",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check staged files (for pre-commit hooks)",
    )
    parser.add_argument(
        "--base",
        default=None,
        help="Base branch/ref for diff comparison (e.g., origin/main)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json", "github"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Treat errors as warnings (for WIP development)",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: rejects DOC_SYNC_SKIP, enforces hard fail",
    )
    parser.add_argument(
        "--pr-body-file",
        default=None,
        help="Path to file containing PR body text",
    )
    parser.add_argument(
        "--commit-msg-file",
        default=None,
        nargs="?",
        const=".git/COMMIT_EDITMSG",
        help=("Path to commit message file (default: .git/COMMIT_EDITMSG)"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Handle DOC_SYNC_SKIP
    if os.environ.get("DOC_SYNC_SKIP", "") == "1":
        if args.ci:
            # CI mode: DOC_SYNC_SKIP is not allowed
            failure = {
                "check": "ci-skip",
                "severity": "error",
                "code": "INVALID_CI_SKIP",
                "message": (
                    "DOC_SYNC_SKIP=1 is not allowed in CI. "
                    "Use the 'docs-impact-exempt' PR label for auditable exemptions."
                ),
            }
            formatter = {
                "text": format_text,
                "json": format_json,
                "github": format_github,
            }[args.output_format]
            print(formatter([failure], [], [args.check], False, None))
            return EXIT_INVALID_CI_SKIP
        else:
            # Local skip
            print("DOC_SYNC_SKIP=1: skipping doc-sync checks")
            return 0

    # Determine which checks to run
    all_checks = ["schema", "index", "cochange", "metadata", "release-note"]
    if args.check == "all":
        checks_to_run = all_checks
    else:
        checks_to_run = [c.strip() for c in args.check.split(",")]
        for c in checks_to_run:
            if c not in all_checks:
                print(f"Unknown check: {c}", file=sys.stderr)
                return 1

    # Check exemption status
    exemption_env = os.environ.get(EXEMPTION_RULES["env_var"], "")
    exemption_active = exemption_env in EXEMPTION_RULES["valid_labels"]
    exemption_source = exemption_env if exemption_active else None

    # Run checks
    failures: list[dict] = []
    warnings: list[dict] = []

    if "schema" in checks_to_run:
        failures.extend(check_schema())

    if "index" in checks_to_run:
        failures.extend(check_index())

    if "cochange" in checks_to_run:
        results = check_cochange(staged=args.staged, base=args.base)
        if exemption_active:
            # Downgrade to warnings under exemption
            for r in results:
                r["severity"] = "warning"
            warnings.extend(results)
        else:
            failures.extend(results)

    if "metadata" in checks_to_run:
        results = check_metadata(
            commit_msg_file=args.commit_msg_file,
            pr_body_file=args.pr_body_file,
            staged=args.staged,
            base=args.base,
            ci=args.ci,
        )
        if exemption_active:
            # Downgrade metadata failures under exemption (except missing source)
            for r in results:
                if r.get("code") != "NO_METADATA_SOURCE":
                    r["severity"] = "warning"
                    warnings.append(r)
                else:
                    failures.append(r)
        else:
            failures.extend(results)

    if "release-note" in checks_to_run:
        results = check_release_note(staged=args.staged, base=args.base)
        failures.extend(results)

    # Handle --warn-only: move all failures to warnings
    if args.warn_only:
        for f in failures:
            f["severity"] = "warning"
        warnings.extend(failures)
        failures = []

    # Format output
    formatter = {
        "text": format_text,
        "json": format_json,
        "github": format_github,
    }[args.output_format]

    output = formatter(
        failures, warnings, checks_to_run, exemption_active, exemption_source
    )
    if output:
        print(output)

    return compute_exit_code(failures)


if __name__ == "__main__":
    sys.exit(main())
