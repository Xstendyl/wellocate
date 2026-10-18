#!/usr/bin/env python3
"""Does replication in the Blind rung follow visible evidence of noise, or precede it? No API calls.

Evidence of noise appears in two ways: the anchor reads far from its stated value (one reading suffices), or
a repeated variant's two readings differ (which needs a re-order first). The test compares replication per
slot before and after the first visible contradiction, paired within campaign, with a bootstrap interval.
The anchor counts as far from its stated 6.87 when a reading differs by more than 0.30 (about 0.6 noise SD).
"""
import collections, json, math, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import repdef.rng as R

ANCHOR, STATED, TOL = "GDIF", 6.87, 0.30
ROW = re.compile(r"^\s*(\d+)\s+([A-Z]{4})\s+(-?\d+\.\d+)\s*$")


def history_of(prompt):
    """The (round, seq, value) rows the prompt actually showed the agent."""
    if "HISTORY" not in prompt:
        return []
    out = []
    for line in prompt.split("HISTORY", 1)[1].splitlines():
        m = ROW.match(line)
        if m:
            out.append((int(m.group(1)), m.group(2), float(m.group(3))))
    return out


def first_contradiction(calls):
    """(round, route) at which the shown history first contradicts an exact-reading world."""
    for c in sorted(calls, key=lambda x: (x["round"], x.get("kind") != "round")):
        rows = history_of(c["prompt"])
        if not rows:
            continue
        vals = collections.defaultdict(list)
        for _r, seq, v in rows:
            vals[seq].append(v)
        # Rounds are scanned in order, so a route seen in an earlier round is credited there.
        a = any(abs(v - STATED) > TOL for v in vals.get(ANCHOR, []))
        b = any(len(v) > 1 and len(set(v)) > 1 for v in vals.values())
        if a or b:
            return c["round"], ("A_anchor" if a and not b else
                                ("B_repeat" if b and not a else "both_same_round"))
    return None, None


def first_reorder(calls):
    """The round in which the agent first orders a variant it has already measured."""
    seen = set()
    for c in sorted(calls, key=lambda x: (x["round"], x.get("kind") != "round")):
        props = c.get("parsed") or []
        if any(s in seen for s in props):
            return c["round"]
        seen.update(props)
    return None


def rep_rate(calls, lo, hi):
    """Replication per slot over rounds in [lo, hi). Returns None when no slots fall in the window."""
    seen, rep, tot = set(), 0, 0
    for c in sorted(calls, key=lambda x: (x["round"], x.get("kind") != "round")):
        props = c.get("parsed") or []
        inside = lo <= c["round"] < hi
        for s in props:
            if inside:
                tot += 1
                if s in seen:
                    rep += 1
            seen.add(s)
    return (rep / tot) if tot else None


def _ols2(x1, x2, y):
    """Two-regressor OLS with an intercept, by normal equations. Returns (b1, b2, se(b2), n).

    Used to absorb the round trend before reading the post-evidence coefficient.
    """
    n = len(y)
    if n < 4:
        return float("nan"), float("nan"), float("nan"), n
    X = [(1.0, a, b) for a, b in zip(x1, x2)]
    XtX = [[sum(r[i] * r[j] for r in X) for j in range(3)] for i in range(3)]
    Xty = [sum(r[i] * yy for r, yy in zip(X, y)) for i in range(3)]
    inv = _inv3(XtX)
    if inv is None:
        return float("nan"), float("nan"), float("nan"), n
    beta = [sum(inv[i][k] * Xty[k] for k in range(3)) for i in range(3)]
    resid = [yy - sum(b_ * r_ for b_, r_ in zip(beta, r)) for r, yy in zip(X, y)]
    s2 = sum(e * e for e in resid) / (n - 3)
    return beta[1], beta[2], math.sqrt(max(0.0, s2 * inv[2][2])), n


def _inv3(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-18:
        return None
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def boot(v, b=4000):
    n = len(v)
    if n < 2:
        return float("nan"), float("nan")
    d = sorted(sum(v[R._u64("b", i, j) % n] for j in range(n)) / n for i in range(b))
    return d[int(0.025 * b)], d[min(b - 1, int(0.975 * b))]


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "stage1"
    rows = [json.loads(l) for l in
            open(os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag))]
    camps = collections.defaultdict(list)
    for r in rows:
        if r["rung"] == "blind" and r.get("kind") != "nomination":
            camps[(r["model"], r["campaign_seed"])].append(r)
    print("=" * 100)
    print("BLIND RUNG: does replication FOLLOW visible evidence of noise?   %d campaigns" % len(camps))
    print("=" * 100)
    print("  anchor %s, stated %.2f, threshold |reading - stated| > %.2f  (sigma at that level 0.502)"
          % (ANCHOR, STATED, TOL))

    route = collections.Counter()
    order_vs_evidence = collections.Counter()
    befores, afters, pairs = [], [], []
    for key, calls in sorted(camps.items()):
        cr, rt = first_contradiction(calls)
        fo = first_reorder(calls)
        route[rt or "none"] += 1
        if cr is None:
            order_vs_evidence["no contradiction ever shown"] += 1
        elif fo is None:
            order_vs_evidence["no re-order ever"] += 1
        elif fo < cr:
            order_vs_evidence["RE-ORDER BEFORE evidence"] += 1
        elif fo == cr:
            order_vs_evidence["same round"] += 1
        else:
            order_vs_evidence["evidence before re-order"] += 1
        if cr is None:
            continue
        b4 = rep_rate(calls, 1, cr)
        af = rep_rate(calls, cr, 10 ** 6)
        if b4 is not None:
            befores.append(b4)
        if af is not None:
            afters.append(af)
        if b4 is not None and af is not None:
            pairs.append(af - b4)

    print("\n  WHICH ROUTE gave the first contradiction:")
    for k, v in route.most_common():
        print("    %-22s %3d" % (k, v))
    print("\n  ORDER OF EVENTS, which is the point:")
    for k, v in order_vs_evidence.most_common():
        print("    %-30s %3d of %d" % (k, v, len(camps)))

    print("\n  " + "-" * 96)
    print("  REPLICATION PER SLOT, before against after the first visible contradiction")
    print("  " + "-" * 96)
    if befores:
        lo, hi = boot(befores)
        print("    before  %5.1f%%  95%% CI [%.1f%%, %.1f%%]  n=%d campaigns"
              % (100 * st.mean(befores), 100 * lo, 100 * hi, len(befores)))
    if afters:
        lo, hi = boot(afters)
        print("    after   %5.1f%%  95%% CI [%.1f%%, %.1f%%]  n=%d campaigns"
              % (100 * st.mean(afters), 100 * lo, 100 * hi, len(afters)))
    verdict = "inconclusive"
    if pairs:
        lo, hi = boot(pairs)
        m = st.mean(pairs)
        print("    PAIRED difference (after minus before)  %+.1f pp  95%% CI [%+.1f, %+.1f]  n=%d"
              % (100 * m, 100 * lo, 100 * hi, len(pairs)))
        if lo > 0:
            verdict = "a clear rise: later replication is EVIDENCE-DRIVEN"
        elif hi < 0:
            verdict = "a clear FALL after the evidence, which no hypothesis predicted"
        else:
            verdict = "NO CHANGE: a default independent of evidence"
        print("\n    READING (fixed before the numbers): %s" % verdict)
    # Before/after is confounded with campaign progress: replication rises as more variants have been
    # measured. Two controls follow.
    print("\n  " + "-" * 96)
    print("  CONTROL 1: replication per ROUND regressed on round AND a post-contradiction indicator")
    print("  " + "-" * 96)
    xs_round, xs_post, ys = [], [], []
    for key, calls in sorted(camps.items()):
        cr, _rt = first_contradiction(calls)
        if cr is None:
            continue
        seen = set()
        for c in sorted(calls, key=lambda x: (x["round"], x.get("kind") != "round")):
            props = c.get("parsed") or []
            if props:
                f = sum(1 for s_ in props if s_ in seen) / len(props)
                xs_round.append(float(c["round"]))
                xs_post.append(1.0 if c["round"] >= cr else 0.0)
                ys.append(f)
            seen.update(props)
    b_round, b_post, se_post, n_obs = _ols2(xs_round, xs_post, ys)
    print("    %d round-observations. Replication fraction per round:" % n_obs)
    print("      slope on ROUND                 %+.5f per round" % b_round)
    print("      coefficient on POST-EVIDENCE   %+.4f +- %.4f  (%.1f SE)"
          % (b_post, se_post, abs(b_post / se_post) if se_post else float("nan")))
    survives = bool(se_post and abs(b_post / se_post) >= 2)
    print("      %s once the campaign's own time trend is absorbed."
          % ("The post-evidence effect SURVIVES" if survives else
             "The post-evidence effect DOES NOT survive"))

    print("\n  CONTROL 2: a NARROW window, the two rounds either side of the contradiction")
    narrow = []
    for key, calls in sorted(camps.items()):
        cr, _rt = first_contradiction(calls)
        if cr is None or cr < 3:
            continue
        b4 = rep_rate(calls, cr - 2, cr)
        af = rep_rate(calls, cr, cr + 2)
        if b4 is not None and af is not None:
            narrow.append(af - b4)
    if narrow:
        lo, hi = boot(narrow)
        print("    paired difference %+.1f pp  95%% CI [%+.1f, %+.1f]  n=%d campaigns with cr >= 3"
              % (100 * st.mean(narrow), 100 * lo, 100 * hi, len(narrow)))
    else:
        print("    too few campaigns with a contradiction at round 3 or later.")

    print("\n  The zero-noise control remains the CONFIRMATORY test. This observational version cannot")
    print("  separate a default from an evidence response that saturates immediately, and its headline")
    print("  before/after contrast is confounded with campaign progress, which is what the two controls")
    print("  above address.")
    json.dump(dict(tag=tag, n_campaigns=len(camps), routes=dict(route),
                   order_of_events=dict(order_vs_evidence),
                   before=st.mean(befores) if befores else None,
                   after=st.mean(afters) if afters else None,
                   paired_diff=st.mean(pairs) if pairs else None,
                   paired_ci=list(boot(pairs)) if pairs else None,
                   n_pairs=len(pairs), threshold=TOL, stated=STATED, verdict=verdict,
                   control_round_slope=b_round, control_post_coef=b_post,
                   control_post_se=se_post, control_post_survives=survives,
                   control_narrow_diff=(st.mean(narrow) if narrow else None),
                   control_narrow_ci=(list(boot(narrow)) if narrow else None),
                   control_narrow_n=len(narrow)),
              open(os.path.join(ROOT, "results", "step9_blind_evidence_timing.json"), "w"), indent=1)
    print("\nsaved results/step9_blind_evidence_timing.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
