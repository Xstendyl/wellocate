#!/usr/bin/env python3
"""Analyse the generalisation runs: the real-protein panel (GB1 and PhoQ) and the NK panel (K = 0 to 3).

Each cell's mean replication share is labelled against its yardstick, the guessing scripted policy's share:
"re-testing generalises", "does not generalise" or "partial", with a slot-loss guard on the lower readings.
Also reports GB1 real minus scrambled names, the trend across K, and how re-testing tracks the yardstick.

Usage: python3 scripts/analyse_0am.py      (writes results/analysis_0am.json)
"""
import collections, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_grid as AG                                   # noqa: E402
import repdef.rng as R                                      # noqa: E402

OUT = os.path.join(ROOT, "results", "analysis_0am.json")
R_TAGS = {"gb1_scrambled": ("gen_r_gb1scr", "gen_r_gb1scr_top"), "gb1_real": ("gen_r_gb1real", "gen_r_gb1real_top"),
          "phoq_scrambled": ("gen_r_phoqscr",)}
K_TAGS = {0: "gen_k0", 1: "gen_k1", 2: "gen_k2", 3: "gen_k3"}
GRID_TAGS = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
LABELLED = ("gb1_scrambled", "phoq_scrambled")
MODELS = ("anthropic/claude-opus-4.7", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1")
OPUS = MODELS[0]
B = 20000
LOST_GUARD = 10.0
NOT_INTERPRETABLE = "not interpretable: slot loss"


def share(r):
    return 100.0 * r["replication_count"] / r["slots_used"] if r["slots_used"] else 0.0


def lines(y):
    return y + 5.0, max(2.0 * y, y + 10.0)


def label(mean, y, ci=None):
    low, high = lines(y)
    if mean >= high:
        out = "re-testing generalises"
    elif mean <= low:
        out = "does not generalise"
    else:
        out = "partial"
    if ci is not None and any(ci[0] < x < ci[1] for x in (low, high)):
        out += " (interval crosses a line)"
    return out


def topup_trigger(mean, ci):
    half = (ci[1] - ci[0]) / 2.0
    return bool(half > 3.0 or (ci[0] < 0.0 < ci[1] and abs(mean) > 2.0)), half


def present(tags):
    return [t for t in tags if os.path.exists(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % t))]


def load(tags, require_truthful=True):
    tags = present(tags)
    if not tags:
        return [], 0
    rows = AG.load("+".join(tags))
    off = [r for r in rows if require_truthful and not (r.get("prompt_options") or {}).get("truthful_reask")]
    if off:
        raise SystemExit("REFUSED: %d campaigns in %s ran without the truthful re-ask that 0am.2 requires"
                         % (len(off), "+".join(tags)))
    kept, n = AG.drop_fallbacks(rows, AG.fallback_seeds(tags))
    return kept, sum(n.values())


def guard(lost_mean):
    return lost_mean > LOST_GUARD


def guarded(reading, lost_mean):
    """A generalising reading always stands; a lower one becomes not interpretable under heavy slot loss."""
    if reading.startswith("re-testing generalises") or not guard(lost_mean):
        return reading
    return NOT_INTERPRETABLE


def share_non_lost(r):
    used = r["slots_used"] - r["lost_slots"]
    return 100.0 * r["replication_count"] / used if used > 0 else 0.0


def cell_summary(v, tag, y=None):
    s = [share(r) for r in v]
    lost = st.mean(r["lost_slots"] for r in v) if v else None
    letters = collections.Counter()
    for r in v:
        letters.update(r.get("out_of_alphabet_letters") or {})
    f = [r["nominated_true"] for r in v]
    snl = [share_non_lost(r) for r in v]
    d = dict(n=len(v), share=st.mean(s) if s else None, share_ci=list(AG.boot_ci(s, tag=tag + "|share")),
             share_non_lost=st.mean(snl) if snl else None,
             share_non_lost_ci=list(AG.boot_ci(snl, tag=tag + "|share_non_lost")),
             fitness=st.mean(f) if f else None, fitness_ci=list(AG.boot_ci(f, tag=tag + "|fit")),
             distinct=st.mean(r["n_distinct_measured"] for r in v) if v else None,
             spend=sum(r["spend"] for r in v),
             round1_top10_any=(sum(1 for r in v if r.get("round1_top10_any")) if v else None),
             round1_global_best=(sum(1 for r in v if r.get("round1_global_best")) if v else None),
             round1_top10_distinct=(st.mean(r.get("round1_top10_distinct", 0) for r in v) if v else None),
             lost_slots_mean=lost, lost_above_10=(guard(lost) if v else None),
             lost_nonviable_mean=(st.mean(r["slots_abandoned"] for r in v) if v else None),
             lost_rounds_mean=(st.mean(r["rounds_lost_slots"] for r in v) if v else None),
             out_of_alphabet_proposals=sum(r.get("out_of_alphabet_proposals") or 0 for r in v),
             out_of_alphabet_campaigns=sum(1 for r in v if r.get("out_of_alphabet_proposals")),
             out_of_alphabet_letters=dict(letters.most_common()))
    if y is not None and s:
        reading = label(d["share"], y, d["share_ci"])
        d.update(yardstick=y, lines=list(lines(y)), reading_before_guard=reading, label=guarded(reading, lost))
    return d


TOPUP_SEED0 = 11_000_030          # the extra Opus seeds are 11,000,030 to 11,000,059


def paired_real_minus_scrambled(real, scr, max_seed=None):
    """Real-name minus scrambled GB1, paired by condition, model and seed.

    The pre-registered outcomes are the share and the final pick; the other fields are descriptive.
    `max_seed` restricts to seeds below it."""
    a = {(r["condition"], r["model"], r["seed"]): r for r in scr}
    b = {(r["condition"], r["model"], r["seed"]): r for r in real}
    fields = (("share", share), ("share_non_lost", share_non_lost), ("distinct", lambda r: r["n_distinct_measured"]),
              ("best_measured", lambda r: r["best_true_measured"]), ("pick", lambda r: r["nominated_true"]),
              ("lost", lambda r: r["lost_slots"]))
    out = {}
    for c in ("Blind", "Mechanism"):
        for m in MODELS:
            ks = sorted(k for k in b if k[0] == c and k[1] == m and k in a and (max_seed is None or k[2] < max_seed))
            if not ks:
                continue
            t = "0am|gb1_real-minus-scrambled|%s|%s|%s" % (c, m.split("/")[-1], max_seed or "all")
            d = dict(pairs=len(ks))
            for name, f in fields:
                diff = [f(b[k]) - f(a[k]) for k in ks]
                d["real_" + name] = st.mean(f(b[k]) for k in ks)
                d["scrambled_" + name] = st.mean(f(a[k]) for k in ks)
                d["d_" + name] = st.mean(diff)
                d["d_" + name + "_ci"] = list(AG.boot_ci(diff, tag=t + "|d" + name))
            # Aliases read by the extra-seed trigger and its tests.
            d["d_fit"], d["d_fit_ci"] = d["d_pick"], d["d_pick_ci"]
            if m == OPUS:
                d["topup_trigger"], d["half_width"] = topup_trigger(d["d_share"], d["d_share_ci"])
            out["%s|%s" % (c, m.split("/")[-1])] = d
    return out


def ols_slope(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else float("nan")


def cluster_boot_slope(points, tag, b=B):
    """points: [(K, landscape, value)]. Resample landscapes within each K, with replacement."""
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for k, lab, v in points:
        by[k][lab].append(v)
    labs = {k: sorted(d) for k, d in by.items()}
    est = ols_slope([p[0] for p in points], [p[2] for p in points])
    draws = []
    for i in range(b):
        xs, ys = [], []
        for k in sorted(labs):
            n = len(labs[k])
            for j in range(n):
                lab = labs[k][R._u64("kslope", tag, i, k, j) % n]
                xs += [k] * len(by[k][lab])
                ys += by[k][lab]
        draws.append(ols_slope(xs, ys))
    draws.sort()
    return est, [draws[int(0.025 * b)], draws[min(b - 1, int(0.975 * b))]]


def diff_ci(a, b, tag, b_=B):
    """95% percentile interval of mean(a) - mean(b), resampling a and b independently (unpaired)."""
    na, nb = len(a), len(b)
    draws = []
    for i in range(b_):
        ma = sum(a[R._u64("diff", tag, "a", i, j) % na] for j in range(na)) / na
        mb = sum(b[R._u64("diff", tag, "b", i, j) % nb] for j in range(nb)) / nb
        draws.append(ma - mb)
    draws.sort()
    return [draws[int(0.025 * b_)], draws[min(b_ - 1, int(0.975 * b_))]]


def adaptation_r(agent, grid, y_change, tag):
    """Agent share on a new landscape minus the grid's, beside the yardstick's change and their ratio."""
    a, g = [share(r) for r in agent], [share(r) for r in grid]
    d = st.mean(a) - st.mean(g)
    ci = diff_ci(a, g, tag)
    lo, hi = sorted((ci[0] / y_change, ci[1] / y_change))
    return dict(n_agent=len(a), n_grid=len(g), agent=st.mean(a), grid=st.mean(g), d_share=d, d_share_ci=ci,
                yardstick_change=y_change, ratio=d / y_change, ratio_ci=[lo, hi])


def landscape_slope(points, tag, b=B):
    """points: [(landscape, y, share)]. Least-squares slope of campaign share on the landscape's yardstick,
    with a 95% percentile interval from resampling landscapes with replacement."""
    by = collections.defaultdict(list)
    for lab, y, v in points:
        by[lab].append((y, v))
    labs = sorted(by)
    est = ols_slope([p[1] for p in points], [p[2] for p in points])
    draws = []
    for i in range(b):
        xs, ys = [], []
        for j in range(len(labs)):
            for y, v in by[labs[R._u64("yslope", tag, i, j) % len(labs)]]:
                xs.append(y)
                ys.append(v)
        draws.append(ols_slope(xs, ys))
    draws = sorted(x for x in draws if x == x)
    return est, [draws[int(0.025 * len(draws))], draws[min(len(draws) - 1, int(0.975 * len(draws)))]]


def main():
    yard = json.load(open(os.path.join(ROOT, "results", "yardsticks_0am.json")))
    ylab = yard["landscapes"]
    out = dict(panel_R={}, panel_K={}, fallbacks_dropped={}, spend={})
    rows_r = {}
    for arm, tags in R_TAGS.items():
        rows_r[arm], out["fallbacks_dropped"][arm] = load(tags)
        out["spend"][arm] = sum(r["spend"] for r in rows_r[arm])
        for c in ("Blind", "Mechanism"):
            for m in MODELS:
                v = [r for r in rows_r[arm] if r["condition"] == c and r["model"] == m]
                if not v:
                    continue
                y = ylab[v[0]["landscape"]]["share_at_kstar"] if arm in LABELLED else None
                out["panel_R"]["%s|%s|%s" % (arm, c, m.split("/")[-1])] = cell_summary(
                    v, "0am|R|%s|%s|%s" % (arm, c, m.split("/")[-1]), y)
    if rows_r["gb1_real"] and rows_r["gb1_scrambled"]:
        out["gb1_real_minus_scrambled"] = paired_real_minus_scrambled(rows_r["gb1_real"], rows_r["gb1_scrambled"])
        # Seeds 0 to 29 only, beside the full set.
        out["gb1_real_minus_scrambled_seeds_0_29"] = paired_real_minus_scrambled(
            rows_r["gb1_real"], rows_r["gb1_scrambled"], max_seed=TOPUP_SEED0)
    for k, tag in K_TAGS.items():
        rows, out["fallbacks_dropped"]["K%d" % k] = load([tag])
        out["spend"]["K%d" % k] = sum(r["spend"] for r in rows)
        for m in MODELS:
            v = [r for r in rows if r["model"] == m]
            if not v:
                continue
            y = st.mean(ylab[r["landscape"]]["share_at_kstar"] for r in v)
            d = cell_summary(v, "0am|K|%d|%s" % (k, m.split("/")[-1]), y)
            d["landscapes"] = len({r["landscape"] for r in v})
            out["panel_K"]["%d|%s" % (k, m.split("/")[-1])] = d
            out.setdefault("_k_points", {}).setdefault(m, []).extend(
                (k, r["landscape"], share(r), share(r) - ylab[r["landscape"]]["share_at_kstar"]) for r in v)
            out.setdefault("_adapt_points", {}).setdefault(m, []).extend(
                (r["landscape"], ylab[r["landscape"]]["share_at_kstar"], share(r)) for r in v)
    trend = {}
    for m, pts in out.pop("_k_points", {}).items():
        if len({p[0] for p in pts}) < 2:
            continue
        s, ci = cluster_boot_slope([(p[0], p[1], p[2]) for p in pts], "share|" + m)
        s2, ci2 = cluster_boot_slope([(p[0], p[1], p[3]) for p in pts], "excess|" + m)
        trend[m.split("/")[-1]] = dict(slope_share_per_K=s, ci=ci, slope_excess_per_K=s2, ci_excess=ci2)
    out["panel_K_trend"] = trend

    # Adaptation: compare each new landscape with the grid, using the grid's alphabet-correct yardstick.
    y_grid = yard["grid"]["alphabet_policy"]["share_at_kstar"]
    grid_rows, _nfb = load(GRID_TAGS, require_truthful=False) if any(rows_r[a] for a in LABELLED) else ([], 0)
    adapt_r = {}
    for arm in LABELLED:
        if not rows_r[arm]:
            continue
        y_arm = ylab[rows_r[arm][0]["landscape"]]["share_at_kstar"]
        for c in ("Blind", "Mechanism"):
            for m in MODELS:
                v = [r for r in rows_r[arm] if r["condition"] == c and r["model"] == m]
                g = [r for r in grid_rows if r["condition"] == c and r["model"] == m]
                if v and g:
                    adapt_r["%s|%s|%s" % (arm, c, m.split("/")[-1])] = adaptation_r(
                        v, g, y_arm - y_grid, "0am|adapt|%s|%s|%s" % (arm, c, m.split("/")[-1]))
    adapt_k = {}
    k1 = {lab for lab, d in ylab.items() if d.get("name") == "nk" and d["kstar"] == 1}
    for m, pts in out.get("_adapt_points", {}).items():
        s, ci = landscape_slope(pts, "all|" + m)
        rest = [p for p in pts if p[0] in k1]
        s1, ci1 = landscape_slope(rest, "kstar1|" + m)
        ys = sorted({p[1] for p in pts})
        adapt_k[m.split("/")[-1]] = dict(slope=s, ci=ci, landscapes=len({p[0] for p in pts}), campaigns=len(pts),
                                         y_min=ys[0], y_max=ys[-1], slope_kstar1_only=s1, ci_kstar1_only=ci1,
                                         landscapes_kstar1_only=len({p[0] for p in rest}))
    out.pop("_adapt_points", None)
    out["adaptation"] = dict(grid_yardstick=y_grid, panel_R=adapt_r, panel_K=adapt_k)
    json.dump(out, open(OUT, "w"), indent=1)
    print("PANEL R")
    for key, d in out["panel_R"].items():
        print("  %-40s n=%3d share %6.2f [%6.2f, %6.2f] (non-lost %.2f)  fit %.3f  lost %.1f (nv %.1f, rounds %.1f)"
              "  ooa %d %s  r1 top10 %s/%d  %s"
              % (key, d["n"], d["share"], d["share_ci"][0], d["share_ci"][1], d["share_non_lost"], d["fitness"],
                 d["lost_slots_mean"], d["lost_nonviable_mean"], d["lost_rounds_mean"],
                 d["out_of_alphabet_proposals"], d["out_of_alphabet_letters"],
                 d["round1_top10_any"], d["n"], d.get("label", "descriptive")))
    for key, d in out.get("gb1_real_minus_scrambled", {}).items():
        print("  GB1 real - scrambled %-28s pairs %3d  d_share %+.2f [%+.2f, %+.2f]%s"
              % (key, d["pairs"], d["d_share"], d["d_share_ci"][0], d["d_share_ci"][1],
                 ("  TOP-UP TRIGGERED (half-width %.2f)" % d["half_width"]) if d.get("topup_trigger") else ""))
    print("PANEL K")
    for key, d in out["panel_K"].items():
        print("  K=%-14s n=%3d over %2d landscapes  share %6.2f [%6.2f, %6.2f]  y %.2f  lost %.1f  ooa %d  %s"
              % (key, d["n"], d["landscapes"], d["share"], d["share_ci"][0], d["share_ci"][1], d["yardstick"],
                 d["lost_slots_mean"], d["out_of_alphabet_proposals"], d["label"]))
    for m, t in trend.items():
        print("  trend %-22s share %+.2f per K [%+.2f, %+.2f]; excess %+.2f [%+.2f, %+.2f]"
              % (m, t["slope_share_per_K"], t["ci"][0], t["ci"][1], t["slope_excess_per_K"], t["ci_excess"][0],
                 t["ci_excess"][1]))
    print("ADAPTATION (descriptive; grid yardstick %.2f%%)" % y_grid)
    for key, d in adapt_r.items():
        print("  %-40s agent %6.2f grid %6.2f  change %+6.2f [%+6.2f, %+6.2f]  yardstick change %+6.2f  "
              "ratio %.2f [%.2f, %.2f]" % (key, d["agent"], d["grid"], d["d_share"], d["d_share_ci"][0],
                                          d["d_share_ci"][1], d["yardstick_change"], d["ratio"], d["ratio_ci"][0],
                                          d["ratio_ci"][1]))
    for m, d in adapt_k.items():
        print("  slope on own yardstick %-20s %.2f [%.2f, %.2f] over %d landscapes; k*=1 only %.2f [%.2f, %.2f]"
              % (m, d["slope"], d["ci"][0], d["ci"][1], d["landscapes"], d["slope_kstar1_only"],
                 d["ci_kstar1_only"][0], d["ci_kstar1_only"][1]))
    print("spend %s; fallbacks dropped %s" % ({k: round(v, 2) for k, v in out["spend"].items()},
                                             out["fallbacks_dropped"]))
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
