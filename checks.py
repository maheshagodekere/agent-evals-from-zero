"""Three code checks. Each reads one run (its trace and the shop's final orders) and answers yes or no.

1. outcome      - the end state: is the order list exactly what the case says it should be (or empty)?
2. looked_first - the process: before a delivery order, did the agent check that address?
3. told_total   - the reply: after placing an order, did the agent tell the customer the total from the till?
"""

import re

from shop.tools import normal_address


def order_key(o):
    """An order in a form that can be compared: items merged and sorted, address normalised, coupon in capitals."""
    if o is None:
        return None
    merged = {}
    for it in o["items"]:
        k = (it["name"].lower(), it.get("size") or "", bool(it.get("gluten_free")))
        merged[k] = merged.get(k, 0) + int(it.get("quantity") or 1)
    addr = normal_address(o["address"]) if o.get("fulfilment") == "delivery" else ""
    return (tuple(sorted(merged.items())), o.get("fulfilment"), addr, (o.get("coupon") or "").upper())


def outcome(case, run, key="v2"):
    """Answer key v1 = only `expected`. v2 (from 21 Nov 2026) also accepts `also_ok`: other outcomes the rules allow."""
    got = [order_key(o) for o in run["orders"]]
    wants = [case["expected"]] + (case.get("also_ok", []) if key == "v2" else [])
    return any(got == ([] if w is None else [order_key(w)]) for w in wants)


def looked_first(case, run):
    checked = set()
    for step in run["trace"]:
        if step["type"] == "tool" and step["name"] == "check_address":
            checked.add(normal_address(step["input"].get("address")))
        if step["type"] == "tool" and step["name"] == "place_order" and step["input"].get("fulfilment") == "delivery":
            if "order_id" in step["result"] and normal_address(step["input"].get("address")) not in checked:
                return False
    return True


def money_in(text):
    return {round(float(x), 2) for x in re.findall(r"\$\s?(\d+(?:\.\d{1,2})?)", text)}


def told_total(case, run):
    placed = [i for i, s in enumerate(run["trace"]) if s["type"] == "tool" and s["name"] == "place_order" and "total" in s["result"]]
    if not placed:
        return True
    total = run["trace"][placed[-1]]["result"]["total"]
    said = " ".join(s["text"] for s in run["trace"][placed[-1]:] if s["type"] == "agent")
    return round(float(total), 2) in money_in(said)


CHECKS = {"outcome": outcome, "looked_first": looked_first, "told_total": told_total}


def check_all(case, run, key="v2"):
    result = {name: (fn(case, run, key) if name == "outcome" else fn(case, run)) for name, fn in CHECKS.items()}
    result["all"] = all(result.values())
    return result
