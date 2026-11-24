"""E5: picks the 30 runs I label by hand (seed 11, from all E3 + E4 runs), before looking at any judge verdict.
Prints each conversation; my labels go in results/e5-labels.txt as: <case>--<rep> honest explained no_allergy_promise (y/n)."""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from judge import chat_text  # noqa: E402

R = Path(__file__).resolve().parent.parent / "results"
runs = []
for name in ("e3-haiku45-20x3", "e4-haiku45-80x3"):
    runs += [(name, json.loads(x)) for x in (R / name / "runs.jsonl").read_text().splitlines() if x.strip()]
runs.sort(key=lambda x: (x[1]["case"], x[1]["rep"]))
pick = random.Random(11).sample(runs, 30)
for name, r in pick:
    print(f"=== {r['case']}--{r['rep']}  ({name})")
    print(chat_text(r["trace"]))
    print()
