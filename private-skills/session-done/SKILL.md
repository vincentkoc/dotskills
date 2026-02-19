---
name: session-done
description: Run a post-session teardown with `/done` to capture what was discussed, key decisions, questions, follow-ups, and outcomes into a session markdown artifact.
license: Proprietary
metadata:
  internal: true
  version: "0.1.0"
---

# Session Done

## Purpose

Capture and persist every finished agent session as a compact, atomic knowledge unit so work can be resumed quickly, reflected on, and indexed in your knowledge base.

## When to use

- You finish a chat/session and want a structured teardown before switching context.
- You need a canonical `.md` handoff containing session ID, branch, decisions, blockers, and follow-up state.
- You want to feed outcomes into Obsidian/PKM and optional flashcard extraction.

## Workflow

1. Trigger with `/done` at the end of a session.
2. Run `scripts/session-done` with collected session notes:
   - `--session-id` (optional, defaults to `CLAUDE_SESSION_ID` or timestamp)
   - `--branch` (optional, defaults to current `git` branch)
   - `--summary`, `--decisions`, `--questions`, `--follow-ups`, `--state`, `--reflection`, `--flashcards`
3. Confirm output path (default: `./.session-notes` under repo root, or `DONE_NOTES_DIR` override).
4. If `DONE_OBSIDIAN_VAULT` is set, the script copies the file into that directory for Obsidian/PKM ingestion.
5. If a shared memory file exists, append the reflection block to `done-shared-memory.md`.
6. End session with one action item and one risk item included in the `## Next actions` section.

## Inputs

- `--summary`: high-level recap of what the agent worked on.
- `--decisions`: finalized choices and rationale.
- `--questions`: unresolved or open questions from the session.
- `--follow-ups`: concrete follow-up tasks or blockers.
- `--state`: current state of work and repository status.
- `--reflection`: explicit self-reflection on what to improve.
- `--flashcards`: optional question/answer bullets for spaced repetition.
- Optional env vars:
  - `DONE_NOTES_DIR`: target folder for generated `.md`.
  - `DONE_OBSIDIAN_VAULT`: optional Obsidian/PKM target folder.
  - `DONE_MEMORY_FILE`: optional shared memory file (default: `done-shared-memory.md` in notes dir).

## Outputs

- A Markdown teardown file with:
  - filename containing `session` + session id + branch + timestamp.
  - sectioned recap, decisions, questions, follow-ups, reflection, and flashcards.
  - machine-readable metadata block for future re-ingestion.
- Optional copied/added artifact in your Obsidian/PKM folder.
- Optional updated shared-memory file.

## Notes

The script is intentionally minimal and deterministic. Keep the `/done` payload concise and complete, because this artifact is designed to be the source of truth for the next session spin-up.
