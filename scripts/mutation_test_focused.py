import io, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["repdef/policies.py", "repdef/campaign.py"]
BAK = {f: io.open(os.path.join(ROOT, f), encoding="utf-8").read() for f in FILES}
MUTANTS = [
 ("repdef/policies.py", "drop the campaign seed from EXPLORATION keys",
  'cand, min(need, len(cand)), "expl", self.seed, view.campaign_seed,\n            view.current_round, champ)',
  'cand, min(need, len(cand)), "expl", self.seed,\n            view.current_round, champ)'),
 ("repdef/policies.py", "drop the campaign seed from the fresh_pool fallback",
  '"fb", self.seed, view.campaign_seed,\n                                       view.current_round, champ)',
  '"fb", self.seed,\n                                       view.current_round, champ)'),
 ("repdef/campaign.py", "remove the re-ask cap (hangs without a structural guard)",
  '                if tries > MAX_REASKS:',
  '                if tries > 10 ** 6:'),
 ("repdef/campaign.py", "bury the cap as a literal instead of the named constant",
  '                if tries > MAX_REASKS:',
  '                if tries > 3:'),
]
def restore():
    for f, s in BAK.items():
        io.open(os.path.join(ROOT, f), "w", encoding="utf-8").write(s)
caught = survived = 0
try:
    for f, desc, old, new in MUTANTS:
        src = BAK[f]
        if old not in src:
            print("  SKIP: %s" % desc); survived += 1; continue
        io.open(os.path.join(ROOT, f), "w", encoding="utf-8").write(src.replace(old, new, 1))
        try:
            r = subprocess.run([sys.executable, "-m", "unittest", "-q",
                                "tests.test_pipeline"], capture_output=True, text=True,
                               cwd=ROOT, timeout=90)
            ok = r.returncode != 0
            note = ""
        except subprocess.TimeoutExpired:
            ok, note = False, "  <-- HUNG, which a behavioural test cannot catch"
        print("  %s  %s%s" % ("CAUGHT  " if ok else "SURVIVED", desc, note))
        caught += ok; survived += (not ok)
        restore()
finally:
    restore()
print("\ncaught %d / survived %d" % (caught, survived))
