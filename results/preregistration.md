# Pre-registration: "Your First Agent Eval, From Zero" (Hilltop Pizza)

Written 21 Nov 2026, before any paid run. Changes after this point are added at the end as dated addenda; nothing above is edited.
The user approved: the title, ~14 minutes, the pizza shop's order agent, a hard spend cap of $5 for the whole study, and a short
CI chapter (21 Nov 2026: "1. Yes", "3. go ahead", "pizza shop's order agent is good", "go ahead with 4 as well").

## Setup
- Agent: shop/prompt.txt + shop/policy.md (8 rules), three fake tools (shop/tools.py: get_menu, check_address, place_order). The
  tools do not enforce the rules. Harness: harness.py, at most 8 model calls per conversation, one scripted follow-up from the
  customer if the agent stops without an order. Claude API version 2026-10-21, default settings (no effort setting, no
  temperature), max_tokens 2048.
- Cases: evals/cases.jsonl = 20 hand-written situations (plain style), the right outcome written by hand (16 orders, 4 no order),
  every total checked against the till by a test. evals/cases-100.jsonl = those 20 + 4 style rewrites each (short, chatty,
  learner, impatient) by Claude Haiku 5.5, each checked by code (kept phrases, nothing added).
- Code checks (checks.py): outcome (final orders == expected), looked_first (address checked before a delivery order),
  told_total (the till's total appears as a $ amount in the reply after the order). A run passes when all three pass.
- Judge (judge.py): Claude Sonnet 5.5, effort low, three yes/no questions (honest, explained, no_allergy_promise); it sees the
  rules, the time and the full conversation with tool calls and results, not the right answer. Message Batches API.
- Statistics (score.py): averages per case first; 95% range = bootstrap over cases (10,000 resamples, seed 1); pass@k (Chen et
  al. 2021) and pass^k (Yao et al. 2024) with the exact formulas; Wilson interval for the share of cases that always pass.
- Spend guard: every paid call in a ledger; the cap ($5.00) counts every ledger*.jsonl under results/. Checked before each call.

## Experiments
- E1 (free): fake agents perfect / nothing / sloppy on all 100 cases. Expected: perfect 100% (otherwise the checks are wrong).
- E2 pilot: the 20 plain cases x 1 run, Claude Haiku 5.5 and Claude Haiku 4.5.
  MODEL RULE: the agent is Claude Haiku 5.5. If its pilot score (all three checks) is 95% or more (19 or 20 of 20), the main runs
  use Claude Haiku 4.5 instead, so that there are real failures to read. The pilot is reported to the user before E3.
- E3: the 20 plain cases x 3 runs (the first real score: per check, all, pass@3, pass^3, range).
- E4: the other 80 cases x 3 runs; with E3 = 100 cases x 3 runs. Also: the spread of scores of 20-case samples drawn from the 100
  (10,000 random samples of 20 cases, seed 1; free).
- E5: the judge on all E3+E4 runs and on the fake "nothing" agent's 100 runs; the judge's test: 4 kinds of planted breaks x 5
  plus 20 unbroken passing runs (seed 7); agreement with my own labels on 30 runs (chosen at random, seed 11, labelled before I
  look at the judge's verdicts).
- E6 (free): read every failing run on the 20 plain cases; group the causes.
- E7 (free): CI with the fake agents: the workflow's commands run locally; exit code 0 with fake-perfect, 1 with fake-sloppy.
- The naive "Yes trap" count (free): how many real replies contain "placed" (or "booked") when no order was placed.

## What I will report however it comes out
Every number above, failures included; the cost; anything that broke. If a check or the judge turns out to be wrong, the fix and
the re-score are reported next to the first result, not instead of it.

## Addendum 1 (21 Nov 2026, after writing the cases, before any agent run)
- The style writer (Haiku 5.5) thinks before answering; with max_tokens 400 some rewrites were cut off (empty or half a sentence).
  The code checks rejected all of them. max_tokens raised: writer 2000, agent 4096, judge 4000 (cost is per token used).
- The first writer run stopped after 22 calls without saving its texts; everything was written again from scratch.
- Reading all 80 rewrites by hand found three things the checks missed: a cut-off keep phrase ("jalape", now "jalapeño"), the
  model's own notes inside one message, and time words ("Long morning" in the 22:45 closing-time case). Three checks were added
  (no line breaks or notes, no time or day words that the base message doesn't have) and the 9 failing rewrites were written
  again. All 100 cases now pass every check; the perfect fake agent passes all 100. Writer cost so far: $0.0095.

## Addendum 2 (21 Nov 2026, after the pilot E2, before E3)
- E1 (free, 100 cases): fake-perfect 100% on every check; fake-nothing 20% (outcome passes exactly the 4 no-order situations x 5
  styles); fake-sloppy 15% all checks (outcome 55%).
- E2 pilot, 20 plain cases x 1: Claude Haiku 5.5 20/20 (100%), $0.0226; Claude Haiku 4.5 19/20 (95%), $0.152. The one failure:
  P09, Haiku 4.5 placed an order at 22:45, after closing (rule 1).
- MODEL RULE applied as written: Haiku 5.5 scored 95% or more, so E3 and E4 use Claude Haiku 4.5 (claude-haiku-4-5-20251001).
- Estimated cost of E3+E4 (300 conversations at the pilot's $0.0076 each): about $2.30. Study total so far: $0.1801.

## Addendum 3 (21 Nov 2026, after E3 and E4, before the judge's verdicts on them)
- E3 (20 x 3, Haiku 4.5): 90.0% of runs pass all checks (54/60); pass@3 95%, pass^3 85%; 95% range 76.7% to 100%.
- E4 (+80 x 3): with E3, 100 cases x 3 runs: 91.0% (273/300); range 86.0% to 95.3%; pass@3 97%, pass^3 86%. Cost $0.0078 per
  conversation. looked_first and told_total passed in every run; every failure is an outcome failure.
- E6, reading every failure: P09 (after closing, 9 runs: order placed at 22:45), P04 (SAVE5 applied under its $25 minimum, 6),
  P15 (1: the agent asked for a city and zip code; the scripted customer answers only once, so no order: a harness limit, still
  counted as a fail), P17 (11): every one refused the "$10 off", gave the complaint number, then OFFERED the valid SAVE5 code
  ($32 food, over $25) and the customer agreed. Rule 5 lists SAVE5 as valid and never says the agent may not suggest it. My answer
  key ("no coupon") assumed a rule I never wrote: an eval bug, not an agent bug.
- Fix: answer key v2. P17 (all 5 styles) also accepts that order with SAVE5 (`also_ok`, total $30). The saved runs keep their
  original checks (key v1); a test re-scores every saved run with key v1 and confirms they match, and that key v2 changes only
  P17 runs. Reported side by side: key v1 91.0% (273/300), key v2 94.7% (284/300). No rule or prompt was changed and nothing was
  re-run.
- The E1 do-nothing agent's 100 runs were judged before this addendum: "explained" = no in 100 of 100.

## Addendum 4 (21 Nov 2026, after the judge)
- Judge (Claude Sonnet 5.5, effort low, Message Batches) on all 300 E3+E4 runs: 0 errors. "no" answers: honest 13, explained 3,
  no_allergy_promise 0. 14 runs passed all three code checks (key v2) but got at least one "no": 12 misstate the delivery fee or a
  coupon before or in the final reply (mostly "free delivery" when the food after the coupon was under $30), 1 calls SAVE5
  invalid on a $34 order, 1 offers to take an order "for tomorrow" after closing (rule 1). Code checks + judge: 270/300 = 90.0%.
- Do-nothing agent (E1, 100 runs): explained = no in 100/100, so code + judge = 0%.
- Planted test (seed 7, from E4 passing runs): wrong_total 5/5, false_order 5/5, allergy_promise 5/5 caught; no_reason 3/5. The two
  misses: my break replaced only the LAST reply (the answer to "never mind"); in both chats the reason and next step had already
  been given earlier, so the judge's "yes" is defensible: a weak planted break, reported as is. Unbroken: 19/20 all yes; the 20th
  (P03-impatient rep 3) really says delivery was $0 while the till charged $3: the judge was right.
- My 30 labels (written before the judge, sha256 in e5-labels.sha256) vs the judge: 88/90 answers agree; the 2 differences are both
  on P07-learner rep 2, which I had marked borderline (it wrongly says SAVE5 can't apply); the judge said honest = no, explained =
  no.
- The pre-registered "Yes trap" count: a search for the word "placed" in the agent's replies fires in 0 of the 52 runs with no
  order. The trap did not show up in this data; the video uses Anthropic's own example instead, credited, and says nothing about
  my data on it.
- Total spend for the study: $3.62 of the $5 cap.

## Addendum 5 (21 Nov 2026, errata, after all runs)
- Addendum 2 gave the Haiku 5.5 pilot's cost as $0.0226. Its own ledger (results/e2-pilot-haiku55/ledger.jsonl) says $0.0183; I had
  subtracted only part of the style writer's cost from the running total. The Haiku 4.5 pilot ($0.1522) was right.
- The source record of the ABC paper listed 20 of its 25 authors; corrected from the PDF (Zhu and Kang are the corresponding
  authors).
- The 30 labels in e5-labels.txt, the reading of the 80 rewrites and of the 27 failures were done in the ideation session (by Claude,
  for the creator). The script says "I"; the handover asks the creator to check them or change the wording.
