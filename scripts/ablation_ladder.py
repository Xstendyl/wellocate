"""Ablation ladder: start from the thresh.py simulation and apply one deviation at a time,
to find which deviation makes the production pipeline disagree with it."""
import csv, random, statistics as st
AA = "ACDEFGHIKLMNPQRSTVWY"

def load(p):
    d = {}
    with open(p) as f:
        r = csv.reader(f); next(r)
        for v, fit in r: d[v] = float(fit)
    return d

_NB = {}
def nbrs(s):
    g = _NB.get(s)
    if g is None:
        g = [s[:i]+a+s[i+1:] for i in range(4) for a in AA if a != s[i]]
        _NB[s] = g
    return g

def campaign(d, pool, poolset, k, sigma, rng, rounds=15, per=4, fail=0.15,
             retry_failed=True, cold_distinct=False, fb_fresh=False,
             explore_pool=False, measurable_pool=False):
    obs = {}                 # successful readings
    tried = set()            # every sequence a slot was spent on
    def mean_of(s): return sum(obs[s])/len(obs[s])
    def champ(): return max(obs, key=mean_of) if obs else None
    for r in range(rounds):
        picks = []; c = champ()
        if c is not None and k > 0: picks += [c]*k
        need = per-len(picks)
        if c is None:
            if cold_distinct:
                picks += rng.sample(pool, need)
            else:
                picks += [rng.choice(pool) for _ in range(need)]
        else:
            excl = tried if not retry_failed else obs
            src = nbrs(c)
            if explore_pool:
                cand = [x for x in src if x in poolset and x not in excl]
            else:
                cand = [x for x in src if x in d and x not in excl]
            rng.shuffle(cand); take = cand[:need]
            if fb_fresh:
                while len(take) < need:
                    x = rng.choice(pool)
                    if x not in excl and x not in take: take.append(x)
            else:
                while len(take) < need: take.append(rng.choice(pool))
            picks += take
        for s in picks:
            if measurable_pool and s not in poolset:
                continue          # rejected, slot not consumed; no re-ask here (upper bound)
            tried.add(s)
            if rng.random() < fail: continue
            obs.setdefault(s, []).append(d[s]+rng.gauss(0, sigma))
    if not obs: return 0.0, 0.0
    return d[champ()], max(d[s] for s in obs)

REF = {"PhoQ": {2.0:{0:21.040,1:23.320,2:22.001,3:19.073}, 4.0:{0:12.443,1:15.574,2:14.911,3:15.076}},
       "GB1":  {2.0:{0:4.186,1:4.292,2:3.939,3:3.224},     4.0:{0:2.684,1:3.097,2:2.972,3:2.648}}}

LADDER = [
    ("verbatim thresh.py",                      dict()),
    ("+ no retry of FAILED sequences",           dict(retry_failed=False)),
    ("+ cold start distinct",                    dict(retry_failed=False, cold_distinct=True)),
    ("+ fallback fresh (no accidental replic.)", dict(retry_failed=False, cold_distinct=True, fb_fresh=True)),
    ("+ EXPLORE restricted to viable pool",      dict(retry_failed=False, cold_distinct=True, fb_fresh=True, explore_pool=True)),
    ("+ MEASURE restricted to viable pool",      dict(retry_failed=False, cold_distinct=True, fb_fresh=True, explore_pool=True, measurable_pool=True)),
]

N = 1200
for name, path, thr, unit in (("PhoQ","phoq.csv",1.0,4.24), ("GB1","gb1.csv",0.1,0.42)):
    d = load(path); pool = [s for s,v in d.items() if v > thr]; poolset = set(pool)
    for ratio in (2.0, 4.0):
        sig = unit*ratio
        print("="*104)
        print("%s  ratio %.1f   REFERENCE  %s" % (name, ratio,
              " ".join("k%d=%7.3f" % (k, REF[name][ratio][k]) for k in (0,1,2,3))))
        for label, kw in LADDER:
            row = []
            for k in (0,1,2,3):
                rng = random.Random(1000+k)
                vals = [campaign(d,pool,poolset,k,sig,rng,**kw)[0] for _ in range(N)]
                row.append((st.mean(vals), st.stdev(vals)/N**0.5))
            bk = max(range(4), key=lambda i: row[i][0])
            g = 100*(row[bk][0]-row[0][0])/row[0][0] if row[0][0] else 0
            print("  %-42s %s | best k=%d  gain %+6.1f%%"
                  % (label, " ".join("%7.3f" % row[i][0] for i in range(4)), bk, g))
