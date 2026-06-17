#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: codebase-memory-graph.sh <command> [options]

Commands:
  init       Configure UI, index the repo, start UI, and run a schema smoke check
  index      Index the repo
  start-ui   Start the tmux keepalive that exposes the HTTP graph UI
  stop-ui    Stop the tmux keepalive session for the repo
  status     Show config, projects, and UI listener state
  schema     Print graph schema for the repo's indexed project
  keepalive  Internal command used inside tmux

Options:
  --repo PATH     Repository root. Defaults to git root or current directory.
  --mode MODE     Index mode: fast, moderate, full, cross-repo-intelligence. Default: full.
  --port PORT     UI port. Default: 9749.
EOF
}

repo=""
mode="full"
port="9749"
command="${1:-}"
[[ -n "$command" ]] && shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="${2:?--repo requires a path}"
      shift 2
      ;;
    --mode)
      mode="${2:?--mode requires a value}"
      shift 2
      ;;
    --port)
      port="${2:?--port requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

need() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'missing required command: %s\n' "$1" >&2
    exit 1
  }
}

resolve_repo() {
  if [[ -n "$repo" ]]; then
    cd "$repo"
    pwd
    return
  fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

json_index_payload() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

print(json.dumps({"repo_path": sys.argv[1], "mode": sys.argv[2]}))
PY
}

json_project_payload() {
  python3 - "$1" <<'PY'
import json
import sys

print(json.dumps({"project": sys.argv[1]}))
PY
}

project_for_repo() {
  local root="$1" projects
  projects="$(codebase-memory-mcp cli list_projects)"
  PROJECTS_JSON="$projects" python3 - "$root" <<'PY'
import json
import os
import sys

root = os.path.realpath(sys.argv[1])
data = json.loads(os.environ["PROJECTS_JSON"])
for project in data.get("projects", []):
    if os.path.realpath(project.get("root_path", "")) == root:
        print(project["name"])
        break
else:
    sys.exit(1)
PY
}

session_for_repo() {
  local root base safe
  root="$1"
  base="$(basename "$root")"
  safe="$(printf '%s' "$base" | tr -cs 'A-Za-z0-9_-' '-')"
  printf 'cbm-%s-ui\n' "${safe:-repo}"
}

configure_ui() {
  codebase-memory-mcp config set ui true
  codebase-memory-mcp config set port "$port"
}

wait_for_ui() {
  local url="http://127.0.0.1:${port}/"
  for _ in $(seq 1 20); do
    if curl -fsS -I "$url" >/dev/null 2>&1; then
      printf 'ui_url=%s\n' "$url"
      return 0
    fi
    sleep 0.5
  done
  printf 'UI did not answer at %s\n' "$url" >&2
  return 1
}

cmd_keepalive() {
  need node
  exec node <<'NODE'
const { spawn } = require("child_process");

const child = spawn("codebase-memory-mcp", [], {
  stdio: ["pipe", "pipe", "pipe"],
});

child.stdout.on("data", () => {});
child.stderr.on("data", (chunk) => process.stderr.write(chunk));

child.stdin.write(JSON.stringify({
  jsonrpc: "2.0",
  id: 1,
  method: "initialize",
  params: {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: {
      name: "codebase-memory-graph-ui-keepalive",
      version: "1",
    },
  },
}) + "\n");
child.stdin.write(JSON.stringify({
  jsonrpc: "2.0",
  method: "notifications/initialized",
  params: {},
}) + "\n");

child.on("exit", (code, signal) => {
  process.exit(code ?? (signal ? 1 : 0));
});
process.on("SIGTERM", () => child.kill("SIGTERM"));
process.on("SIGINT", () => child.kill("SIGINT"));
setInterval(() => {}, 2147483647);
NODE
}

cmd_index() {
  local root payload
  need codebase-memory-mcp
  need python3
  root="$(resolve_repo)"
  payload="$(json_index_payload "$root" "$mode")"
  codebase-memory-mcp cli index_repository "$payload"
}

cmd_start_ui() {
  local root session script
  need codebase-memory-mcp
  need tmux
  need curl
  configure_ui
  root="$(resolve_repo)"
  session="$(session_for_repo "$root")"
  script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
  if ! tmux has-session -t "$session" 2>/dev/null; then
    tmux new-session -d -s "$session" "$script keepalive"
  fi
  printf 'tmux_session=%s\n' "$session"
  wait_for_ui
}

cmd_stop_ui() {
  local root session
  need tmux
  root="$(resolve_repo)"
  session="$(session_for_repo "$root")"
  if tmux has-session -t "$session" 2>/dev/null; then
    tmux kill-session -t "$session"
    printf 'stopped=%s\n' "$session"
  else
    printf 'not_running=%s\n' "$session"
  fi
}

cmd_schema() {
  local root project payload
  need codebase-memory-mcp
  need python3
  root="$(resolve_repo)"
  project="$(project_for_repo "$root")"
  payload="$(json_project_payload "$project")"
  codebase-memory-mcp cli get_graph_schema "$payload"
}

cmd_status() {
  local root session
  need codebase-memory-mcp
  root="$(resolve_repo)"
  session="$(session_for_repo "$root")"
  printf 'repo=%s\n' "$root"
  printf 'tmux_session=%s\n' "$session"
  codebase-memory-mcp config list
  codebase-memory-mcp cli list_projects
  if command -v tmux >/dev/null 2>&1; then
    tmux has-session -t "$session" 2>/dev/null && printf 'ui_keepalive=running\n' || printf 'ui_keepalive=stopped\n'
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN || true
  fi
  curl -fsS -I "http://127.0.0.1:${port}/" || true
}

cmd_init() {
  need codebase-memory-mcp
  need python3
  configure_ui
  cmd_index
  cmd_start_ui
  cmd_schema >/dev/null
  cmd_status
}

case "$command" in
  init) cmd_init ;;
  index) cmd_index ;;
  start-ui) cmd_start_ui ;;
  stop-ui) cmd_stop_ui ;;
  status) cmd_status ;;
  schema) cmd_schema ;;
  keepalive) cmd_keepalive ;;
  -h|--help|"") usage ;;
  *)
    printf 'unknown command: %s\n' "$command" >&2
    usage >&2
    exit 2
    ;;
esac
