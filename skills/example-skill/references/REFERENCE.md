# Example Skill Reference

Use this file for details that are useful but not needed in every activation.

## Frontmatter checklist

- `name` matches the folder name and uses lowercase-hyphen format.
- `description` states both what the skill does and when to use it.
- Optional fields (`license`, `compatibility`, `metadata`, `allowed-tools`) are valid if present.

## Authoring checklist

- Keep `SKILL.md` concise; move depth to `references/`.
- Keep references one level from `SKILL.md` (for example `references/REFERENCE.md`).
- Put deterministic helpers in `scripts/`.
- Put output templates and static assets in `assets/`.
