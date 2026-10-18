#!/usr/bin/env python3
"""Check whether a Gemini 4 model is listed on OpenRouter, from its public model list (no key is used).

Reports every listed id that names Gemini 4 or Argon, with its listing date, its input, output and reasoning
prices per million tokens, and whether the `reasoning` parameter is supported. Prints "none listed" otherwise.

Usage: python3 scripts/openrouter_watch.py
"""
import datetime, json, re, sys, urllib.request

URL = "https://openrouter.ai/api/v1/models"
PATTERN = re.compile(r"gemini[-_ ]?4|argon", re.I)


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "repdef-openrouter-watch"})
    data = json.load(urllib.request.urlopen(req, timeout=60))["data"]
    hits = [m for m in data if PATTERN.search(m["id"]) or PATTERN.search(m.get("name") or "")]
    print("%s: %d models listed" % (datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), len(data)))
    if not hits:
        print("Gemini 4: none listed")
        return 0
    for m in sorted(hits, key=lambda m: m["id"]):
        p = m.get("pricing") or {}
        per_m = lambda k: "%.2f" % (1e6 * float(p[k])) if p.get(k) not in (None, "") else "n/a"
        print("Gemini 4 listed: %s (%s), since %s; $%s in, $%s out, $%s internal reasoning per million; reasoning "
              "parameter %s" % (m["id"], m.get("name"), datetime.datetime.utcfromtimestamp(m["created"]).strftime("%Y-%m-%d"),
                                per_m("prompt"), per_m("completion"), per_m("internal_reasoning"),
                                "supported" if "reasoning" in (m.get("supported_parameters") or []) else "not listed"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
