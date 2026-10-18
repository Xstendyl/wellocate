"""Score the logged replies of the independent check for all three models.

A reply line counts as a proposal up to four; missing lines and invalid letters count as non-repeats.
Usage: python3 score_all_models.py
"""
import collections, importlib.util, json, math, os, re, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("v", os.path.join(HERE, "indep_vignette.py"))
v = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(v)

for name in ["results_raw.json", "results_raw_gemini-2.5-flash.json", "results_raw_deepseek-chat-v3.1.json"]:
    r = json.load(open(os.path.join(HERE, name)))
    by = collections.defaultdict(dict)
    for x in r:
        _, measured, champ = v.render(x["seed"], x["arm"])
        props = [p.upper() for p in re.findall(r"^\s*\**\s*([A-Za-z]{4})\s*\**\s*\|", x["text"], re.M)[:4]]
        rep = sum(p in measured for p in props)
        by[x["arm"]][x["seed"]] = (rep / 4.0, champ in props, len(props))
    print(name, "calls", len(r))
    for a, nm in zip("ABC", ["exact, stated", "exact, unstated", "noisy, stated"]):
        vals = list(by[a].values())
        print("   %-16s n=%d repeat share %.3f | best re-ordered %d | replies with <4 lines %d"
              % (nm, len(vals), st.mean(x[0] for x in vals), sum(x[1] for x in vals), sum(x[2] < 4 for x in vals)))
    for nm, X, Y in [("C-A", "C", "A"), ("B-A", "B", "A")]:
        ks = sorted(set(by[X]) & set(by[Y]))
        d = [by[X][k][0] - by[Y][k][0] for k in ks]
        print("   %s paired %.3f (SE %.3f, n=%d)" % (nm, st.mean(d), st.stdev(d) / math.sqrt(len(d)), len(d)))
