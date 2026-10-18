import sys, os, time, statistics as st
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import landscape as L, sweep as S, metrics as M, policies as P

N = 5000
for fr, label in ((0.15, "MAIN (failure_rate=0.15)"), (0.0, "REPRODUCTION (failure_rate=0.0)")):
    for name in ("phoq", "gb1"):
        ls = L.load(name)
        t = time.time()
        g = S.k_sweep(ls, S.REFERENCE_RATIOS, n_campaigns=N, failure_rate=fr,
                      explore_scope="pool", fallback="fresh_pool")
        print(S.table(g, title="\n%s  %s  PRODUCTION DESIGN (pool-restricted)  N=%d  [%.0fs]"
                      % (name.upper(), label, N, time.time()-t),
                      ref=S.REFERENCE[name]))
        # significance of the best-k contrast
        for ratio in S.REFERENCE_RATIOS:
            row = g[ratio]
            means = {k: row[k].summary["true_of_nominated"][0] for k in (0,1,2,3)}
            bk = max(means, key=means.get)
            pd = M.paired_diff([r.nominated_true for r in row[bk].results],
                               [r.nominated_true for r in row[0].results])
            sig = "SIGNIFICANT" if pd["se"] and abs(pd["diff"]) > 2*pd["se"] else "not significant"
            need = M.power_n(pd["sd_of_diff"], pd["diff"]) if pd["diff"] else None
            print("        ratio %.1f: best k=%d, paired diff %+7.4f +- %.4f -> %s"
                  "   (n needed for this effect: %s paired)"
                  % (ratio, bk, pd["diff"], pd["se"], sig,
                     "{:,}".format(need) if need else "n/a"))
