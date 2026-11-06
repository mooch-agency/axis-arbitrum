# Server-side fetch route: Claude Sonnet 5.5 on the Messages API with Anthropic's server-side web_fetch tool.
#
# Question: does an agent whose fetches run on someone else's servers get past arbitrum.io's bot check?
# This is the "hosted research agent" case: every request to arbitrum.io leaves Anthropic's
# infrastructure, not our computer. Same model and same five prompts as the browser routes (only the
# tool sentence changes), web search off, fetches fenced to arbitrum.io.
# Not the AXIS harness: AXIS drives Claude Code, which has no server-side fetch, so this script calls the
# API directly and records the same time, tokens and cost fields.
#
# Usage (from the repo root, after scripts/make-scenarios.py has written axis/browser/scenarios):
#   python3 -m venv .venv && .venv/bin/pip install anthropic==2.5.0
#   ANTHROPIC_API_KEY=... .venv/bin/python -I scripts/server-runs.py runs/server-run1
# Offline: `python3 -I scripts/server-runs.py runs/server-run1 --from-raw` re-summarises the saved
# responses in raw/ without calling the API, keeping each question's duration from server-runs.json.
# Optional: ANTHROPIC_WORKSPACE_ID=... if your key is not scoped to one workspace (we needed it; sent as
# the anthropic-workspace-id header).
# Writes <out dir>/server-runs.json (one row per question) and <out dir>/raw/<q>.json (every response,
# including the page text the tool returned: keep it private).
import glob, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIOS = os.path.join(HERE, "..", "axis", "browser", "scenarios")
MODEL = "claude-sonnet-5-5"
# List prices per MTok for Sonnet 5.5 at the time of the test: input, output, cache read, 5m cache write.
# web_fetch has no per-call charge and its code execution (dynamic filtering) is free, so tokens are the cost.
PRICE = (2.00, 10.00, 0.20, 2.50)
TOOL_SENTENCE_OLD = "Use the browser tools to open Arbitrum's website at https://arbitrum.io/ ."
TOOL_SENTENCE_NEW = "Use your web fetch tool to read Arbitrum's website at https://arbitrum.io/ ."


def prompts():
    """The browser route's five live prompts, with the tool sentence swapped. Fails loudly if it no longer matches."""
    out = []
    for f in sorted(glob.glob(os.path.join(SCENARIOS, "*.json"))):
        p = json.load(open(f))["variants"][0]["prompt"]
        assert TOOL_SENTENCE_OLD in p, f
        out.append((os.path.basename(f)[:-5], p.replace(TOOL_SENTENCE_OLD, TOOL_SENTENCE_NEW)))
    return out


def run_one(client, prompt):
    """One question: loop on pause_turn (server tools can pause a long turn) until the model ends its turn."""
    messages, responses = [{"role": "user", "content": prompt}], []
    t0 = time.time()
    for _ in range(8):
        r = client.messages.create(
            model=MODEL, max_tokens=16000, messages=messages,
            tools=[{"type": "web_fetch_20260209", "name": "web_fetch",
                    "allowed_domains": ["arbitrum.io"], "max_uses": 10}],
        )
        responses.append(r.to_dict())
        if r.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": r.content})
    return time.time() - t0, responses


def summarise(key, secs, responses):
    """Tokens, cost, tool calls, each fetch's URL and outcome, and the final answer for one question."""
    tok = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    fetches, tool_calls, texts = [], 0, []
    for r in responses:
        u = r.get("usage") or {}
        for k in tok:
            tok[k] += u.get(k) or 0
        for b in r.get("content", []):
            t = b.get("type")
            if t == "server_tool_use":   # web_fetch calls plus the code execution behind dynamic filtering
                tool_calls += 1
                if b.get("name") == "web_fetch":
                    fetches.append({"id": b.get("id"), "url": (b.get("input") or {}).get("url")})
            elif t == "web_fetch_tool_result":
                c = b.get("content") or {}
                hit = next((f for f in fetches if f["id"] == b.get("tool_use_id")), None)
                if hit is not None:
                    # "web_fetch_result" on success, else the error code (e.g. url_not_in_prior_context).
                    hit["result"] = c.get("error_code") or c.get("type")
                    doc = ((c.get("content") or {}).get("source") or {}).get("data") or ""
                    hit["head"] = doc[:200]
            elif t == "text":
                texts.append(b.get("text", ""))
    # The final answer is the last text block. Earlier text blocks are the agent thinking aloud between tool
    # calls (e.g. "Result shape is odd; let me inspect."). The version we ran on 4 Nov joined them all;
    # we re-summarised the saved responses with --from-raw to apply this fix.
    answer = texts[-1] if texts else ""
    cost = (tok["input_tokens"] * PRICE[0] + tok["output_tokens"] * PRICE[1]
            + tok["cache_read_input_tokens"] * PRICE[2] + tok["cache_creation_input_tokens"] * PRICE[3]) / 1e6
    return {"key": key, "duration_ms": round(secs * 1000), "api_calls": len(responses), "tokens": tok,
            "tokens_total": sum(tok.values()), "cost_usd": round(cost, 4), "tool_calls": tool_calls,
            "fetches": fetches, "stop_reason": responses[-1].get("stop_reason"), "answer": answer}


def from_raw(out):
    """Re-summarise saved responses offline; durations come from the existing server-runs.json."""
    old = {r["key"]: r for r in json.load(open(os.path.join(out, "server-runs.json")))["runs"]}
    rows = []
    for f in sorted(glob.glob(os.path.join(out, "raw", "*.json"))):
        key = os.path.basename(f)[:-5]
        rows.append(summarise(key, old[key]["duration_ms"] / 1000, json.load(open(f))["responses"]))
    return rows


def main():
    out = sys.argv[1]
    if "--from-raw" in sys.argv:
        rows = from_raw(out)
        summary = {"runs": len(rows), "model": MODEL, "cost_usd_total": round(sum(r["cost_usd"] for r in rows), 4)}
        json.dump({"summary": summary, "runs": rows}, open(os.path.join(out, "server-runs.json"), "w"), indent=1)
        print(json.dumps(summary))
        return
    import anthropic  # only needed for live runs
    os.makedirs(os.path.join(out, "raw"), exist_ok=True)
    ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    client = anthropic.Anthropic(default_headers={"anthropic-workspace-id": ws} if ws else None)  # key from ANTHROPIC_API_KEY
    rows = []
    for key, prompt in prompts():
        secs, responses = run_one(client, prompt)
        json.dump({"prompt": prompt, "responses": responses}, open(os.path.join(out, "raw", key + ".json"), "w"), indent=1, default=str)  # responses carry datetimes
        rows.append(summarise(key, secs, responses))
        print(key, rows[-1]["duration_ms"], rows[-1]["cost_usd"], [f.get("result") for f in rows[-1]["fetches"]], flush=True)
    summary = {"runs": len(rows), "model": MODEL, "cost_usd_total": round(sum(r["cost_usd"] for r in rows), 4)}
    json.dump({"summary": summary, "runs": rows}, open(os.path.join(out, "server-runs.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
