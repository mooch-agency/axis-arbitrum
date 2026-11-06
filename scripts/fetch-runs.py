# Per-run facts and log check for the direct fetch route (Claude Code's WebFetch on copy A and copy B).
#
# Usage: COPY_A_HOST=... COPY_B_HOST=... python3 -I scripts/fetch-runs.py <AXIS report dir> <batch out dir>
# Reads the AXIS report plus <batch out dir>/vercel-{a,b}.jsonl (the copies' request logs, written by
# run-batch.sh) and <batch out dir>/api-bodies, and writes <batch out dir>/fetch-runs.json (one row per
# run) and marks.md (answers laid out for hand-marking).
#
# What it checks:
#   - Every WebFetch is matched to a middleware log line, including the failed ones: on copy A the 403
#     IS the result under test, so a failed fetch is evidence, not noise. Pass = every A fetch was served
#     challenge-403 (robots.txt excepted), every B fetch was served page/redirect/robots, nothing went off
#     the run's own copy, and no search or shell was used.
#   - Runs are unscored (axis run --no-score, hand marks only), so there are no grader lines to filter.
#   - Tokens and cost per run come from the raw API bodies (main model + page reader, list prices),
#     grouped by Claude Code session, the same maths as browser-runs.py.
import glob, importlib.util, json, os, sys
from datetime import datetime, timedelta
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("common", os.path.join(HERE, "common.py"))
common = importlib.util.module_from_spec(spec); spec.loader.exec_module(common)

# The two private copies' hostnames. We don't publish ours; set your own.
HOSTS = {"a": os.environ.get("COPY_A_HOST", "{COPY_A}"), "b": os.environ.get("COPY_B_HOST", "{COPY_B}")}
WANT = {"a": {"challenge-403", "robots"}, "b": {"page", "redirect", "robots"}}


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_logs(path):
    """The middleware's one-JSON-line-per-request records from a `vercel logs --json` dump."""
    out = []
    for line in open(path):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        d = rec.get("data") or rec
        msg = d.get("message", "")
        if not isinstance(msg, str) or not msg.startswith("{"):
            continue
        try:
            m = json.loads(msg)
        except ValueError:
            continue
        if m.get("axis") != "pt3":   # the tag copy/middleware.js puts on every request line ('pt3' was our working name for this test; change both together)
            continue
        out.append({"t": ts(d["timestamp"]) if isinstance(d.get("timestamp"), str)
                    else datetime.fromtimestamp(d["timestamp"] / 1000).astimezone(),
                    "path": m["path"], "served": m["served"], "ua": m["ua"], "accept": m["accept"], "used": False})
    return out


def main():
    rep, out = sys.argv[1], sys.argv[2]
    logs = {v: load_logs(os.path.join(out, f"vercel-{v}.jsonl")) for v in "ab"}
    costs = common.session_tokens(os.path.join(out, "api-bodies"))
    rows = []
    for f in sorted(glob.glob(os.path.join(rep, "scenarios", "*", "**", "*.json"), recursive=True)):
        d = json.load(open(f))
        if "output" not in d:
            continue
        q, v = d["scenarioKey"].split("@")
        tr = d["output"].get("transcript") or []
        meta = d["output"].get("metadata") or {}
        sid = next((t["content"].get("session_id") for t in tr if t.get("type") == "system"), None)
        stamps = [t.get("timestamp") for t in tr if t.get("timestamp")]
        calls = common.tool_calls(tr)
        fetches = [c for c in calls if c["name"] == "WebFetch"]
        problems, matched = [], []
        for c in fetches:
            url = (c["input"] or {}).get("url") or ""
            if urlparse(url).hostname != HOSTS[v]:
                problems.append(f"fetch off own copy: {url}")
                continue
            path = urlparse(url).path.rstrip("/") or "/"
            # Match the fetch to the first unused log line for the same path within its time window.
            t0, t1 = ts(c["ts"]) - timedelta(seconds=3), ts(c["ts"]) + timedelta(seconds=90)
            cands = [l for l in logs[v] if not l["used"] and t0 <= l["t"] <= t1 and (l["path"].rstrip("/") or "/") == path]
            if not cands:
                problems.append(f"no log line for {path}")
                continue
            l = min(cands, key=lambda l: l["t"]); l["used"] = True
            matched.append({"path": path, "served": l["served"], "ua": l["ua"][:60],
                            "tool_error": (c["result"] or {}).get("is_error"), "result_head": (c["result"] or {}).get("head", "")[:200]})
            if l["served"] not in WANT[v]:
                problems.append(f"{path} served {l['served']} on {v}")
        banned = [c["name"] for c in calls if c["name"] in ("WebSearch", "Bash")]
        if banned:
            problems.append(f"banned tools used: {banned}")
        sc = costs.get(sid, {})
        cost = sum(m["cost_micro"] for m in sc.values()) / 1e6
        rows.append({
            "key": d["scenarioKey"], "question": q.split("-")[0], "version": v, "session_id": sid,
            "start": stamps[0] if stamps else None, "end": stamps[-1] if stamps else None,
            "duration_ms": d.get("durationMs") or meta.get("durationMs"),
            "axis_cost_usd": meta.get("totalCostUsd") or d.get("totalCostUsd"),
            "bodies_cost_usd": round(cost, 4),
            "bodies_by_model": {m: dict(c) for m, c in sc.items()},
            "tool_calls": len(calls), "tool_names": [c["name"] for c in calls],
            "fetches": matched, "fetch_ok": sum(1 for m in matched if not m["tool_error"]),
            "fetch_failed": sum(1 for m in matched if m["tool_error"]),
            "log_check_pass": not problems, "problems": problems,
            "answer": d["output"].get("result"),
        })
    rows.sort(key=lambda r: (r["question"], r["version"]))
    stray = {v: [(l["t"].isoformat(), l["path"], l["served"], l["ua"][:40]) for l in logs[v] if not l["used"]] for v in logs}
    summary = {"runs": len(rows), "log_check_pass": sum(r["log_check_pass"] for r in rows),
               "fails": [f"{r['key']}: {r['problems']}" for r in rows if not r["log_check_pass"]],
               "unmatched_log_lines": stray,
               "cost_usd": {v: round(sum(r["bodies_cost_usd"] for r in rows if r["version"] == v), 4) for v in "ab"}}
    json.dump({"summary": summary, "runs": rows}, open(os.path.join(out, "fetch-runs.json"), "w"), indent=1, default=str)
    with open(os.path.join(out, "marks.md"), "w") as m:
        for r in rows:
            m.write(f"## {r['key']} | {r['duration_ms']} ms | ${r['bodies_cost_usd']} | tools {r['tool_calls']} | "
                    f"log {'pass' if r['log_check_pass'] else r['problems']}\n\n")
            for x in r["fetches"]:
                m.write(f"- {x['path']} served {x['served']} (tool error {x['tool_error']}): {x['result_head'][:120]!r}\n")
            m.write("\nANSWER:\n" + (r["answer"] or "(none)") + "\n\n")
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
