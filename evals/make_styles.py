"""Writes evals/cases-100.jsonl: the 20 hand-written cases + each one rewritten in 4 more styles = 100 cases.

Claude Haiku 5.5 rewrites only the customer's FIRST message. Code then checks every rewrite: it must keep the case's phrases word
for word, add no menu item, no coupon code, no dollar amount and no number that wasn't there, and not add the forbidden words.
A rewrite that fails is asked for again (5 tries at most). Rewrites that passed are kept if the script is run again. The right outcome, the time and the follow-up stay the same.

Run: python3 evals/make_styles.py --out runs   (costs about $0.02; needs a key)
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from model import Ledger, _request, API, cost_of  # noqa: E402
from shop.tools import MENU  # noqa: E402

STYLES = {
    "short": "very short, like a quick text message typed on a phone",
    "chatty": "friendly and chatty, with a little small talk about their day, but no new requests",
    "learner": "someone still learning English: simple words and a few small grammar mistakes",
    "impatient": "impatient and in a hurry, a bit demanding, but polite enough and with no new requests",
}
WRITER = "claude-haiku-5-5"

PROMPT = """Rewrite a customer's message to a pizza shop's chat assistant, in a different style.

The message: {message}

Style: {style}

Rules:
- Keep these phrases exactly, word for word: {keep}
- Ask for exactly the same thing. Add no other food, no other code, no prices, no numbers and no new requests.
- Don't mention the time or the day.
Reply with the rewritten message only."""

ITEM_WORDS = [n.lower() for n in list(MENU["pizzas"]) + list(MENU["sides"])] + ["sodas", "garlic breads"]


def problems(base, text):
    low, blow = text.lower(), base["message"].lower()
    out = [f"missing '{k}'" for k in base["keep"] if k.lower() not in low]
    out += [f"adds '{w}'" for w in base.get("forbid", []) if re.search(rf"\b{w}\b", low)]
    out += [f"adds item '{w}'" for w in ITEM_WORDS if w in low and w not in blow and not (w == "sodas" and "soda" in blow)]
    out += [f"adds code '{c}'" for c in re.findall(r"\b[A-Z]{3,}\d+\b", text) if c not in base["message"]]
    out += [f"adds number '{d}'" for d in set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", base["message"]))]
    if "$" in text and "$" not in base["message"]:
        out.append("adds a price")
    if len(text) > 4 * len(base["message"]) + 200:
        out.append("too long")
    if "\n" in text.strip() or re.search(r"\b(rule|phrase|final:|wait,|exactly)\b", low):          # added 21 Nov: leaked notes
        out.append("notes or line breaks in the message")
    times = r"\b(mornings?|afternoons?|evenings?|tonight|tomorrow|today|noon|midnight|(mon|tues|wednes|thurs|fri|satur|sun)day|\d+ ?(am|pm))\b"
    if re.search(times, low) and not re.search(times, blow):                                          # added 21 Nov: time words
        out.append("mentions a time or day")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs", help="study folder (its ledgers count toward the cap)")
    ap.add_argument("--max-cost", type=float, default=1.00)
    a = ap.parse_args()
    here = Path(__file__).parent
    base_cases = [json.loads(line) for line in (here / "cases.jsonl").read_text().splitlines() if line.strip()]
    ledger = Ledger(Path(a.out) / "writer" / "ledger.jsonl", a.max_cost, a.out)
    att_file = Path(a.out) / "writer" / "attempts.jsonl"
    log = [json.loads(x) for x in att_file.read_text().splitlines()] if att_file.exists() else []
    by_id = {c["id"]: c for c in base_cases}
    good = {(x["case"], x["style"]): x["text"] for x in log                          # resume: keep rewrites that pass
            if not problems(by_id[x["case"]], x["text"])}                             # today's checks
    good = {k: v for k, v in good.items() if v}
    out = list(base_cases)
    for base in base_cases:
        for style, desc in STYLES.items():
            if (base["id"], style) in good:
                out.append({**base, "id": f"{base['id']}-{style}", "style": style, "message": good[(base["id"], style)]})
                continue
            for attempt in range(1, 6):
                ledger.check(0.001)
                body = {"model": WRITER, "max_tokens": 2000, "messages": [{"role": "user", "content": PROMPT.format(
                    message=base["message"], style=desc, keep="; ".join(f'"{k}"' for k in base["keep"]))}]}
                reply = _request(API, body)
                cost = cost_of(WRITER, reply.get("usage") or {})
                ledger.add({"tag": f"writer:{base['id']}:{style}:{attempt}", "model": WRITER, "usage": reply.get("usage"),
                            "cost": cost, "id": reply.get("id")})
                text = "".join(b.get("text", "") for b in reply["content"] if b["type"] == "text").strip().strip('"')
                bad = problems(base, text)
                row = {"case": base["id"], "style": style, "attempt": attempt, "text": text, "problems": bad}
                log.append(row)
                with open(att_file, "a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                if not bad:
                    out.append({**base, "id": f"{base['id']}-{style}", "style": style, "message": text})
                    print(f"{base['id']}-{style:<9} {text}")
                    break
                print(f"{base['id']}-{style:<9} retry ({', '.join(bad)}): {text[:160]}")
            else:
                raise SystemExit(f"{base['id']} {style}: no valid rewrite in 5 tries")
    (here / "cases-100.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in out))
    print(f"\nwrote {len(out)} cases; writer cost ${ledger.now:.4f}")


if __name__ == "__main__":
    main()
