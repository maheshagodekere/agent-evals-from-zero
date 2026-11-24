"""Run the eval: every case, several runs each, through the harness and the three code checks.

  python3 run_eval.py --model fake-perfect                     # free: the checks must give 100%
  python3 run_eval.py --model fake-nothing                     # free: what doing nothing scores
  python3 run_eval.py --model claude-haiku-5-5 --runs 3        # real: costs money, needs a key (see README)

Every run is saved to <out>/<name>/runs.jsonl (the trace, the orders, the checks, the cost). Runs already saved are skipped, so
an interrupted eval continues where it stopped. With --min-score, the script exits with code 1 if the score is lower (for CI).
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from checks import check_all
from harness import run_case
from model import Ledger, SpendCapReached, make_model
from score import report


def load_cases(path, only=None, styles=None):
    cases = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    return [c for c in cases if (not only or c["id"] in only) and (not styles or c.get("style") in styles)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="fake-perfect", help="claude-haiku-5-5, claude-haiku-4-5-20251001, ... or fake-perfect / fake-nothing / fake-sloppy")
    ap.add_argument("--cases", default="evals/cases.jsonl")
    ap.add_argument("--runs", type=int, default=1, help="runs per case")
    ap.add_argument("--out", default="runs", help="study folder; the spend cap counts every ledger in it")
    ap.add_argument("--name", help="run folder name (default: model-cases-runs)")
    ap.add_argument("--max-cost", type=float, default=1.00, help="hard stop in dollars, for everything in --out")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", nargs="*", help="case ids")
    ap.add_argument("--styles", nargs="*", help="only these styles (plain short chatty learner impatient)")
    ap.add_argument("--min-score", type=float, help="exit 1 if the share of runs passing all checks is lower")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    cases = load_cases(a.cases, a.only, a.styles)
    if not cases:
        raise SystemExit("no cases match")
    name = a.name or f"{a.model}-{Path(a.cases).stem}-x{a.runs}"
    folder = Path(a.out) / name
    folder.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(folder / "ledger.jsonl", a.max_cost, a.out)
    runs_file = folder / "runs.jsonl"
    done = set()
    if runs_file.exists():
        done = {(r["case"], r["rep"]) for r in map(json.loads, runs_file.read_text().splitlines())}
    (folder / "command.json").write_text(json.dumps({"argv": sys.argv[1:], "started": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1))

    todo = [(c, rep) for rep in range(1, a.runs + 1) for c in cases if (c["id"], rep) not in done]

    def one(job):
        case, rep = job
        model = make_model(a.model, case, ledger, tag=f"{name}:{case['id']}:{rep}")
        t0 = time.time()
        run = run_case(case, model)
        row = {"case": case["id"], "rep": rep, "style": case.get("style"), "model": a.model, "checks": check_all(case, run),
               **run, "cost": model.cost, "usage": model.usage, "secs": round(time.time() - t0, 2)}
        return row

    with ThreadPoolExecutor(a.workers) as pool, open(runs_file, "a") as f:
        try:
            for row in pool.map(one, todo):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                if not a.quiet:
                    marks = "  ".join(f"{k} {'✓' if v else '✗'}" for k, v in row["checks"].items() if k != "all")
                    print(f"{row['case']}  run {row['rep']}   {marks}   {'PASS' if row['checks']['all'] else 'FAIL'}")
        except SpendCapReached as e:
            print(f"\nSTOPPED: {e}")
            pool.shutdown(cancel_futures=True)

    print(f"\n{name}   spent in this study so far: ${ledger.total():.4f} (cap ${a.max_cost:.2f})\n")
    s = report(folder)
    (folder / "summary.json").write_text(json.dumps(s, indent=1))
    if a.min_score is not None and s["pass_rate"] < a.min_score:
        print(f"\nFAIL: score {100 * s['pass_rate']:.1f}% is below the minimum {100 * a.min_score:.1f}%")
        sys.exit(1)


if __name__ == "__main__":
    main()
