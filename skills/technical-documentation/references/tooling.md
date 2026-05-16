# OpenClaw Docs Tooling Guide

Use this file when platform, routing, generated docs, or validation choices
matter.

## OpenClaw docs stack

- Public docs source lives under `docs/**`.
- Navigation and page grouping live in `docs/docs.json`.
- Use `pnpm docs:list` to discover indexed docs and docs-list routing hints.
- Treat filesystem paths, Mintlify routes, redirects, and published
  `https://docs.openclaw.ai/...` URLs as separate maps.
- Generated references, redirect-only pages, and hidden support pages should not
  be added to visible nav without an explicit reason.

## Path and route checks

- Resolve docs paths relative to the config or source that declares them.
- Verify `docs/docs.json` entries point to existing files or intentional routes.
- Verify moved docs keep addressability through redirects or stable related
  links when needed.
- When reporting published docs, include the relevant full
  `https://docs.openclaw.ai/...` URL.

## Validation commands

Use the narrowest commands that prove the touched surface:

```bash
pnpm docs:list
pnpm docs:check-mdx
pnpm docs:check-links
pnpm docs:check-i18n-glossary
pnpm format:docs:check
pnpm lint:docs
git diff --check
```

Generated docs, plugin inventories, labeler changes, or scripts may require
their own inventory/generated checks. Behavior claims may require source-backed
tests or command probes beyond docs checks.

## Platform-fit review

- Prefer existing OpenClaw/Mintlify components and navigation patterns.
- Do not propose a docs-platform migration for ordinary content problems.
- Keep key facts in text, not image-only screenshots.
- Prefer stable anchors, descriptive headings, and structured tables only when
  they reduce lookup effort.
