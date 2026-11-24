"""Replay saved runs in the terminal, step by step. No API key, no network, no cost.

  python3 replay.py case P09                                   # one case, as the line of JSON it is
  python3 replay.py conv results/e3-haiku45-20x3 P09 --rep 1   # one saved conversation, then its checks (and the judge, if any)
  python3 replay.py eval results/e3-haiku45-20x3               # a whole saved eval, line by line, then the score
  python3 replay.py fake P09 --agent nothing                    # run a fake agent live (free) and show its conversation

--delay sets the pause between steps (seconds), for screen recording.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from checks import check_all
from harness import run_case
from model import Fake
from score import report

HERE = Path(__file__).parent
C = {"customer": "\033[38;5;117m", "agent": "\033[38;5;222m", "tool": "\033[38;5;245m", "ok": "\033[38;5;114m",
     "bad": "\033[38;5;203m", "dim": "\033[2m", "bold": "\033[1m", "end": "\033[0m"}


def paint(kind, text):
    return f"{C[kind]}{text}{C['end']}" if sys.stdout.isatty() or FORCE_COLOR else text


FORCE_COLOR = False


def load_cases():
    cases = {}
    for name in ("cases.jsonl", "cases-100.jsonl"):
        p = HERE / "evals" / name
        if p.exists():
            cases.update({c["id"]: c for c in map(json.loads, p.read_text().splitlines())})
    return cases


def show_case(case, delay):
    keep = ("id", "now_text", "message", "follow_up", "expected", "expected_total", "why")
    print(json.dumps({k: case[k] for k in keep}, indent=2, ensure_ascii=False))
    time.sleep(delay)


def show_trace(trace, delay):
    for s in trace:
        if s["type"] == "customer":
            print(paint("customer", "CUSTOMER  ") + s["text"])
        elif s["type"] == "agent":
            text = s["text"].strip().replace("\n", "\n          ")
            print(paint("agent", "AGENT     ") + text)
        else:
            print(paint("tool", f"  tool -> {s['name']}({json.dumps(s['input'], ensure_ascii=False)})"))
            print(paint("tool", f"  tool <- {json.dumps(s['result'], ensure_ascii=False)}"))
        print()
        time.sleep(delay)


def show_checks(checks, delay):
    for k, v in checks.items():
        if k == "all":
            continue
        print(f"  {k:<13} " + (paint("ok", "✓ yes") if v else paint("bad", "✗ no")))
        time.sleep(delay / 2)
    print("  " + (paint("ok", paint("bold", "PASS")) if checks["all"] else paint("bad", paint("bold", "FAIL"))))


def cmd_conv(a):
    folder = Path(a.folder)
    runs = [json.loads(line) for line in (folder / "runs.jsonl").read_text().splitlines() if line.strip()]
    run = next((r for r in runs if r["case"] == a.case and r["rep"] == a.rep), None)
    if run is None:
        raise SystemExit(f"no run {a.case} rep {a.rep} in {folder.name}")
    case = load_cases()[a.case]
    print(paint("dim", f"{folder.name} · {a.case} · run {a.rep} · {case['now_text']}"))
    print()
    show_trace(run["trace"], a.delay)
    print(paint("dim", "the checks:"))
    show_checks(check_all(case, run), a.delay)
    judged = folder / "judged.jsonl"
    if judged.exists():
        v = next((json.loads(x) for x in judged.read_text().splitlines() if json.loads(x)["id"] == f"{a.case}--{a.rep}"), None)
        if v and "error" not in v:
            print()
            print(paint("dim", "the AI judge:"))
            for q in ("honest", "explained", "no_allergy_promise"):
                print(f"  {q:<19} " + (paint("ok", "✓ yes") if v[q] else paint("bad", "✗ no")))
                time.sleep(a.delay / 2)
            print(paint("dim", f"  note: {v.get('note', '')}"))


def cmd_eval(a):
    folder = Path(a.folder)
    rows = [json.loads(line) for line in (folder / "runs.jsonl").read_text().splitlines() if line.strip()]
    if a.style:
        rows = [r for r in rows if r.get("style") in a.style]
    for r in rows:
        marks = "  ".join(f"{k} {paint('ok', '✓') if v else paint('bad', '✗')}" for k, v in r["checks"].items() if k != "all")
        verdict = paint("ok", "PASS") if r["checks"]["all"] else paint("bad", "FAIL")
        print(f"{r['case']:<14} run {r['rep']}   {marks}   {verdict}")
        time.sleep(a.delay)
    print()
    report(folder)


def cmd_fake(a):
    case = load_cases()[a.case]
    run = run_case(case, Fake(a.agent, case))
    print(paint("dim", f"fake agent '{a.agent}' · {a.case} · {case['now_text']}"))
    print()
    show_trace(run["trace"], a.delay)
    show_checks(check_all(case, run), a.delay)


def main():
    global FORCE_COLOR
    common = argparse.ArgumentParser(add_help=False)          # accepted before or after the subcommand
    common.add_argument("--delay", type=float, default=argparse.SUPPRESS, help="pause between steps, in seconds")
    common.add_argument("--color", action="store_true", default=argparse.SUPPRESS, help="colours even when not printing to a terminal")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("case", parents=[common])
    p.add_argument("case")
    p = sub.add_parser("conv", parents=[common])
    p.add_argument("folder")
    p.add_argument("case")
    p.add_argument("--rep", type=int, default=1)
    p = sub.add_parser("eval", parents=[common])
    p.add_argument("folder")
    p.add_argument("--style", nargs="*")
    p = sub.add_parser("fake", parents=[common])
    p.add_argument("case")
    p.add_argument("--agent", default="nothing", choices=["perfect", "nothing", "sloppy"])
    a = ap.parse_args()
    a.delay = getattr(a, "delay", 0.0)
    FORCE_COLOR = getattr(a, "color", False)
    if a.cmd == "case":
        show_case(load_cases()[a.case], a.delay)
    elif a.cmd == "conv":
        cmd_conv(a)
    elif a.cmd == "eval":
        cmd_eval(a)
    else:
        cmd_fake(a)


if __name__ == "__main__":
    main()
