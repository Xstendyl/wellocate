#!/usr/bin/env python3
"""Run Gemini 3.1 Pro's remaining grid re-runs and GB1 Menu seeds one at a time, bounded by the credit balance.

Before each campaign the balance is re-read; the script stops if Gemini's spend plus the largest campaign seen
in the arm could pass $80. A failed grid re-run drops its seed from both sides; a failed Menu seed is re-run once
and dropped if it fails again. The log goes to results/finish_0an7.log.

Usage: set -a; . ./.env; set +a; python3 scripts/finish_0an7.py [--run]
"""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import launch_0an7 as L                                                  # noqa: E402

GEM = "google/gemini-3.1-pro-preview"
CEILING = 80.0
LAUNCH_BALANCE = 530.76110143          # every main-run manifest's credit_balance_at_launch
PLAN = [("gen_0an7_gem_grid_blind", "_rerun", s) for s in (300022, 300040, 300044)] + \
       [("gen_0an7_gem_gb1_menu", "_cont", s) for s in (11000000, 11000002, 11000011)]


def rows(tag):
    p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def gemini_spend():
    import grid
    sol = sum(r["spend"] for t in ("grid_blind", "gb1_blind", "gb1_menu") for r in rows("gen_0an7_sol_" + t))
    bal = grid.credit_balance()
    return LAUNCH_BALANCE - bal - sol, bal


def args_for(base, suffix, seed):
    for tag, m, name, n, args in L.main_arms():
        if tag == base:
            a = list(args)
            a[a.index("--tag") + 1] = base + suffix
            a[a.index("--workers") + 1] = "1"
            a[a.index("--budget-usd") + 1] = "%.2f" % CEILING
            return a + ["--seeds", str(seed)]
    raise SystemExit("no arm %s" % base)


def log_lines(tag):
    p = os.path.join(ROOT, "results", "grid_%s.log" % tag)
    return open(p).read().splitlines() if os.path.exists(p) else []


def main():
    run = "--run" in sys.argv
    log = open(os.path.join(ROOT, "results", "finish_0an7.log"), "a")
    say = lambda s: (print(s), log.write(s + "\n"), log.flush())
    queue, dropped = list(PLAN), []
    tries = {}
    while queue:
        base, suffix, seed = queue.pop(0)
        tag = base + suffix
        if any(r["seed"] == seed for r in rows(tag)):
            say("seed %d already written under %s" % (seed, tag))
            continue
        biggest = max(r["spend"] for r in rows(base))
        spent, bal = gemini_spend()
        say("before %s seed %d: balance $%.4f, Gemini by balance $%.4f, largest %s campaign $%.4f"
            % (tag, seed, bal, spent, base, biggest))
        if spent + biggest > CEILING:
            say("STOP: the next campaign could take Gemini past $%.0f; seeds left: %s" % (CEILING, [seed] + [q[2] for q in queue]))
            return 1
        if not run:
            say("dry: would run %s" % " ".join(args_for(base, suffix, seed)))
            continue
        before = len(log_lines(tag))
        with open(os.path.join(ROOT, "results", "grid_%s.log" % tag), "a") as f:
            subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + args_for(base, suffix, seed),
                           cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        mp = os.path.join(ROOT, "results", "grid_%s_manifest.json" % tag)
        if os.path.exists(mp):
            shutil.copy(mp, mp.replace(".json", "_%d.json" % seed))
        ok = any(r["seed"] == seed for r in rows(tag))
        new = log_lines(tag)[before:]
        abandoned = any(("FAILED" in l or "ABANDONED" in l) and str(seed) in l for l in new)
        # Only a FAILED or ABANDONED line counts as an abandonment; a launch that never ran stops the script.
        if not ok and not abandoned:
            say("STOP: %s seed %d neither wrote a row nor failed; the run did not start. Last log lines: %s"
                % (tag, seed, " | ".join(x.strip() for x in new[-3:])))
            return 1
        tries[(tag, seed)] = tries.get((tag, seed), 0) + 1
        say("%s seed %d: %s" % (tag, seed, "written" if ok else "abandoned"))
        if not ok:
            if suffix == "_rerun" or tries[(tag, seed)] >= 2:
                dropped.append(seed)
                say("seed %d abandoned twice: dropped from both sides of every pairing that uses it" % seed)
            else:
                queue.insert(0, (base, suffix, seed))
    spent, bal = gemini_spend()
    say("done: balance $%.4f, Gemini by balance $%.4f; dropped seeds %s" % (bal, spent, dropped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
