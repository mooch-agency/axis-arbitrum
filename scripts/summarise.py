# Rebuilds results/summary.csv and every results number in README.md from results/runs.csv.
#
# Usage (from anywhere): python3 -I scripts/summarise.py
# Standard library only. It:
#   1. checks each run's cost_usd against its tokens at list prices (fails loudly if they disagree),
#   2. writes results/summary.csv, one row per setup, means per question over that setup's runs,
#   3. rewrites the README blocks between <!-- summarise:NAME:start --> and <!-- summarise:NAME:end -->,
#      so the README can't drift from the data. Edit the wording here, not in the README.
import csv, os, re, statistics

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RUNS = os.path.join(ROOT, "results", "runs.csv")
SUMMARY = os.path.join(ROOT, "results", "summary.csv")
README = os.path.join(ROOT, "README.md")

# List prices, $ per million tokens, at the time of the test (4 Nov 2026).
SONNET = {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write_5m": 2.50}  # the agent
HAIKU = {"input": 0.10, "output": 0.50}                                                 # WebFetch's page reader

# Setups in the post's order: (label, route, bot_check, live_or_copy).
SETUPS = [
    ("Direct fetch, bot check on", "Direct fetch", "on", "copy"),
    ("Headless browser (live)", "Headless browser", "on", "live"),
    ("Server-side fetch (live)", "Server-side fetch", "on", "live"),
    ("Visible browser (live)", "Visible browser", "on", "live"),
    ("Direct fetch, bot check off", "Direct fetch", "off", "copy"),
]


def num(v):
    return float(v) if v not in ("", None) else None


def mean(rows, col):
    vals = [num(r[col]) for r in rows if num(r[col]) is not None]
    return statistics.mean(vals) if vals else None


def check_cost(r):
    """Every cache write in our runs was 5-minute, so tokens x list prices must equal the recorded cost."""
    want = (int(r["main_input_tokens"]) * SONNET["input"] + int(r["main_output_tokens"]) * SONNET["output"]
            + int(r["main_cache_read_tokens"]) * SONNET["cache_read"]
            + int(r["main_cache_write_tokens"]) * SONNET["cache_write_5m"]
            + int(r["reader_input_tokens"]) * HAIKU["input"] + int(r["reader_output_tokens"]) * HAIKU["output"]) / 1e6
    assert abs(want - float(r["cost_usd"])) < 2e-6, (r["route"], r["bot_check"], r["question"], want, r["cost_usd"])


def summarise(rows):
    out = []
    for label, route, bot, site in SETUPS:
        rs = [r for r in rows if r["route"] == route and r["bot_check"] == bot and r["live_or_copy"] == site]
        marks = [r["mark"] for r in rs]
        out.append({
            "setup": label, "route": route, "bot_check": bot, "live_or_copy": site, "runs": len(rs),
            "right": marks.count("Right"), "partial": marks.count("Partial"), "wrong": marks.count("Wrong"),
            "not_found": marks.count("Not found"),
            "main_tokens_mean": mean(rs, "main_tokens"),
            "all_tokens_mean": statistics.mean(float(r["main_tokens"]) + float(r["reader_tokens"]) for r in rs),
            "cost_usd_mean": mean(rs, "cost_usd"), "cost_usd_total": sum(float(r["cost_usd"]) for r in rs),
            "wall_seconds_mean": mean(rs, "wall_seconds"), "page_reader_seconds_mean": mean(rs, "page_reader_seconds"),
            "tool_seconds_mean": mean(rs, "tool_seconds"), "tool_calls_mean": mean(rs, "tool_calls"),
            "page_requests_mean": mean(rs, "page_requests"), "refused_fetches_mean": mean(rs, "refused_fetches"),
        })
    return out


def write_summary(s):
    cols = list(s[0].keys())
    with open(SUMMARY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in s:
            w.writerow({k: (round(v, 6) if isinstance(v, float) else ("" if v is None else v)) for k, v in row.items()})


def k(x):
    return f"{x / 1000:.0f}k"


def d1(x):
    """One decimal place, without a trailing .0 (7.0 -> 7, 3.4 -> 3.4), for prose."""
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s


def pct(a, b):
    return f"{(a / b - 1) * 100:.0f}%"


def blocks(rows, s):
    by = {row["setup"]: row for row in s}
    on, head, server = by["Direct fetch, bot check on"], by["Headless browser (live)"], by["Server-side fetch (live)"]
    vis, off = by["Visible browser (live)"], by["Direct fetch, bot check off"]
    n = len(rows)
    total = sum(float(r["cost_usd"]) for r in rows)
    per_q = s[0]["runs"]

    def of(row):
        return f"{row['right']} of {row['runs']}"

    if vis["right"] and head["right"] == server["right"] == 0:
        lead = f"On the live site, only the visible browser got through: {of(vis)} right."
    else:
        lead = f"On the live site, the visible browser got {of(vis)} right."
    if head["right"] == server["right"] and head["runs"] == server["runs"]:
        others = f"The headless browser and server-side fetch got {of(head)}."
    else:
        others = f"The headless browser got {of(head)} and the server-side fetch {of(server)}."
    headline = (f"{lead} {others} On our private copies, direct fetch got {of(on)} with the bot check on "
                f"and {of(off)} with it off.")

    # Misses: under the shared rule "the agent saying it couldn't find it" is Not found, even when the
    # answer also states something false. marks.json records any such statement as false_statement.
    misses = [r for r in rows if r["mark"] != "Right"]
    false = [r for r in misses if r["false_statement"]]
    if all(row["partial"] == row["wrong"] == 0 for row in s):
        marks_note = ("No answer was marked Partial or Wrong. Every answer that wasn't Right was Not found: the agent "
                      "said it couldn't find the answer. The shared rule marks that Not found even if the answer also "
                      "says something false.")
        if false:
            said = "; ".join(f"on the {r['route'].lower()}'s {r['question'].upper()} run, "
                             f"{r['false_statement'][0].lower()}{r['false_statement'][1:].rstrip('.')}" for r in false)
            marks_note += (f" {'One' if len(false) == 1 else len(false)} did: {said}. "
                           f"The other {len(misses) - len(false)} misses stated nothing false.")
        else:
            marks_note += " None of them did."
    else:
        marks_note = "See results/runs.csv for the Partial and Wrong marks."

    table = ["| Setup | Right | Main-model tokens | Seconds | Tool calls | Cost |",
             "| --- | --- | --- | --- | --- | --- |"]
    for row in s:
        table.append(f"| {row['setup']} | {row['right']}/{row['runs']} | {k(row['main_tokens_mean'])} | "
                     f"{row['wall_seconds_mean']:.1f} | {row['tool_calls_mean']:.1f} | "
                     f"{row['cost_usd_mean'] * 100:.1f} cents |")
    results = "\n".join(table + [
        "",
        f"Every number is a mean per question over that setup's {per_q} runs, except Right, which is a count. "
        + marks_note,
    ])

    code_exec = server["tool_calls_mean"] - server["page_requests_mean"]
    outside_reader = off["tool_seconds_mean"] - off["page_reader_seconds_mean"]

    # Like for like: only the questions both setups got right on every run.
    vis_rows = [r for r in rows if r["route"] == "Visible browser"]
    off_rows = [r for r in rows if r["route"] == "Direct fetch" and r["bot_check"] == "off"]
    both = sorted({r["question"] for r in vis_rows} & {r["question"] for r in off_rows})
    both = [q for q in both if all(r["mark"] == "Right" for r in vis_rows + off_rows if r["question"] == q)]
    vis_both = [r for r in vis_rows if r["question"] in both]
    off_both = [r for r in off_rows if r["question"] in both]
    names = [q.upper() for q in both]
    qlist = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else "".join(names)
    like = (f" Like for like, on the {len(both)} questions both got right ({qlist}), the browser used "
            f"{pct(mean(vis_both, 'main_tokens'), mean(off_both, 'main_tokens'))} more main-model tokens and cost "
            f"{pct(mean(vis_both, 'cost_usd'), mean(off_both, 'cost_usd'))} more.")
    vis_miss = [r for r in vis_rows if r["mark"] != "Right"]
    if vis_miss:
        worst = max(vis_miss, key=lambda r: int(r["main_tokens"]))
        same_q = [r for r in off_rows if r["question"] == worst["question"]]
        # The worst run's share of the per-question token gap between the two setups.
        share = ((int(worst["main_tokens"]) - mean(same_q, "main_tokens")) / len(vis_rows)
                 / (vis["main_tokens_mean"] - off["main_tokens_mean"]))
        like += (f" {'Most' if share > 0.5 else 'Part'} of the {pct(vis['main_tokens_mean'], off['main_tokens_mean'])} "
                 f"comes from the browser's failed {worst['question'].upper()} run, which used {k(int(worst['main_tokens']))} tokens.")

    findings = "\n".join([
        f"- **Visible browser against direct fetch with the bot check off.** The browser used "
        f"{pct(vis['main_tokens_mean'], off['main_tokens_mean'])} more main-model tokens "
        f"({k(vis['main_tokens_mean'])} against {k(off['main_tokens_mean'])}) and cost "
        f"{pct(vis['cost_usd_mean'], off['cost_usd_mean'])} more a question." + like + " It took "
        f"{d1(vis['tool_calls_mean'])} tool calls against {d1(off['tool_calls_mean'])}, and it was faster: "
        f"{vis['wall_seconds_mean']:.1f} seconds against {off['wall_seconds_mean']:.1f}.",
        f"- **Why direct fetch was slower.** WebFetch hands every page to a second, smaller model (Claude Haiku 5.5) "
        f"to summarise before the agent reads it. With the bot check off, that page reader took "
        f"{off['page_reader_seconds_mean']:.1f} of the {off['wall_seconds_mean']:.1f} seconds. All other tool time, "
        f"fetching included, came to {outside_reader:.1f} seconds.",
        f"- **Counting the page reader's tokens too**, direct fetch with the bot check off used "
        f"{k(off['all_tokens_mean'])} tokens a question, and the visible browser used "
        f"{pct(vis['all_tokens_mean'], off['all_tokens_mean'])} more.",
        f"- **Server-side fetch** made {d1(server['page_requests_mean'])} fetches a question, the most we allowed; "
        f"that cap is the \"usage limit\" some of its answers mention. "
        f"The tool refused {d1(server['refused_fetches_mean'])} of them, because the agent had guessed addresses "
        f"it hadn't seen linked; the others re-read the homepage. The other {d1(code_exec)} tool calls a question "
        f"were the tool running code to filter what it fetched.",
    ])

    cost_table = ["| Setup | Total | A question |", "| --- | --- | --- |"]
    cost_table += [f"| {row['setup']} | ${row['cost_usd_total']:.2f} | {row['cost_usd_mean'] * 100:.1f} cents |" for row in s]
    costs = "\n".join([
        f"All {n} runs cost **${total:.2f}** at Anthropic's list prices.",
        "",
        *cost_table,
        "",
        f"Basis: Claude Sonnet 5.5 at ${SONNET['input']:.2f} per million input tokens, ${SONNET['output']:.2f} output, "
        f"${SONNET['cache_read']:.2f} cache reads and ${SONNET['cache_write_5m']:.2f} 5-minute cache writes; "
        f"Claude Haiku 5.5 (the page reader) at ${HAIKU['input']:.2f} input and ${HAIKU['output']:.2f} output. "
        "Token counts come from the usage in every API response. The server-side web fetch tool and the code it "
        "runs had no charge of their own at the time. Nothing here is a grader's cost: we marked by hand.",
    ])
    return {"headline": headline, "results": results, "findings": findings, "costs": costs}


def write_readme(b):
    text = open(README).read()
    for name, body in b.items():
        pat = re.compile(rf"(<!-- summarise:{name}:start -->\n).*?(<!-- summarise:{name}:end -->)", re.S)
        assert pat.search(text), f"README has no summarise:{name} block"
        text = pat.sub(lambda m: m.group(1) + body + "\n" + m.group(2), text)
    open(README, "w").write(text)


def main():
    rows = list(csv.DictReader(open(RUNS)))
    for r in rows:
        check_cost(r)
    s = summarise(rows)
    write_summary(s)
    b = blocks(rows, s)
    if os.path.exists(README):
        write_readme(b)
    for v in b.values():
        print(v, end="\n\n")


if __name__ == "__main__":
    main()
