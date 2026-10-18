#!/usr/bin/env python3
"""Checks on the raw data of the generalisation runs.

  1. Every campaign ran with the truthful re-ask on and every other prompt option off.
  2. The NK panel's K = 0 landscapes are exactly additive: zero epistasis on random double mutants.
  3. The NK panel's mechanism, per K and model: rejections, distinct candidates, share, lost slots, beside the
     guessing policy's share on the same landscapes.
  4. Out-of-alphabet behaviour: per cell the count and letters, the campaigns that lost the most slots to it,
     and whether the re-ask those campaigns were sent named the bad candidates and the alphabet.

Descriptive only. Usage: python3 scripts/checks_0am.py
(writes results/checks_0am.json)
"""
import collections, glob, gzip, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import envs as E                                        # noqa: E402
import repdef.rng as R                                              # noqa: E402

TAGS = ["gen_r_gb1scr", "gen_r_gb1real", "gen_r_phoqscr", "gen_r_gb1scr_top", "gen_r_gb1real_top",
        "gen_k0", "gen_k1", "gen_k2", "gen_k3"]
OUT = os.path.join(ROOT, "results", "checks_0am.json")


def rows(tag):
    p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def calls(tag):
    for g in sorted(glob.glob(os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz"))):
        with gzip.open(g, "rt") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)


def epistasis_k0(n_pairs=3000):
    """For each K = 0 landscape, the largest |f(ab) - f(a) - f(b) + f(0)| over random double mutants."""
    worst = {}
    for seed in E.PANEL_K_SEEDS[0]:
        fit = E.nk(0, seed).fit
        keys = sorted(fit)
        m = 0.0
        for i in range(n_pairs):
            s = keys[R._u64("epi", seed, i) % len(keys)]
            p, q = sorted(R.sample_without_replacement(list(range(4)), 2, "epipos", seed, i))
            a = E.ABSTRACT[R._u64("epia", seed, i) % 20]
            b = E.ABSTRACT[R._u64("epib", seed, i) % 20]
            if a == s[p] or b == s[q]:
                continue
            sa = s[:p] + a + s[p + 1:]
            sb = s[:q] + b + s[q + 1:]
            sab = sa[:q] + b + sa[q + 1:]
            m = max(m, abs(fit[sab] - fit[sa] - fit[sb] + fit[s]))
        worst[seed] = m
    return worst


def main():
    out = {}
    allrows = {t: rows(t) for t in TAGS}
    opts = collections.Counter()
    for t, rs in allrows.items():
        for r in rs:
            o = r.get("prompt_options") or {}
            opts[(o.get("truthful_reask"), o.get("goal_true_value"), o.get("fix_replacement_budget"),
                  o.get("riskfree_rejection"))] += 1
    out["options"] = {str(k): v for k, v in opts.items()}
    out["campaigns"] = {t: len(v) for t, v in allrows.items()}
    print("campaigns per tag: %s" % out["campaigns"])
    print("option sets (truthful, goal, budget, riskfree): %s" % dict(opts))

    w = epistasis_k0()
    out["k0_max_abs_epistasis"] = w
    print("K = 0 landscapes, largest |epistasis| on 3,000 double mutants each: max over 20 = %.3g" % max(w.values()))

    y = json.load(open(os.path.join(ROOT, "results", "yardsticks_0am.json")))["landscapes"]
    mech = {}
    for k in E.PANEL_K:
        for r in allrows["gen_k%d" % k]:
            mech.setdefault((k, r["model"].split("/")[-1]), []).append(r)
    out["panel_k_mechanism"] = {}
    print("\nPanel K, per K and model (means per campaign)")
    print("  %-2s %-20s %4s %10s %9s %7s %6s %10s" % ("K", "model", "n", "rejections", "distinct", "share%", "lost",
                                                     "guessing%"))
    for (k, m), v in sorted(mech.items()):
        d = dict(n=len(v), rejections=st.mean(r["n_rejected"] for r in v),
                 distinct=st.mean(r["n_distinct_measured"] for r in v),
                 share=st.mean(100.0 * r["replication_count"] / r["slots_used"] for r in v),
                 lost=st.mean(r["lost_slots"] for r in v),
                 guessing=st.mean(y[r["landscape"]]["share_at_kstar"] for r in v))
        out["panel_k_mechanism"]["%d|%s" % (k, m)] = d
        print("  %-2d %-20s %4d %10.1f %9.1f %7.1f %6.1f %10.1f" % (k, m, d["n"], d["rejections"], d["distinct"],
                                                                   d["share"], d["lost"], d["guessing"]))

    print("\nOut-of-alphabet proposals per cell (every attempt), and the letters")
    out["out_of_alphabet"] = {}
    worst = []
    for t, rs in allrows.items():
        cells = collections.defaultdict(list)
        for r in rs:
            cells[(r["condition"], r["model"].split("/")[-1])].append(r)
        for (c, m), v in sorted(cells.items()):
            n = sum(r.get("out_of_alphabet_proposals") or 0 for r in v)
            letters = collections.Counter()
            for r in v:
                letters.update(r.get("out_of_alphabet_letters") or {})
            out["out_of_alphabet"]["%s|%s|%s" % (t, c, m)] = dict(
                proposals=n, campaigns_with_any=sum(1 for r in v if r.get("out_of_alphabet_proposals")),
                campaigns=len(v), letters=dict(letters.most_common()))
            if n:
                print("  %-18s %-9s %-20s %4d in %2d of %2d campaigns  %s"
                      % (t, c, m, n, sum(1 for r in v if r.get("out_of_alphabet_proposals")), len(v),
                         dict(letters.most_common())))
            worst += [(r["rounds_lost_slots"], t, r) for r in v if (r.get("out_of_alphabet_proposals") or 0) >= 20]
    worst.sort(key=lambda x: -x[0])
    out["heaviest_alphabet_losses"] = []
    print("\nCampaigns with 20 or more out-of-alphabet proposals, by slots lost to lost rounds")
    for lost, t, r in worst[:8]:
        told = [c for c in calls(t) if c.get("campaign_seed") == r["seed"] and c.get("model") == r["model"]
                and c.get("cell", c.get("rung")) in (r["condition"], r.get("rung"))
                and "contain letters that are not in the alphabet" in (c.get("prompt") or "")]
        sample = ""
        if told:
            p = told[0]["prompt"]
            sample = p[p.index("Your previous reply could not be used"):][:220].replace("\n", " ")
        rec = dict(tag=t, model=r["model"], condition=r["condition"], seed=r["seed"],
                   out_of_alphabet=r.get("out_of_alphabet_proposals"), letters=r.get("out_of_alphabet_letters"),
                   rounds_lost_slots=lost, lost_slots=r["lost_slots"], truthful_reasks_sent=len(told),
                   reask_sample=sample)
        out["heaviest_alphabet_losses"].append(rec)
        print("  %-14s %-28s %-9s seed %d: %d proposals %s, %d slots in lost rounds, %d truthful re-asks sent"
              % (t, r["model"], r["condition"], r["seed"], rec["out_of_alphabet"], rec["letters"], lost,
                 len(told)))
        if sample:
            print("      re-ask as sent: %s..." % sample)
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    print("\nwrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
