# Builds results/runs.csv (one row per run) from the extraction scripts' output and the hand marks.
#
# Mark your runs in results/marks.json first: one entry per run, keyed by route, bot_check, question and
# run (the run's number within that question, counting from 1 in the order the extraction scripts list
# them). A run with no entry is written as "Unmarked", with a warning.
#
# Usage (from the repo root): [COPY_A_HOST=... COPY_B_HOST=...] python3 -I scripts/build-runs-csv.py [runs dir]
# Reads whichever of these exist under [runs dir] (default runs/), and skips the rest with a note:
#   fetch-run1/fetch-runs.json       from fetch-runs.py      (direct fetch, copy A and copy B)
#   browser-run1/browser-runs.json   from browser-runs.py --bodies   (visible browser, live)
#   headless-run1/browser-runs.json  from browser-runs.py --bodies   (headless browser, live)
#   server-run1/server-runs.json     from server-runs.py     (server-side fetch, live)
#   time-breakdown.json              from time-breakdown.py  (LangSmith span times; optional)
# Those inputs hold the copies' hostnames and the pages the agent read, so keep them private and publish
# only this CSV. With COPY_A_HOST and COPY_B_HOST set, the copy hostnames in answers become {COPY_A} / {COPY_B}.
#
# Column notes:
#   run           the run's number within its route, bot_check and question.
#   main_*        the agent's model (Claude Sonnet 5.5), summed over every API call in the run.
#                 Total = input + output + cache read + cache write.
#   reader_*      Claude Haiku 5.5 inside Claude Code's WebFetch, which summarises each page before the
#                 agent sees it (direct fetch only; it never uses the prompt cache).
#   cost_usd      main model + page reader at list prices, from the exact usage in each API response.
#   wall_seconds  AXIS's durationMs for Claude Code runs; the script's own timer around the API calls for
#                 the server-side fetch.
#   page_reader_seconds, tool_seconds  summed span times from LangSmith; blank where we didn't trace.
#   tool_calls    every tool call the agent made. Claude Code runs include one ToolSearch (Claude Code loads
#                 the fetch or browser tools on demand); server-side fetch counts web_fetch calls plus the
#                 code execution calls the tool makes for dynamic filtering.
#   page_requests WebFetch calls, browser navigations, or web_fetch calls.
#   refused_fetches  server-side fetch only: web_fetch calls the tool refused (the URL hadn't appeared
#                 in anything it had fetched before).
#   false_statement  from marks.json: anything false the answer stated, even when the mark is Not found.
import collections, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RUNS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "runs")
MAIN, READER = "claude-sonnet-5-5", "claude-haiku-5-5"
HOSTS = {h: p for h, p in ((os.environ.get("COPY_A_HOST"), "{COPY_A}"), (os.environ.get("COPY_B_HOST"), "{COPY_B}")) if h}
COLUMNS = ["route", "bot_check", "live_or_copy", "question", "run", "mark", "mark_reason", "false_statement",
           "main_input_tokens", "main_output_tokens", "main_cache_read_tokens", "main_cache_write_tokens", "main_tokens",
           "reader_input_tokens", "reader_output_tokens", "reader_tokens", "cost_usd",
           "wall_seconds", "page_reader_seconds", "tool_seconds", "tool_calls", "page_requests", "refused_fetches",
           "answer"]


def warn(msg):
    print("note:", msg, file=sys.stderr)


def load(rel):
    """An input file under the runs dir, or None (with a note) if it isn't there."""
    path = os.path.join(RUNS, rel)
    if not os.path.exists(path):
        warn(f"{rel} not found, skipped")
        return None
    return json.load(open(path))


def scrub(text):
    """Replace the private copy hostnames with placeholders."""
    for host, placeholder in HOSTS.items():
        text = text.replace(host, placeholder)
    return text


def tokens(by_model):
    """Main-model and page-reader token columns, plus cost, from a session's per-model sums."""
    m, r = by_model.get(MAIN, {}), by_model.get(READER, {})
    row = {"main_input_tokens": m.get("input_tokens", 0), "main_output_tokens": m.get("output_tokens", 0),
           "main_cache_read_tokens": m.get("cache_read_input_tokens", 0),
           "main_cache_write_tokens": m.get("cache_creation_input_tokens", 0)}
    row["main_tokens"] = sum(row.values())
    row["reader_input_tokens"] = r.get("input_tokens", 0)
    row["reader_output_tokens"] = r.get("output_tokens", 0)
    assert not r.get("cache_read_input_tokens") and not r.get("cache_creation_input_tokens"), "reader used the cache"
    row["reader_tokens"] = row["reader_input_tokens"] + row["reader_output_tokens"]
    row["cost_usd"] = f"{sum(c.get('cost_micro', 0) for c in by_model.values()) / 1e6:.6f}"
    return row


def times(route_times, sid):
    t = (route_times or {}).get(sid)
    if t is None:
        return {"page_reader_seconds": "", "tool_seconds": ""}
    return {"page_reader_seconds": t.get("page_reader", 0), "tool_seconds": t.get("tools", 0)}


def main():
    marks = {(m["route"], m["bot_check"], m["question"], m["run"]): m
             for m in json.load(open(os.path.join(ROOT, "results", "marks.json")))["marks"]}
    span_times = load("time-breakdown.json") or {}
    rows, seen = [], collections.Counter()

    def add(route, bot_check, live_or_copy, q, extra):
        seen[(route, bot_check, q)] += 1
        run = seen[(route, bot_check, q)]
        m = marks.get((route, bot_check, q, run))
        if m is None:
            warn(f"no mark for {route}, bot check {bot_check}, {q}, run {run}: written as Unmarked")
            m = {"mark": "Unmarked", "reason": ""}
        rows.append({"route": route, "bot_check": bot_check, "live_or_copy": live_or_copy, "question": q, "run": run,
                     "mark": m["mark"], "mark_reason": m["reason"], "false_statement": m.get("false_statement", ""),
                     **extra})

    fetch = load("fetch-run1/fetch-runs.json")
    if fetch and not HOSTS:
        warn("COPY_A_HOST / COPY_B_HOST not set: copy hostnames in answers are left as they are")
    for r in (fetch or {}).get("runs", []):
        add("Direct fetch", "on" if r["version"] == "a" else "off", "copy", r["question"], {
            **tokens(r["bodies_by_model"]), **times(span_times.get("fetch"), r["session_id"]),
            "wall_seconds": round(r["duration_ms"] / 1000, 3), "tool_calls": r["tool_calls"],
            "page_requests": r["tool_names"].count("WebFetch"), "refused_fetches": "",
            "answer": scrub(r["answer"] or "")})

    for route, rel, trace_key in (("Visible browser", "browser-run1/browser-runs.json", "browser"),
                                  ("Headless browser", "headless-run1/browser-runs.json", "headless")):
        for r in (load(rel) or {}).get("runs", []):
            add(route, "on", "live", r["key"].split("-")[0], {
                **tokens(r["bodies_by_model"]), **times(span_times.get(trace_key), r["session_id"]),
                "wall_seconds": round(r["duration_ms"] / 1000, 3), "tool_calls": r["tool_calls"],
                "page_requests": len(r["navigations"]), "refused_fetches": "",
                "answer": scrub(r["answer"] or "")})

    for r in (load("server-run1/server-runs.json") or {}).get("runs", []):
        t = r["tokens"]
        by_model = {MAIN: {**t, "cost_micro": t["input_tokens"] * 2 + t["output_tokens"] * 10
                           + t["cache_read_input_tokens"] * 0.2 + t["cache_creation_input_tokens"] * 2.5}}
        add("Server-side fetch", "on", "live", r["key"].split("-")[0], {
            **tokens(by_model), "page_reader_seconds": "", "tool_seconds": "",
            "wall_seconds": round(r["duration_ms"] / 1000, 3), "tool_calls": r["tool_calls"],
            "page_requests": len(r["fetches"]),
            "refused_fetches": sum(1 for f in r["fetches"] if f.get("result") != "web_fetch_result"),
            "answer": scrub(r["answer"] or "")})

    order = [("Direct fetch", "on"), ("Headless browser", "on"), ("Server-side fetch", "on"),
             ("Visible browser", "on"), ("Direct fetch", "off")]
    rows.sort(key=lambda r: (order.index((r["route"], r["bot_check"])), r["question"], r["run"]))
    if len(rows) != 25:
        warn(f"{len(rows)} runs, not the 25 of our test")
    with open(os.path.join(ROOT, "results", "runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> results/runs.csv")


if __name__ == "__main__":
    main()
