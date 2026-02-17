---
name: session-done
description: Capture each completed agent session as a structured `/done` teardown with branch/session metadata, key decisions, questions, follow-ups, reflection, and PKM-friendly handoff artifacts.
license: AGPL-3.0-only
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# Session Done

## Purpose

Create an atomic handoff for every finished agent session so context can be resumed without ambiguity and work can be resumed in small, traceable units.

## When to use

- A session has ended and you want a durable teardown before context switch.
- You need a canonical `.md` record with session id, branch, decisions, questions, and follow-ups.
- You want optional Obsidian/PKM sync plus shared-memory updates.
- You want self-reflection plus flashcard-ready prompts captured alongside outcomes.

## Workflow

1. End with `/done` and collect values for at least one section.
2. Run `scripts/session-done` with section flags:
   - `--summary`
   - `--decisions`
   - `--questions`
   - `--follow-ups`
   - `--state`
   - `--reflection`
   - `--flashcards`
3. Use `--session-id` for the current Claude session and `--branch` (defaults to git branch).
4. Review the generated `.md` file in `DONE_NOTES_DIR` (or `.session-notes`).
5. If configured, confirm sync to Obsidian/PKM and shared-memory append.

## Inputs

- `--summary`: what was discussed or changed.
- `--decisions`: final choices and rationale.
- `--questions`: unresolved questions.
- `--follow-ups`: pending items.
- `--state`: work state / status.
- `--reflection`: what to improve next session.
- `--flashcards`: optional spaced-repetition prompts.
- Optional env vars:
  - `DONE_NOTES_DIR`: output directory (default `./.session-notes`).
  - `DONE_OBSIDIAN_VAULT`: optional PKM/Obsidian target directory.
  - `DONE_MEMORY_FILE`: optional shared-memory filename in notes dir.

## Outputs

- One markdown file named with session id + branch + timestamp.
- Structured sections for summary, decisions, questions, follow-ups, state, reflection, and flashcards.
- Optional Obsidian/PKM copy and optional shared-memory append.
