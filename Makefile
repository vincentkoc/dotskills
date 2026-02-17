.PHONY: list validate validate-spec sync sync-copy precommit-install precommit-run import-anthropic import-anthropic-dry import-huggingface-dry marketplace releases-index check-generated changed-skills ci publish-skill release

list:
	./bin/agent-skills list

validate:
	./bin/agent-skills validate

validate-spec:
	./scripts/validate_spec.py

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

import-huggingface-dry:
	./bin/agent-skills import --source huggingface --repo https://github.com/huggingface/skills.git --ref main --dry-run

marketplace:
	./scripts/generate_marketplace.sh

releases-index:
	./scripts/generate_releases_index.sh

check-generated:
	./scripts/check_generated.sh

changed-skills:
	./scripts/changed_skills.sh $(BASE) $(HEAD)

ci: marketplace releases-index validate precommit-run check-generated

publish-skill:
	./scripts/publish_skill.sh $(SKILL) $(TAG) $(REPO)

release:
	@test -n "$(VERSION)" || (echo "VERSION is required (example: VERSION=v0.4.0)" && exit 1)
	@git diff --quiet || (echo "Working tree is not clean" && exit 1)
	$(MAKE) ci
	git tag -a "$(VERSION)" -m "Release $(VERSION)"
	@echo "Created tag $(VERSION). Push with: git push origin $(VERSION)"
