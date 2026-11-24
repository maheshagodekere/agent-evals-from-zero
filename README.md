# AI Evals Hands-On: Your First Agent Eval, From Zero

The code and every saved run behind the video *AI Evals Hands-On: Your First Agent Eval, From Zero* on
[my YouTube channel](https://www.youtube.com/@maheshagodekere).

An agent eval has five parts: **a case** (one test, as data), **a harness** (the code that runs the agent's tool loop), **a trace**
(everything that happened), **graders** (checks that read the trace), and **a score** over many cases and many runs. This repo
builds all five from zero, for a small agent everyone understands: the order assistant of a made-up pizza shop, Hilltop Pizza.
Python standard library only. Replay all saved runs and fake agents locally; bring your own API key only for live model runs.

## Contents

1. [Quick start (replay saved runs & fake agents)](#1-quick-start-replay-saved-runs--fake-agents)
2. [What is inside](#2-what-is-inside)
3. [The five parts](#3-the-five-parts)
4. [The experiment and its results](#4-the-experiment-and-its-results)
5. [Run it with a real model](#5-run-it-with-a-real-model)
6. [Make it your own](#6-make-it-your-own)
7. [Evals in CI](#7-evals-in-ci)
8. [Command reference](#8-command-reference)
9. [Data formats](#9-data-formats)
10. [Tests](#10-tests)
11. [Honest limits](#11-honest-limits)
12. [Sources](#12-sources)
13. [License](#13-license)

## 1. Quick start (replay saved runs & fake agents)

```sh
git clone https://github.com/maheshagodekere/agent-evals-from-zero.git
cd agent-evals-from-zero

python3 replay.py case P09                                   # one case: a line of JSON
python3 replay.py fake P11 --agent nothing                   # a fake agent that does nothing... and passes
python3 replay.py conv results/e3-haiku45-20x3 P09 --rep 1   # a saved real conversation and its checks
python3 replay.py eval results/e3-haiku45-20x3               # a saved eval: 20 cases x 3 runs, then the score
python3 run_eval.py --model fake-perfect                     # run the eval live with the fake perfect agent
python3 -m unittest discover -s tests -t .                   # the tests
```

Python 3.10 or newer. Nothing to install (`requirements.txt` is empty on purpose).

## 2. What is inside

| File | What it is |
|---|---|
| `shop/policy.md` | The shop's 8 rules: the agent's one-page "policy". |
| `shop/prompt.txt` | The system prompt: the time "now" and the rules. |
| `shop/menu.json` | Prices, delivery streets, fees. |
| `shop/tools.py` | The three fake tools (`get_menu`, `check_address`, `place_order`) and the till. They do **not** enforce the rules, on purpose. |
| `evals/make_base_cases.py` | The 20 hand-written cases, with the right outcome written by hand. Writes `evals/cases.jsonl`. |
| `evals/make_styles.py` | Rewrites each case's message in 4 more styles with Claude Haiku 5.5, checked by code. Writes `evals/cases-100.jsonl`. |
| `harness.py` | The harness: runs the agent's tool loop on one case and records the trace (about 40 lines). |
| `model.py` | Claude through the API (with a spend cap), and three fake agents: `perfect`, `nothing`, `sloppy`. |
| `checks.py` | Three code checks: `outcome`, `looked_first`, `told_total`. |
| `judge.py` | An AI judge for what code can't check well (three yes/no questions), and its own test with planted mistakes. |
| `run_eval.py` | Runs many cases x many runs, saves everything, prints the score; `--min-score` for CI. |
| `score.py` | Pass rates, pass@k, pass^k, a 95% range (bootstrap over cases), Wilson intervals. |
| `analyze.py` | Every number in the video, from the saved runs. Writes `results/numbers.json`. |
| `replay.py` | Replays saved runs in the terminal. No key, no cost. |
| `results/` | Every run I made, with its trace, checks, cost and ledger; `preregistration.md` (written before running, with dated addenda). |
| `.github/workflows/evals.yml` | The CI workflow (section 7). |
| `tests/` | Tests that need no key. |

## 3. The five parts

1. **The case** is one line of JSON: the time "now", the customer's message, one scripted follow-up, and the right outcome (the
   order that should exist after the run, or none), written by hand from the rules. `python3 replay.py case P03`.
2. **The harness** (`harness.py`) sends the message and the tools to the model. The model never runs a tool; it asks for one. The
   harness runs it on a fresh fake shop, sends the result back, and repeats until the agent replies in plain text (8 model calls
   at most). If the agent stops without an order, the simulated customer answers once with the case's follow-up.
3. **The trace** is everything that happened: messages, tool calls, tool results. Saved in `runs.jsonl`.
4. **The graders.** Code first (`checks.py`): the *outcome* (are the shop's orders exactly the expected ones?), the *process*
   (was the address checked before a delivery order?), the *reply* (did the agent tell the till's total?). Then an AI judge
   (`judge.py`) for what code can't check well: is the reply honest, does it explain a "no", does it avoid allergy promises?
5. **The score** (`score.py`): every case run several times; averages per case first; pass@k (at least one of k runs passes) and
   pass^k (all k pass); a 95% range by resampling cases.

## 4. The experiment and its results

Everything below ran on 21 November 2026 (Claude API version 2026-10-21) and is saved in `results/`. `python3 analyze.py`
recomputes every number from the saved runs into `results/numbers.json`. The plan was written before running, in
`results/preregistration.md`, with five dated addenda for what changed and why.

| Step | What | Result | Cost |
|---|---|---|---|
| E1 | The fake agents on all 100 cases | perfect 100% · do-nothing **20%** · sloppy 15% | $0 |
| E2 | Pilot: 20 cases x 1 run | Claude Haiku 5.5: 20 of 20 · Claude Haiku 4.5: 19 of 20 | $0.17 |
| E3 | Claude Haiku 4.5, 20 cases x 3 runs | **90.0%** of runs pass (54/60) · pass@3 95% · pass^3 85% · 95% range 76.7% to 100% | $0.48 |
| E4 | + 80 rewritten cases x 3 = 100 x 3 | **91.0%** (273/300) · range 86.0% to 95.3% · pass@3 97% · pass^3 86% | $1.85 |
| E4 | 10,000 random sets of 20 cases from the 100 | scores from 70% to 100% (same agent, same runs) | $0 |
| E6 | Reading all 27 failures | 9 orders after closing · 6 SAVE5 under its $25 minimum · 1 harness limit (asked for a zip code; the scripted customer answers once) · 11 my answer key (P17: the agent offered a valid coupon the rules allow) | $0 |
| E6 | Answer key v2 (P17 fixed, nothing re-run) | **94.7%** (284/300) · range 90.7% to 98.0% · pass@3 98% · pass^3 91% | $0 |
| E5 | AI judge (Claude Sonnet 5.5) on the 300 runs | 14 runs passed every code check but told the customer something false (mostly the delivery fee) · code + judge 90.0% (270/300) · do-nothing agent with the judge: **0%** | $1.11 |
| E5 | Testing the judge | planted mistakes caught 18 of 20 (the 2 misses were weak breaks of mine) · untouched good runs 19 of 20 (the 20th really was wrong) · my labels on 30 runs: 88 of 90 answers agree | in E5 |
| E7 | CI with the fake agents | perfect: exit code 0 · sloppy: exit code 1 ("15.0% is below the minimum 100.0%") | $0 |

The whole study cost **$3.62** (the Haiku 5.5 style rewrites $0.01 included), under a hard cap of $5.

## 5. Run it with a real model

The key comes from the environment variable `ANTHROPIC_API_KEY` (or, on a Mac, the Keychain item `anthropic-api`). It is never
printed. Every paid call is written to a ledger, and `--max-cost` stops the run before the total of all ledgers in `--out` passes
the cap (default $1.00).

```sh
export ANTHROPIC_API_KEY=...        # your key
python3 run_eval.py --model claude-haiku-5-5 --runs 1                 # 20 cases, about $0.02
python3 run_eval.py --model claude-haiku-5-5 --cases evals/cases-100.jsonl --runs 3 --max-cost 1   # about $0.35
python3 score.py runs/claude-haiku-5-5-cases-100-x3
```

What my runs cost per conversation: Claude Haiku 5.5 about $0.001, Claude Haiku 4.5 about $0.008, and one Claude Sonnet 5.5 judge
verdict about $0.0025 through the Message Batches API (half price). Prices: Anthropic's pricing page, read 19 Nov 2026 (`model.py`).

Your numbers will differ a little from mine: the same model can answer differently each time, and models change.

## 6. Make it your own

Change three things and the rest works as it is:

1. **The rules and the tools:** `shop/policy.md`, `shop/prompt.txt`, `shop/tools.py` (keep `Shop.run(name, args)` and a list of
   what the agent changed, like `orders`).
2. **The cases:** `evals/make_base_cases.py` (the message, the follow-up, the right end state).
3. **The checks:** `checks.py` (compare the end state; add a process check if order matters).

Then: run `fake-perfect` first (it must score 100%, or your checks are wrong), `fake-nothing` second (see what doing nothing
scores), then a real model on 20 cases, then read every failure before you change anything.

## 7. Evals in CI

`.github/workflows/evals.yml` has two jobs:

- **free**, on every pull request: the tests, and the fake perfect agent must score 100% on all 100 cases. It catches a change
  that breaks the harness or the checks. No key, no cost.
- **real**, only when a maintainer adds the label `run-evals`, and never for pull requests from forks (GitHub doesn't give
  secrets to those): 20 cases x 1 run with Claude Haiku 5.5, at most $0.50, and the job fails below 85%. A threshold, not "every
  run must pass": with 60 runs that each pass 99% of the time, "all must pass" turns red about 45% of the time with nothing wrong
  (1 - 0.99^60).

The key goes in the repository's secrets as `ANTHROPIC_API_KEY`.

## 8. Command reference

```text
run_eval.py  --model M  --cases FILE  --runs N  --out DIR  --name NAME  --max-cost USD  --workers N
             --only ID...  --styles STYLE...  --min-score 0.85  --quiet
judge.py     RUN_FOLDER  [--planted]  --out DIR  --max-cost USD
score.py     RUN_FOLDER
replay.py    case ID | conv RUN_FOLDER ID [--rep N] | eval RUN_FOLDER [--style ...] | fake ID [--agent perfect|nothing|sloppy]
             [--delay SECONDS] [--color]
analyze.py
evals/make_base_cases.py
evals/make_styles.py --out DIR --max-cost USD
```

## 9. Data formats

- **A case** (`evals/cases*.jsonl`): `id`, `title`, `style`, `now`, `now_text`, `message`, `follow_up`, `expected` (an order or
  `null`), `expected_total`, `why` (the rule behind the right answer), `asked` (what the customer literally asked for, used by the
  sloppy fake), `keep`/`forbid` (for the style checker), `address_notes` (P16 only).
- **A run** (`results/<run>/runs.jsonl`): `case`, `rep`, `style`, `model`, `checks`, `trace` (a list of `customer`, `agent` and
  `tool` steps; a tool step has `name`, `input`, `result`), `orders` (the shop's end state), `turns`, `cost`, `usage`, `secs`.
- **A ledger** (`results/**/ledger*.jsonl`): one line per paid call, with the usage and the cost in dollars.

## 10. Tests

`python3 -m unittest discover -s tests -t .` checks: every hand-written total against the till; that the tools don't enforce the
rules; the address and order comparisons; that the perfect fake passes all 100 cases and the do-nothing fake passes exactly the
"no order" cases; pass@k and pass^k on a worked example; Wilson's interval for 20 of 20; that the style checker catches changes;
and that every saved run re-scores to the same result with today's code.

## 11. Honest limits

- One made-up shop, 20 situations written by me, and customer messages rewritten by an AI: a hands-on study, not a benchmark.
- The simulated customer answers once, from a script. One failure (P15) is that limit, not the agent; it is still counted.
- The main runs use Claude Haiku 4.5 because Claude Haiku 5.5 passed all 20 pilot cases (the rule was written before the
  pilot). A newer model scores higher on this simple shop.
- The answer key was corrected after the results (P17). Both scores are reported; the saved runs keep their original checks.
- The labels for the judge test are one person's, on 30 runs that were nearly all fine, so 88 of 90 says little about rare
  mistakes. The planted mistakes were mine too, and two of them were too weak.
- Runs of the same case are not independent: averages are per case first, and the ranges resample cases.
- The spend cap is checked before every call, but separate processes running at the same time each read the ledgers when they
  start, so the cap is approximate when runs overlap. (The total stayed at $3.62 of $5.)
- Models change. Re-running gives different numbers; the saved runs are the record.

## 12. Sources

- Mikaela Grace, Jeremy Hadfield, Rodrigo Olivares, Jiri De Jonghe (Anthropic), "Demystifying evals for AI agents", 9 Jan 2026:
  https://www.anthropic.com/research/demystifying-evals-for-ai-agents
- Ruth Appel, Evan Frondorf, Jeremy Hadfield, Rebecca Hiscott, Kamya Jagadish, Shayne Longpre, Madeleine Tucker, Brett
  Wittmershaus (Anthropic), "Building strong safety evaluations", 13 Nov 2026: https://www.anthropic.com/research/building-strong-safety-evaluations
- Lance Martin (Anthropic), "Automating eval design and hillclimbing with Claude", 28 Sep 2026:
  https://claude.dev/blog/automating-eval-design-and-hillclimbing/
- Anthropic, "How tool use works" (Claude docs): https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works
- Anthropic, "Test plugins with evals" (Claude Code docs): https://code.claude.com/docs/en/plugin-evals
- Shunyu Yao, Noah Shinn, Pedram Razavi, Karthik Narasimhan, "τ-bench", 2024 (preprint): https://arxiv.org/abs/2406.12045
- Victor Barres, Honghua Dong, Soham Ray, Xujie Si, Karthik Narasimhan, "τ²-Bench", 2025 (preprint): https://arxiv.org/abs/2506.07982
- Sierra, τ-bench repository and docs (MIT): https://github.com/sierra-research/tau2-bench
- Yuxuan Zhu, Daniel Kang and 23 co-authors, "Establishing Best Practices for Building Rigorous Agentic Benchmarks", 2025
  (preprint): https://arxiv.org/abs/2507.02825
- Mark Chen and colleagues (OpenAI), "Evaluating Large Language Models Trained on Code", 2021 (preprint): https://arxiv.org/abs/2107.03374
- SWE-bench issue #465 (the `git log` leak): https://github.com/SWE-bench/SWE-bench/issues/465
- OpenAI, "Why we no longer evaluate SWE-bench Verified", Feb 2026: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
- Terminal-Bench, "Terminal-Bench 4.1", Nov 2026: https://www.tbench.ai/news/terminal-bench-4-1
- Hamel Husain and Shreya Shankar, "AI Evals: Everything You Need to Know": https://hamel.dev/blog/posts/evals-faq/
- Supabase, `braintrust-evals.yml` (Apache-2.0): https://github.com/supabase/supabase/blob/4ead4b092ee7e5ad4def2cd295b14492db12720b/.github/workflows/braintrust-evals.yml
- GitHub Docs, "Using secrets in GitHub Actions": https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets

## 13. License

MIT (see `LICENSE`). The shop, its rules and its customers are made up.
