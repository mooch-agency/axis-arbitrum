# Per-run time, tokens, cost and route for the browser routes (visible and headless Chrome via
# Playwright MCP, both on live arbitrum.io).
#
# Usage: python3 -I scripts/browser-runs.py <AXIS report dir> <out dir> [--bodies <api-bodies dir>]
# Writes <out dir>/browser-runs.json, one row per run:
#   time    durationMs from AXIS, plus first and last transcript timestamps
#   tokens  AXIS tokenUsage, and with --bodies the exact per-run sums by model from the raw API bodies.
#           Use the bodies figures: AXIS's tokenUsage leaves out cache-write tokens.
#   cost    AXIS totalCostUsd, and with --bodies the per-run list-price cost from the bodies
#   route   every Playwright navigation (URL), pages opened on arbitrum.io, any navigation off it,
#           and whether the run ever sat on Cloudflare's "Just a moment..." page.
# Reads transcripts with the same tool_calls() as fetch-runs.py, so both routes count tool calls alike.
#
# Change made when publishing: the per-run bodies split (bodies_by_model, bodies_cost_usd) was added.
# The version we ran on 4 Nov only summed the bodies for the whole batch.
import collections, glob, importlib.util, json, os, sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("common", os.path.join(HERE, "common.py"))
common = importlib.util.module_from_spec(spec); spec.loader.exec_module(common)
LIVE = {"arbitrum.io", "www.arbitrum.io"}


def main():
    rep, out = sys.argv[1], sys.argv[2]
    bodies = sys.argv[sys.argv.index("--bodies") + 1] if "--bodies" in sys.argv else None
    per_session = common.session_tokens(bodies) if bodies else {}
    os.makedirs(out, exist_ok=True)
    rows = []
    for f in sorted(glob.glob(os.path.join(rep, "scenarios", "*", "**", "*.json"), recursive=True)):
        d = json.load(open(f))
        if "output" not in d:
            continue
        tr = d["output"].get("transcript") or []
        meta = d["output"].get("metadata") or {}
        ts = [t.get("timestamp") for t in tr if t.get("timestamp")]
        calls = common.tool_calls(tr)
        navs = [(c["input"] or {}).get("url") for c in calls if c["name"].endswith("browser_navigate")]
        heads = " ".join((c["result"] or {}).get("head", "") for c in calls)
        crit = (d.get("score") or {}).get("goalAchievement", {}).get("criteria", [])
        sid = next((t["content"].get("session_id") for t in tr if t.get("type") == "system"), None)
        sc = per_session.get(sid, {})
        rows.append({
            "file": os.path.relpath(f, rep), "key": d.get("scenarioKey"), "session_id": sid,
            "start": ts[0] if ts else None, "end": ts[-1] if ts else None,
            "duration_ms": d.get("durationMs") or meta.get("durationMs"),
            "axis_tokens": meta.get("tokenUsage") or d.get("tokenUsage"),
            "axis_cost_usd": meta.get("totalCostUsd") or d.get("totalCostUsd"),
            "bodies_by_model": {m: dict(c) for m, c in sc.items()} if bodies else None,
            "bodies_cost_usd": round(sum(m["cost_micro"] for m in sc.values()) / 1e6, 4) if bodies else None,
            "tool_calls": len(calls), "tool_names": collections.Counter(c["name"] for c in calls),
            "navigations": navs,
            "pages_on_site": sorted({u for u in navs if u and urlparse(u).hostname in LIVE}),
            "off_site_navigations": [u for u in navs if u and urlparse(u).hostname not in LIVE],
            "saw_challenge": "Just a moment" in heads,
            "key_score": crit[0].get("score") if crit else None,
            "answer": d["output"].get("result"),
        })
    summary = {"runs": len(rows),
               "duration_ms": [r["duration_ms"] for r in rows],
               "axis_cost_usd_total": round(sum(r["axis_cost_usd"] or 0 for r in rows), 4)}
    if bodies:
        summary["bodies_cost_usd_total"] = round(sum(r["bodies_cost_usd"] for r in rows), 4)
    json.dump({"summary": summary, "runs": rows}, open(os.path.join(out, "browser-runs.json"), "w"), indent=1, default=dict)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
