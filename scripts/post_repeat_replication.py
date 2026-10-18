#!/usr/bin/env python3
"""Post-repeat replication, zero-noise against noise: do agents replicate in response to noise?

  python3 scripts/post_repeat_replication.py zeronoise stage1 --redact --out DIR

Definitions:
  * a replication slot is an order for a variant that already has a successful reading. Re-ordering a variant
    whose only previous order failed is not replication, unlike campaign.py's replication_count, which counts
    every attempted order. Both are reported.
  * r* is the round in which a second successful reading of any variant is received; it becomes visible in
    the prompt for r*+1.
  * post-repeat replication is the replication fraction over the orders in rounds r*+1 to 15.
  * campaigns with no repeat, or r* = 15, are excluded and counted per cell on both tags.

The per-slot history is not saved, so it is rebuilt from the histories the prompts showed, in both the
per-reading view (`round seq value`) and the aggregated view (`candidate n mean se`, where n >= 2 is a repeat).
"""
import argparse, collections, glob, gzip, json, math, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_grid as AG                                            # noqa: E402
import repdef.rng as R                                               # noqa: E402

ROW = re.compile(r"^\s*(\d+)\s+([A-Z]{4})\s+(-?\d+\.\d+)\s*$")       # per-reading view
AGG = re.compile(r"^\s*([A-Z]{4})\s+(\d+)\s+")                       # aggregated view: candidate, n
# The final nomination history lists every charged slot in measurement order, for the four per-reading
# rungs (60 rows per campaign).
SLOT_ROW = re.compile(r"^\s*(\d+)\s+(\S+)\s+(.*)$")
REJECTED = "rejected, not viable"
FAILED = "order failed, no reading"
SLOT_LOST = "SLOT LOST"
ROUND_LOST = "ROUND LOST"
LADDER = ["Blind", "Quantitative", "Mechanism", "Aggregated", "Decision-rule"]
RUNG = {"Blind": "blind", "Quantitative": "informed", "Mechanism": "instructed",
        "Aggregated": "aggregated", "Decision-rule": "decision_rule"}
REP_DEFS = [("over slots used", "replication_fraction"),
            ("over all 60 slots", "replication_fraction_of_budget"),
            ("excl anchor, slots used", "replication_fraction_excl_anchor"),
            ("excl anchor, all 60", "replication_fraction_excl_anchor_of_budget")]


def calls_of(tag):
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


def read_counts(prompt):
    """{variant: number of successful readings} as the prompt showed it. Both view formats."""
    if "HISTORY" not in prompt:
        return {}
    body = prompt.split("HISTORY", 1)[1]
    per = collections.Counter()
    agg = {}
    for line in body.splitlines():
        m = ROW.match(line)
        if m:
            per[m.group(2)] += 1
            continue
        a = AGG.match(line)
        if a:
            agg[a.group(1)] = int(a.group(2))
    if per and agg:
        # Both matched, which would mean the view changed mid-prompt. Refuse instead of guessing.
        raise ValueError("a prompt matched BOTH history formats; the parser cannot choose")
    return dict(per) if per else agg


def viable_set():
    """The viable pool, rebuilt from the grid's landscape, to tell an order that used a slot from a proposal
    rejected as non-viable."""
    import grid as G
    _fit, pool = G.landscape()
    return set(pool)


def final_history(calls):
    """The charged slots in measurement order, from the final nomination prompt. (round, seq, kind).

    kind is "read", "failed", "lost" or "round_lost". A `rejected, not viable` row is skipped, because that
    slot was refilled by a replacement and charged only once, at whatever finally occupied it.
    """
    nom = [c for c in calls if c.get("kind") == "nomination"]
    if not nom:
        return None
    body = (nom[-1].get("prompt") or "").split("HISTORY", 1)
    if len(body) < 2:
        return None
    out = []
    for line in body[1].splitlines():
        m = SLOT_ROW.match(line)
        if not m:
            continue
        rnd, seq, tail = int(m.group(1)), m.group(2), m.group(3).strip()
        if tail.startswith(REJECTED):
            continue
        if re.match(r"^-?\d+\.\d+$", tail):
            out.append((rnd, seq, "read"))
        elif tail.startswith(FAILED):
            out.append((rnd, seq, "failed"))
        elif tail.startswith(SLOT_LOST):
            out.append((rnd, seq, "lost"))
        elif tail.startswith(ROUND_LOST):
            out.append((rnd, seq, "round_lost"))
    return out or None


def measurement_time(hist):
    """Primary definition: walk the charged slots in measurement order.

    A slot is replication when its variant already has a successful reading when it is measured. The
    denominator is the slots where a measurement was attempted (a reading or a failed order), not lost slots
    or lost rounds. `slots_counted` is every charged slot, so it reconciles with `slots_used`.
    """
    have, r_star = set(), None
    per_round = collections.defaultdict(lambda: [0, 0])          # round -> [reps, measured slots]
    charged = 0
    for rnd, seq, kind in hist:
        charged += 1
        if kind not in ("read", "failed"):
            continue                                             # charged, but no measurement attempted
        per_round[rnd][1] += 1
        if seq in have:
            per_round[rnd][0] += 1
            if kind == "read" and r_star is None:
                r_star = rnd                                     # the SECOND successful reading
        if kind == "read":
            have.add(seq)
    if r_star is None:
        return dict(r_star=None, reps_after=0, orders_after=0, slots_counted=charged, post_repeat=None)
    reps = sum(v[0] for r, v in per_round.items() if r > r_star)
    slots = sum(v[1] for r, v in per_round.items() if r > r_star)
    return dict(r_star=r_star, reps_after=reps, orders_after=slots, slots_counted=charged,
                post_repeat=(reps / float(slots)) if slots else None)


def reconstruct(cs, seed, viable, fail_rate=0.15, slots_per_round=4, slots_total=60, rounds=15):
    """The charged slots in measurement order, rebuilt from the calls, for the aggregated rung.

    Walk each round's batch in order. A non-viable batch order is rejected and takes no slot: consume the next
    replacement calls of that round in file order, at most three, until one is viable; if none is, the slot is
    lost. Failure is redrawn from the oracle's stream, `uniform("fail", seed, seq, i) < 0.15`, where i counts
    only that variant's slot-consuming attempts, as in `Oracle.measure`.

    Returns (history, unconsumed_replacements); a leftover replacement call means the walk missed an ask.
    """
    by_round = collections.defaultdict(lambda: {"batch": None, "reps": []})
    for c in cs:
        if c["kind"] == "round":
            by_round[c["round"]]["batch"] = list(c.get("parsed") or [])
        elif c["kind"] == "replacement":
            by_round[c["round"]]["reps"].append(list(c.get("parsed") or []))
    hist, attempts, used, leftover = [], collections.Counter(), 0, 0
    for rnd in range(1, rounds + 1):
        if rnd not in by_round or used >= slots_total:
            continue
        budget = min(slots_per_round, slots_total - used)
        batch, reps = by_round[rnd]["batch"], by_round[rnd]["reps"]
        ptr = 0
        if not batch:
            # A reply that was not the requested number of candidates forfeits the whole round.
            for _ in range(budget):
                hist.append((rnd, "----", "round_lost"))
            used += budget
            leftover += len(reps)
            continue
        filled = 0
        for pick in batch:
            if filled >= budget:
                break
            cand, tries = pick, 0
            while True:
                if cand in viable:
                    i = attempts[cand]
                    attempts[cand] = i + 1
                    failed = R.uniform("fail", seed, cand, i) < fail_rate
                    hist.append((rnd, cand, "failed" if failed else "read"))
                    filled += 1
                    used += 1
                    break
                tries += 1
                if tries > 3 or ptr >= len(reps):
                    hist.append((rnd, cand, "lost"))
                    filled += 1
                    used += 1
                    break
                nxt = reps[ptr]
                ptr += 1
                if not nxt:
                    # An empty replacement parse abandons the slot at once, under the candidate just
                    # rejected, as campaign.py does.
                    hist.append((rnd, cand, "lost"))
                    filled += 1
                    used += 1
                    break
                cand = nxt[0]
        leftover += max(0, len(reps) - ptr)
    return hist, leftover


def per_campaign(tag, viable=None):
    """(model, rung, seed) -> the post-repeat quantities, from the shown histories alone.

    The key includes the model because all models share the same seed range.
    """
    if viable is None:
        viable = viable_set()
    byc = collections.defaultdict(list)
    for c in calls_of(tag):
        # The nomination call is kept because its prompt carries the final measurement-ordered history;
        # it is not an order, so the slot loop skips it.
        if c.get("kind") in ("round", "replacement", "nomination"):
            byc[(c["model"], c["rung"], c["campaign_seed"])].append(c)
    out = {}
    for key, cs in byc.items():
        cs.sort(key=lambda x: (x["round"], {"round": 0, "replacement": 1}.get(x["kind"], 2)))
        r_star = None
        orders_after = reps_after = slots_total = 0
        for c in cs:
            if c["kind"] == "nomination":
                continue                      # not an order; used only for final_history
            try:
                counts = read_counts(c.get("prompt") or "")
            except ValueError:
                counts = None
            # Slot-consuming orders only, counted on every round, so the total can be checked against
            # slots_used (viable orders + lost_slots == slots_used).
            taken = [q for q in (c.get("parsed") or []) if q in viable]
            slots_total += len(taken)
            if counts is None:
                continue
            shown_round = c["round"]
            # r* is the round in which the second reading was received. A round prompt's history covers only
            # completed rounds, so a duplicate there arrived in the previous round; a replacement prompt is
            # rendered mid-round, so a duplicate there arrived in this round.
            if r_star is None and any(v >= 2 for v in counts.values()):
                r_star = shown_round - 1 if c["kind"] == "round" else shown_round
            if r_star is not None and shown_round > r_star:
                have = {k for k, v in counts.items() if v >= 1}
                for seq in taken:
                    orders_after += 1
                    if seq in have:
                        reps_after += 1
        decision = dict(r_star=r_star, orders_after=orders_after, reps_after=reps_after,
                        slots_counted=slots_total,
                        post_repeat=(reps_after / float(orders_after)) if orders_after else None)
        hist = final_history(cs)
        if hist is not None:
            prim = measurement_time(hist)
            prim["decision_time"] = decision
            prim["source"] = "final_history"
            out[key] = prim
        else:
            # The aggregated rung shows no order, so it is reconstructed. The walk reproduces the final
            # history on every per-reading campaign, where it can be checked.
            hist2, leftover = reconstruct(cs, key[2], viable)
            prim = measurement_time(hist2)
            prim["decision_time"] = decision
            prim["source"] = "reconstructed"
            prim["unconsumed_replacements"] = leftover
            out[key] = prim
    return out


def check_slots(tag, pc):
    """Per campaign, the slots counted here must reconcile exactly with slots_used."""
    rows = AG.load(tag)
    bad, n = [], 0
    for r in rows:
        k = (r["model"], RUNG[r["condition"]], r["seed"])
        got = (pc.get(k) or {}).get("slots_counted")
        if got is None:
            bad.append((k, "no calls found"))
            continue
        n += 1
        src = (pc.get(k) or {}).get("source")
        # The exact and reconstructed paths count every charged slot, so both equal slots_used; the
        # decision-time fallback counts viable orders only, so lost_slots is subtracted.
        want = r["slots_used"] if src in ("final_history", "reconstructed") else r["slots_used"] - (r.get("lost_slots") or 0)
        if got != want:
            bad.append((k, "source %s: counted %d != %d (slots_used %d, lost %d)"
                        % (src, got, want, r["slots_used"], r.get("lost_slots") or 0)))
    return n, bad


def boot_ci(v, b=None, tag="ci"):
    b = AG.BOOT_REPS if b is None else b
    if len(v) < 2:
        return float("nan"), float("nan")
    n = len(v)
    d = sorted(st.mean([v[R._u64(tag, i, j) % n] for j in range(n)]) for i in range(b))
    return d[int(0.025 * b)], d[min(b - 1, int(0.975 * b))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("panel")
    ap.add_argument("reference")
    ap.add_argument("--out", default=None)
    ap.add_argument("--redact", action="store_true")
    a = ap.parse_args()
    if a.redact:
        os.environ["ANALYSE_GRID_REDACT"] = "1"
    out = a.out or os.path.join(ROOT, "results", "analysis_final", a.panel)
    os.makedirs(out, exist_ok=True)

    viable = viable_set()
    pan_pr, ref_pr = per_campaign(a.panel, viable), per_campaign(a.reference, viable)
    for tag, pc in ((a.panel, pan_pr), (a.reference, ref_pr)):
        n, bad = check_slots(tag, pc)
        print("  slot reconciliation, %-10s %4d campaigns checked, %d mismatches" % (tag, n, len(bad)))
        for b in bad[:5]:
            print("    %s %s" % b)
        if bad:
            sys.exit("REFUSED: the slots counted do not reconcile with slots_used, so the denominator "
                     "is not the slots.")
    pan_c = AG.by_seed_rows(AG.load(a.panel))
    ref_c = AG.by_seed_rows(AG.load(a.reference))
    models = sorted({m for _c, m in pan_c} & {m for _c, m in ref_c})

    L = ["TABLE 2c. THE CENTRAL TEST (section 0ad): %r against %r, paired by seed." % (a.panel, a.reference),
         "Post-repeat replication uses the 0ad definition: an order for a variant that ALREADY HAS a",
         "successful reading, over the rounds after a second successful reading was received. This",
         "differs from campaign.py's replication_count, which counts a re-order of any variant already",
         "ATTEMPTED; both are shown. EXPLORATORY, Holm within this table only.", "",
         "%-14s %-22s %5s %5s %5s %9s %9s %20s %10s"
         % ("condition", "model", "pair", "exP", "exR", "level0", "diff", "level0 95% CI", "wild p")]
    raw, meta = [], []
    for cond in LADDER:
        rung = RUNG[cond]
        for m in models:
            A, B = ref_c.get((cond, m)), pan_c.get((cond, m))
            if not A or not B:
                continue
            ks, exP, exR = [], 0, 0
            for k in sorted(set(A) & set(B)):
                pp = (pan_pr.get((m, rung, k)) or {}).get("post_repeat")
                rr = (ref_pr.get((m, rung, k)) or {}).get("post_repeat")
                if pp is None:
                    exP += 1
                if rr is None:
                    exR += 1
                if pp is not None and rr is not None:
                    ks.append((k, pp, rr))
            if len(ks) < 2:
                continue
            d = [p - r for _k, p, r in ks]
            lvl = [p for _k, p, _r in ks]
            if st.stdev(d) == 0:
                continue
            diff, se, _pt = AG.paired_t_p(d)
            wp = AG.paired_wild_p(d, tag="c%s%s%s" % (a.panel, cond, m))
            lo, hi = boot_ci(lvl, tag="l%s%s" % (cond, m))
            raw.append(wp)
            meta.append((cond, m, len(ks), exP, exR, st.mean(lvl), diff, lo, hi, wp))
    for (cond, m, n, exP, exR, lvl, diff, lo, hi, wp), (_i, _p, adj, rej) in zip(meta, AG.holm(raw, 0.05)):
        L.append("%-14s %-22s %5d %5d %5d %9.4f %+9.4f  [%7.4f, %7.4f] %10.5f"
                 % (cond, m.split("/")[-1], n, exP, exR, lvl, diff, lo, hi, wp))
    if meta:
        L += ["", "level0 is post-repeat replication IN THE PANEL with its bootstrap interval, reported",
              "beside the difference because 0q(a)'s reading is about the LEVEL being near zero and not",
              "only about the change. exP and exR count campaigns excluded for having no repeat, or",
              "r* = 15, in the panel and in the reference.", "",
              "%-14s %-22s %11s %11s %s" % ("condition", "model", "raw p", "Holm p", "reject")]
        for (cond, m, *_r), (_i, pv, adj, rej) in zip(meta, AG.holm(raw, 0.05)):
            L.append("%-14s %-22s %11.5f %11.5f %s"
                     % (cond, m.split("/")[-1], pv, adj, "YES" if rej else "no"))
    else:
        L.append("  no cell had two usable pairs; nothing is computed.")

    # (b) the four whole-campaign definitions and (c) distinct variants, paired the same way.
    L += ["", "THE FOUR WHOLE-CAMPAIGN DEFINITIONS OF 0d, AND DISTINCT VARIANTS, paired by seed.",
          "These use the harness's replication_count, which counts a re-order of any variant already",
          "ATTEMPTED, including one never successfully read. That is a DIFFERENT quantity from the one",
          "above, and the gap between them is the cost of that choice.", "",
          "%-14s %-22s %-26s %6s %+9s %9s" % ("condition", "model", "metric", "pairs", "diff", "wild p")]
    for cond in LADDER:
        for m in models:
            for lbl, field in REP_DEFS + [("distinct variants", "n_distinct_measured")]:
                A = AG.by_seed_rows(AG.load(a.reference), field=field).get((cond, m))
                B = AG.by_seed_rows(AG.load(a.panel), field=field).get((cond, m))
                if not A or not B:
                    continue
                ks = sorted(set(A) & set(B))
                d = [B[k] - A[k] for k in ks if A[k] is not None and B[k] is not None]
                if len(d) < 2 or st.stdev(d) == 0:
                    continue
                diff, se, _p = AG.paired_t_p(d)
                wp = AG.paired_wild_p(d, tag="d%s%s%s" % (cond, m, field))
                L.append("%-14s %-22s %-26s %6d %+9.4f %9.5f"
                         % (cond, m.split("/")[-1], lbl, len(d), diff, wp))
    AG.table(L, os.path.join(out, "table2c_central_test.txt"))
    AG.dump_json(dict(panel=a.panel, reference=a.reference,
                      rows=[dict(condition=c, model=m, pairs=n, excluded_panel=xp,
                                 excluded_ref=xr, panel_level=lv, diff=df, lo=lo, hi=hi, wild_p=wp)
                            for c, m, n, xp, xr, lv, df, lo, hi, wp in meta]),
                 os.path.join(out, "table2c_central_test.json"))
    print("  wrote %s" % os.path.relpath(os.path.join(out, "table2c_central_test.txt"), ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
