"""The pizza shop's three tools, all fake: they change an order list held in memory, nothing real.

On purpose, the tools do NOT enforce the shop's rules (hours, delivery area, coupon conditions, 10 pizzas at most). They do what
they are asked, like the tools in tau-bench. Following the rules is the agent's job, and checking that is the eval's job.
They only refuse input they can't understand: an unknown item, a missing size, an unknown coupon code.
"""

import json
import re
from pathlib import Path

MENU = json.loads((Path(__file__).parent / "menu.json").read_text())

TOOLS = [
    {"name": "get_menu", "description": "Get the menu: pizzas with their prices by size, sides, and the gluten-free base.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "check_address", "description": "Check whether we deliver to an address, and how long delivery takes.",
     "input_schema": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"]}},
    {"name": "place_order", "description": "Place an order. Returns the order id, the price breakdown and the total in dollars.",
     "input_schema": {"type": "object", "properties": {
         "items": {"type": "array", "items": {"type": "object", "properties": {
             "name": {"type": "string", "description": "A pizza or side, exactly as on the menu"},
             "size": {"type": "string", "enum": ["small", "medium", "large"], "description": "Pizzas only"},
             "quantity": {"type": "integer", "minimum": 1},
             "gluten_free": {"type": "boolean", "description": "Gluten-free base"}},
             "required": ["name", "quantity"]}},
         "fulfilment": {"type": "string", "enum": ["delivery", "pickup"]},
         "address": {"type": "string", "description": "For delivery"},
         "coupon": {"type": "string", "description": "One coupon code, if any"}},
         "required": ["items", "fulfilment"]}},
]

COUPONS = ("SAVE5", "TUESDAY50")


def street_of(address):
    """'14 Elm St.' -> ('14', 'Elm Street'). Returns (None, None) if no street is recognised."""
    a = " " + re.sub(r"[^a-z0-9 ]", " ", (address or "").lower()) + " "
    for short, full in ((" st ", " street "), (" ave ", " avenue "), (" av ", " avenue "), (" rd ", " road "), (" ln ", " lane ")):
        a = a.replace(short, full)
    m = re.search(r"(\d+)\s+([a-z]+ (?:street|avenue|lane|road))\b", a)
    return (m.group(1), m.group(2).title()) if m else (None, None)


def normal_address(address):
    number, street = street_of(address)
    return f"{number} {street}" if street else (address or "").strip().lower()


def find_name(name, names):
    return next((n for n in names if n.lower() == (name or "").strip().lower()), None)


def price_order(items, fulfilment, coupon):
    """The till: food, discount, delivery fee and total, for an order the tool has already understood."""
    food = pizzas = 0
    for it in items:
        if it["name"] in MENU["pizzas"]:
            p = (MENU["pizzas"][it["name"]][it["size"]] + (MENU["gluten_free_base"]["extra"] if it.get("gluten_free") else 0))
            pizzas += p * it["quantity"]
        else:
            p = MENU["sides"][it["name"]]
        food += p * it["quantity"]
    discount = {"SAVE5": 5, "TUESDAY50": pizzas / 2}.get(coupon or "", 0)
    after = food - discount
    fee = 0 if fulfilment == "pickup" or after >= MENU["free_delivery_from"] else MENU["delivery_fee"]
    return {"food": food, "discount": discount, "delivery_fee": fee, "total": round(after + fee, 2)}


class Shop:
    """A fresh fake shop for one run. `orders` is the final state that the outcome check reads."""

    def __init__(self, case):
        self.notes = case.get("address_notes", {})
        self.orders = []

    def run(self, name, args):
        if name == "get_menu":
            return {k: MENU[k] for k in ("pizzas", "sides", "gluten_free_base")}
        if name == "check_address":
            number, street = street_of(args.get("address"))
            if street not in MENU["delivery_streets"]:
                return {"deliverable": False, "reason": "outside our delivery area"}
            out = {"deliverable": True, "eta_minutes": MENU["delivery_streets"][street]}
            note = self.notes.get(f"{number} {street}")
            return {**out, "note": note} if note else out
        if name == "place_order":
            return self.place_order(args)
        return {"error": f"unknown tool {name}"}

    def place_order(self, args):
        items = []
        for it in args.get("items") or []:
            pizza = find_name(it.get("name"), MENU["pizzas"])
            side = find_name(it.get("name"), MENU["sides"])
            if not (pizza or side):
                return {"error": f"'{it.get('name')}' is not on the menu"}
            if pizza and it.get("size") not in ("small", "medium", "large"):
                return {"error": f"a size is needed for {pizza}"}
            items.append({"name": pizza or side, "size": it.get("size") if pizza else None,
                          "quantity": int(it.get("quantity") or 1), "gluten_free": bool(it.get("gluten_free")) if pizza else False})
        if not items:
            return {"error": "the order has no items"}
        coupon = (args.get("coupon") or "").strip().upper() or None
        if coupon and coupon not in COUPONS:
            return {"error": f"unknown coupon code {coupon}"}
        fulfilment = args.get("fulfilment")
        if fulfilment == "delivery" and not args.get("address"):
            return {"error": "a delivery order needs an address"}
        order = {"order_id": f"HP-{1041 + len(self.orders)}", "items": items, "fulfilment": fulfilment,
                 "address": args.get("address") if fulfilment == "delivery" else None, "coupon": coupon,
                 **price_order(items, fulfilment, coupon)}
        self.orders.append(order)
        return {k: order[k] for k in ("order_id", "food", "discount", "delivery_fee", "total")}
