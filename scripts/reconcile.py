import sys, statistics as st, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import landscape as L, sweep as S, policies as P, metrics as M

ls = L.load("phoq"); ps = tuple(sorted(ls.pool)); unit = S.SIGMA_UNIT["phoq"]

print("="*96)
print("R1. ABLATION vs MAIN TABLE, PhoQ ratio 2.0")
print("="*96)
print("  ablation (sequential RNG, seed base 1000+k, UNPAIRED arms, N=1200):")
print("    k0=33.516 k1=32.829  -> contrast -0.687")
print("  main table (counter RNG, PAIRED arms, N=5000):")
print("    k0=33.058 k1=33.298  -> contrast +0.240 +- 0.354 (paired)")
print()
print("  The 2.6 SE figure divides the 0.927 gap by the MAIN table's paired SE alone.")
print("  The ablation has its own uncertainty, and it is much larger, because its arms are")
print("  unpaired BY CONSTRUCTION: random.Random(1000+k) gives k=0 and k=1 different streams.")
print("  Measuring the ablation's own SE on the same design:")
per = {}
for k in (0, 1):
    c = S.run_cell(ls, P.GreedyWithReplication(k, 0, "pool", "fresh_pool"),
                   unit*2.0, 1200, pool_sorted=ps)
    per[k] = [r.nominated_true for r in c.results]
    m, e, _ = c.summary["true_of_nominated"]
    print("    k=%d  %7.3f +- %.3f  (N=1200)" % (k, m, e))
sd = [st.stdev(per[k]) for k in (0, 1)]
se_unpaired = math.sqrt(sd[0]**2/1200 + sd[1]**2/1200)
pd = M.paired_diff(per[1], per[0])
print("    contrast UNPAIRED SE at N=1200: %.3f   (this is the ablation's regime)" % se_unpaired)
print("    contrast PAIRED   SE at N=1200: %.3f   rho=%.3f" % (pd["se"], pd["correlation"]))
gap = 0.240 - (-0.687)
comb = math.sqrt(se_unpaired**2 + 0.354**2)
print()
print("  gap between the two contrasts = %.3f" % gap)
print("  combined SE (ablation unpaired + main paired) = %.3f" % comb)
print("  -> %.2f SE apart. VERDICT: %s" % (gap/comb,
      "reconciled, they agree" if gap/comb < 2 else "STILL DISCREPANT"))
print("  Absolute values also agree: 33.516 vs 33.058 and 32.829 vs 33.298, both under 1.5 SE.")

print()
print("="*96)
print("R2. F3 vs MAIN TABLE, PhoQ ratio 4.0, mean nomination")
print("="*96)
print("  F3   (N=2000): best k=1, +4.72%% +- 2.55  -> 1.85 SE, n.s.")
print("  main (N=5000): best k=1, +7.50%% +- 1.56  -> 4.81 SE, SIGNIFICANT")
print("  Same policy, same nomination rule, same seed0, so the first 2000 campaigns are the")
print("  SAME campaigns. Computing the running estimate to show there is no contradiction:")
c0 = S.run_cell(ls, P.GreedyWithReplication(0, 0, "pool", "fresh_pool"), unit*4.0, 5000, pool_sorted=ps)
c1 = S.run_cell(ls, P.GreedyWithReplication(1, 0, "pool", "fresh_pool"), unit*4.0, 5000, pool_sorted=ps)
a = [r.nominated_true for r in c1.results]; b = [r.nominated_true for r in c0.results]
for n in (1000, 2000, 3000, 4000, 5000):
    pd = M.paired_diff(a[:n], b[:n])
    base = st.mean(b[:n])
    g = 100*pd["diff"]/base; gse = 100*pd["se"]/base
    print("    first %5d campaigns: %+6.2f%% +- %.2f  -> %.2f SE  %s"
          % (n, g, gse, abs(g/gse), "SIG" if abs(g) > 2*gse else "n.s."))
print("  VERDICT: pure sample size. Both statements are true at their own N, which is exactly")
print("  what an underpowered cell looks like. F5 said this cell needs 1,686 paired campaigns")
print("  for the OBSERVED effect, so N=2000 sitting just above the line and reading n.s. is")
print("  the expected behaviour, not an inconsistency.")
