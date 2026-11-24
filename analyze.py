"""Every number in the video, computed from the saved runs (free, no key). Writes results/numbers.json and prints a summary.

  python3 analyze.py
"""

import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from checks import check_all
from score import summary

R = Path(__file__).parent / "results"
CASES = {c["id"]: c for c in map(json.loads, (Path(__file__).parent / "evals" / "cases-100.jsonl").read_text().splitlines())}


def rows(name):
    p = R / name / "runs.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def spent():
    total, by = 0.0, defaultdict(float)
    for p in R.rglob("ledger*.jsonl"):
        for line in p.read_text().splitlines():
            c = json.loads(line)["cost"]
            total += c
            by[p.parent.name + "/" + p.name] += c
    return round(total, 4), {k: round(v, 4) for k, v in sorted(by.items())}


def rate(rs, key="all"):
    return sum(r["checks"][key] for r in rs) / len(rs) if rs else None


def failures(rs):
    out = Counter()
    for r in rs:
        if not r["checks"]["all"]:
            out[(r["case"].split("-")[0], ",".join(k for k, v in r["checks"].items() if k != "all" and not v))] += 1
    return {f"{k[0]} ({k[1]})": v for k, v in sorted(out.items())}


def naive_placed_check(rs):
    """The 'Yes trap': a code check that looks for the word 'placed' in the agent's replies to decide that the agent said an order
    was placed. How often does it fire when NO order was placed?"""
    fired = total = 0
    examples = []
    for r in rs:
        if r["orders"]:
            continue
        total += 1
        hit = re.search(r"\bplaced\b", " ".join(s["text"] for s in r["trace"] if s["type"] == "agent"), re.I)
        if hit:
            fired += 1
            said = " ".join(s["text"] for s in r["trace"] if s["type"] == "agent")
            examples.append({"case": r["case"], "rep": r["rep"], "text": said[max(0, hit.start() - 90): hit.start() + 50].replace("\n", " ")})
    return {"no_order_runs": total, "naive_check_says_placed": fired, "examples": examples[:6]}


def subsample_spread(rs, n=20, reps=10000, seed=1):
    per_case = defaultdict(list)
    for r in rs:
        per_case[r["case"]].append(r["checks"]["all"])
    means = [sum(v) / len(v) for v in per_case.values()]
    rng = random.Random(seed)
    scores = sorted(sum(rng.sample(means, n)) / n for _ in range(reps))
    return {"samples": reps, "cases_per_sample": n, "lowest": scores[0], "p2_5": scores[int(0.025 * reps)],
            "median": scores[reps // 2], "p97_5": scores[int(0.975 * reps) - 1], "highest": scores[-1],
            "full_100": sum(means) / len(means)}


Q = ("honest", "explained", "no_allergy_promise")
TARGET = {"wrong_total": "honest", "false_order": "honest", "allergy_promise": "no_allergy_promise", "no_reason": "explained"}


def load_jsonl(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]


def judge_numbers(v2_rows):
    verdicts = {}
    for name in ("e3-haiku45-20x3", "e4-haiku45-80x3"):
        verdicts.update({v["id"]: v for v in load_jsonl(R / name / "judged.jsonl")})
    nothing = load_jsonl(R / "e1-fake-nothing" / "judged.jsonl")
    nothing_code = {f"{r['case']}--{r['rep']}": r["checks"]["all"] for r in load_jsonl(R / "e1-fake-nothing" / "runs.jsonl")}
    planted = load_jsonl(R / "e4-haiku45-80x3" / "judge-planted.jsonl")
    caught = defaultdict(lambda: [0, 0])
    for v in planted:
        if v["label"] == "unbroken":
            caught["unbroken_all_yes"][0] += all(v[q] for q in Q)
        else:
            caught[v["label"]][0] += v[TARGET[v["label"]]] is False
        caught["unbroken_all_yes" if v["label"] == "unbroken" else v["label"]][1] += 1
    labels = {}
    for line in (R / "e5-labels.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            p = line.split()
            labels[p[0]] = dict(zip(Q, [x == "y" for x in p[1:4]], strict=True))
    agree = sum(labels[k][q] == verdicts[k][q] for k in labels for q in Q)
    flagged_code_pass = []
    both = 0
    for r in v2_rows:
        v = verdicts[f"{r['case']}--{r['rep']}"]
        ok = all(v[q] for q in Q)
        both += r["checks"]["all"] and ok
        if r["checks"]["all"] and not ok:
            flagged_code_pass.append({"id": f"{r['case']}--{r['rep']}", "no": [q for q in Q if not v[q]], "note": v["note"]})
    return {"runs_judged": len(verdicts), "judge_errors": sum("error" in v for v in verdicts.values()),
            "no_counts": {q: sum(v.get(q) is False for v in verdicts.values()) for q in Q},
            "code_pass_but_judge_no": len(flagged_code_pass), "code_pass_but_judge_no_runs": flagged_code_pass,
            "pass_code_and_judge_key_v2": both / len(v2_rows), "pass_code_and_judge_count": both,
            "nothing_agent": {q: sum(v[q] for v in nothing) for q in Q} | {"runs": len(nothing),
                              "pass_code_and_judge": sum(all(v[q] for q in Q) for v in nothing
                                                         if nothing_code[v["id"]])},
            "planted": {k: {"caught": c, "of": n} for k, (c, n) in caught.items()},
            "labels": {"runs": len(labels), "judgements": 3 * len(labels), "agree": agree}}


def main():
    e3, e4 = rows("e3-haiku45-20x3"), rows("e4-haiku45-80x3")
    main_rows = e3 + e4
    out = {"spent_total": spent()[0], "spent_by_ledger": spent()[1]}
    for name in ("e1-fake-perfect", "e1-fake-nothing", "e1-fake-sloppy", "e2-pilot-haiku55", "e2-pilot-haiku45"):
        rs = rows(name)
        out[name] = {k: rate(rs, k) for k in ("outcome", "looked_first", "told_total", "all")} | {"runs": len(rs)}
    out["e3"] = summary(e3) | {"failures": failures(e3), "per_check": {k: summary(e3, k)["pass_rate"] for k in ("outcome", "looked_first", "told_total")}}
    if e4:
        out["e4_styles_only"] = summary(e4) | {"failures": failures(e4)}
        out["e4_100x3"] = summary(main_rows) | {"failures": failures(main_rows),
                                               "per_check": {k: summary(main_rows, k)["pass_rate"] for k in ("outcome", "looked_first", "told_total")}}
        out["by_style"] = {st: rate([r for r in main_rows if r["style"] == st]) for st in ("plain", "short", "chatty", "learner", "impatient")}
        by_sit = defaultdict(list)
        for r in main_rows:
            by_sit[r["case"].split("-")[0]].append(r["checks"]["all"])
        out["by_situation"] = {k: sum(v) / len(v) for k, v in sorted(by_sit.items())}
        out["subsample_20_of_100"] = subsample_spread(main_rows)
        out["naive_placed_check"] = naive_placed_check(main_rows)
        out["cost_per_conversation_haiku45"] = sum(r["cost"] for r in main_rows) / len(main_rows)
        # answer key v2 (addendum 3): P17 also accepts the valid SAVE5 coupon the agent offered
        v2 = [{**r, "checks": check_all(CASES[r["case"]], r, key="v2")} for r in main_rows]
        e3v2 = [r for r in v2 if r["style"] == "plain"]
        out["key_v2"] = {"e3": summary(e3v2) | {"failures": failures(e3v2)},
                         "e4_100x3": summary(v2) | {"failures": failures(v2)},
                         "subsample_20_of_100": subsample_spread(v2),
                         "by_style": {st: rate([r for r in v2 if r["style"] == st]) for st in ("plain", "short", "chatty", "learner", "impatient")}}
        out["re_scored_with_key_v1_match"] = all(check_all(CASES[r["case"]], r, key="v1") == r["checks"] for r in main_rows)
    if e4 and (R / "e4-haiku45-80x3" / "judged.jsonl").exists():
        out["judge"] = judge_numbers(v2)
    (R / "numbers.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
