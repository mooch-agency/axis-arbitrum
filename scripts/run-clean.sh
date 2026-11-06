#!/usr/bin/env bash
# Run AXIS hermetically for one route, keeping every raw API body, with optional LangSmith tracing.
#
# Usage: ANTHROPIC_API_KEY=... [LANGSMITH_API_KEY=... LANGSMITH_PROJECT=...] scripts/run-clean.sh <config dir> [extra axis args]
#   e.g. scripts/run-clean.sh axis/browser --runs 1 --no-score
# Normally called by scripts/run-batch.sh, which sets AXIS_BODIES_DIR and keeps the log.
#
# Why each piece exists (verified Oct 2026 on @netlify/axis 1.21.0):
# - `env -i`: AXIS strips the env for the AGENT, but the JUDGE inherits the axis process env verbatim
#   (adapters/base/agent-adapter.ts: `input.env ?? process.env`). We ran with --no-score, so no judge
#   ran, but a clean env keeps scored runs honest too.
# - Clean HOME: with your real HOME, Claude Code loads ~/.claude (CLAUDE.md, skills, plugins). An empty
#   temp HOME keeps every Claude Code process clean.
# - OTEL vars: Claude Code's own OpenTelemetry tracing. Needs no plugin, so the agent's session still
#   lists plugins: []. The config lists these names under "env" so AXIS passes them to the agent.
# - OTEL_LOG_RAW_API_BODIES in "file:<dir>" mode writes every API request and response body to <dir>
#   (<id>.request.json / .response.json plus index.jsonl). The extraction scripts read exact token usage
#   from these. They also hold the page text the agent read, so keep them private.
#   Set AXIS_BODIES_DIR to choose <dir>; the default is <config dir>/api-bodies/<UTC timestamp>.
# - DISABLE_AUTOUPDATER=1: AXIS runs the installed `claude` from PATH. Its version decides the page-reader
#   model, so no run may update it mid-batch. The version is printed before and after the run.
#   We used Claude Code 2.1.318.
# - Workspace header: if your key is not scoped to one workspace, every API call needs an
#   anthropic-workspace-id header. Claude Code honours ANTHROPIC_CUSTOM_HEADERS for this, so set
#   ANTHROPIC_CUSTOM_HEADERS="anthropic-workspace-id: <your workspace id>". Unset, nothing changes.
# - LangSmith (optional): with LANGSMITH_API_KEY and LANGSMITH_PROJECT set, spans go to LangSmith's OTLP
#   endpoint, which time-breakdown.py reads. We always ran with it on. Without it the trace exporter is
#   set to "none"; we have not tested that raw bodies are still written in that mode, so check that
#   index.jsonl appears after your first run.
set -euo pipefail

: "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY in the environment, never in a file in this repo}"
CONFIG_DIR="${1:?config dir, e.g. axis/browser}"; shift || true

HERE="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BODIES_DIR="${AXIS_BODIES_DIR:-$HERE/$CONFIG_DIR/api-bodies/$STAMP}"
mkdir -p "$BODIES_DIR"
echo "Claude Code before: $(claude --version 2>&1) | start ${STAMP}"
CLEAN_HOME="$(mktemp -d "${TMPDIR:-/tmp}/axis-clean-homeXXXXXX")"
trap 'rm -rf "$CLEAN_HOME"' EXIT

if [ -n "${LANGSMITH_API_KEY:-}" ]; then
  : "${LANGSMITH_PROJECT:?set LANGSMITH_PROJECT to the LangSmith project to trace to}"
  TRACES=otlp
  OTLP_ENDPOINT=https://api.smith.langchain.com/otel/v1/traces
  OTLP_HEADERS="x-api-key=${LANGSMITH_API_KEY},Langsmith-Project=${LANGSMITH_PROJECT}"
else
  TRACES=none; OTLP_ENDPOINT=; OTLP_HEADERS=
fi

cd "$HERE/$CONFIG_DIR"
env -i \
  PATH="$PATH" USER="$USER" SHELL="${SHELL:-/bin/zsh}" LANG=en_GB.UTF-8 TERM=dumb TMPDIR="${TMPDIR:-/tmp}" \
  HOME="$CLEAN_HOME" \
  ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  ${ANTHROPIC_CUSTOM_HEADERS:+ANTHROPIC_CUSTOM_HEADERS="$ANTHROPIC_CUSTOM_HEADERS"} \
  CLAUDE_CODE_ENABLE_TELEMETRY=1 CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1 \
  OTEL_TRACES_EXPORTER="$TRACES" OTEL_METRICS_EXPORTER=none OTEL_LOGS_EXPORTER=none \
  OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
  OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="$OTLP_ENDPOINT" \
  OTEL_EXPORTER_OTLP_HEADERS="$OTLP_HEADERS" \
  OTEL_LOG_TOOL_DETAILS=1 OTEL_SERVICE_NAME=axis-claude-code \
  OTEL_LOG_TOOL_CONTENT=1 OTEL_LOG_RAW_API_BODIES="file:${BODIES_DIR}" \
  DISABLE_AUTOUPDATER=1 \
  "$HERE/node_modules/.bin/axis" run "$@" 2>&1 \
  | sed -E 's/sk-[a]nt-[A-Za-z0-9_-]+/[REDACTED]/g; s/ls[v]2_[A-Za-z0-9_]+/[REDACTED]/g'   # keep Anthropic and LangSmith keys out of the log ([a] and [v] stop this line matching a key scan)
echo "Claude Code after: $(claude --version 2>&1) | end $(date -u +%Y%m%dT%H%M%SZ)"
