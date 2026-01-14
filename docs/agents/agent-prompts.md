# Agent Prompts

**Purpose:**
This document provides reusable prompts for LLM agents working on the VPO codebase. Use these as starting points for common development tasks.

---

## Code Generation Prompts

### Implementing a New CLI Command

```text
I need to add a new CLI command to VPO. The command should:
- [Describe the command's purpose]
- [List required arguments and options]
- [Describe expected output format]

Follow the existing patterns in:
- src/vpo/cli/scan.py
- src/vpo/cli/inspect.py

Requirements:
- Use click decorators for arguments and options
- Support both human-readable and JSON output (--json flag)
- Define appropriate exit codes
- Add the command to cli/__init__.py
- Include docstring with examples
```

### Adding a Database Table

```text
I need to add a new table to the VPO database. The table should store:
- [Describe the data to store]
- [List columns with types]
- [Describe relationships to existing tables]

Follow the existing patterns in:
- src/vpo/db/schema.py (for CREATE TABLE)
- src/vpo/db/models.py (for dataclasses and operations)

Requirements:
- Add migration logic in schema.py
- Increment schema version
- Create domain model (@dataclass) and database record classes
- Add CRUD operations (insert, get, update, delete)
- Use UTC timestamps with ISO 8601 format
- Include appropriate indexes
```

### Adding a New Introspector

```text
I need to add a new media introspector that wraps [tool name].

Follow the existing pattern in:
- src/vpo/introspector/ffprobe.py
- src/vpo/introspector/interface.py

Requirements:
- Implement the MediaIntrospector protocol
- Add is_available() class method for tool detection
- Parse tool output into TrackInfo objects
- Handle errors with MediaIntrospectionError
- Add unit tests with mocked subprocess calls
```

---

## Bug Fix Prompts

### Investigating a Failing Test

```text
The test [test name] in [file path] is failing with:
[Error message]

Please:
1. Read the test file to understand the expected behavior
2. Read the implementation being tested
3. Identify the root cause
4. Propose a fix that maintains backward compatibility
5. Verify the fix doesn't break other tests
```

### Debugging a CLI Error

```text
Running `vpo [command]` produces this error:
[Error output]

Please:
1. Trace the code path from the CLI command to the error
2. Identify where the error originates
3. Propose a fix with proper error handling
4. Add a test case to prevent regression
```

---

## Refactoring Prompts

### Extracting a Shared Utility

```text
I've noticed duplicated code in:
- [file 1]
- [file 2]

Please:
1. Identify the common pattern
2. Extract to an appropriate shared module
3. Update all call sites
4. Ensure tests still pass
5. Add tests for the new utility if needed
```

### Improving Error Messages

```text
The error messages in [module] are not user-friendly. Please:
1. Review all error paths in the module
2. Improve messages to be clear and actionable
3. Add hints where appropriate (like "Hint: ...")
4. Maintain consistent formatting with existing CLI output
```

---

## Documentation Prompts

### Documenting a New Feature

```text
I've implemented [feature name]. Please create documentation:
1. Add usage documentation to docs/usage/
2. Add design documentation to docs/design/ if complex
3. Update docs/INDEX.md with links
4. Add examples to existing CLI usage docs
5. Update CLAUDE.md if there are new patterns
```

---

## Related docs

- [Documentation Index](../INDEX.md)
- [Agent Playbook](agent-playbook.md)
- [Error Handling](../internals/error-handling.md)
