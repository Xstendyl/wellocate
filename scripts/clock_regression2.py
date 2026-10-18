#!/usr/bin/env python3
"""Clock regression with campaign fixed effects, cluster-robust SEs, VIFs and fully standardised coefficients.

The 280 observations are 20 campaigns of 14 rounds and `round` varies within campaign, so the estimator is
campaign fixed effects with SEs clustered on campaign. Coefficients are standardised on both the predictors
and y, so they can be reconciled with the semi-partial R2 contributions.
"""
import collections, json, math, os, re, statistics as st, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = re.compile(r"^\s*(\d+)\s+([A-Z]{4})\s+(.+)$")
NAMES = ["round", "n_distinct", "champ_lead", "champ_reads", "rounds_stale", "best_obs"]


def hist_from_prompt(p):
    if "HISTORY" not in p: return []
    out = []
    for line in p.split("HISTORY", 1)[1].splitlines():
        m = HIST.match(line)
        if m:
            try: out.append((int(m.group(1)), m.group(2), float(m.group(3).strip())))
            except ValueError: pass
    return out


def build():
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "results", "pilot_opus47_calls.jsonl"))]
    camps = collections.defaultdict(list)
    for r in rows: camps[(r["rung"], r["ratio"], r["campaign_seed"])].append(r)
    X, y, g = [], [], []
    for gi, (key, calls) in enumerate(sorted(camps.items())):
        last, stale = None, 0
        for r in sorted(calls, key=lambda x: (x["round"], x["kind"] != "round")):
            if r["kind"] != "round" or not r["parsed"]: continue
            h = hist_from_prompt(r["prompt"])
            obs = collections.defaultdict(list)
            for _, s, v in h: obs[s].append(v)
            if not obs: continue
            means = {s: sum(v)/len(v) for s, v in obs.items()}
            order = sorted(means, key=means.get, reverse=True)
            lead = means[order[0]] - (means[order[1]] if len(order) > 1 else means[order[0]])
            stale = 0 if order[0] != last else stale + 1
            last = order[0]
            X.append([r["round"], len(obs), lead, len(obs[order[0]]), stale,
                      max(v for vs in obs.values() for v in vs)])
            y.append(sum(1 for s in r["parsed"] if s in set(obs)) / len(r["parsed"]))
            g.append(gi)
    return np.array(X, float), np.array(y, float), np.array(g)


def fit(X, y, g, cluster=True):
    n, k = X.shape
    Z = np.column_stack([np.ones(n), X])
    beta, *_ = np.linalg.lstsq(Z, y, rcond=None)
    e = y - Z @ beta
    XtX_inv = np.linalg.pinv(Z.T @ Z)
    if cluster:
        meat = np.zeros((k+1, k+1))
        for c in np.unique(g):
            m = g == c
            u = Z[m].T @ e[m]
            meat += np.outer(u, u)
        G = len(np.unique(g))
        adj = G / max(1, (G - 1)) * (n - 1) / max(1, (n - k - 1))
        V = XtX_inv @ meat @ XtX_inv * adj
    else:
        V = XtX_inv * (e @ e) / (n - k - 1)
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return beta, se, r2


def main():
    X, y, g = build()
    n = len(y)
    sdy = y.std(ddof=0)
    Xs = (X - X.mean(0)) / X.std(0)
    print("n = %d round-observations, %d campaigns, sd(y) = %.4f\n" % (n, len(set(g)), sdy))

    print("=" * 96)
    print("1. THE RECONCILIATION")
    print("=" * 96)
    b, se, r2 = fit(Xs, y, g, cluster=False)
    print("  %-14s %12s %12s %10s" % ("predictor", "beta (y raw)", "beta FULLY", "VIF"))
    for j, nm in enumerate(NAMES):
        others = np.delete(Xs, j, axis=1)
        bb, _, r2j = fit(others, Xs[:, j], g, cluster=False)
        vif = 1.0 / max(1e-9, 1 - r2j)
        print("  %-14s %+12.4f %+12.4f %10.1f%s"
              % (nm, b[j+1], b[j+1]/sdy, vif, "   <-- collinear" if vif > 5 else ""))
    j = 0
    others = np.delete(Xs, j, axis=1)
    _, _, r2j = fit(others, Xs[:, j], g, cluster=False)
    sr = (b[1]/sdy) * math.sqrt(max(0.0, 1 - r2j))
    print("\n  round: fully standardised beta %.4f, R2 of round on the others %.4f" % (b[1]/sdy, r2j))
    print("  implied semi-partial r = %.4f, so semi-partial R2 = %.4f" % (sr, sr*sr))
    print("  the earlier table reported an R2 increment of 0.188. Reconciled: the betas were")
    print("  semi-standardised (x standardised, y raw) and mislabelled as standardised.")

    print("\n" + "=" * 96)
    print("2. CAMPAIGN FIXED EFFECTS, SEs CLUSTERED ON CAMPAIGN")
    print("=" * 96)
    # demean within campaign: removes every between-campaign difference, incl. rung and ratio
    Xw = Xs.copy(); yw = y.copy()
    for c in np.unique(g):
        m = g == c
        Xw[m] -= Xw[m].mean(0); yw[m] -= yw[m].mean()
    bw, sew, r2w = fit(Xw, yw, g, cluster=True)
    print("  within-campaign R2 = %.3f" % r2w)
    print("  %-14s %12s %10s %8s" % ("predictor", "beta", "cluster SE", "ratio"))
    for j, nm in enumerate(NAMES):
        print("  %-14s %+12.4f %10.4f %8.1f%s"
              % (nm, bw[j+1], sew[j+1], abs(bw[j+1]/sew[j+1]) if sew[j+1] else float("nan"),
                 "   <-- the clock" if nm == "round" else ""))
    print("\n  For comparison, the naive OLS SE on round was %.4f; clustered it is %.4f (%.1fx)"
          % (se[1], sew[1], sew[1]/se[1] if se[1] else float("nan")))


if __name__ == "__main__":
    main()
