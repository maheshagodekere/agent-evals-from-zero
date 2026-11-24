"""Tests that need no key and no network: the till, the checks, the fake agents, the statistics, the style checker."""

import json
import unittest
from pathlib import Path

from checks import check_all, money_in, order_key
from evals.make_styles import problems
from harness import run_case
from model import Fake
from score import pass_at_k, pass_hat_k, wilson
from shop.tools import Shop, normal_address

ROOT = Path(__file__).resolve().parent.parent


def cases(name="cases.jsonl"):
    p = ROOT / "evals" / name
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []


def run_fake(kind, case):
    return check_all(case, run_case(case, Fake(kind, case)))


class Till(unittest.TestCase):
    def test_hand_written_totals_match_the_till(self):
        for c in cases():
            if c["expected"] is None:
                continue
            e = c["expected"]
            args = {"items": [{k: v for k, v in it.items() if v not in (None, False)} for it in e["items"]],
                    "fulfilment": e["fulfilment"], **{k: e[k] for k in ("address", "coupon") if e[k]}}
            self.assertEqual(Shop(c).place_order(args)["total"], c["expected_total"], c["id"])

    def test_tools_do_not_enforce_rules(self):
        # On purpose: the shop's tools accept a rule-breaking order. Catching it is the eval's job.
        r = Shop({}).place_order({"items": [{"name": "Pepperoni", "size": "large", "quantity": 15}], "fulfilment": "pickup"})
        self.assertIn("order_id", r)

    def test_unknown_coupon_and_item_are_refused(self):
        self.assertIn("error", Shop({}).place_order({"items": [{"name": "Pepperoni", "size": "large", "quantity": 1}],
                                                     "fulfilment": "pickup", "coupon": "STAFF100"}))
        self.assertIn("error", Shop({}).place_order({"items": [{"name": "Quattro Formaggi", "size": "large", "quantity": 1}],
                                                     "fulfilment": "pickup"}))


class Checks(unittest.TestCase):
    def test_addresses(self):
        self.assertEqual(normal_address("14, Elm St."), "14 Elm Street")
        self.assertEqual(normal_address("14 Elm Street, Hilltop"), "14 Elm Street")

    def test_order_key_merges_lines(self):
        a = {"items": [{"name": "Pepperoni", "size": "large", "quantity": 1}] * 2, "fulfilment": "pickup", "coupon": None}
        b = {"items": [{"name": "pepperoni", "size": "large", "quantity": 2}], "fulfilment": "pickup", "coupon": ""}
        self.assertEqual(order_key(a), order_key(b))

    def test_money(self):
        self.assertEqual(money_in("Total: $31.00, or $ 31"), {31.0})

    def test_perfect_agent_passes_every_case(self):
        for name in ("cases.jsonl", "cases-100.jsonl"):
            for c in cases(name):
                self.assertTrue(run_fake("perfect", c)["all"], c["id"])

    def test_do_nothing_passes_only_no_order_cases(self):
        for c in cases():
            self.assertEqual(run_fake("nothing", c)["outcome"], c["expected"] is None, c["id"])


class Stats(unittest.TestCase):
    def test_pass_at_k_and_pass_hat_k(self):
        tasks = [(3, 3), (3, 2), (3, 0)]
        self.assertAlmostEqual(sum(pass_at_k(n, c, 3) for n, c in tasks) / 3, 2 / 3)
        self.assertAlmostEqual(sum(pass_hat_k(n, c, 3) for n, c in tasks) / 3, 1 / 3)
        self.assertAlmostEqual(pass_hat_k(10, 7, 3), 35 / 120)

    def test_wilson_20_of_20(self):
        self.assertAlmostEqual(wilson(20, 20)[0], 20 / (20 + 1.96 ** 2), places=6)


class Styles(unittest.TestCase):
    def test_checker_catches_changes(self):
        base = cases()[2]  # P03
        self.assertEqual(problems(base, base["message"]), [])
        self.assertTrue(problems(base, base["message"] + " And a soda."))
        self.assertTrue(problems(base, base["message"].replace("SAVE5", "SAVE10")))
        self.assertTrue(problems(base, "A large BBQ chicken to 3 Oak Avenue, code SAVE5."))


if __name__ == "__main__":
    unittest.main()
