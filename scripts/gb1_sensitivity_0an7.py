#!/usr/bin/env python3
"""How much GPT-6.1 Sol's GB1 Blind result rests on one nominee. No model is called.

Sol nominated the same candidate, FSRM, in 12 of its 30 GB1 Blind campaigns. Two checks treat these as
dependent: a cluster bootstrap that resamples distinct nominees, and a version that counts the FSRM campaigns
as one. Each is applied to the pick, its lead over the guessing reference (whose interval adds guessing's own
uncertainty in quadrature) and Menu minus Blind paired by seed.

Usage: python3 scripts/gb1_sensitivity_0an7.py      (writes results/gb1_sensitivity_0an7.json)
"""
import collections, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
from repdef import envs as EV, rng as R                                   # noqa: E402
import analyse_grid as AG                                                 # noqa: E402

B = AG.BOOT_REPS


def cluster_ci(units, tag):
    """units: list of (cluster, value). Resample clusters with replacement; the statistic is the mean over units."""
    by = collections.defaultdict(list)
    for c, v in units:
        by[c].append(v)
    keys = sorted(by)
    n, d = len(keys), []
    for i in range(B):
        vals = [v for j in range(n) for v in by[keys[R._u64(tag, i, j) % n]]]
        d.append(st.mean(vals))
    d.sort()
    return [d[int(0.025 * B)], d[min(B - 1, int(0.975 * B))]]


def main():
    a = json.load(open(os.path.join(ROOT, "results", "analysis_0an7.json")))
    g = json.load(open(os.path.join(ROOT, "results", "references_0an7.json")))["gb1_scrambled"]["guessing"]["at_kstar"]
    fit = EV.env_for("gb1_scrambled").fit
    blind = a["cells"]["sol|gb1_blind"]["campaigns"]
    menu = {c["seed"]: c for c in a["cells"]["sol|gb1_menu"]["campaigns"]}
    top, count = collections.Counter(c["nominee"] for c in blind).most_common(1)[0]
    gh = 1.96 * g["pick_se"]
    out = dict(top_nominee=top, top_nominee_campaigns=count, campaigns=len(blind), top_nominee_true=fit[top],
               distinct_nominees=len({c["nominee"] for c in blind}), guessing=g["pick"], guessing_se=g["pick_se"],
               versions={})
    assert all(abs(c["pick"] - fit[c["nominee"]]) < 1e-9 for c in blind), "a campaign pick is not its nominee's true value"
    collapsed = [c for c in blind if c["nominee"] != top] + [next(c for c in blind if c["nominee"] == top)]
    pairs = [(c["nominee"], menu[c["seed"]]["pick"] - c["pick"]) for c in blind if c["seed"] in menu]
    top_pairs = [d for n, d in pairs if n == top]
    pairs_collapsed = [(n, d) for n, d in pairs if n != top] + [(top, st.mean(top_pairs))]
    picks = [c["pick"] for c in blind]
    picks_c = [c["pick"] for c in collapsed]
    versions = {
        "as registered (seed bootstrap)": (picks, AG.boot_ci(picks, tag="A2|seed|pick"),
                                           [d for _n, d in pairs], AG.boot_ci([d for _n, d in pairs], tag="A2|seed|mmb")),
        "cluster bootstrap by nominee": (picks, cluster_ci([(c["nominee"], c["pick"]) for c in blind], "A2|cl|pick"),
                                         [d for _n, d in pairs], cluster_ci(pairs, "A2|cl|mmb")),
        "FSRM collapsed to one (seed bootstrap)": (picks_c, AG.boot_ci(picks_c, tag="A2|col|pick"),
                                                   [d for _n, d in pairs_collapsed],
                                                   AG.boot_ci([d for _n, d in pairs_collapsed], tag="A2|col|mmb")),
        "FSRM collapsed, cluster bootstrap": (picks_c, cluster_ci([(c["nominee"], c["pick"]) for c in collapsed], "A2|colcl|pick"),
                                              [d for _n, d in pairs_collapsed], cluster_ci(pairs_collapsed, "A2|colcl|mmb")),
    }
    for name, (p, pci, d, dci) in versions.items():
        m = st.mean(p)
        lead = m - g["pick"]
        lead_ci = [lead - ((m - pci[0]) ** 2 + gh ** 2) ** 0.5, lead + ((pci[1] - m) ** 2 + gh ** 2) ** 0.5]
        v = dict(n=len(p), pick=m, pick_ci=list(pci), pick_minus_guessing=lead, pick_minus_guessing_ci=lead_ci,
                 beats_guessing=lead_ci[0] > 0, menu_minus_blind=st.mean(d), menu_minus_blind_ci=list(dci), pairs=len(d))
        out["versions"][name] = v
        print("%-40s n=%2d pick %.3f [%.3f, %.3f], minus guessing %+.3f [%+.3f, %+.3f], beats guessing: %s | "
              "Menu minus Blind %+.3f [%+.3f, %+.3f] over %d pairs"
              % (name, v["n"], v["pick"], pci[0], pci[1], lead, lead_ci[0], lead_ci[1], v["beats_guessing"],
                 v["menu_minus_blind"], dci[0], dci[1], v["pairs"]))
    out["survives"] = all(v["beats_guessing"] for v in out["versions"].values())
    out["verdict"] = ("survives every version" if out["survives"] else "holds as registered only; it does not survive "
                      "clustering by nominee or collapsing FSRM to one campaign")
    print("%s nominated in %d of %d (true %.3f); 'Sol beats guessing on GB1': %s"
          % (top, count, len(blind), fit[top], out["verdict"]))
    json.dump(out, open(os.path.join(ROOT, "results", "gb1_sensitivity_0an7.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
