---
description: Prudent AI Coding Implementation Style
trigger: always_on
---

# Safety & Intent
- If requirements are ambiguous, ask targeted clarifying questions before editing.
# Minimal, Incremental Changes
- Avoid deleting or rewriting unfamiliar code unless necessary to meet the request.
- Preserve existing behavior by default; gate behavior changes behind flags/configs when possible.
# Codebase Awareness
- Locate the authoritative entrypoints and data flow before changing architecture.
- Reuse existing abstractions/patterns rather than introducing parallel ones.
- Avoid duplicating logic across files/modules; if duplication is needed temporarily, leave a clear follow-up task.
# Testing & Verification
- Prefer fast feedback loops:
  - Add/extend unit tests when changing logic.
  - Run quick checks (typecheck/lint/unit tests) before heavier validations.
- Do not claim a fix works without evidence; if you cannot run tests, state what should be run and why.
- When changing behavior, add regression tests that would have caught the original bug.
# Logging & Observability
- When debugging, add high-signal logging or error messages at the root cause boundary.
# Interfaces & Backwards Compatibility
- Do not break public APIs lightly; prefer compatibility layers.
- When renaming flags/options, support aliases temporarily and normalize internally.
# Dependency Hygiene
- Avoid adding new dependencies unless clearly justified.
- Prefer existing dependencies already present in the repo.
- If a new dependency is required, choose a stable widely-used one and document the reason.
# Tooling / MCP Usage
- Prefer using MCP tools when available for tasks they can handle (e.g., chain-specific helpers, documentation lookup).
- Clearly state when a conclusion is based on MCP output vs general knowledge.
# Communication
- Provide a concise summary of what changed and how to validate it.
- If uncertain, explicitly say what you don’t know and what information would unblock you.