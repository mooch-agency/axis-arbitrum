# Can an AI agent read arbitrum.io?

arbitrum.io sits behind Cloudflare's bot check, a screen that tries to tell people from bots. We wanted to know what that means for someone who sends an AI agent to research Arbitrum. So we asked an agent five questions someone building on Arbitrum might ask, and told it to answer from the site alone.

This repo holds the method, data and scripts behind our write-up on LinkedIn, [How agent-friendly is your website?](https://www.linkedin.com/pulse/how-agent-friendly-your-website-tahi-gichigi-4dspe)

## The short version

<!-- summarise:headline:start -->
On the live site, only the visible browser got through: 4 of 5 right. The headless browser and server-side fetch got 0 of 5. On our private copies, direct fetch got 0 of 5 with the bot check on and 5 of 5 with it off.
<!-- summarise:headline:end -->

## What we did

- **The agent.** Claude Sonnet 5.5 (`claude-sonnet-5-5`) on every run. Web search was off, so it had to use the site itself.
- **The questions.** [Natalie Gent](https://nataliegent.com) wrote five questions, each answered on arbitrum.io and nowhere in Arbitrum's docs. She wrote the answer keys. We marked every answer by hand. See [questions/](questions/README.md).
- **The runs.** Five setups, five questions, one run each: 25 runs, all on 4 November 2026.

### Bot check on, bot check off

We saved arbitrum.io's pages and put up two private copies on Vercel, a web host.

- **Copy A has the bot check on.** It sends what the real site sends to any program that isn't a full browser: a "403 Forbidden" error and Cloudflare's "Just a moment..." page. Like the real site, it lets robots.txt through, the file that tells bots what they may read.
- **Copy B has the bot check off.** Same pages, served normally.

The copies let us switch the check off to see what an agent gets without it. One setting, read by one small file ([copy/middleware.js](copy/middleware.js)), is the only difference between them.

### Four routes in

An agent can reach a web page in four main ways. We tried all four.

1. **Direct fetch.** The agent asks for the page's text, with no browser. We used Claude Code's built-in WebFetch tool. It hands every page to a second, smaller model (Claude Haiku 5.5) to summarise before the agent reads it. We ran it on both copies.
2. **Server-side fetch.** The same idea, but the request comes from the AI company's computers, not ours. We used the Claude API with Anthropic's server-side `web_fetch` tool. Live site.
3. **Headless browser.** A real Chrome browser with no window, driven by the agent through Playwright MCP, a free tool that lets an AI agent control a browser. It ran on our own computer. Live site.
4. **Visible browser.** The same, with a real Chrome window open on a computer that stayed unlocked. Live site.

AXIS is Netlify's free tool for running agents on set questions and recording each run.

| Setup | Route | Site | Run with |
| --- | --- | --- | --- |
| Direct fetch, bot check on | Claude Code WebFetch | Copy A | AXIS + Claude Code |
| Headless browser (live) | Playwright MCP, headless Chrome | arbitrum.io | AXIS + Claude Code |
| Server-side fetch (live) | Claude API `web_fetch` tool | arbitrum.io | `scripts/server-runs.py` |
| Visible browser (live) | Playwright MCP, visible Chrome | arbitrum.io | AXIS + Claude Code |
| Direct fetch, bot check off | Claude Code WebFetch | Copy B | AXIS + Claude Code |

## The five questions

1. Which companies does Arbitrum name as examples of confidentiality on Arbitrum? **Right:** Fairblock, Renegade and Fhenix.
2. What information can a dedicated Arbitrum chain export for compliance reporting? **Right:** blocked addresses and transaction activity.
3. Under high demand, how do Arbitrum's transaction prices compare with competing networks? **Right:** 17x less volatile and 15% lower.
4. If I supply USDG to vaults on Arbitrum One, which incentive programme rewards it, and what does its name stand for? **Right:** DRIP, the DeFi Renaissance Incentive Program.
5. Which chains does Arbitrum show on its Launch a Chain page as part of its growing ecosystem? **Right:** Plume Network, Corn, EDU Chain, Gravity Chain, Reya, ApeChain, Superposition and Blackbird.

Each answer counts only if the agent got it from a page on the site. The full keys, with Partial and Wrong, the shared grading rule and the exact prompts for each route, are in [questions/README.md](questions/README.md). The scenario files keep "Nat" in their answer-key lines, as they ran.

## Results

<!-- summarise:results:start -->
| Setup | Right | Main-model tokens | Seconds | Tool calls | Cost |
| --- | --- | --- | --- | --- | --- |
| Direct fetch, bot check on | 0/5 | 49k | 8.6 | 2.0 | 3.0 cents |
| Headless browser (live) | 0/5 | 100k | 25.3 | 5.6 | 4.9 cents |
| Server-side fetch (live) | 0/5 | 45k | 28.1 | 14.6 | 10.3 cents |
| Visible browser (live) | 4/5 | 118k | 21.2 | 7.0 | 6.9 cents |
| Direct fetch, bot check off | 5/5 | 70k | 32.2 | 3.4 | 4.8 cents |

Every number is a mean per question over that setup's 5 runs, except Right, which is a count. No answer was marked Partial or Wrong. Every answer that wasn't Right was Not found: the agent said it couldn't find the answer. The shared rule marks that Not found even if the answer also says something false. One did: on the visible browser's Q4 run, the agent said the site doesn't say which incentive programme rewards USDG, but the site's /products/usdg-on-arbitrum page names DRIP. The other 15 misses stated nothing false.
<!-- summarise:results:end -->

What the columns mean:

- **Right:** answers we marked Right against the key.
- **Main-model tokens:** tokens are the chunks of text a model reads and writes; you pay per token. This column counts the agent's own model only, Claude Sonnet 5.5, counting input, output and prompt-cache reads and writes. Direct fetch's page reader is not in this column (see below).
- **Seconds:** clock time, start to finish, for the whole run, as AXIS measured it. For the server-side fetch, our script's timer around the API calls.
- **Tool calls:** every tool call the agent made. Claude Code runs include one call to load the tools. Server-side fetch counts its fetches plus the code its fetch tool runs to filter pages.
- **Cost:** what the run cost at list prices, page reader included.

<!-- summarise:findings:start -->
- **Visible browser against direct fetch with the bot check off.** The browser used 70% more main-model tokens (118k against 70k) and cost 44% more a question. Like for like, on the 4 questions both got right (Q1, Q2, Q3 and Q5), the browser used 33% more main-model tokens and cost 19% more. Most of the 70% comes from the browser's failed Q4 run, which used 222k tokens. It took 7 tool calls against 3.4, and it was faster: 21.2 seconds against 32.2.
- **Why direct fetch was slower.** WebFetch hands every page to a second, smaller model (Claude Haiku 5.5) to summarise before the agent reads it. With the bot check off, that page reader took 21.4 of the 32.2 seconds. All other tool time, fetching included, came to 0.9 seconds.
- **Counting the page reader's tokens too**, direct fetch with the bot check off used 104k tokens a question, and the visible browser used 14% more.
- **Server-side fetch** made 10 fetches a question, the most we allowed; that cap is the "usage limit" some of its answers mention. The tool refused 8 of them, because the agent had guessed addresses it hadn't seen linked; the others re-read the homepage. The other 4.6 tool calls a question were the tool running code to filter what it fetched.
<!-- summarise:findings:end -->

Every run, with its mark, our reason, tokens, cost, time and the agent's final answer, is in [results/runs.csv](results/runs.csv). The means above are in [results/summary.csv](results/summary.csv). Both, and every number in this section and the next, come from `scripts/summarise.py`.

## Costs

<!-- summarise:costs:start -->
All 25 runs cost **$1.49** at Anthropic's list prices.

| Setup | Total | A question |
| --- | --- | --- |
| Direct fetch, bot check on | $0.15 | 3.0 cents |
| Headless browser (live) | $0.24 | 4.9 cents |
| Server-side fetch (live) | $0.52 | 10.3 cents |
| Visible browser (live) | $0.35 | 6.9 cents |
| Direct fetch, bot check off | $0.24 | 4.8 cents |

Basis: Claude Sonnet 5.5 at $2.00 per million input tokens, $10.00 output, $0.20 cache reads and $2.50 5-minute cache writes; Claude Haiku 5.5 (the page reader) at $0.10 input and $0.50 output. Token counts come from the usage in every API response. The server-side web fetch tool and the code it runs had no charge of their own at the time. Nothing here is a grader's cost: we marked by hand.
<!-- summarise:costs:end -->

## Caveats

- **Small sample.** One run per question per setup. The numbers are means of five runs, and a second run could differ. Treat this as a demonstration, not a study.
- **Tokens are the main model only** in the results table. Direct fetch also spends tokens in its page reader; those are in `reader_tokens` in runs.csv.
- **The page reader's time is Claude Code's design.** Other tools that fetch pages may not summarise each page with a second model, so they may be faster or slower than our direct fetch.
- **It's specific to Claude Code and Claude.** Direct fetch and both browsers ran in Claude Code 2.1.318, all with Claude Sonnet 5.5. Other agents and models fetch, browse and give up differently.
- **The site may have changed.** We ran everything on 4 November 2026. arbitrum.io, its Cloudflare settings and the tools we used may all have changed since.
- **The copies aren't perfect.** Copy A challenges every request except robots.txt, while live serves a few static files without the challenge. The copies don't host images, styles or scripts, so a person sees an unstyled page; agents read the HTML. Vercel adds a small toolbar script to every page on both copies.
- **One marker.** We marked every answer ourselves, against Natalie's keys. The reasons are in runs.csv and [results/marks.json](results/marks.json), so you can check them.
- **Timing is noisy.** Seconds depend on network and API load on the day.

## How to rerun

You need macOS (the batch script uses `caffeinate` and BSD `date`), Node with pnpm, Python 3.11, Google Chrome and Claude Code 2.1.318 on your PATH. The copy routes also need the `vercel` CLI. Keys come from environment variables only.

1. **Install.** `pnpm install` pins AXIS 1.21.0 and Playwright MCP 0.0.83.
2. **Scenarios.** They're already in `axis/*/scenarios/`. To change a question, edit `scripts/make-scenarios.py` and run `python3 -I scripts/make-scenarios.py`.
3. **Live routes (need only an Anthropic API key).**
   - Replace `{REPO}` in `axis/browser/axis.config.json` and `axis/headless/axis.config.json` with this repo's absolute path, e.g. `sed -i '' "s#{REPO}#$PWD#g" axis/browser/axis.config.json axis/headless/axis.config.json`.
   - `export ANTHROPIC_API_KEY=...`
   - Visible browser: `scripts/run-batch.sh browser run1 1`. Keep the computer unlocked: a Chrome window opens for each run.
   - Headless browser: `scripts/run-batch.sh headless run1 1`.
   - Server-side fetch: `python3 -m venv .venv && .venv/bin/pip install anthropic==2.5.0`, then `.venv/bin/python -I scripts/server-runs.py runs/server-run1`. Use a venv: `python3 -I` ignores packages installed with `pip install --user`. The script keeps only the agent's last text block as its answer. We fixed that after the runs and rebuilt the answers offline from the saved responses with `--from-raw`, so no test was rerun.
   - Optional: set `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` to trace runs, which `scripts/time-breakdown.py` needs for the page-reader timing.
4. **Copy routes (need your own copies).** We don't ship arbitrum.io's pages, so build your own: save the pages you need from a browser that passes the bot check, put them in a folder with the files in `copy/`, add a `challenge.js` (see the comment at the top of `copy/middleware.js`), and deploy it twice to Vercel as previews, once with `AXIS_VARIANT=a` and once with `AXIS_VARIANT=b`. Turn off Vercel's Deployment Protection for previews, or the agent hits Vercel's login instead of your copy. Then replace `{COPY_A}` and `{COPY_B}` in `axis/fetch/axis.config.json`, run `COPY_A_HOST=... COPY_B_HOST=... python3 -I scripts/make-scenarios.py`, and run `scripts/run-batch.sh fetch run1 1` with `COPY_A_URL`, `COPY_B_URL` and `COPY_PROJECT_DIR` set.

   Our copies held these pages, saved from live arbitrum.io on 2 November 2026 (arbitrum.io's sitemap plus two footer pages), with links rewritten to stay on the copy. They also served robots.txt and redirected /arbitrum-101 to the homepage, as live does.

   ```
   /
   /brand-kit
   /build-app
   /build-app/contact
   /contact
   /developer-tos
   /integrations
   /launch-chain
   /launch-chain/contact
   /press
   /press/contact
   /privacy
   /products/pga-and-fast-feed
   /products/usdg-on-arbitrum
   /solutions/consumer
   /solutions/consumer/contact
   /solutions/finance
   /solutions/finance/contact
   /solutions/gaming
   /solutions/gaming/contact
   /talks
   /tos
   /tos/reputation-scoring
   /why-arbitrum/features/compliance
   /why-arbitrum/features/confidentiality
   /why-arbitrum/features/customization
   /why-arbitrum/features/performance
   ```
5. **Extract and summarise.**
   - `COPY_A_HOST=... COPY_B_HOST=... python3 -I scripts/fetch-runs.py axis/fetch/.axis/reports/<report> runs/fetch-run1`
   - `python3 -I scripts/browser-runs.py axis/browser/.axis/reports/<report> runs/browser-run1 --bodies runs/browser-run1/api-bodies` (and the same for headless)
   - `python3 -I scripts/time-breakdown.py runs/time-breakdown.json fetch <project> <start> <end>` (and `browser`), if you traced
   - Mark your runs in `results/marks.json` first (one entry per run), then `COPY_A_HOST=... COPY_B_HOST=... python3 -I scripts/build-runs-csv.py`. It skips any route you didn't run.
   - `python3 -I scripts/summarise.py`

Your `runs/` folder will hold the pages the agent read, raw API bodies and transcripts. `.gitignore` keeps it out of git; keep it private.

## What's in this repo

```
README.md            this page
questions/README.md  the five questions, answer keys, grading rule and prompts
results/runs.csv     one row per run (25)
results/summary.csv  means per setup, written by scripts/summarise.py
results/marks.json   our hand marks and reasons
axis/                AXIS configs and scenarios for the three Claude Code setups
copy/                how copy A and copy B work: middleware.js, vercel.json, robots.txt, package.json
scripts/
  make-scenarios.py  writes the scenarios from the question list
  run-batch.sh       runs one Claude Code setup end to end (calls run-clean.sh)
  run-clean.sh       runs AXIS in a clean environment and keeps the raw API bodies
  server-runs.py     the server-side fetch route, straight on the Claude API
  fetch-runs.py      per-run facts for direct fetch, with a check against the copies' request logs
  browser-runs.py    per-run facts for the two browser setups
  time-breakdown.py  where the time went, from LangSmith traces
  build-runs-csv.py  joins all of the above and the marks into results/runs.csv
  summarise.py       rebuilds summary.csv and the numbers in this README from runs.csv
  common.py          shared transcript reading and list prices
```

## What we left out, and why

- **arbitrum.io's pages.** The copies hold Arbitrum's content, which isn't ours to publish. Short quotes survive inside the agents' answers in runs.csv.
- **Cloudflare's challenge page.** Copy A served live's 403 page word for word from a file called `challenge.js`. That page is Cloudflare's, so we describe it instead: an HTML page titled "Just a moment...", which runs Cloudflare's JavaScript check, sent with status 403 and the header `cf-mitigated: challenge`.
- **Raw API bodies, AXIS transcripts and run logs.** They hold the full text of every page the agent read, plus details of our machine. runs.csv keeps the numbers and the final answers.
- **The copies' addresses and request logs.** The copies are unlisted previews. In this repo their hostnames are `{COPY_A}` and `{COPY_B}`.
- **Tracing data.** Our LangSmith traces gave the page-reader timing. The timing is in runs.csv; the traces aren't.
- **An extra check.** We also pointed the server-side fetch at copy B once, to see whether it strips links from every site. It didn't. That check isn't one of the 25 runs, so it isn't in the data.

## Licences

- **Code** (`scripts/`, `copy/`, `axis/`, `package.json`): MIT. See [LICENSE](LICENSE).
- **Data and docs** (`results/`, `questions/`, this README): CC BY 4.0. See [LICENSE-DATA](LICENSE-DATA).
- The question text appears in both: under MIT in the code folders (`scripts/make-scenarios.py`, `axis/*/scenarios/`) and under CC BY 4.0 in `questions/`.
- Text quoted from arbitrum.io in the agents' answers belongs to its owners. We're not affiliated with Arbitrum, Offchain Labs or Cloudflare.

## Credit

We ran the Claude Code setups with [AXIS](https://www.npmjs.com/package/@netlify/axis) by Netlify (`@netlify/axis` 1.21.0, under the "MIT License, Copyright (c) 2026 Netlify"), which runs agents against scenarios and records every run. The browsers ran through [Playwright MCP](https://www.npmjs.com/package/@playwright/mcp) by Microsoft (`@playwright/mcp` 0.0.83, Apache 2.0 licence). Thank you to both teams.
