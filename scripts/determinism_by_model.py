#!/usr/bin/env python3
"""How deterministic is temperature 0, per model? Measured on the round-1 prompt.

At round 1 there is no history, so the prompt is identical across all seeds within a cell, and the number
of distinct replies shows how much sampling variation temperature 0 leaves for each model.
"""
import collections, glob, gzip, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rows_for(tag):
    p = os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag)
    if os.path.exists(p):
        with open(p) as f:
            for l in f:
                if l.strip():
                    yield json.loads(l)
        return
    for g in sorted(glob.glob(os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz"))):
        with gzip.open(g, "rt") as f:
            for l in f:
                if l.strip():
                    yield json.loads(l)


def main():
    for tag in sys.argv[1:] or ["stage0", "stage1"]:
        cells = collections.defaultdict(list)
        prompts = collections.defaultdict(set)
        raw = collections.defaultdict(list)
        for r in rows_for(tag):
            if r.get("kind") != "round" or r.get("round") != 1:
                continue
            k = (r["model"].split("/")[-1], r["rung"])
            raw[k].append((r.get("prompt") or "", (r.get("raw_response") or "").strip()))
        # Format-reminder re-asks are also logged as kind="round", so only replies to the prompt every
        # seed received are counted; the rest are reported as excluded.
        excluded = {}
        for k, pairs in raw.items():
            modal_prompt = collections.Counter(p for p, _ in pairs).most_common(1)[0][0]
            cells[k] = [a for p, a in pairs if p == modal_prompt]
            prompts[k] = {modal_prompt}
            excluded[k] = len(pairs) - len(cells[k])
        if not cells:
            print("%s: no round-1 calls found" % tag)
            continue
        print("=" * 100)
        print("ROUND-1 DETERMINISM, tag=%s. One prompt per cell, sent n times." % tag)
        print("=" * 100)
        print("  %-22s %-14s %4s %8s %9s %9s %s"
              % ("model", "rung", "n", "re-asks", "distinct", "modal", "identical?"))
        by_model = collections.defaultdict(list)
        for (m, rung), reps in sorted(cells.items()):
            n = len(reps)
            d = len(set(reps))
            modal = collections.Counter(reps).most_common(1)[0][1]
            np_ = excluded[(m, rung)]
            print("  %-22s %-14s %4d %8d %9d %9d %s"
                  % (m, rung, n, np_, d, modal, "yes" if d == 1 else "no"))
            by_model[m].append((n, d, modal))
        print()
        print("  PER MODEL, over its rungs:")
        for m, v in sorted(by_model.items()):
            tot = sum(x[0] for x in v)
            mm = sum(x[2] for x in v)
            print("    %-22s distinct replies per cell %s   modal reply covers %d of %d calls (%.0f%%)"
                  % (m, "-".join(str(x) for x in sorted({x[1] for x in v})), mm, tot, 100.0 * mm / tot))
        dst = os.path.join(ROOT, "results", "determinism_by_model_%s.json" % tag)
        json.dump({"%s|%s" % k: dict(n=len(v), distinct=len(set(v)),
                                     modal=collections.Counter(v).most_common(1)[0][1])
                   for k, v in cells.items()}, open(dst, "w"), indent=1)
        print("\n  wrote %s\n" % os.path.relpath(dst, ROOT))


if __name__ == "__main__":
    main()
