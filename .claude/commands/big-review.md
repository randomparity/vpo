---
description: Review all new code commits on the current branch using relevant review agents in parallel, then consolidate findings into a prioritized implementation plan.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The user may specify a base branch, specific files to focus on, or agents to include/exclude.

## Goal

Perform a comprehensive, multi-agent code review of all changes on the current branch (compared to the base branch). Select the most relevant review agents, run them in parallel, consolidate all findings into a single prioritized TodoWrite list grouped by file, present an implementation plan with batched commits, and optionally create GitHub issues for deferred items.

## Execution Steps

### 1. Determine Scope of Changes

Run these commands to understand what changed:

```bash
# Determine base branch (default: main, or user-specified)
git log --oneline main..HEAD
git diff main...HEAD --stat
git diff main...HEAD --name-only
```

Parse the output to build:
- **CHANGED_FILES**: List of all modified/added files with their paths
- **CHANGE_SUMMARY**: High-level description of what changed (new features, bug fixes, refactors, etc.)
- **FILE_TYPES**: Categorize files by type (Python, JavaScript, CSS, HTML/Jinja2, Markdown, YAML, SQL, Rust, config)

If there are no changes compared to the base branch, inform the user and stop.

### 2. Select Relevant Review Agents

Read all agent definitions from `.claude/agents/*.md` and select agents based on the file types and change patterns detected. Use this mapping:

| Change Pattern | Agents to Select |
|---|---|
| Any Python files changed | `python-code-reviewer` |
| Python + HTML/JS/CSS changed | `fullstack-web-reviewer` |
| SQLite/database code changed | `python-sqlite-review` |
| JavaScript or CSS changed | `ui-ux-reviewer` |
| Markdown docs changed | `markdown-docs-reviewer` |
| Threading/async/multiprocessing code | `concurrency-reviewer` |
| JSON/YAML/Pydantic/serialization code | `data-integrity-reviewer` |
| Error handling / try-except / retry logic | `error-handling-reviewer` |
| Multi-module changes (3+ modules) | `module-boundaries-reviewer` |
| Logging / metrics / monitoring code | `observability-reviewer` |
| Loops / batch processing / large data | `perf-scalability-reviewer` |
| File handles / connections / pools | `resource-lifecycle-reviewer` |
| Datetime / timezone / scheduling code | `timezone-datetime-reviewer` |
| Text processing / user input / i18n | `unicode-text-reviewer` |

**Selection rules:**
- `python-code-reviewer` is ALWAYS included if any Python files changed (it's the generalist)
- `module-boundaries-reviewer` is included when changes span 3+ distinct modules/packages
- Read the actual diff content (not just filenames) to detect patterns like async/await, try/except, datetime usage, etc.
- Maximum 8 agents per review to keep results manageable. If more than 8 match, prioritize: python-code-reviewer > fullstack-web-reviewer > domain-specific reviewers (by relevance to the actual changes)
- Minimum 1 agent must be selected

Report to the user which agents were selected and why before proceeding.

### 3. Run Review Agents in Parallel

Launch ALL selected agents simultaneously using the Task tool. Each agent receives the same context:

**Agent prompt template:**

```
Review the changes on the current branch compared to main.

Changed files:
{CHANGED_FILES list}

Focus your review on the files and patterns relevant to your specialty.

For EACH finding, provide:
1. **Severity**: ERROR (bugs, security issues, data loss risk), WARNING (potential problems, bad patterns), or SUGGESTION (improvements, best practices)
2. **File**: Exact file path
3. **Line(s)**: Line number or range (if applicable)
4. **Finding**: Clear description of the issue
5. **Recommendation**: Specific fix or improvement with code snippet if applicable

Use `git diff main...HEAD` to see the actual changes. Read the changed files for full context.

Output your findings as a structured list. If you find no issues in your domain, explicitly state "No findings" rather than inventing issues.
```

IMPORTANT: All agents MUST be launched in a single message with multiple Task tool calls to ensure true parallel execution.

### 4. Collect and Deduplicate Findings

After all agents complete, merge their results:

1. **Parse** each agent's output into structured findings (severity, file, lines, finding, recommendation)
2. **Deduplicate** findings that multiple agents flagged (keep the most detailed version, note which agents agreed)
3. **Group by file**: Organize all findings under their file path
4. **Sort within each file** by line number

### 5. Prioritize and Create TodoWrite List

Write ALL findings to TodoWrite, organized as follows:

**Priority ordering:**
1. **ERRORS** first (bugs, security issues, data loss risks)
2. **WARNINGS** second (potential problems, bad patterns, robustness issues)
3. **SUGGESTIONS** third (improvements, best practices, style)

**TodoWrite format for each item:**

```
[{SEVERITY}] {file_path}:{line} - {finding} | Recommended: {recommendation} (from: {agent_names})
```

Every single finding from every agent must be captured - do NOT filter or omit findings at this stage.

### 6. Present Consolidated Implementation Plan

Present the plan to the user in this format:

```markdown
## Review Summary

**Branch**: {branch_name} (vs {base_branch})
**Files changed**: {count}
**Agents used**: {agent_list}
**Total findings**: {count} ({error_count} errors, {warning_count} warnings, {suggestion_count} suggestions)

## Findings by File

### {file_path}
| # | Severity | Line(s) | Finding | Agents |
|---|----------|---------|---------|--------|
| 1 | ERROR    | 42      | ...     | python-code-reviewer, error-handling-reviewer |
| 2 | WARNING  | 88-92   | ...     | concurrency-reviewer |

(repeat for each file with findings)

## Implementation Batches

### Batch 1: Critical Fixes (ERRORS)
- Fix {description} in {file} (finding #N)
- Fix {description} in {file} (finding #N)
- **Commit**: `fix: {summary of error fixes}`

### Batch 2: Warnings
- Address {description} in {file} (finding #N)
- Address {description} in {file} (finding #N)
- **Commit**: `refactor: {summary of warning fixes}`

### Batch 3: Suggestions
- Improve {description} in {file} (finding #N)
- Improve {description} in {file} (finding #N)
- **Commit**: `chore: {summary of suggestions}`

(Group related changes within each severity tier. Each batch MUST end with a commit step.)
```

**Batching rules:**
- Each batch addresses one severity level (errors, then warnings, then suggestions)
- Within a severity level, group related changes that can be committed together
- If a single severity level has many findings across unrelated areas, split into sub-batches
- Every batch explicitly includes a commit step with a descriptive message
- Batch descriptions should be concrete enough to execute without re-reading the findings

### 7. Get User Confirmation

Ask the user to confirm the plan using AskUserQuestion:

- **Option 1**: "Implement all batches" - Execute all findings
- **Option 2**: "Implement errors and warnings only" - Skip suggestions
- **Option 3**: "Implement errors only" - Only fix critical issues
- **Option 4**: "Review findings first" - Let user cherry-pick individual items

If the user chooses Option 4, present the TodoWrite list and let them mark items to skip. Update the batch plan accordingly.

### 8. Execute Approved Batches

For each approved batch:

1. Implement all changes in the batch
2. Run `uv run ruff check --fix` on modified Python files
3. Run the test suite: `uv run pytest` (or targeted tests if the full suite is too large)
4. If tests pass, stage and commit with the batch's commit message
5. If tests fail, diagnose and fix before committing
6. Move to the next batch

### 9. Handle Deferred/Skipped Findings

After all approved batches are complete, check if any findings were skipped or deferred. If so, ask the user:

"The following review findings were not implemented. Would you like to create GitHub issues to track them?"

- **Option 1**: "Create issues for all skipped findings" - Create one issue per finding
- **Option 2**: "Create issues grouped by file" - One issue per file with multiple findings
- **Option 3**: "Create issues for warnings only" - Skip suggestions
- **Option 4**: "Skip issue creation" - No issues created

When creating issues, use this format:

```bash
gh issue create \
  --title "{severity}: {short finding description}" \
  --label "code-review,{severity_label}" \
  --body "$(cat <<'EOF'
## Source

From big-review of branch `{branch_name}` on {date}.
Detected by: {agent_names}

## Finding

{detailed finding description}

## File(s)

- `{file_path}:{line}`

## Recommendation

{recommendation with code snippet if applicable}

---
Generated by `/big-review`
EOF
)"
```

Severity labels: `priority:high` for errors, `priority:medium` for warnings, `priority:low` for suggestions.

## Operating Principles

### Quality
- **No invented findings**: If an agent finds nothing, that's fine. Never pad results.
- **Preserve author intent**: Review findings should improve code, not rewrite it in the reviewer's preferred style.
- **Concrete recommendations**: Every finding must include a specific, actionable fix.

### Efficiency
- **Parallel execution**: All agents run simultaneously. Never run agents sequentially.
- **Deduplicate aggressively**: If 3 agents flag the same issue, show it once with all 3 credited.
- **Batch commits logically**: Minimize commit noise while keeping each commit atomic and passing tests.

### Transparency
- **Show agent selection rationale**: Tell the user why each agent was selected.
- **Show all findings**: Never silently drop findings. If something is low-priority, label it as such.
- **Track everything**: Every finding is either implemented, deferred to an issue, or explicitly skipped by the user.

## Context

$ARGUMENTS
