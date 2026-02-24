"""Tests for scripts/check_doc_sync.py — V2 doc-sync enforcement."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import check_doc_sync
import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _set_repo_root(tmp_path, monkeypatch):
    """Override REPO_ROOT to use a temp directory for isolation."""
    monkeypatch.setattr(check_doc_sync, "REPO_ROOT", tmp_path)
    return tmp_path


@pytest.fixture()
def repo(tmp_path):
    """Create a minimal repo structure in tmp_path."""
    return tmp_path


def _write(repo: Path, relpath: str, content: str) -> Path:
    """Helper to write a file relative to repo root."""
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content))
    return p


# =============================================================================
# Check A: Schema version drift
# =============================================================================


class TestSchemaCheck:
    def test_detects_yaml_drift(self, repo):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            """\
            # Policies

            ```yaml
            schema_version: 12
            phases: []
            ```
            """,
        )

        failures = check_doc_sync.check_schema()
        assert len(failures) == 1
        assert failures[0]["code"] == "SCHEMA_YAML_DRIFT"
        assert failures[0]["found_version"] == 12
        assert failures[0]["expected_version"] == 13

    def test_passes_when_versions_match(self, repo):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            """\
            # Policies

            ```yaml
            schema_version: 13
            phases: []
            ```
            """,
        )

        failures = check_doc_sync.check_schema()
        assert failures == []

    def test_detects_prose_drift(self, repo):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            "VPO uses the V12 schema for policies.\n",
        )

        failures = check_doc_sync.check_schema()
        assert len(failures) == 1
        assert failures[0]["code"] == "SCHEMA_PROSE_DRIFT"

    def test_ignores_old_versions_in_prose(self, repo):
        """V10, V9 etc. should not be flagged (only adjacent versions)."""
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            "The V10 format was deprecated long ago.\n",
        )

        failures = check_doc_sync.check_schema()
        assert failures == []

    def test_excludes_migration_doc(self, repo):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/v11-migration.md",
            """\
            # V11 Migration

            ```yaml
            schema_version: 11
            ```
            """,
        )

        failures = check_doc_sync.check_schema()
        assert failures == []

    def test_version_source_missing(self, repo):
        # Don't create loader.py
        failures = check_doc_sync.check_schema()
        assert len(failures) == 1
        assert failures[0]["code"] == "SCHEMA_VERSION_NOT_FOUND"

    def test_multiple_yaml_blocks(self, repo):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            """\
            # Example 1

            ```yaml
            schema_version: 12
            phases: []
            ```

            # Example 2

            ```yaml
            schema_version: 12
            phases:
              - name: test
            ```
            """,
        )

        failures = check_doc_sync.check_schema()
        assert len(failures) == 2
        assert all(f["code"] == "SCHEMA_YAML_DRIFT" for f in failures)

    def test_ignores_version_in_code_block_for_prose(self, repo):
        """Versions inside code blocks should only be checked as YAML, not prose."""
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            """\
            Correct V13 prose.

            ```yaml
            schema_version: 13
            ```
            """,
        )

        failures = check_doc_sync.check_schema()
        assert failures == []

    def test_v11_in_migration_prose_allowed(self, repo):
        """V11 references in migration docs should not be flagged."""
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/v11-migration.md",
            "Upgrading from V11 to the current schema.\n",
        )

        # File is excluded entirely
        failures = check_doc_sync.check_schema()
        assert failures == []


# =============================================================================
# Check B: Index completeness
# =============================================================================


class TestIndexCheck:
    def test_detects_unindexed_doc(self, repo):
        _write(
            repo,
            "docs/INDEX.md",
            "# Index\n\n- [usage/policies.md](usage/policies.md)\n",
        )
        _write(repo, "docs/usage/policies.md", "# Policies\n")
        _write(repo, "docs/usage/new-feature.md", "# New Feature\n")

        failures = check_doc_sync.check_index()
        assert len(failures) == 1
        assert failures[0]["code"] == "INDEX_MISSING_ENTRY"
        assert "new-feature.md" in failures[0]["message"]

    def test_passes_when_all_indexed(self, repo):
        _write(
            repo,
            "docs/INDEX.md",
            "# Index\n\n- [usage/policies.md](usage/policies.md)\n",
        )
        _write(repo, "docs/usage/policies.md", "# Policies\n")

        failures = check_doc_sync.check_index()
        assert failures == []

    def test_exempt_marker_works(self, repo):
        _write(
            repo,
            "docs/INDEX.md",
            "# Index\n",
        )
        _write(
            repo,
            "docs/usage/internal-notes.md",
            "<!-- DOCSYNC:INDEX_EXEMPT -->\n# Internal Notes\n",
        )

        failures = check_doc_sync.check_index()
        assert failures == []

    def test_excluded_files_not_checked(self, repo):
        _write(repo, "docs/INDEX.md", "# Index\n")
        _write(repo, "docs/design/DESIGN_INDEX.md", "# Design Index\n")

        failures = check_doc_sync.check_index()
        assert failures == []

    def test_index_file_missing(self, repo):
        failures = check_doc_sync.check_index()
        assert len(failures) == 1
        assert failures[0]["code"] == "INDEX_FILE_MISSING"

    def test_only_tracks_specified_directories(self, repo):
        _write(repo, "docs/INDEX.md", "# Index\n")
        # File in non-tracked directory
        _write(repo, "docs/agents/agent-prompts.md", "# Agent Prompts\n")

        failures = check_doc_sync.check_index()
        assert failures == []


# =============================================================================
# Check C: Co-change enforcement
# =============================================================================


class TestCochangeCheck:
    def test_detects_missing_doc(self):
        changed = ["src/vpo/policy/loader.py"]
        violations = check_doc_sync._match_cochange_rules(changed)
        assert len(violations) == 1
        assert violations[0]["code"] == "COCHANGE_MISSING_DOC"
        assert "docs/usage/policies.md" in violations[0]["required_docs"]

    def test_passes_when_docs_present(self):
        changed = ["src/vpo/policy/loader.py", "docs/usage/policies.md"]
        violations = check_doc_sync._match_cochange_rules(changed)
        assert violations == []

    def test_excludes_test_files(self):
        changed = ["tests/unit/test_policy.py"]
        violations = check_doc_sync._match_cochange_rules(changed)
        assert violations == []

    def test_excludes_conftest(self):
        changed = ["tests/conftest.py"]
        violations = check_doc_sync._match_cochange_rules(changed)
        assert violations == []

    def test_excludes_scripts(self):
        changed = ["scripts/check_doc_sync.py"]
        violations = check_doc_sync._match_cochange_rules(changed)
        assert violations == []

    def test_multiple_rules_fire(self):
        changed = [
            "src/vpo/policy/loader.py",
            "src/vpo/cli/scan.py",
        ]
        violations = check_doc_sync._match_cochange_rules(changed)
        assert len(violations) == 2
        categories = {v["category"] for v in violations}
        assert categories == {"policy", "cli"}

    def test_cli_glob_matches(self):
        changed = ["src/vpo/cli/serve.py"]
        violations = check_doc_sync._match_cochange_rules(changed)
        assert len(violations) == 1
        assert violations[0]["category"] == "cli"

    def test_transcode_rules(self):
        changed = ["src/vpo/executor/transcode.py"]
        violations = check_doc_sync._match_cochange_rules(changed)
        assert len(violations) == 1
        assert "docs/usage/transcode-policy.md" in violations[0]["required_docs"]


# =============================================================================
# Check D: Metadata enforcement
# =============================================================================


class TestMetadataCheck:
    def test_valid_required(self, repo):
        msg_file = _write(
            repo,
            "COMMIT_MSG",
            "feat: add feature\n\nDocs-Impact: required\n",
        )
        failures = check_doc_sync.check_metadata(commit_msg_file=str(msg_file))
        assert failures == []

    def test_valid_none_with_reason(self, repo):
        msg_file = _write(
            repo,
            "COMMIT_MSG",
            "refactor: cleanup\n\n"
            "Docs-Impact: none\n"
            "Docs-Reason: Internal refactor only.\n",
        )
        failures = check_doc_sync.check_metadata(commit_msg_file=str(msg_file))
        assert failures == []

    def test_missing_trailer(self, repo):
        msg_file = _write(
            repo,
            "COMMIT_MSG",
            "feat: add feature\n\nSome description.\n",
        )
        failures = check_doc_sync.check_metadata(commit_msg_file=str(msg_file))
        assert len(failures) == 1
        assert failures[0]["code"] == "MISSING_DOCS_IMPACT"

    def test_invalid_value(self, repo):
        msg_file = _write(
            repo,
            "COMMIT_MSG",
            "feat: add\n\nDocs-Impact: maybe\n",
        )
        failures = check_doc_sync.check_metadata(commit_msg_file=str(msg_file))
        assert len(failures) == 1
        assert failures[0]["code"] == "INVALID_DOCS_IMPACT"

    def test_none_without_reason(self, repo):
        msg_file = _write(
            repo,
            "COMMIT_MSG",
            "refactor: cleanup\n\nDocs-Impact: none\n",
        )
        failures = check_doc_sync.check_metadata(commit_msg_file=str(msg_file))
        assert len(failures) == 1
        assert failures[0]["code"] == "MISSING_DOCS_REASON"

    def test_pr_body_fallback(self, repo):
        pr_body = _write(
            repo,
            "PR_BODY",
            "## Summary\n\nDocs-Impact: required\n",
        )
        failures = check_doc_sync.check_metadata(pr_body_file=str(pr_body))
        assert failures == []

    def test_commit_msg_takes_priority_over_pr_body(self, repo):
        msg_file = _write(
            repo,
            "COMMIT_MSG",
            "feat: add\n\nDocs-Impact: required\n",
        )
        pr_body = _write(
            repo,
            "PR_BODY",
            "Docs-Impact: none\n",
        )
        failures = check_doc_sync.check_metadata(
            commit_msg_file=str(msg_file), pr_body_file=str(pr_body)
        )
        assert failures == []

    def test_no_source_silent_locally(self, repo):
        failures = check_doc_sync.check_metadata()
        assert failures == []

    def test_no_source_fails_in_ci(self, repo):
        failures = check_doc_sync.check_metadata(ci=True)
        assert len(failures) == 1
        assert failures[0]["code"] == "NO_METADATA_SOURCE"

    def test_ci_cross_check_with_cochange(self, repo):
        """In CI, Docs-Impact: none should fail if cochange rules fire."""
        msg_file = _write(
            repo,
            "COMMIT_MSG",
            "refactor: cleanup\n\nDocs-Impact: none\nDocs-Reason: Internal only.\n",
        )
        # Mock get_changed_files to return policy files
        with patch.object(
            check_doc_sync,
            "get_changed_files",
            return_value=["src/vpo/policy/loader.py"],
        ):
            failures = check_doc_sync.check_metadata(
                commit_msg_file=str(msg_file), ci=True
            )

        conflict = [f for f in failures if f["code"] == "METADATA_COCHANGE_CONFLICT"]
        assert len(conflict) == 1

    def test_ci_cross_check_exempt(self, repo, monkeypatch):
        """Exemption label should suppress cochange cross-check."""
        msg_file = _write(
            repo,
            "COMMIT_MSG",
            "refactor: cleanup\n\nDocs-Impact: none\nDocs-Reason: Internal only.\n",
        )
        monkeypatch.setenv("DOC_SYNC_EXEMPTION", "docs-impact-exempt")
        with patch.object(
            check_doc_sync,
            "get_changed_files",
            return_value=["src/vpo/policy/loader.py"],
        ):
            failures = check_doc_sync.check_metadata(
                commit_msg_file=str(msg_file), ci=True
            )

        conflict = [f for f in failures if f["code"] == "METADATA_COCHANGE_CONFLICT"]
        assert len(conflict) == 0

    def test_case_insensitive_trailer(self, repo):
        msg_file = _write(
            repo,
            "COMMIT_MSG",
            "feat: add\n\ndocs-impact: Required\n",
        )
        failures = check_doc_sync.check_metadata(commit_msg_file=str(msg_file))
        assert failures == []


# =============================================================================
# Check E: Release-note enforcement
# =============================================================================


class TestReleaseNoteCheck:
    def test_requires_fragment_for_visible_changes(self):
        changed = ["src/vpo/policy/loader.py"]
        with patch.object(check_doc_sync, "get_changed_files", return_value=changed):
            failures = check_doc_sync.check_release_note()
        assert len(failures) == 1
        assert failures[0]["code"] == "MISSING_RELEASE_NOTE"

    def test_passes_with_fragment(self):
        changed = [
            "src/vpo/policy/loader.py",
            "changelog.d/add-validation.md",
        ]
        with patch.object(check_doc_sync, "get_changed_files", return_value=changed):
            failures = check_doc_sync.check_release_note()
        assert failures == []

    def test_no_violation_for_non_visible_changes(self):
        changed = ["tests/unit/test_policy.py"]
        with patch.object(check_doc_sync, "get_changed_files", return_value=changed):
            failures = check_doc_sync.check_release_note()
        assert failures == []


# =============================================================================
# CI skip / exemption handling
# =============================================================================


class TestCISkip:
    def test_local_skip_allowed(self, repo, monkeypatch):
        monkeypatch.setenv("DOC_SYNC_SKIP", "1")
        exit_code = check_doc_sync.main(["--check", "schema"])
        assert exit_code == 0

    def test_ci_skip_rejected(self, repo, monkeypatch, capsys):
        monkeypatch.setenv("DOC_SYNC_SKIP", "1")
        exit_code = check_doc_sync.main(["--check", "schema", "--ci"])
        assert exit_code == check_doc_sync.EXIT_INVALID_CI_SKIP
        captured = capsys.readouterr()
        assert "not allowed in CI" in captured.out

    def test_ci_skip_json_format(self, repo, monkeypatch, capsys):
        monkeypatch.setenv("DOC_SYNC_SKIP", "1")
        exit_code = check_doc_sync.main(
            ["--check", "schema", "--ci", "--format", "json"]
        )
        assert exit_code == check_doc_sync.EXIT_INVALID_CI_SKIP
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is False
        assert any(f["code"] == "INVALID_CI_SKIP" for f in data["failures"])


# =============================================================================
# Exemption handling
# =============================================================================


class TestExemptions:
    def test_cochange_downgraded_to_warning(self, repo, monkeypatch):
        monkeypatch.setenv("DOC_SYNC_EXEMPTION", "docs-impact-exempt")
        with patch.object(
            check_doc_sync,
            "get_changed_files",
            return_value=["src/vpo/policy/loader.py"],
        ):
            exit_code = check_doc_sync.main(["--check", "cochange", "--format", "json"])
        assert exit_code == 0  # No failures, just warnings

    def test_invalid_exemption_ignored(self, repo, monkeypatch):
        monkeypatch.setenv("DOC_SYNC_EXEMPTION", "not-a-valid-label")
        with patch.object(
            check_doc_sync,
            "get_changed_files",
            return_value=["src/vpo/policy/loader.py"],
        ):
            exit_code = check_doc_sync.main(["--check", "cochange", "--format", "json"])
        assert exit_code == check_doc_sync.EXIT_COCHANGE


# =============================================================================
# Output format tests
# =============================================================================


class TestOutputFormats:
    def test_json_schema_shape(self, repo, capsys):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            "```yaml\nschema_version: 12\n```\n",
        )

        check_doc_sync.main(["--check", "schema", "--format", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert "ok" in data
        assert "checks_run" in data
        assert "failures" in data
        assert "warnings" in data
        assert "exemptions" in data
        assert isinstance(data["failures"], list)
        assert isinstance(data["exemptions"], dict)
        assert data["ok"] is False

    def test_json_passes(self, repo, capsys):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")

        check_doc_sync.main(["--check", "schema", "--format", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True

    def test_github_annotations(self, repo, capsys):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            "```yaml\nschema_version: 12\n```\n",
        )

        check_doc_sync.main(["--check", "schema", "--format", "github"])
        captured = capsys.readouterr()
        assert captured.out.startswith("::error")
        assert "schema" in captured.out.lower()

    def test_text_format_pass(self, repo, capsys):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")

        check_doc_sync.main(["--check", "schema", "--format", "text"])
        captured = capsys.readouterr()
        assert "passed" in captured.out.lower()


# =============================================================================
# Exit code tests
# =============================================================================


class TestExitCodes:
    def test_schema_exit_code(self, repo):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            "```yaml\nschema_version: 12\n```\n",
        )
        exit_code = check_doc_sync.main(["--check", "schema"])
        assert exit_code == check_doc_sync.EXIT_SCHEMA

    def test_index_exit_code(self, repo):
        _write(repo, "docs/INDEX.md", "# Index\n")
        _write(repo, "docs/usage/new.md", "# New\n")
        exit_code = check_doc_sync.main(["--check", "index"])
        assert exit_code == check_doc_sync.EXIT_INDEX

    def test_combined_exit_codes(self, repo):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            "```yaml\nschema_version: 12\n```\n",
        )
        _write(repo, "docs/INDEX.md", "# Index\n")
        _write(repo, "docs/usage/new.md", "# New\n")
        exit_code = check_doc_sync.main(["--check", "schema,index"])
        assert exit_code == (check_doc_sync.EXIT_SCHEMA | check_doc_sync.EXIT_INDEX)

    def test_zero_on_pass(self, repo):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        exit_code = check_doc_sync.main(["--check", "schema"])
        assert exit_code == 0


# =============================================================================
# Warn-only mode
# =============================================================================


class TestWarnOnly:
    def test_warn_only_returns_zero(self, repo):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            "```yaml\nschema_version: 12\n```\n",
        )
        exit_code = check_doc_sync.main(["--check", "schema", "--warn-only"])
        assert exit_code == 0

    def test_warn_only_json_has_warnings(self, repo, capsys):
        _write(repo, "src/vpo/policy/loader.py", "SCHEMA_VERSION = 13\n")
        _write(
            repo,
            "docs/usage/policies.md",
            "```yaml\nschema_version: 12\n```\n",
        )
        check_doc_sync.main(["--check", "schema", "--warn-only", "--format", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert len(data["warnings"]) > 0
        assert len(data["failures"]) == 0


# =============================================================================
# Metadata parsing
# =============================================================================


class TestMetadataParsing:
    def test_parse_basic(self):
        text = "feat: add\n\nDocs-Impact: required\nDocs-Reason: New feature.\n"
        result = check_doc_sync.parse_metadata_from_text(text)
        assert result["docs_impact"] == "required"
        assert result["docs_reason"] == "New feature."

    def test_parse_case_insensitive(self):
        text = "docs-impact: None\ndocs-reason: Internal.\n"
        result = check_doc_sync.parse_metadata_from_text(text)
        assert result["docs_impact"] == "none"
        assert result["docs_reason"] == "Internal."

    def test_parse_missing(self):
        text = "feat: add feature\n\nSome body text.\n"
        result = check_doc_sync.parse_metadata_from_text(text)
        assert result["docs_impact"] is None
        assert result["docs_reason"] is None

    def test_parse_with_whitespace(self):
        text = "Docs-Impact:   required  \n"
        result = check_doc_sync.parse_metadata_from_text(text)
        assert result["docs_impact"] == "required"

    def test_parse_markdown_bullet(self):
        text = "- Docs-Impact: required\n- Docs-Reason: New feature.\n"
        result = check_doc_sync.parse_metadata_from_text(text)
        assert result["docs_impact"] == "required"
        assert result["docs_reason"] == "New feature."

    def test_parse_backtick_wrapped(self):
        text = "`Docs-Impact: required`\n"
        result = check_doc_sync.parse_metadata_from_text(text)
        assert result["docs_impact"] == "required"

    def test_parse_bullet_backtick_with_description(self):
        text = "- `Docs-Impact: required` \u2014 updated docs\n"
        result = check_doc_sync.parse_metadata_from_text(text)
        assert result["docs_impact"] == "required"

    def test_parse_checkbox_format(self):
        text = "- [x] Docs-Impact: none\n- Docs-Reason: Internal only.\n"
        result = check_doc_sync.parse_metadata_from_text(text)
        assert result["docs_impact"] == "none"
        assert result["docs_reason"] == "Internal only."

    def test_parse_skips_html_comment_placeholder(self):
        text = "Docs-Impact: <!-- required OR none -->\n"
        result = check_doc_sync.parse_metadata_from_text(text)
        assert result["docs_impact"] is None
