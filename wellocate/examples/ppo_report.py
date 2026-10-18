#!/usr/bin/env python3
"""Print the PPO test report from results/b11_test_<run>.json.

Sections:
  checkpoints      each seed's selected update, validation score, SHA-256, episodes and wall clock
  criteria         the pre-registered comparisons: trained minus its initialisation and minus random ordering, paired by
                   test episode, mean over seeds with the 95% and Bonferroni intervals, each seed's mean, and
                   whether the criterion holds
  test table       pick, re-testing share, exploration and selection loss per policy: the networks with a
                   two-level interval (seeds, then episodes) and each seed's 95% interval over episodes; the scripted
                   policies with a 95% interval over episodes
  versus scripted  trained minus each scripted policy, reported and not required
  adaptation       the trained policy's re-testing share on each landscape beside the best scripted policy's
The training curves are printed by wellocate/examples/ppo_curves.py.

Usage: python3 wellocate/examples/ppo_report.py [results/b11_test_A.json ...]
"""
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COLS = (("pick", "pick", "%.3f"), ("share", "re-testing share, %", "%.1f"), ("exploration", "exploration loss", "%.3f"),
        ("selection", "selection loss", "%.3f"))


def ci(x, f="%.3f"):
    return "[%s, %s]" % (f % x[0], f % x[1])


def report(path):
    r = json.load(open(path))
    out = ["# B11 Run %s (%s)" % (r["run"], os.path.relpath(path, ROOT)), "", "## Checkpoints", "",
           "| seed | selected update | validation score | episodes trained | wall clock | SHA-256 (selected) |",
           "|---|---|---|---|---|---|"]
    for c in r["checkpoints"]:
        out.append("| %d | %d | %.4f | %d | %.2f h | `%s` |" % (c["seed"], c["best_update"], c["best_score"], c["episodes"],
                                                            c["wall_s"] / 3600, c["best_sha256"][:16]))
    out += ["", "## Registered criteria", "",
            "| test split | trained minus | mean | 95% interval | Bonferroni (8) interval | per seed | holds | holds at "
            "Bonferroni | episodes |", "|---|---|---|---|---|---|---|---|---|"]
    for split, s in r["splits"].items():
        for name, c in s["comparisons"].items():
            out.append("| %s | %s | %+.3f | %s | %s | %s | %s | %s | %d |" % (
                split, name.replace("vs ", ""), c["mean"], ci(c["ci"]), ci(c["ci_bonferroni8"]),
                ", ".join("%+.3f" % x for x in c["per_seed"]), "yes" if c["holds"] else "no",
                "yes" if c["holds_bonferroni8"] else "no", c["episodes"]))
    for split, s in r["splits"].items():
        out += ["", "## Test table: %s (%d episodes; guessing k=%d and informed k=%d chosen on validation)" % (
            split, s["episodes"], s["validation_k"]["guessing"], s["validation_k"]["informed"]), "",
            "| policy | %s |" % " | ".join(label for _k, label, _f in COLS), "|---|%s" % ("---|" * len(COLS))]
        for name, t in s["table"].items():
            out.append("| %s (3 seeds, two-level) | %s |" % (name, " | ".join(
                "%s %s" % (f % t[k]["mean"], ci(t[k]["ci_two_level"], f)) for k, _l, f in COLS)))
            for i, ps in enumerate(t["pick"]["per_seed"]):
                out.append("| %s, seed %d | %s |" % (name, i, " | ".join(
                    "%s %s" % (f % t[k]["per_seed"][i]["mean"], ci(t[k]["per_seed"][i]["ci"], f)) for k, _l, f in COLS)))
        for name in ("random", "guessing", "informed", "model-guided"):
            t = s["scripted"][name]
            out.append("| %s | %s |" % (name, " | ".join(
                "%s %s" % (f % t[k]["mean"], ci(t[k]["per_seed"][0]["ci"], f)) for k, _l, f in COLS)))
        out += ["", "Every k (pick, re-testing share): " + "; ".join(
            "%s %.3f, %.1f%%" % (n, s["scripted"][n]["pick"]["mean"], s["scripted"][n]["share"]["mean"])
            for n in sorted(s["scripted"]) if " k=" in n)]
        out += ["", "Trained minus each scripted policy (reported; the registration does not require it): " + "; ".join(
            "%s %+.3f %s" % (n, c["mean"], ci(c["ci"])) for n, c in s["versus_scripted"].items())]
    out += ["", "## Adaptation of the re-testing share", "",
            "| test split | trained share, % (two-level interval) | best scripted policy on test | its share, % |",
            "|---|---|---|---|"]
    for split, s in r["splits"].items():
        t, b = s["table"]["trained"]["share"], s["best_scripted_on_test"]
        out.append("| %s | %.1f %s | %s | %.1f |" % (split, t["mean"], ci(t["ci_two_level"], "%.1f"), b["policy"],
                                                    b["share"]))
    return "\n".join(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    paths = argv or sorted(glob.glob(os.path.join(ROOT, "results", "b11_test_*.json")))
    print("\n\n".join(report(p) for p in paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
