#!/usr/bin/env python3
"""Run a language model through Wellocate in text mode: the exact prompts the paper's agents received.

The model is called through OpenRouter with the key in the OPENROUTER_API_KEY environment variable. The key is
read by repdef.llm and never printed. Without --run the script prints the first prompt and exits, so nothing is
spent until you ask.

Usage: python3 examples/llm_agent_loop.py                                   (print the first prompt)
       OPENROUTER_API_KEY=... python3 examples/llm_agent_loop.py --run --model google/gemini-2.5-flash
"""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import llm  # noqa: E402
from wellocate import Wellocate  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--landscape", default="gb1")
    ap.add_argument("--split", default="gb1:test")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default="google/gemini-2.5-flash")
    ap.add_argument("--run", action="store_true", help="call the model (costs money)")
    a = ap.parse_args()
    env = Wellocate(a.landscape, a.split, seed=a.seed)
    if not a.run:
        print(env.prompt())
        return 0
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("set OPENROUTER_API_KEY in the environment")
    done, info, calls = False, {}, 0
    while not done:
        call = llm.complete(env.prompt(), a.model, max_tokens=3000, temperature=0.0)
        if not call.ok:
            raise SystemExit("the call failed: %s" % call.error)
        calls += 1
        _obs, reward, done, info = env.act_text(call.text)
    sc = info["scorecard"]
    print("nominee %s, true value %.3f, re-testing share %.1f%%, %d calls"
          % (info["nominee"], reward, sc["share_budget"], calls))
    return 0


if __name__ == "__main__":
    sys.exit(main())
