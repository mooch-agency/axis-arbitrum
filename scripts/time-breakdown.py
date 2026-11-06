# Where each run's time goes, from Claude Code's OpenTelemetry spans in LangSmith.
# Written to explain why the visible browser (21 s a question) beat direct fetch on the bot-check-off
# copy (32 s): most of the fetch route's time is WebFetch's page reader.
#
# Usage: LANGSMITH_API_KEY=... python3 -I scripts/time-breakdown.py <out.json> <route> <project> <start ISO UTC> <end ISO UTC>
#   e.g. ... runs/time-breakdown.json fetch my-langsmith-project 2026-11-04T10:18:00Z 2026-11-04T10:21:00Z
# Run once per route; each call adds or replaces that route's entry in <out.json>.
# <project> is the LangSmith project run-clean.sh traced to; the window should cover the batch
# (start and end are in the batch's meta.txt).
#
# Per test-taker session it sums span durations by kind:
#   main model   claude_code.llm_request spans on claude-sonnet-5-5 that aren't the page reader
#   page reader  claude_code.llm_request spans whose query_source is web_fetch_apply (Haiku 5.5 inside WebFetch)
#   tools        claude_code.tool.execution spans (for WebFetch this INCLUDES the page reader, so the
#                network part of a fetch is tool time minus reader time)
#   wall         the claude_code.interaction span (the whole turn)
# Spans can overlap (parallel tool calls), so the parts are reported alongside wall time, not forced to sum to it.
import collections, datetime, json, os, sys, time, urllib.error, urllib.request

KEY = os.environ["LANGSMITH_API_KEY"]
API = "https://api.smith.langchain.com"


def call(path, body=None):
    # LangSmith rate-limits run queries (429), so back off and retry rather than fail the whole pull.
    for attempt in range(8):
        req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                     headers={"x-api-key": KEY, "content-type": "application/json"})
        try:
            return json.load(urllib.request.urlopen(req))
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("LangSmith kept returning 429")


def spans(project, start, end):
    pid = call("/api/v1/sessions?name=" + project)[0]["id"]
    out, cursor = [], None
    while True:
        body = {"session": [pid], "limit": 100, "select": ["name", "start_time", "end_time", "extra"],
                "filter": f'and(gte(start_time, "{start}"), lte(start_time, "{end}"))'}
        if cursor:
            body["cursor"] = cursor
        r = call("/api/v1/runs/query", body)
        out += r["runs"]
        cursor = (r.get("cursors") or {}).get("next")
        if not cursor:
            return out


def secs(s):
    t = lambda x: datetime.datetime.fromisoformat(x.replace("Z", "+00:00"))
    return (t(s["end_time"]) - t(s["start_time"])).total_seconds() if s.get("end_time") else 0.0


def main():
    out_path, route, project, start, end = sys.argv[1:6]
    by_session = collections.defaultdict(collections.Counter)
    models = collections.defaultdict(set)
    for s in spans(project, start, end):
        md = (s.get("extra") or {}).get("metadata") or {}
        sid = md.get("otel.span.session.id")
        if not sid:
            continue
        d, n = secs(s), s["name"]
        if n == "claude_code.llm_request":
            model = md.get("otel.span.model") or md.get("ls_model_name") or ""
            models[sid].add(model)
            src = md.get("otel.span.query_source_safe") or md.get("otel.span.query_source") or ""
            if src == "web_fetch_apply":
                by_session[sid]["page_reader"] += d; by_session[sid]["reader_calls"] += 1
            else:
                by_session[sid]["main_model"] += d; by_session[sid]["model_calls"] += 1
        elif n == "claude_code.tool.execution":
            by_session[sid]["tools"] += d; by_session[sid]["tool_calls"] += 1
        elif n == "claude_code.interaction":
            by_session[sid]["wall"] += d
    rows = {sid: {k: round(v, 2) for k, v in c.items()} for sid, c in by_session.items()
            if any("sonnet" in m for m in models[sid])}  # test-taker sessions only
    result = json.load(open(out_path)) if os.path.exists(out_path) else {}
    result[route] = rows
    json.dump(result, open(out_path, "w"), indent=1)
    print(route, len(rows), "sessions")
    for sid, r in rows.items():
        print("  ", sid[:8], r)


if __name__ == "__main__":
    main()
