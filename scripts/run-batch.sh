#!/usr/bin/env bash
# One batch for one Claude Code route, end to end: every question once, raw API bodies kept, log saved.
#
# Usage (from anywhere): ANTHROPIC_API_KEY=... [LANGSMITH_API_KEY=... LANGSMITH_PROJECT=...] \
#   scripts/run-batch.sh <fetch|browser|headless> <label> <runs per question>
#   fetch:    scripts/run-batch.sh fetch run1 1      every question on copy A and copy B once (AXIS interleaves them)
#   browser:  scripts/run-batch.sh browser run1 1    every question once on live arbitrum.io, visible Chrome
#   headless: scripts/run-batch.sh headless run1 1   the same in headless Chrome
# Output: runs/<route>-<label>/{meta.txt,run.log,api-bodies/}. The AXIS report lands in axis/<route>/.axis/reports.
# Keep runs/ and .axis/ private: they hold the pages the agent read.
#
# Fetch route only: it needs your own two copies of the site (see copy/). Set COPY_A_URL and COPY_B_URL
# (https://...) and, to pull the copies' request logs for fetch-runs.py's log check, COPY_PROJECT_DIR
# (the Vercel-linked copy directory). The log pull uses BSD `date -v` (macOS).
#
# Browser notes (checked 2 Nov 2026 with the installed Google Chrome):
# - Headless Chrome stays on Cloudflare's "Just a moment..." page; headed Chrome passes it. So the visible
#   route opens a Chrome window per run and the computer must stay unlocked and awake (caffeinate below).
#   Concurrency is 1 in both browser configs.
# - --isolated gives every run a fresh in-memory profile, so no run inherits another's Cloudflare clearance cookie.
# - Arbitrum's docs, blog, portal and other subdomains are blocked in the browser (--blocked-origins),
#   matching the copy, which only holds arbitrum.io. WebFetch, WebSearch and Bash are denied.
# - One-off install before the first browser run: pnpm install (pins @playwright/mcp 0.0.83), then replace
#   {REPO} in axis/browser/axis.config.json and axis/headless/axis.config.json with this repo's absolute path.
#
# We marked by hand, so AXIS runs with --no-score (no judge, no judge cost). Drop it to have AXIS's judge
# score each run against the checks in the scenarios; that costs extra.
#
# Time, tokens and cost per run afterwards:
#   fetch:             python3 -I scripts/fetch-runs.py axis/fetch/.axis/reports/<report> runs/fetch-<label>
#   browser, headless: python3 -I scripts/browser-runs.py axis/<route>/.axis/reports/<report> runs/<route>-<label> \
#                        --bodies runs/<route>-<label>/api-bodies
set -euo pipefail
ROUTE="${1:?route: fetch, browser or headless}"; LABEL="${2:?label, e.g. run1}"; RUNS="${3:?runs per question}"
case "$ROUTE" in fetch|browser|headless) ;; *) echo "route must be fetch, browser or headless" >&2; exit 2;; esac
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/runs/$ROUTE-$LABEL"
mkdir -p "$OUT"

if [ "$ROUTE" != fetch ] && [ ! -x "$HERE/node_modules/.bin/playwright-mcp" ]; then
  echo "Playwright MCP missing: cd $HERE && pnpm install" >&2; exit 2
fi
ls "$HERE/axis/$ROUTE/scenarios/"*.json >/dev/null 2>&1 || { echo "no scenarios: run scripts/make-scenarios.py" >&2; exit 2; }

START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "route=$ROUTE batch=$LABEL runs=$RUNS start=$START" | tee "$OUT/meta.txt"

AXIS_BODIES_DIR="$OUT/api-bodies" \
  caffeinate -dims "$HERE/scripts/run-clean.sh" "axis/$ROUTE" --runs "$RUNS" --concurrency "$([ "$ROUTE" = fetch ] && echo 2 || echo 1)" \
  --no-score --debug ${AXIS_EXTRA:-} \
  > "$OUT/run.log" 2>&1 || echo "axis exit $?" >> "$OUT/meta.txt"

END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "end=$END" | tee -a "$OUT/meta.txt"
grep -E "Report saved|Claude Code (before|after)" "$OUT/run.log" | tee -a "$OUT/meta.txt" || true

# Fetch route only: request logs from both copies (the middleware logs one JSON line per request),
# so every fetch can be matched: copy A answered 403, copy B served the page.
if [ "$ROUTE" = fetch ] && [ -n "${COPY_PROJECT_DIR:-}" ]; then
  cd "$COPY_PROJECT_DIR"
  for v in a b; do
    url="${COPY_A_URL:?}"; [ "$v" = b ] && url="${COPY_B_URL:?}"
    vercel logs --deployment "$url" --since "$(date -u -v-1M -j -f %Y-%m-%dT%H:%M:%SZ "$START" +%Y-%m-%dT%H:%M:%SZ)" \
      --until "$(date -u -v+1M -j -f %Y-%m-%dT%H:%M:%SZ "$END" +%Y-%m-%dT%H:%M:%SZ)" --json -n 10000 \
      > "$OUT/vercel-$v.jsonl" 2> "$OUT/vercel-$v.stderr" || echo "vercel logs $v failed" >> "$OUT/meta.txt"
    echo "vercel-$v lines: $(wc -l < "$OUT/vercel-$v.jsonl")" | tee -a "$OUT/meta.txt"
  done
fi
