# Source Inputs

Use this order unless user overrides:

1. `~/.codex/history.jsonl`
2. `~/.codex/archived_sessions/*.jsonl`
3. `~/.codex/sessions/*.jsonl`
4. `~/.codex/log/*`
5. Repository-local telemetry and instructions (`AGENTS.md`, existing skills)
6. MCP-exposed resources (only when explicitly authorized)

For opt-in personal extension:

- Messaging MCP resources or local logs should only be read when user explicitly approves.
- Do not join personal communication patterns into coding-skill candidates unless user asks for a merged scope.
