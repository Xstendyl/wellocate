#!/usr/bin/env python3
"""Check that the extra Opus menu campaigns run exactly the configuration of the original menu panel.

  1  Prompts. One stand-in campaign (a scripted model, no API call) on seed 300,030 with the menu options, run
     once in a checkout of the panel's commit and once in this tree; every prompt must be byte-identical.
  2  Settings. `grid.py --dry` on the launch command writes a manifest without any model call; every setting it
     shares with the panel's manifest must match, and any prompt option added later must be off.
The --dry manifest and the checkout are removed afterwards.

Usage: python3 scripts/same_config_0an5.py      (writes results/same_config_0an5.json; exit 1 on any difference)
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import launch_0an as L                                                  # noqa: E402

F2_COMMIT = "9bc8ef4"
CAPTURE = r'''
import json, os, re, sys
T = sys.argv[1]; sys.path[:0] = [T, os.path.join(T, "scripts")]
from repdef import llm, tools
import grid
seen = []
def model(prompt, model, **kw):
    seen.append(prompt)
    if "ANSWER: XXXX" in prompt:
        return llm.Call(text="ANSWER: GDIF\nREASON: x", model=model)
    n = int(re.search(r"Reply with exactly (\d+) lines", prompt).group(1))
    rnd = int(re.search(r"ROUND (\d+) OF", prompt).group(1))
    nb = sorted(tools._neighbours("GDIF", grid.ALPHABET))
    picks = ["GDIF"] + nb[3 * rnd: 3 * rnd + 3]
    if n == 1:
        picks = [nb[(rnd * 7 + len(seen)) % len(nb)]]
    return llm.Call(text="\n".join("%s | x" % p for p in picks[:n]), model=model)
llm.complete = model
fit, pool = grid.landscape()
grid.one_campaign(fit, pool, tuple(sorted(pool)), (7.0, 0.1), "vendor/stub", "blind", 300030, [], 6000, 3,
                  prompt_options=dict(truthful_reask=True, menu=True))
sys.stdout.write(json.dumps(seen))
'''
SHARED = ("K", "anchor", "anchor_reading", "comparator", "conditions", "cv", "example", "fail_pct", "gb1_max",
          "global_best", "landscape", "max_reasks", "max_tokens", "noise", "noise_floor", "order_seed", "pct", "pool",
          "primary_outcome", "prior_rel_floor", "prompt_landscape", "reasoning_effort", "riskfree_cap", "rounds",
          "seed", "shuffled", "slots", "space", "temperature", "workers", "credit_floor_usd")


def capture(tree, script):
    r = subprocess.run([sys.executable, "-B", script, tree], cwd=tree, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("capture failed in %s:\n%s" % (tree, r.stderr[-2000:]))
    return json.loads(r.stdout[r.stdout.index("["):])


def main():
    out, bad = {}, []
    tmp = tempfile.mkdtemp(prefix="repdef_f2_")
    wt = os.path.join(tmp, "f2")
    subprocess.run(["git", "worktree", "add", "--detach", wt, F2_COMMIT], cwd=ROOT, check=True, capture_output=True)
    try:
        script = os.path.join(tmp, "capture.py")
        open(script, "w").write(CAPTURE)
        old, new = capture(wt, script), capture(ROOT, script)
        same = old == new
        out["prompts"] = dict(f2_commit=F2_COMMIT, sent_at_f2_commit=len(old), sent_now=len(new), identical=same)
        if not same:
            i = next((k for k, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
            bad.append("prompt %d differs from %s" % (i, F2_COMMIT))
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", wt], cwd=ROOT, capture_output=True)
    tag = "tmp0an5configcheck"
    (_t, _n, _c, args), = L.arms("topup_0an5")
    args = [a if a != L.TOPUP_0AN5["tag"] else tag for a in args]
    r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + args + ["--dry", "--allow-dirty"],
                       cwd=ROOT, capture_output=True, text=True)
    mp = os.path.join(ROOT, "results", "grid_%s_manifest.json" % tag)
    if not os.path.exists(mp):
        raise SystemExit("grid.py --dry wrote no manifest:\n%s" % (r.stdout[-1500:] + r.stderr[-1500:]))
    now = json.load(open(mp))
    for f in [p for p in os.listdir(os.path.join(ROOT, "results")) if tag in p]:
        os.remove(os.path.join(ROOT, "results", f))
    f2 = json.load(open(os.path.join(ROOT, "results", "grid_gen_0an_f2_menu_manifest.json")))
    diffs = {k: (f2.get(k), now.get(k)) for k in SHARED if f2.get(k) != now.get(k)}
    po_f2, po_now = f2["prompt_options"], now["prompt_options"]
    added = {k: v for k, v in po_now.items() if k not in po_f2}
    po_diff = {k: (po_f2[k], po_now.get(k)) for k in po_f2 if po_f2[k] != po_now.get(k)}
    out["settings"] = dict(compared=list(SHARED), differences=diffs, prompt_option_differences=po_diff,
                           prompt_options_added_since=added, models=[m["id"] for m in now["models"]],
                           seed0=now["seed0"], campaigns=now["campaigns_per_cell"], budget_usd=now["budget_usd"])
    if diffs or po_diff or any(added.values()):
        bad.append("settings differ: %s %s %s" % (diffs, po_diff, added))
    out["verdict"] = "same F2 configuration" if not bad else bad
    json.dump(out, open(os.path.join(ROOT, "results", "same_config_0an5.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
