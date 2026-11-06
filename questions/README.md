# The five questions

[Natalie Gent](https://nataliegent.com) wrote five questions someone building on Arbitrum might ask. Each one is answered on arbitrum.io and nowhere in Arbitrum's docs. She wrote the answer keys, and we marked every run by hand against them and the shared grading rule below.

The exact files the agents ran are in `axis/fetch/scenarios/`, `axis/browser/scenarios/` and `axis/headless/scenarios/`. `scripts/make-scenarios.py` writes them from the question list inside it, and `scripts/server-runs.py` reuses the browser prompts for the server-side fetch. We've lightly edited the keys below for reading; the scenario files hold the exact text that ran, including "Nat" for Natalie.

## Questions and answer keys

### Q1. Confidentiality examples

- **Question:** Which companies does Arbitrum name as examples of confidentiality on Arbitrum?
- **Persona in the prompt:** I'm a fintech product lead looking into Arbitrum.
- **Right:** Fairblock, Renegade and Fhenix.
- **Partial:** One or two of the three.
- **Wrong:** None of the three, or other companies stated as Arbitrum's examples.
- **Where the answer is:** /why-arbitrum/features/confidentiality. Route from the homepage: Why Arbitrum, Features, Confidentiality.

### Q2. Compliance exports

- **Question:** What information can a dedicated Arbitrum chain export for compliance reporting?
- **Persona in the prompt:** I'm a compliance lead looking into a dedicated Arbitrum chain.
- **Right:** Blocked addresses and transaction activity.
- **Partial:** One of the two.
- **Wrong:** Neither, or exports the page doesn't name stated as fact.
- **Where the answer is:** /why-arbitrum/features/compliance, "Real-Time Reporting". Route from the homepage: Why Arbitrum, Features, Compliance.

### Q3. Fees under heavy demand

- **Question:** Under high demand, how do Arbitrum's transaction prices compare with competing networks?
- **Persona in the prompt:** I'm a developer looking into Arbitrum.
- **Right:** 17x less volatile and 15% lower.
- **Partial:** One of the two.
- **Wrong:** Wrong numbers, or no numbers: an answer that only says fees are lower or smoother, with no numbers, is Wrong. The 98% spike figure alongside the right numbers is fine; the live median price is not in the key.
- **Where the answer is:** /why-arbitrum/features/performance. Route from the homepage: Why Arbitrum, Features, Performance.

### Q4. USDG rewards

- **Question:** If I supply USDG to vaults on Arbitrum One, which incentive programme rewards it, and what does its name stand for?
- **Persona in the prompt:** I'm a DeFi user looking into Arbitrum.
- **Right:** DRIP, the DeFi Renaissance Incentive Program.
- **Partial:** DRIP without the name, or the name without DRIP.
- **Wrong:** Another programme stated as the answer, or neither part.
- **Where the answer is:** /products/usdg-on-arbitrum. Route from the homepage: Products, USDG on Arbitrum.

### Q5. Chains on the Launch a Chain page

- **Question:** Which chains does Arbitrum show on its Launch a Chain page as part of its growing ecosystem?
- **Persona in the prompt:** I'm a chain operator looking into Arbitrum.
- **Right:** Plume Network, Corn, EDU Chain, Gravity Chain, Reya, ApeChain, Superposition, Blackbird.
- **Partial:** One to seven of the eight. Record the count (x of 8) on every run.
- **Wrong:** None, or invented chains (extra or invented chains alongside real ones are logged, not penalised).
- **Where the answer is:** /launch-chain, ecosystem logo section. Route from the homepage: Launch a Chain.

## Shared grading rule

The same rule applies to every question. In the scenario files, `the site` is the host the run used (arbitrum.io, or one of our copies), and `fetched` reads `opened in the browser` for the browser routes. We marked by hand, so the scoring lines at the end were our guide, not a grader's prompt.

> SHARED GRADING RULE: Right is complete, correct and sourced. Partial is correct and sourced but incomplete, with nothing false in it. Wrong is anything false, even if the rest is right. Not found is an answer with no source on the site (it came from the model's memory, not the site), or the agent saying it couldn't find it. Every right answer must be checkable on a specific page: no key marks an agent on proving something doesn't exist. Any route the agent gives must be real and one the site itself presents for that purpose. Grade from the transcript against this key and rule only; do not browse the site yourself. Score 10 if the final answer is right as defined above AND is supported by a page on the site that the agent successfully fetched in this run. Score 5 if the answer is partial as defined above, with the same source requirement. Score 0 if the answer is wrong, not found or missing. An answer that matches the key but has no supporting page on the site that the agent fetched counts as not found, because it came from memory, not the site.

Not found takes precedence over the Wrong cells: if the agent says it couldn't find the answer, we mark Not found even when the answer also states something false. We record any false statement in the `false_statement` field of results/marks.json.

Each scenario also carries two guard checks, weighted 0.15 each against the key's 0.7:

> Not confidently wrong: the final answer states nothing as fact that contradicts the answer key above. Saying it could not find something scores 10. A wrong provider, figure, firm or support route stated as fact scores 0.

> Honest sourcing: every URL the answer cites as a source is on the site and was actually fetched in this run. An invented URL, a third-party source, or no URL at all scores 0.

## Prompts per route

Every route got the same persona and question inside a short frame. Only the sentence about tools changes. Here is Q1 on each route, word for word.

**Direct fetch, bot check on (copy A).** `{COPY_A}` stands for our private copy's hostname.

> I'm a fintech product lead looking into Arbitrum. A copy of Arbitrum's website is at https://{COPY_A}/ . Starting from that homepage, find out: Which companies does Arbitrum name as examples of confidentiality on Arbitrum? Use only pages on {COPY_A} as your source: you can't search the web or open other sites. Answer in a few sentences and give the URL of the page where you found each part of the answer. If you can't find the answer on the site, say so plainly.

**Direct fetch, bot check off (copy B).** The same, on `{COPY_B}`.

> I'm a fintech product lead looking into Arbitrum. A copy of Arbitrum's website is at https://{COPY_B}/ . Starting from that homepage, find out: Which companies does Arbitrum name as examples of confidentiality on Arbitrum? Use only pages on {COPY_B} as your source: you can't search the web or open other sites. Answer in a few sentences and give the URL of the page where you found each part of the answer. If you can't find the answer on the site, say so plainly.

**Visible browser and headless browser (live).**

> I'm a fintech product lead looking into Arbitrum. Use the browser tools to open Arbitrum's website at https://arbitrum.io/ . Starting from that homepage, find out: Which companies does Arbitrum name as examples of confidentiality on Arbitrum? Use only pages on arbitrum.io as your source: you can't search the web or open other sites, including Arbitrum's docs, blog or portal. Answer in a few sentences and give the URL of the page where you found each part of the answer. If you can't find the answer on the site, say so plainly.

**Server-side fetch (live).** The browser prompt with one sentence swapped.

> I'm a fintech product lead looking into Arbitrum. Use your web fetch tool to read Arbitrum's website at https://arbitrum.io/ . Starting from that homepage, find out: Which companies does Arbitrum name as examples of confidentiality on Arbitrum? Use only pages on arbitrum.io as your source: you can't search the web or open other sites, including Arbitrum's docs, blog or portal. Answer in a few sentences and give the URL of the page where you found each part of the answer. If you can't find the answer on the site, say so plainly.

## What each route was allowed to use

- **Direct fetch:** Claude Code's WebFetch, allowed only on the run's own copy. Web search and the shell were denied.
- **Visible and headless browser:** Playwright MCP only, in a fresh browser profile per run. WebFetch, web search and the shell were denied. Arbitrum's other sites (docs, blog, portal, status, support, openhouse, jobs, bridge) were blocked in the browser, so the agent stayed on arbitrum.io as the copies do.
- **Server-side fetch:** Anthropic's server-side `web_fetch` tool (`web_fetch_20260209`), allowed only on arbitrum.io, up to 10 fetches a question. No web search.
