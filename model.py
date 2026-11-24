"""Models the harness can run: Claude through the API (with a spend guard), and three fake agents that need no key.

Fake agents (free, no network):
  perfect  - reads the answer key and does exactly the right thing. If it doesn't score 100%, the checks are wrong.
  nothing  - calls no tool and says "Sorry, I can't help with that." It shows what an eval gives for doing nothing.
  sloppy   - places what the customer literally asked for, without checking the address or the rules.

The API key: the environment variable ANTHROPIC_API_KEY, or else the macOS Keychain item "anthropic-api". It is never printed.
"""

import json
import os
import random
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.anthropic.com/v1/messages"
BATCH_API = "https://api.anthropic.com/v1/messages/batches"
VERSION = "2026-10-21"

# Dollars per million tokens: input, cache write (5 min), cache read, output. Claude pricing page, read 19 Nov 2026.
PRICES = {"claude-haiku-5-5": (0.10, 0.125, 0.01, 0.50), "claude-haiku-4-5-20251001": (1.00, 1.25, 0.10, 5.00),
          "claude-sonnet-5-5": (2.00, 2.50, 0.10, 10.00), "claude-opus-5-5": (4.00, 5.00, 0.20, 20.00)}


class SpendCapReached(Exception):
    pass


class Ledger:
    """Every paid call is written to a ledger file. The cap counts ALL ledger*.jsonl files under the study folder."""

    def __init__(self, path, cap, root):
        self.path, self.cap, self.root = Path(path), float(cap), Path(root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.before = self.spent_in_folder()
        self.now = 0.0

    def spent_in_folder(self):
        total = 0.0
        for p in self.root.rglob("ledger*.jsonl"):
            for line in p.read_text().splitlines():
                try:
                    total += json.loads(line)["cost"]
                except (ValueError, KeyError):
                    pass
        return total

    def total(self):
        return self.before + self.now

    def check(self, next_cost=0.0):
        if self.total() + next_cost > self.cap:
            raise SpendCapReached(f"spend cap: ${self.total():.4f} spent (+${next_cost:.4f} next) > cap ${self.cap:.2f}")

    def add(self, row):
        with self.lock:
            self.now += row["cost"]
            with open(self.path, "a") as f:
                f.write(json.dumps(row) + "\n")


def cost_of(model, usage, batch=False):
    p_in, p_cw, p_cr, p_out = PRICES[model]
    usd = (usage.get("input_tokens", 0) * p_in + usage.get("cache_creation_input_tokens", 0) * p_cw
           + usage.get("cache_read_input_tokens", 0) * p_cr + usage.get("output_tokens", 0) * p_out) / 1e6
    return usd * (0.5 if batch else 1.0)


_KEY = None


def api_key():
    global _KEY
    if _KEY is None:
        _KEY = os.environ.get("ANTHROPIC_API_KEY") or subprocess.run(
            ["security", "find-generic-password", "-s", "anthropic-api", "-w"], capture_output=True, text=True).stdout.strip()
        if not _KEY:
            raise SystemExit("No API key: set ANTHROPIC_API_KEY (or use --fake to run without one).")
    return _KEY


def _request(url, body=None, tries=7, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    delay = 2.0
    for i in range(tries):
        req = urllib.request.Request(url, data=data, headers={
            "x-api-key": api_key(), "anthropic-version": VERSION, "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data_in = r.read()
                return data_in if raw else json.loads(data_in)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 504, 529) and i < tries - 1:
                time.sleep(delay + random.random())
                delay = min(delay * 2, 60)
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i < tries - 1:
                time.sleep(delay + random.random())
                delay = min(delay * 2, 60)
                continue
            raise RuntimeError(f"network error: {type(e).__name__}") from None


class Claude:
    """A callable model for the harness: model(system, tools, messages) -> the API's reply."""

    def __init__(self, name, ledger, tag="", max_tokens=4096, est_call=0.01):
        self.name, self.ledger, self.tag, self.max_tokens, self.est_call = name, ledger, tag, max_tokens, est_call
        self.cost = 0.0
        self.usage = {"input_tokens": 0, "output_tokens": 0}

    def __call__(self, system, tools, messages):
        self.ledger.check(self.est_call)
        body = {"model": self.name, "max_tokens": self.max_tokens, "system": system, "tools": tools, "messages": messages}
        reply = _request(API, body)
        usage = reply.get("usage") or {}
        cost = cost_of(self.name, usage)
        self.ledger.add({"t": time.time(), "tag": self.tag, "model": self.name, "usage": usage, "cost": cost, "id": reply.get("id")})
        self.cost += cost
        for k in self.usage:
            self.usage[k] += usage.get(k, 0)
        return reply


def batch(ledger, requests, est_each, poll=20, log=print):
    """Send many single calls through the Message Batches API (half price). requests: [(custom_id, body)].
    Refuses to start if the estimate would pass the cap. Returns {custom_id: reply or {"error": ...}}."""
    ledger.check(est_each * len(requests))
    job = _request(BATCH_API, {"requests": [{"custom_id": cid, "params": body} for cid, body in requests]})
    log(f"batch {job['id']}: {len(requests)} requests sent")
    while True:
        time.sleep(poll)
        job = _request(f"{BATCH_API}/{job['id']}")
        if job.get("processing_status") == "ended":
            break
        log(f"  {job.get('request_counts')}")
    names = {cid: body["model"] for cid, body in requests}
    out = {}
    for line in _request(job["results_url"], raw=True).decode().splitlines():
        if line.strip():
            x = json.loads(line)
            res = x.get("result", {})
            if res.get("type") == "succeeded":
                msg = res["message"]
                cost = cost_of(names[x["custom_id"]], msg.get("usage") or {}, batch=True)
                ledger.add({"t": time.time(), "tag": "batch:" + job["id"], "model": names[x["custom_id"]],
                            "usage": msg.get("usage"), "cost": cost, "id": msg.get("id"), "batch": True})
                out[x["custom_id"]] = msg
            else:
                out[x["custom_id"]] = {"error": res.get("type")}
    return out


# ------------------------------------------------------------------ fake agents (no key, no cost)

def _say(text):
    return {"content": [{"type": "text", "text": text}], "usage": {}}


def _use(name, args, n):
    return {"content": [{"type": "tool_use", "id": f"fake_{n}", "name": name, "input": args}], "usage": {}}


def _last_result(messages):
    m = messages[-1]
    if m["role"] == "user" and isinstance(m["content"], list):
        return json.loads(m["content"][0]["content"])
    return None


def _items_for_tool(items):
    return [{k: v for k, v in it.items() if v not in (None, False)} for it in items]


class Fake:
    def __init__(self, kind, case):
        self.kind, self.case = kind, case
        self.name, self.cost, self.usage = f"fake-{kind}", 0.0, {"input_tokens": 0, "output_tokens": 0}

    def __call__(self, system, tools, messages):
        c, n = self.case, len(messages)
        if self.kind == "nothing":
            return _say("Sorry, I can't help with that.")
        plan = c["expected"] if self.kind == "perfect" else c["asked"]
        if plan is None:
            return _say(f"I'm sorry, I can't place this order. {c['why']}")
        last = _last_result(messages)
        if last is None and plan["fulfilment"] == "delivery" and self.kind == "perfect":
            return _use("check_address", {"address": plan["address"]}, n)
        if last is None or "deliverable" in last:
            args = {"items": _items_for_tool(plan["items"]), "fulfilment": plan["fulfilment"]}
            args.update({k: plan[k] for k in ("address", "coupon") if plan.get(k)})
            return _use("place_order", args, n)
        if "total" in last:
            when = "ready for pickup in 20 minutes" if plan["fulfilment"] == "pickup" else "on its way soon"
            return _say(f"Your order {last['order_id']} is placed. The total is ${last['total']:.2f}, {when}.")
        return _say(f"Sorry, something went wrong: {last.get('error')}")


def make_model(spec, case, ledger=None, tag=""):
    if spec.startswith("fake-"):
        return Fake(spec[5:], case)
    return Claude(spec, ledger, tag=tag)
