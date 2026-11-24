"""The score over many cases and runs: pass rates per check, pass@k and pass^k, and a 95% range.

Runs of the same case are not independent, so every number is first averaged per case, and the range is a bootstrap over CASES
(10,000 resamples, seed 1). Wilson's interval is also given for the share of cases.

Run: python3 score.py runs/<run-folder>
"""

import json
import math
import random
import sys
from math import comb
from pathlib import Path


def load(folder):
    return [json.loads(line) for line in (Path(folder) / "runs.jsonl").read_text().splitlines() if line.strip()]


def by_case(rows, key="all"):
    cases = {}
    for r in rows:
        cases.setdefault(r["case"], []).append(bool(r["checks"][key]))
    return cases


def pass_at_k(n, c, k):
    """Chen et al. 2021: the chance that at least one of k runs (drawn from the n we made) passes."""
    return 1.0 if n - c < k else 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n, c, k):
    """Yao et al. 2024 (tau-bench): the chance that all k runs pass."""
    return comb(c, k) / comb(n, k)


def wilson(passes, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = passes / n
    mid = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, mid - half), min(1.0, mid + half))


def bootstrap(values, reps=10000, seed=1):
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(reps))
    return (means[int(0.025 * reps)], means[int(0.975 * reps) - 1])


def summary(rows, key="all"):
    cases = by_case(rows, key)
    per_case = [sum(v) / len(v) for v in cases.values()]
    k = min(len(v) for v in cases.values())
    out = {"check": key, "cases": len(cases), "runs": sum(len(v) for v in cases.values()), "runs_per_case": k,
           "pass_rate": sum(per_case) / len(per_case), "range95": bootstrap(per_case)}
    if k > 1:
        out[f"pass@{k}"] = sum(pass_at_k(len(v), sum(v), k) for v in cases.values()) / len(cases)
        out[f"pass^{k}"] = sum(pass_hat_k(len(v), sum(v), k) for v in cases.values()) / len(cases)
        always = sum(all(v) for v in cases.values())
        out["cases_always_pass"] = always
        out["cases_always_pass_wilson95"] = wilson(always, len(cases))
    return out


def pct(x):
    return f"{100 * x:.1f}%"


def report(folder):
    rows = load(folder)
    keys = [k for k in rows[0]["checks"] if k != "all"] + ["all"]
    for key in keys:
        s = summary(rows, key)
        lo, hi = s["range95"]
        extra = ""
        k = s["runs_per_case"]
        if k > 1:
            extra = f"   pass@{k} {pct(s[f'pass@{k}'])}   pass^{k} {pct(s[f'pass^{k}'])}"
        print(f"{key:<13} {pct(s['pass_rate']):>7}   95% range {pct(lo)} to {pct(hi)}{extra}")
    s = summary(rows, "all")
    print(f"\n{s['cases']} cases x {s['runs_per_case']} runs = {s['runs']} runs")
    return s


if __name__ == "__main__":
    report(sys.argv[1])
