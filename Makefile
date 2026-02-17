.PHONY: list validate sync sync-copy precommit-install precommit-run import-anthropic import-anthropic-dry

list:
	./bin/agent-skills list

validate:
	./bin/agent-skills validate

sync:
	./bin/agent-skills sync --profile codex,cursor --mode symlink

sync-copy:
	./bin/agent-skills sync --profile codex,cursor --mode copy

precommit-install:
	pre-commit install

precommit-run:
	pre-commit run --all-files

import-anthropic:
	./bin/agent-skills import --source anthropics --repo https://github.com/anthropics/skills.git --ref main --subdir skills --skills skill-creator

import-anthropic-dry:
	./bin/agent-skills import --source anthropics --repo https://github.com/anthropics/skills.git --ref main --subdir skills --skills skill-creator --dry-run
