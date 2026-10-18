#!/usr/bin/env python3
"""Test whether replication is driven by the round clock or by evidence the agent can see.

If the round effect survives controlling for evidence, the behaviour is a context artefact; if the evidence
predictors absorb it, the rise is rational convergence. Every predictor is reconstructed from the HISTORY
block of the agent's own prompt, with no true values.

  round            the campaign clock
  n_distinct       how many distinct variants have readings, a proxy for "ideas used up"
  champ_lead       best mean minus second-best mean, the evidence that the leader is settled
  champ_reads      readings on the current leader, so more is less marginal value
  rounds_stale     rounds since the leader last changed, the evidence exploration has stopped paying
  best_obs         best reading so far, a proxy for "good enough"

No API calls.
"""
import collections
import json
import math
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "results", "pilot_opus47_calls.jsonl")
HIST = re.compile(r"^\s*(\d+)\s+([A-Z]{4})\s+(.+)$")


def hist_from_prompt(p):
    if "HISTORY" not in p:
        return []
    out = []
    for line in p.split("HISTORY", 1)[1].splitlines():
        m = HIST.match(line)
        if not m:
            continue
        try:
            out.append((int(m.group(1)), m.group(2), float(m.group(3).strip())))
        except ValueError:
            pass
    return out


def ols(X, y, names):
    """Multiple regression by normal equations with an intercept. Predictors standardised so the
    coefficients are directly comparable in units of one standard deviation."""
    n, k = len(X), len(X[0])
    mu = [st.mean([r[j] for r in X]) for j in range(k)]
    sd = [st.pstdev([r[j] for r in X]) or 1.0 for j in range(k)]
    Z = [[1.0] + [(r[j] - mu[j]) / sd[j] for j in range(k)] for r in X]
    p = k + 1
    A = [[sum(Z[i][a] * Z[i][b] for i in range(n)) for b in range(p)] for a in range(p)]
    bv = [sum(Z[i][a] * y[i] for i in range(n)) for a in range(p)]
    # Gaussian elimination with partial pivoting
    M = [A[i][:] + [bv[i]] for i in range(p)]
    for c in range(p):
        piv = max(range(c, p), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None
        M[c], M[piv] = M[piv], M[c]
        for r in range(p):
            if r == c:
                continue
            f = M[r][c] / M[c][c]
            for cc in range(c, p + 1):
                M[r][cc] -= f * M[c][cc]
    beta = [M[i][p] / M[i][i] for i in range(p)]
    fit = [sum(beta[j] * Z[i][j] for j in range(p)) for i in range(n)]
    resid = [y[i] - fit[i] for i in range(n)]
    sse = sum(r * r for r in resid)
    sst = sum((v - st.mean(y)) ** 2 for v in y)
    s2 = sse / (n - p)
    # standard errors from the inverse diagonal, recomputed by solving A x = e_j
    ses = []
    for j in range(p):
        M2 = [A[i][:] + [1.0 if i == j else 0.0] for i in range(p)]
        for c in range(p):
            piv = max(range(c, p), key=lambda r: abs(M2[r][c]))
            M2[c], M2[piv] = M2[piv], M2[c]
            for r in range(p):
                if r == c:
                    continue
                f = M2[r][c] / M2[c][c]
                for cc in range(c, p + 1):
                    M2[r][cc] -= f * M2[c][cc]
        ses.append(math.sqrt(max(0.0, s2 * (M2[j][p] / M2[j][j]))))
    return {"names": ["intercept"] + names, "beta": beta, "se": ses,
            "r2": 1.0 - sse / sst if sst else float("nan"), "n": n}


def main():
    rows = [json.loads(l) for l in open(LOG)]
    camps = collections.defaultdict(list)
    for r in rows:
        camps[(r["rung"], r["ratio"], r["campaign_seed"])].append(r)

    X, y, names = [], [], ["round", "n_distinct", "champ_lead", "champ_reads",
                           "rounds_stale", "best_obs"]
    for key, calls in sorted(camps.items()):
        last_champ, stale = None, 0
        for r in sorted(calls, key=lambda x: (x["round"], x["kind"] != "round")):
            if r["kind"] != "round" or not r["parsed"]:
                continue
            h = hist_from_prompt(r["prompt"])
            obs = collections.defaultdict(list)
            for _, s, v in h:
                obs[s].append(v)
            if not obs:
                continue
            means = {s: sum(v) / len(v) for s, v in obs.items()}
            order = sorted(means, key=means.get, reverse=True)
            champ = order[0]
            lead = means[order[0]] - (means[order[1]] if len(order) > 1 else means[order[0]])
            stale = 0 if champ != last_champ else stale + 1
            last_champ = champ
            seen = set(obs)
            rep = sum(1 for s in r["parsed"] if s in seen) / len(r["parsed"])
            X.append([r["round"], len(obs), lead, len(obs[champ]), stale,
                      max(v for vs in obs.values() for v in vs)])
            y.append(rep)

    print("CLOCK REGRESSION. n = %d round-observations across 20 campaigns, no API calls.\n" % len(X))
    print("  UNIVARIATE, each predictor alone:")
    for j, nm in enumerate(names):
        r = ols([[row[j]] for row in X], y, [nm])
        print("    %-14s beta %+7.4f +- %.4f   (%.1f SE)   R2 %.3f"
              % (nm, r["beta"][1], r["se"][1], abs(r["beta"][1] / r["se"][1]), r["r2"]))
    print()
    full = ols(X, y, names)
    print("  MULTIPLE, all predictors together, standardised so betas are comparable:")
    for j, nm in enumerate(full["names"]):
        b, s = full["beta"][j], full["se"][j]
        print("    %-14s beta %+7.4f +- %.4f   (%.1f SE)%s"
              % (nm, b, s, abs(b / s) if s else float("nan"),
                 "   <-- the clock" if nm == "round" else ""))
    print("    R2 = %.3f" % full["r2"])
    print()
    no_round = ols([[row[j] for j in range(1, len(names))] for row in X], y, names[1:])
    print("  WITHOUT the clock: R2 = %.3f   (full model %.3f, so the clock adds %.3f)"
          % (no_round["r2"], full["r2"], full["r2"] - no_round["r2"]))
    only_round = ols([[row[0]] for row in X], y, ["round"])
    print("  CLOCK ALONE   : R2 = %.3f" % only_round["r2"])


if __name__ == "__main__":
    main()
