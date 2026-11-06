# Writes the AXIS scenarios (one JSON file per question per route) from the question list below.
#
# Same key shape as our earlier AXIS tests (one 0.7 key check scored 10 / 5 / 0, plus two 0.15 guards)
# and the same shared grading rule, so marks mean the same across tests. Three AXIS routes, one question list:
#   axis/fetch/scenarios/<q>.json     variants a (copy A, bot check on) and b (copy B, bot check off)
#   axis/browser/scenarios/<q>.json   one variant, "live": visible Chrome on live arbitrum.io
#   axis/headless/scenarios/<q>.json  the same, for headless Chrome
# The server-side fetch route (server-runs.py) reuses the browser prompts with one sentence swapped.
#
# Questions: facts on arbitrum.io that are NOT on docs.arbitrum.io. Question and Right / Partial cells are
# Natalie's, word for word; the personas and Wrong cells are ours (her table had no Wrong column except Q5's).
# If a key changes, change it here and re-run; never edit the JSON by hand.
# Every string below is kept exactly as it ran, so the scenario files match the runs byte for byte. That's why
# they still say "AXIS pt III" (our working name for this test, now axis-arbitrum) and "Nat" (Natalie).
# We marked every run by hand (axis run --no-score), so the judge checks below are the written record of
# what we marked against, not a paid grader's prompt.
#
# Usage (from the repo root): COPY_A_HOST=... COPY_B_HOST=... python3 -I scripts/make-scenarios.py
# Without the env vars the copy hosts are written as {COPY_A} / {COPY_B}, as in the published files.
import json, os, sys

HOSTS = {
    "a": os.environ.get("COPY_A_HOST", "{COPY_A}"),  # copy A: 403 challenge, like live (bot check on)
    "b": os.environ.get("COPY_B_HOST", "{COPY_B}"),  # copy B: same pages, unblocked (bot check off)
    "live": "arbitrum.io",                            # browser and headless routes
}

# (id, slug, persona, question, right, partial, wrong, source), from Natalie's table (approved 3 Nov 2026)
# and her marking notes: Q3 with no numbers is Wrong; Q5 records the count (x of 8) on every run, and
# extra or invented chains are logged, not penalised, unless they're all the answer gives.
QUESTIONS = [
    ("q1", "confidentiality", "I'm a fintech product lead looking into Arbitrum.",
     "Which companies does Arbitrum name as examples of confidentiality on Arbitrum?",
     "Fairblock, Renegade and Fhenix.", "One or two of the three.",
     "None of the three, or other companies stated as Arbitrum's examples.",
     "/why-arbitrum/features/confidentiality. Route from the homepage: Why Arbitrum, Features, Confidentiality."),
    ("q2", "compliance", "I'm a compliance lead looking into a dedicated Arbitrum chain.",
     "What information can a dedicated Arbitrum chain export for compliance reporting?",
     "Blocked addresses and transaction activity.", "One of the two.",
     "Neither, or exports the page doesn't name stated as fact.",
     "/why-arbitrum/features/compliance, \"Real-Time Reporting\". Route from the homepage: Why Arbitrum, Features, Compliance."),
    ("q3", "performance", "I'm a developer looking into Arbitrum.",
     "Under high demand, how do Arbitrum's transaction prices compare with competing networks?",
     "17x less volatile and 15% lower.", "One of the two.",
     "No numbers (an answer about smoother or lower fees in general terms is Wrong, Nat 3 Nov), or wrong numbers. "
     "The 98% spike figure alongside the right numbers is fine; the live median price is not in the key.",
     "/why-arbitrum/features/performance. Route from the homepage: Why Arbitrum, Features, Performance."),
    ("q4", "usdg", "I'm a DeFi user looking into Arbitrum.",
     "If I supply USDG to vaults on Arbitrum One, which incentive programme rewards it, and what does its name stand for?",
     "DRIP, the DeFi Renaissance Incentive Program.", "DRIP without the name, or the name without DRIP.",
     "Another programme stated as the answer, or neither part.",
     "/products/usdg-on-arbitrum. Route from the homepage: Products, USDG on Arbitrum."),
    ("q5", "chains", "I'm a chain operator looking into Arbitrum.",
     "Which chains does Arbitrum show on its Launch a Chain page as part of its growing ecosystem?",
     "Plume Network, Corn, EDU Chain, Gravity Chain, Reya, ApeChain, Superposition, Blackbird.",
     "One to seven of the eight. Record the count (x of 8) on every run.",
     "None, or invented chains (extra or invented chains alongside real ones are logged, not penalised).",
     "/launch-chain, ecosystem logo section. Route from the homepage: Launch a Chain."),
]


def shared_rule(host, verb):
    # The shared grading rule, with the host and the verb ("fetched" or "opened in the browser").
    return (
        "SHARED GRADING RULE: Right is complete, correct and sourced. Partial is correct and sourced but "
        "incomplete, with nothing false in it. Wrong is anything false, even if the rest is right. Not found "
        f"is an answer with no source on {host} (it came from the model's memory, not the site), or the agent "
        "saying it couldn't find it. Every right answer must be checkable on a specific page: no key marks an "
        "agent on proving something doesn't exist. Any route the agent gives must be real and one the site "
        "itself presents for that purpose. Grade from the transcript against this key and rule only; do not "
        f"browse the site yourself. Score 10 if the final answer is right as defined above AND is supported by "
        f"a page on {host} that the agent successfully {verb} in this run. Score 5 if the answer is partial as "
        "defined above, with the same source requirement. Score 0 if the answer is wrong, not found or missing. "
        f"An answer that matches the key but has no supporting page on {host} that the agent {verb} counts as "
        "not found, because it came from memory, not the site."
    )


def variant(v, q):
    qid, slug, persona, question, right, partial, wrong, source = q
    host = HOSTS[v]
    if v == "live":
        verb = "opened in the browser"
        prompt = (
            f"{persona} Use the browser tools to open Arbitrum's website at https://{host}/ . Starting from "
            f"that homepage, find out: {question} Use only pages on {host} as your source: you can't search "
            "the web or open other sites, including Arbitrum's docs, blog or portal. Answer in a few sentences "
            "and give the URL of the page where you found each part of the answer. If you can't find the "
            "answer on the site, say so plainly."
        )
    else:
        verb = "fetched"
        prompt = (
            f"{persona} A copy of Arbitrum's website is at https://{host}/ . Starting from that homepage, "
            f"find out: {question} Use only pages on {host} as your source: you can't search the web or open "
            "other sites. Answer in a few sentences and give the URL of the page where you found each part of "
            "the answer. If you can't find the answer on the site, say so plainly."
        )
    key = (
        f"ANSWER KEY ({qid.upper()}, Nat): Right: {right} Partial: {partial} Wrong: {wrong} "
        f"Source, and route from the homepage (paths are on {host}): {source} {shared_rule(host, verb)}"
    )
    return {
        "name": v,
        "prompt": prompt,
        "judge": [
            {"check": key, "weight": 0.7},
            {"check": "Not confidently wrong: the final answer states nothing as fact that contradicts the "
                      "answer key above. Saying it could not find something scores 10. A wrong provider, "
                      "figure, firm or support route stated as fact scores 0.", "weight": 0.15},
            {"check": f"Honest sourcing: every URL the answer cites as a source is on {host} and was actually "
                      f"{verb} in this run. An invented URL, a third-party source, or no URL at all scores 0.",
             "weight": 0.15},
        ],
    }


if not QUESTIONS:
    sys.exit("No questions yet.")
here = os.path.dirname(os.path.abspath(__file__))
# The headless route was added after the first two; its scenarios are the browser ones under a new name.
for route, variants in (("fetch", ("a", "b")), ("browser", ("live",)), ("headless", ("live",))):
    out = os.path.join(here, "..", "axis", route, "scenarios")
    os.makedirs(out, exist_ok=True)
    for q in QUESTIONS:
        doc = {
            "name": f"AXIS pt III ({route}), {q[0].upper()}: {q[3]}",
            "prompt": "Template only: the variants carry the real prompts.",
            "judge": "Template only: the variants carry the real checks.",
            "variants": [variant(v, q) for v in variants],
        }
        path = os.path.join(out, f"{q[0]}-{q[1]}.json")
        with open(path, "w") as f:
            json.dump(doc, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print("wrote", os.path.relpath(path))
