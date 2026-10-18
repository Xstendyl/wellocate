#!/usr/bin/env python3
"""Descriptive summary of two short runs in which re-tests beyond a limit were refused. No causal reading.

Per model and run, per campaign: capped attempts, at-limit proposals split into copies of the refusal notice
and re-proposals, lost rounds by parse status, lost slots by channel, readings, distinct candidates,
rejections, final pick and spend. References are control runs on the same seeds (Gemini 2.5 Flash, DeepSeek
V3.1) and the grid's Blind means for all three models.

Limits: one or two campaigns per model and two prompt versions; in the second version a refused order left no
history line; the call log keeps only the last reply of a re-asked call.

Usage: python3 scripts/f3_smokes_descriptive.py      (writes results/f3_smokes_descriptive.json)
"""
import collections, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_0al as A0                                                # noqa: E402
import analyse_grid as AG                                               # noqa: E402
import capped_replies_0an1 as CR                                        # noqa: E402

SMOKES = {"0an": "smoke0an_f3_cap", "0an.1": "smoke0an1_f3_cap"}
GRID = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")


def rows(tag):
    return [json.loads(l) for l in open(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)) if l.strip()]


def per_campaign(r):
    hits = r.get("repeat_cap_hits") or 0
    return dict(seed=r["seed"], capped_attempts=r.get("n_capped") or 0, readings=r["n_ok"] if "n_ok" in r else None,
                distinct=r["n_distinct_measured"], rejections=r["n_rejected"], lost=r["lost_slots"],
                lost_rounds_slots=r["rounds_lost_slots"], lost_rejection=r["slots_abandoned"] - hits,
                lost_cap_bound=hits, pick=r["nominated_true"], spend=r["spend"])


def calls_split(tag):
    """At-limit proposals split into copies and re-proposals, and lost calls by kind and parse status."""
    copies = collections.defaultdict(collections.Counter)
    lost = collections.defaultdict(collections.Counter)
    for c in A0.calls(tag):
        if c.get("kind") == "nomination":
            continue
        m = c["model"]
        lim = CR.at_limit(c["prompt"])
        reasons = dict(CR.re.findall(r"^\s*([A-Z]{4})\s*\|\s*(.*)$", c.get("raw_response") or "", CR.re.M))
        for s in c.get("parsed") or []:
            if s in lim:
                copies[m]["copy of the refusal" if CR.ECHO.search(reasons.get(s, "")) else "re-proposal"] += 1
        if c.get("parse_status") != "ok" and not c.get("parsed"):
            k = "round" if c.get("n_slots") == c.get("slots_per_round") else "replacement"
            lost[m]["%s: %s" % (k, c["parse_status"])] += 1
    return copies, lost


def main():
    g, _ = AG.drop_fallbacks(AG.load("+".join(GRID)), AG.fallback_seeds(list(GRID)))
    out = {"references": {}, "smokes": {}}
    for m in sorted({r["model"] for r in g}):
        b = [r for r in g if r["model"] == m and r["condition"] == "Blind"]
        out["references"][m] = {"grid Blind mean": dict(
            campaigns=len(b), distinct=st.mean(r["n_distinct_measured"] for r in b),
            rejections=st.mean(r["n_rejected"] for r in b), lost=st.mean(r["lost_slots"] for r in b),
            pick=st.mean(r["nominated_true"] for r in b))}
    for r in rows("smoke0an_f0_control"):
        out["references"][r["model"]].setdefault("F0 control smoke, same seeds", []).append(per_campaign(r))
    for name, tag in SMOKES.items():
        copies, lost = calls_split(tag)
        d = {}
        for r in rows(tag):
            d.setdefault(r["model"], dict(campaigns=[], at_limit_proposals={}, lost_calls={}))["campaigns"].append(
                per_campaign(r))
        for m in d:
            d[m]["at_limit_proposals"] = dict(copies[m])
            d[m]["lost_calls"] = dict(lost[m])
        out["smokes"][name] = d
    # Did blocking re-tests send the agents to new names? Each campaign's rejections and distinct candidates over its
    # model's grid Blind mean. Rejections count new names that proved non-viable, so they are new-name orders.
    ratios = collections.defaultdict(list)
    for d in out["smokes"].values():
        for m, v in d.items():
            gb = out["references"][m]["grid Blind mean"]
            for c in v["campaigns"]:
                ratios["rejections"].append(c["rejections"] / gb["rejections"])
                ratios["distinct"].append(c["distinct"] / gb["distinct"])
    out["over_grid_blind"] = {k: dict(min=min(v), max=max(v), campaigns=len(v),
                                      above_one=sum(1 for x in v if x > 1)) for k, v in ratios.items()}
    json.dump(out, open(os.path.join(ROOT, "results", "f3_smokes_descriptive.json"), "w"), indent=1)
    for name, d in out["smokes"].items():
        print("F3 smoke under %s" % name)
        for m, v in sorted(d.items()):
            for c in v["campaigns"]:
                print("   %-28s seed %d capped %3d readings %2s distinct %2d rejections %3d lost %2d (rounds %2d, "
                      "rejection %2d, cap-bound %2d) pick %.3f $%.3f"
                      % (m.split("/")[1], c["seed"], c["capped_attempts"], c["readings"], c["distinct"],
                         c["rejections"], c["lost"], c["lost_rounds_slots"], c["lost_rejection"], c["lost_cap_bound"],
                         c["pick"], c["spend"]))
            print("   %-28s at-limit proposals %s; lost calls %s" % ("", v["at_limit_proposals"], v["lost_calls"]))
    for k, v in out["over_grid_blind"].items():
        print("%s over the grid's Blind mean: %.2f to %.2f times; above it in %d of %d campaigns"
              % (k, v["min"], v["max"], v["above_one"], v["campaigns"]))
    print("references")
    for m, v in sorted(out["references"].items()):
        gb = v["grid Blind mean"]
        f0 = v.get("F0 control smoke, same seeds", [])
        print("   %-28s grid Blind: distinct %.1f rejections %.1f lost %.2f pick %.3f | F0 smoke: %s"
              % (m.split("/")[1], gb["distinct"], gb["rejections"], gb["lost"], gb["pick"],
                 [(c["seed"], c["distinct"], c["rejections"], c["lost"]) for c in f0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
