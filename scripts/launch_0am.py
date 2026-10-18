#!/usr/bin/env python3
"""Launch the generalisation runs one stage at a time. Spends nothing without --run.

Stages (each arm runs as a separate grid.py process with its own tag):
  smoke   2 pilot campaigns per model on each landscape, $0.75 cap per arm.
  R       the real-protein panel: GB1 scrambled, GB1 real and PhoQ scrambled, Blind and Mechanism.
  K       the NK panel: K = 0 to 3, Blind, over 20 landscapes each.
  topup   30 extra Opus seeds in both GB1 arms, launched only when scripts/analyse_0am.py reports the trigger.
The launch refuses if any planned seed range overlaps seeds already used in results, manifests or code.

Usage:
  python3 scripts/launch_0am.py --stage R                 # check seeds, print the commands, spend nothing
  set -a; . ./.env; set +a; python3 scripts/launch_0am.py --stage R --run
  python3 scripts/launch_0am.py --smoke-report            # check the pilot results on disk
"""
import argparse, json, os, statistics as st, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import replicate_decision_rule as RD                                 # noqa: E402

SEED0 = {"R": 11_000_000, "K": 12_000_000, "smoke": 13_000_000, "smoke2": 13_000_001}
COMMON = ["--max-tokens", "6000", "--max-reasks", "3", "--temperature", "0.0", "--noise", "multiplicative",
          "--credit-floor", "50", "--workers", "3", "--shuffle", "--order-seed", "20261003",
          "--truthful-reask"]                 # every arm, from smoke2 onwards
R_ARMS = (("gen_r_gb1scr", "gb1_scrambled"), ("gen_r_gb1real", "gb1_real"),
          ("gen_r_phoqscr", "phoq_scrambled"))
# Budget ceiling per arm, in USD.
CEILING = {"smoke": 0.75, "smoke2": 0.75, "R": 21.0, "K": 9.50, "topup": 19.0}


def arms(stage):
    """[(tag, grid.py arguments)] for one stage."""
    out = []
    if stage in ("smoke", "smoke2"):
        pre = "smoke0am_" if stage == "smoke" else "smoke0am2_"
        for tag, land, extra in (("gb1scr", "gb1_scrambled", []), ("gb1real", "gb1_real", []),
                                 ("phoqscr", "phoq_scrambled", []), ("nk3", "nk", ["--nk-k", "3"])):
            out.append((pre + tag, ["--landscape", land] + extra + [
                "--conditions", "Blind,Mechanism", "--campaigns", "1", "--seed0", str(SEED0[stage])]))
    elif stage == "R":
        for tag, land in R_ARMS:
            out.append((tag, ["--landscape", land, "--conditions", "Blind,Mechanism", "--campaigns", "60",
                              "--campaigns-by-model", "frontier=30", "--seed0", str(SEED0["R"])]))
    elif stage == "K":
        for k in (0, 1, 2, 3):
            out.append(("gen_k%d" % k, ["--landscape", "nk", "--nk-k", str(k), "--conditions", "Blind",
                                        "--campaigns", "60", "--campaigns-by-model", "frontier=20",
                                        "--seed0", str(SEED0["K"])]))
    elif stage == "topup":
        for tag, land in R_ARMS[:2]:
            out.append((tag + "_top", ["--landscape", land, "--conditions", "Blind,Mechanism",
                                       "--models", "frontier", "--campaigns", "30",
                                       "--seed0", str(SEED0["R"] + 30)]))
    else:
        raise SystemExit("unknown stage %r" % stage)
    return [(tag, a + ["--tag", tag, "--stage", "0am_" + stage, "--budget-usd", "%.2f" % CEILING[stage]]
             + COMMON) for tag, a in out]


RANGES = {"smoke": (SEED0["smoke"], SEED0["smoke"] + 1), "smoke2": (SEED0["smoke2"], SEED0["smoke2"] + 1),
          "R": (SEED0["R"], SEED0["R"] + 60),
          "K": (SEED0["K"], SEED0["K"] + 60), "topup": (SEED0["R"] + 30, SEED0["R"] + 60)}
OPUS = "anthropic/claude-opus-4.7"


def opus_seeds_in_results():
    """Every seed an Opus campaign row records, in any results file."""
    import glob
    out = set()
    for p in glob.glob(os.path.join(ROOT, "results", "**", "*_campaigns.jsonl"), recursive=True):
        for line in open(p, errors="replace"):
            if OPUS in line:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("model") == OPUS and isinstance(r.get("seed"), int):
                    out.add(r["seed"])
    return out


def check_seeds(stage):
    """Refuse if the stage's seed range is already used in results, another manifest, or a seed base in code.

    The topup stage reuses the R panel's seeds 30 to 59 so Opus pairs with Gemini and DeepSeek there; for it,
    only Opus campaigns must not already hold those seeds."""
    lo, hi = RANGES[stage]
    own = [t for t, _x in arms(stage)] + ([t for t, _x in arms("R")] if stage == "topup" else [])
    for other, (a, b) in RANGES.items():
        if other != stage and {stage, other} != {"topup", "R"} and a < hi and lo < b:
            raise SystemExit("REFUSED: %s overlaps 0am's %s range" % (stage, other))
    if stage == "topup":
        hit = sorted(set(range(lo, hi)) & opus_seeds_in_results())
        if hit:
            raise SystemExit("REFUSED: an Opus campaign already holds top-up seeds %s" % hit[:5])
    elif set(range(lo, hi)) & RD.seeds_in_results():
        raise SystemExit("REFUSED: %s seeds %d..%d are already used in results" % (stage, lo, hi - 1))
    for a, b, src in RD.ranges_in_manifests():
        if a < hi and lo < b and not any(("grid_%s_manifest" % t) in src for t in own):
            raise SystemExit("REFUSED: %s seeds overlap %s's range [%d, %d)" % (stage, src, a, b))
    for base, src in RD.bases_in_code():
        if "launch_0am.py" not in src and base < hi and lo < base + RD.SPAN:
            raise SystemExit("REFUSED: %s seeds fall within %d of the seed base %d at %s"
                             % (stage, RD.SPAN, base, src))
    print("seeds %s %d..%d are clear for this stage" % (stage, lo, hi - 1))


def smoke_report(stage="smoke"):
    """Check the pilot stage: all campaigns completed, no empty or truncated replies, the two parsers agree,
    and each panel's cost projected from measured spend per campaign stays under its ceiling."""
    import analyse_0al as A0
    bad, per = [], {}
    for tag, _a in arms(stage):
        p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
        h = os.path.join(ROOT, "results", "grid_%s_health.json" % tag)
        rows = [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []
        health = json.load(open(h)) if os.path.exists(h) else {}
        calls = list(A0.calls(tag))
        genuine = sum(1 for c in calls if not c.get("parsers_agree", True) and c.get("parsed"))
        print("%s: %d campaigns, %d calls, %d genuine parser disagreements" % (tag, len(rows), len(calls), genuine))
        if genuine:
            bad.append((tag, "%d parser disagreements" % genuine))
        for m in sorted({r["model"] for r in rows}):
            v = [r for r in rows if r["model"] == m]
            hh = health.get(m, {})
            per[(tag, m)] = st.mean(r["spend"] for r in v)
            print("   %-30s n=%d  $/campaign %.4f  ok %s  lost %s  out-of-alphabet %s %s  empty %s  truncated %s  "
                  "malformed %s  rep %s"
                  % (m, len(v), per[(tag, m)], [r["n_ok"] for r in v], [r["lost_slots"] for r in v],
                     [r.get("out_of_alphabet_proposals") for r in v],
                     [r.get("out_of_alphabet_letters") for r in v], hh.get("empty"),
                     hh.get("truncated"), hh.get("malformed"),
                     ["%.0f%%" % (100 * r["replication_fraction"]) for r in v]))
            for r in v:
                if r["lost_slots"] > 10:
                    bad.append((tag, m, r["condition"], "lost %d slots" % r["lost_slots"]))
            if hh.get("empty") or hh.get("truncated"):
                bad.append((tag, m))
        if len(rows) != 6:
            bad.append((tag, "only %d of 6 campaigns" % len(rows)))
    if per:
        def proj(tag, n_opus, n_other, both):
            ms = sorted({m for t, m in per if t == tag})
            return sum((n_opus if "opus" in m else n_other) * per[(tag, m)] * (2 if both else 1) for m in ms)
        pre = "smoke0am_" if stage == "smoke" else "smoke0am2_"
        r_cost = sum(proj(pre + t, 30, 60, True) for t in ("gb1scr", "gb1real", "phoqscr"))
        k_cost = 4 * proj(pre + "nk3", 20, 60, False)
        print("projected from the smoke: Panel R $%.2f (ceiling $%.2f), Panel K $%.2f (ceiling $%.2f)"
              % (r_cost, 3 * CEILING["R"], k_cost, 4 * CEILING["K"]))
        if r_cost > 3 * CEILING["R"] or k_cost > 4 * CEILING["K"]:
            bad.append(("projection", "a panel's projected cost passes its ceiling"))
    print("SMOKE GATE: %s" % ("PASS" if not bad else "FAIL %s" % bad))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("smoke", "smoke2", "R", "K", "topup"))
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--smoke-report", nargs="?", const="smoke", default=None, choices=("smoke", "smoke2"))
    a = ap.parse_args()
    if a.smoke_report:
        return smoke_report(a.smoke_report)
    if not a.stage:
        raise SystemExit("--stage is required")
    check_seeds(a.stage)
    cmds = [(tag, [sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py")] + args)
            for tag, args in arms(a.stage)]
    for tag, c in cmds:
        print("launch %s: %s" % (tag, " ".join(c[2:]).replace(ROOT + "/", "")))
    if not a.run:
        print("dry: nothing launched. Re-run with --run.")
        return 0
    procs = []
    for tag, c in cmds:
        log = open(os.path.join(ROOT, "results", "grid_%s.log" % tag), "a")
        procs.append((tag, subprocess.Popen(c, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)))
        print("started %s (pid %d), log results/grid_%s.log" % (tag, procs[-1][1].pid, tag))
    codes = {tag: p.wait() for tag, p in procs}
    print("exit codes: %s" % codes)
    return max(codes.values())


if __name__ == "__main__":
    sys.exit(main())
