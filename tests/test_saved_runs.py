"""Every saved run re-scores to exactly what was saved, with today's code and the answer key it ran with (v1).
The corrected answer key (v2, preregistration addendum 3) may change only the P17 runs."""

import json
import unittest
from pathlib import Path

from checks import check_all

ROOT = Path(__file__).resolve().parent.parent
CASES = {c["id"]: c for c in map(json.loads, (ROOT / "evals" / "cases-100.jsonl").read_text().splitlines())}


def saved_runs():
    for p in sorted((ROOT / "results").glob("*/runs.jsonl")):
        for line in p.read_text().splitlines():
            if line.strip():
                yield p.parent.name, json.loads(line)


class SavedRuns(unittest.TestCase):
    def test_rescore_with_key_v1_matches(self):
        n = 0
        for folder, r in saved_runs():
            self.assertEqual(check_all(CASES[r["case"]], r, key="v1"), r["checks"], f"{folder} {r['case']} {r['rep']}")
            n += 1
        self.assertGreater(n, 0)

    def test_key_v2_changes_only_p17(self):
        for folder, r in saved_runs():
            if check_all(CASES[r["case"]], r, key="v2") != r["checks"]:
                self.assertTrue(r["case"].startswith("P17"), f"{folder} {r['case']}")


if __name__ == "__main__":
    unittest.main()
