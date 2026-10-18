#!/usr/bin/env python3
"""Check whether agents take most new names from the suggested list, though their own are viable more often.

New name: an accepted proposal in a round or replacement call that the campaign had not proposed in an earlier
call, the given starting candidate left out. Viable: in the grid's viable pool. Every name is classed once:
  list          on the current prompt's SUGGESTED NEW CANDIDATES list
  earlier list  not on the current list, but shown on an earlier list in the same campaign
  own           never shown on any list in the campaign
The baseline is new names with no list, from the control runs (Gemini 2.5 Flash, DeepSeek V3.1) and the
all-options-off Blind campaigns (all three models). Viable rates are compared by round band (1-3, 4-6, 7-9,
10-12, 13-15), with the own rate standardised to the list's round mix, and by distance from the best measured
candidate at the time (one letter, two, three or more). Intervals are 95% percentile bootstraps over whole
campaigns (2,000 draws, fixed seed); rates are ratios of sums.

Usage: python3 scripts/menu_check_0an.py      (writes results/menu_check_0an.json)
"""
import collections, json, os, random, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_0al as A0                                                 # noqa: E402
import grid                                                              # noqa: E402

ITEM = re.compile(r"^\d+\. ([A-Z]{4})$", re.M)
ROW = re.compile(r"^\s*\d+\s+([A-Z]{4})\s+(-?\d+\.\d+)\s*$", re.M)
BANDS = ((1, 3), (4, 6), (7, 9), (10, 12), (13, 15))
REF = "GDIF"
B = 2000


def band(r):
    return next(i for i, (lo, hi) in enumerate(BANDS) if lo <= r <= hi)


def hamming(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def best_measured(prompt):
    hist = prompt.split("HISTORY", 1)[1].split("SUGGESTED NEW CANDIDATES", 1)[0].split("Choose", 1)[0] \
        if "HISTORY" in prompt else ""
    v = collections.defaultdict(list)
    for s, x in ROW.findall(hist):
        v[s].append(float(x))
    return max(v, key=lambda s: sum(v[s]) / len(v[s])) if v else REF


def names(tag, cond=None, pool=None):
    """Per campaign: list of (class, round band, distance bucket, viable) for every new name."""
    camp = collections.defaultdict(list)
    seen = collections.defaultdict(set)
    shown = collections.defaultdict(set)
    for c in A0.calls(tag):
        if c.get("kind") == "nomination":
            continue
        if cond and cond not in (c.get("cell") or "").lower():
            continue
        key = (c["model"], c["campaign_seed"])
        p = c.get("prompt") or ""
        menu = set(ITEM.findall(p.split("SUGGESTED NEW CANDIDATES", 1)[1].split("Choose", 1)[0])) \
            if "SUGGESTED NEW CANDIDATES" in p else set()
        shown_before = set(shown[key])
        shown[key] |= menu
        best = best_measured(p)
        for s in c.get("parsed") or []:
            if s in seen[key] or s == REF:
                seen[key].add(s)
                continue
            seen[key].add(s)
            cls = "list" if s in menu else ("earlier list" if s in shown_before else "own")
            d = hamming(s, best)
            camp[key].append((cls, band(c["round"]), "1" if d <= 1 else "2" if d == 2 else "3+", s in pool))
    return camp


def rate(camps, keys, pred):
    n = v = 0
    for k in keys:
        for x in camps[k]:
            if pred(x):
                n += 1
                v += x[3]
    return (v / n if n else float("nan")), n, v


def std_own(camps, keys):
    """Own-name viable rate standardised to the list names' round-band mix."""
    w = collections.Counter()
    for k in keys:
        for x in camps[k]:
            if x[0] == "list":
                w[x[1]] += 1
    tot, acc = 0, 0.0
    for b, wt in w.items():
        r, n, _v = rate(camps, keys, lambda x, b=b: x[0] == "own" and x[1] == b)
        if n:
            acc += wt * r
            tot += wt
    return acc / tot if tot else float("nan")


def boot(camps, keys, fn, tag):
    rng = random.Random(tag)
    vals = []
    for _ in range(B):
        ks = [rng.choice(keys) for _ in keys]
        x = fn(camps, ks)
        if x == x:
            vals.append(x)
    vals.sort()
    return [vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]] if vals else [None, None]


def main():
    _fit, pool = grid.landscape()
    f2 = names("gen_0an_f2_menu", pool=pool)
    base = {"F0 control": names("gen_0an_f0_control", pool=pool),
            "Panel A0 Blind": names("panelA0_original", cond="blind", pool=pool)}
    out = {}
    for m in sorted({k[0] for k in f2}):
        keys = [k for k in f2 if k[0] == m]
        d = dict(campaigns=len(keys))
        for cls in ("list", "earlier list", "own"):
            r, n, v = rate(f2, keys, lambda x, cls=cls: x[0] == cls)
            d[cls] = dict(names=n, viable=v, rate=r,
                          ci=boot(f2, keys, lambda c, ks, cls=cls: rate(c, ks, lambda x: x[0] == cls)[0], m + cls))
        d["own_minus_list"] = dict(
            diff=d["own"]["rate"] - d["list"]["rate"],
            ci=boot(f2, keys, lambda c, ks: rate(c, ks, lambda x: x[0] == "own")[0] -
                    rate(c, ks, lambda x: x[0] == "list")[0], m + "diff"))
        d["own_round_standardised"] = dict(
            rate=std_own(f2, keys), ci=boot(f2, keys, std_own, m + "std"))
        d["own_std_minus_list"] = dict(
            diff=d["own_round_standardised"]["rate"] - d["list"]["rate"],
            ci=boot(f2, keys, lambda c, ks: std_own(c, ks) - rate(c, ks, lambda x: x[0] == "list")[0], m + "stdd"))
        d["by_band"] = {"%d-%d" % BANDS[b]: {cls: rate(f2, keys, lambda x, cls=cls, b=b: x[0] == cls and x[1] == b)
                                             for cls in ("list", "earlier list", "own")} for b in range(len(BANDS))}
        d["by_distance"] = {}
        for dist in ("1", "2", "3+"):
            d["by_distance"][dist] = {cls: rate(f2, keys, lambda x, cls=cls, dist=dist: x[0] == cls and x[2] == dist)
                                      for cls in ("list", "earlier list", "own")}
        d["baseline"] = {}
        for bname, bc in base.items():
            bk = [k for k in bc if k[0] == m]
            if not bk:
                continue
            r, n, v = rate(bc, bk, lambda x: True)
            d["baseline"][bname] = dict(campaigns=len(bk), names=n, viable=v, rate=r,
                                        ci=boot(bc, bk, lambda c, ks: rate(c, ks, lambda x: True)[0], m + bname),
                                        by_distance={dist: rate(bc, bk, lambda x, dist=dist: x[2] == dist)
                                                     for dist in ("1", "2", "3+")})
        out[m] = d
    json.dump(out, open(os.path.join(ROOT, "results", "menu_check_0an.json"), "w"), indent=1)
    for m, d in out.items():
        print("%s (%d campaigns)" % (m, d["campaigns"]))
        for cls in ("list", "earlier list", "own"):
            x = d[cls]
            print("   %-13s %5d names, %5d viable, %5.1f%% [%5.1f, %5.1f]" % (cls, x["names"], x["viable"],
                                                                         100 * x["rate"], 100 * x["ci"][0],
                                                                         100 * x["ci"][1]))
        print("   own minus list %+5.1f points [%+5.1f, %+5.1f]; own standardised to the list's rounds %.1f%%, minus list "
              "%+5.1f [%+5.1f, %+5.1f]" % (100 * d["own_minus_list"]["diff"], 100 * d["own_minus_list"]["ci"][0],
                                          100 * d["own_minus_list"]["ci"][1], 100 * d["own_round_standardised"]["rate"],
                                          100 * d["own_std_minus_list"]["diff"], 100 * d["own_std_minus_list"]["ci"][0],
                                          100 * d["own_std_minus_list"]["ci"][1]))
        for bname, b in d["baseline"].items():
            print("   baseline %-14s %5d names, %5d viable, %5.1f%% [%5.1f, %5.1f]" % (bname, b["names"], b["viable"],
                                                                                  100 * b["rate"], 100 * b["ci"][0],
                                                                                  100 * b["ci"][1]))
        for dist, v in d["by_distance"].items():
            print("   distance %-3s " % dist + "  ".join("%s %d/%d" % (cls, v[cls][2], v[cls][1]) for cls in v) +
                  "  | baselines " + "  ".join("%s %d/%d" % (bn, b["by_distance"][dist][2], b["by_distance"][dist][1])
                                               for bn, b in d["baseline"].items()))
        for bb, v in d["by_band"].items():
            print("   rounds %-6s " % bb + "  ".join("%s %d/%d" % (cls, v[cls][2], v[cls][1]) for cls in v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
