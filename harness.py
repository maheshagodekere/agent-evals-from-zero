"""The harness: runs the agent on ONE case and records the trace.

The model never runs a tool. It only asks for one. This loop runs the tool on a fake shop, sends the result back, and repeats
until the agent replies in plain text. If the agent stops without placing an order (for example to ask a question), the
simulated customer answers once, with the case's scripted follow-up.
"""

import json
from pathlib import Path

from shop.tools import TOOLS, Shop

HERE = Path(__file__).parent
PROMPT = (HERE / "shop" / "prompt.txt").read_text()
POLICY = (HERE / "shop" / "policy.md").read_text()


def run_case(case, model, max_turns=8):
    shop = Shop(case)                                    # a fresh fake shop for every run
    system = PROMPT.format(now=case["now_text"], policy=POLICY)
    messages = [{"role": "user", "content": case["message"]}]
    trace = [{"type": "customer", "text": case["message"]}]
    followed_up = False

    for _ in range(max_turns):
        reply = model(system, TOOLS, messages)           # one call to the model
        messages.append({"role": "assistant", "content": reply["content"]})
        calls = [b for b in reply["content"] if b["type"] == "tool_use"]
        trace += [{"type": "agent", "text": b["text"]} for b in reply["content"] if b["type"] == "text" and b["text"].strip()]

        if calls:                                        # the agent asked for tools: run them, send the results back
            results = []
            for call in calls:
                result = shop.run(call["name"], call["input"])
                trace.append({"type": "tool", "name": call["name"], "input": call["input"], "result": result})
                results.append({"type": "tool_result", "tool_use_id": call["id"], "content": json.dumps(result)})
            messages.append({"role": "user", "content": results})
            continue

        if not shop.orders and not followed_up:          # stopped without an order: the customer answers once
            followed_up = True
            messages.append({"role": "user", "content": case["follow_up"]})
            trace.append({"type": "customer", "text": case["follow_up"]})
            continue
        break                                            # a plain-text reply and nothing left to do: the run is over

    return {"trace": trace, "orders": shop.orders, "turns": len([m for m in messages if m["role"] == "assistant"])}
