.PHONY: list validate sync

list:
	./bin/agent-skills list

validate:
	./bin/agent-skills validate

sync:
	./bin/agent-skills sync --profile codex,cursor --mode symlink
