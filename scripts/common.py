# Shared helpers for the extraction scripts: transcript reading and list-price costing.
#
# Both came from our earlier AXIS write-up's scripts (an extract-runs.py and a cost-from-langsmith.py
# that are not in this repo); they are copied here unchanged in logic so every route reads
# transcripts and prices tokens the same way.
import collections, json, os

# $ per million tokens: input, output, cache read, 5-minute cache write (1.25x input).
# Anthropic list prices as of the test (4 Nov 2026). A 1-hour cache write costs 2x input; the
# costing below reads the real 5m/1h split from each response, and every write in our runs was 5m.
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),   # the agent (main model) on every route
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),    # WebFetch's page reader inside Claude Code
}


def price_for(model):
    """List prices for a model id (prefix match), or None if we have none on file."""
    for name, p in PRICES.items():
        if model and model.startswith(name):
            return p
    return None


def tool_calls(transcript):
    """All tool_use blocks in an AXIS (Claude Code) transcript, each with its result's error flag and first chars."""
    uses, results = [], {}
    for t in transcript:
        c = t.get("content") or {}
        msg = c.get("message") or {}
        for b in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
            if b.get("type") == "tool_use":
                uses.append({"id": b["id"], "name": b["name"], "input": b.get("input"), "ts": t.get("timestamp")})
            elif b.get("type") == "tool_result":
                body = b.get("content")
                text = body if isinstance(body, str) else json.dumps(body)
                results[b.get("tool_use_id")] = {"is_error": bool(b.get("is_error")), "head": text[:300], "ts": t.get("timestamp")}
    for u in uses:
        u["result"] = results.get(u["id"])
    return uses


def session_tokens(bodies_dir):
    """session_id -> model -> token sums, call count and list-price cost (micro-dollars).

    Reads Claude Code's raw API bodies (OTEL_LOG_RAW_API_BODIES=file:<dir>): index.jsonl names each
    call's session, model and response file, and each response carries its exact usage.
    """
    out = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for line in open(os.path.join(bodies_dir, "index.jsonl")):
        e = json.loads(line)
        try:
            u = json.load(open(os.path.join(bodies_dir, e["response_file"]))).get("usage") or {}
        except (OSError, ValueError, KeyError):
            continue
        p = price_for(e["model"])
        cc = u.get("cache_creation") or {}
        w5, w1 = cc.get("ephemeral_5m_input_tokens", 0) or 0, cc.get("ephemeral_1h_input_tokens", 0) or 0
        if not cc:
            w5 = u.get("cache_creation_input_tokens", 0) or 0
        c = out[e["session_id"]][e["model"]]
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
            c[k] += u.get(k) or 0
        c["cache_creation_input_tokens"] += w5 + w1
        c["calls"] += 1
        if p:
            c["cost_micro"] += round((u.get("input_tokens") or 0) * p[0] + (u.get("output_tokens") or 0) * p[1]
                                     + (u.get("cache_read_input_tokens") or 0) * p[2] + w5 * p[3] + w1 * p[0] * 2)
    return out
