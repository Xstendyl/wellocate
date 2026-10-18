#!/usr/bin/env python3
"""Find logged calls whose answer was taken from the model's reasoning text, and what each campaign did with them.

A call is flagged when raw_response is non-empty, reasoning_tokens > 0 and completion_tokens - reasoning_tokens
<= 5. Every archived call log (results/grid_<tag>_calls/*.jsonl.gz) and any plain one is read. For each flagged
call it records whether the round or slot was lost, the parsed candidates were ordered, or the parse became the
nominee.

Usage: python3 scripts/audit_reasoning_fallback.py      (writes results/audit_reasoning_fallback.json)
"""
import collections, glob, gzip, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")


def suspect(c):
    rt, ct = c.get("reasoning_tokens") or 0, c.get("completion_tokens") or 0
    return bool((c.get("raw_response") or "").strip()) and rt > 0 and ct - rt <= 5


def outcome(c):
    got = c.get("parsed") or []
    if c.get("kind") == "nomination":
        return "nomination parsed as %r" % (got,) if got else "nomination unparsed"
    if c.get("n_slots") == c.get("slots_per_round"):
        return "round call: candidates ordered %s" % got if got else "round call: no candidates, round lost"
    return "replacement ask: %s ordered" % got if got else "replacement ask: no candidate, slot lost"


def main():
    out, total, per = {}, 0, collections.Counter()
    files = sorted(glob.glob(os.path.join(RES, "grid_*_calls", "*.jsonl.gz"))) + \
        sorted(p for p in glob.glob(os.path.join(RES, "grid_*_calls.jsonl")) if os.path.getsize(p) > 0)
    for f in files:
        tag = os.path.basename(os.path.dirname(f) if f.endswith(".gz") else f)[len("grid_"):].replace("_calls.jsonl", "").replace("_calls", "")
        fh = gzip.open(f, "rt") if f.endswith(".gz") else open(f)
        with fh:
            for line in fh:
                if not line.strip():
                    continue
                c = json.loads(line)
                total += 1
                cell = c.get("cell") or os.path.basename(f).split("__")[0]
                key = "%s|%s|%s" % (tag, cell, (c.get("model") or "").split("/")[-1])
                per[key] += 0
                if len(c.get("raw_response") or "") > 1500:
                    vis = (c.get("completion_tokens") or 0) - (c.get("reasoning_tokens") or 0)
                    lg = out.setdefault("long", {}).setdefault(key, [0, None])
                    lg[0] += 1
                    lg[1] = vis if lg[1] is None else min(lg[1], vis)
                if suspect(c):
                    per[key] += 1
                    out.setdefault("suspects", []).append(dict(
                        tag=tag, cell=cell, model=c.get("model"), seed=c.get("campaign_seed"), round=c.get("round"),
                        kind=c.get("kind") or ("round" if c.get("n_slots") == c.get("slots_per_round") else "replacement"),
                        completion_tokens=c.get("completion_tokens"), reasoning_tokens=c.get("reasoning_tokens"),
                        parse_status=c.get("parse_status"), text_start=(c.get("raw_response") or "")[:60],
                        what_the_campaign_did=outcome(c)))
    tags = collections.Counter(k.split("|")[0] for k, v in per.items() if v)
    res = dict(rule="raw_response non-empty, reasoning_tokens > 0, completion_tokens - reasoning_tokens <= 5",
               calls_read=total, files_read=len(files), suspects=out.get("suspects", []),
               per_tag_cell_model={k: v for k, v in sorted(per.items())}, tags_with_suspects=dict(tags),
               long_answers={k: dict(calls=v[0], fewest_visible_tokens=v[1]) for k, v in sorted(out.get("long", {}).items())})
    json.dump(res, open(os.path.join(RES, "audit_reasoning_fallback.json"), "w"), indent=1)
    print("%d calls in %d files; rule: %s" % (total, len(files), res["rule"]))
    print("suspect calls: %d" % len(res["suspects"]))
    for s in res["suspects"]:
        print("   %s | %s | %s seed %s round %s %s | %s/%s tokens | %s | %r | %s"
              % (s["tag"], s["cell"], (s["model"] or "").split("/")[-1], s["seed"], s["round"], s["kind"],
                 s["completion_tokens"], s["reasoning_tokens"], s["parse_status"], s["text_start"][:30],
                 s["what_the_campaign_did"]))
    for k, v in res["long_answers"].items():
        if k.startswith("panelc|"):
            print("long answers (over 1,500 characters) %s: %d, fewest visible tokens %s" % (k, v["calls"],
                                                                                         v["fewest_visible_tokens"]))
    by_tag = collections.defaultdict(int)
    for k, v in per.items():
        by_tag[k.split("|")[0]] += v
    print("per tag (suspects): " + ", ".join("%s %d" % (t, n) for t, n in sorted(by_tag.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
