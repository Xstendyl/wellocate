#!/usr/bin/env python3
"""Check whether max_tokens (6,000, reasoning effort "medium") truncates the reasoning panel's calls.

Reported per model and per call kind, since round decisions and the final nomination can differ.
"""
import collections, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(tag):
    p = os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag)
    return [json.loads(l) for l in open(p) if l.strip()]


def q(v, p):
    if not v:
        return float("nan")
    s = sorted(v)
    i = min(len(s) - 1, int(round(p * (len(s) - 1))))
    return s[i]


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "rprobe"
    rows = load(tag)
    man = json.load(open(os.path.join(ROOT, "results", "grid_%s_manifest.json" % tag)))
    cap = man["max_tokens"]
    # OpenRouter's "effort" budget is a fraction of max_tokens (half for medium); both thresholds are reported.
    half = cap // 2
    print("=" * 104)
    print("REASONING BUDGET  tag=%s  max_tokens=%d  effort=%s  (half of max_tokens = %d)"
          % (tag, cap, man.get("reasoning_effort"), half))
    print("=" * 104)
    print("  %-22s %-12s %5s %8s %8s %8s %8s %7s %7s %7s"
          % ("model", "kind", "n", "median", "p90", "max", "mean", ">=half", ">=cap", "zero"))
    out = []
    for m in sorted({r["model"] for r in rows}):
        for kind in ("round", "nomination", "reask", "replacement"):
            v = [r.get("reasoning_tokens") or 0 for r in rows
                 if r["model"] == m and r["kind"] == kind]
            if not v:
                continue
            at_half = sum(1 for x in v if x >= half)
            at_cap = sum(1 for x in v if x >= cap)
            zero = sum(1 for x in v if x == 0)
            print("  %-22s %-12s %5d %8.0f %8.0f %8d %8.1f %6.1f%% %6.1f%% %6.1f%%"
                  % (m.split("/")[-1], kind, len(v), st.median(v), q(v, 0.90), max(v),
                     st.mean(v), 100.0 * at_half / len(v), 100.0 * at_cap / len(v),
                     100.0 * zero / len(v)))
            out.append(dict(model=m, kind=kind, n=len(v), median=st.median(v), p90=q(v, 0.90),
                            max=max(v), mean=st.mean(v), share_at_half=at_half / len(v),
                            share_at_cap=at_cap / len(v), share_zero=zero / len(v)))
    print()
    print("  SHARE OF CALLS THAT REASONED AT ALL, and COMPLETION tokens beside them, since a reasoning")
    print("  ceiling that binds steals room from the answer the model still has to produce:")
    print("  %-22s %-12s %5s %9s %11s %11s" % ("model", "kind", "n", "reasoned", "median compl", "max compl"))
    for m in sorted({r["model"] for r in rows}):
        for kind in ("round", "nomination"):
            v = [r for r in rows if r["model"] == m and r["kind"] == kind]
            if not v:
                continue
            rr = sum(1 for r in v if (r.get("reasoning_tokens") or 0) > 0)
            c = [r.get("completion_tokens") or 0 for r in v]
            print("  %-22s %-12s %5d %8.1f%% %11.0f %11d"
                  % (m.split("/")[-1], kind, len(v), 100.0 * rr / len(v), st.median(c), max(c)))
    print()
    print("  FINISH REASONS. A `length` finish is the ceiling speaking, and is the only direct evidence")
    print("  that a call was cut off instead of choosing to stop:")
    fr = collections.Counter((r["model"].split("/")[-1], r["kind"], r.get("finish_reason"))
                             for r in rows)
    for (m, k, f), n in sorted(fr.items()):
        print("    %-22s %-12s %-14s %d" % (m, k, f, n))
    dst = os.path.join(ROOT, "results", "reasoning_budget_%s.json" % tag)
    json.dump(dict(tag=tag, max_tokens=cap, half=half, effort=man.get("reasoning_effort"),
                   rows=out), open(dst, "w"), indent=1)
    print("\n  wrote %s" % os.path.relpath(dst, ROOT))


if __name__ == "__main__":
    main()
