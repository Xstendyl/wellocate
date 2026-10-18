#!/usr/bin/env python3
"""Cold recall probe: can a study model recover a landscape before any campaign runs on it?

The probe of `scripts/recall_probe.py`, with its reply format, parser and scoring, on four tasks and the
three study models, one call each at temperature 0:

  gb1_named        the existing GB1 task, word for word. The positive control: the probe can see recall.
  phoq_named       the existing PhoQ task, word for word.
  gb1_scrambled    the scrambled GB1 landscape as a campaign sees it: the abstract framing, the letters A
                   to T, its reference point and reading, and no study named. Scored against the scrambled
                   truth.
  phoq_scrambled   the same for scrambled PhoQ.

A model recovers a scrambled landscape if it names that landscape's best string exactly, or puts two or more of
its true top 10 in its own top 10. Ten guesses among 160,000 strings hit one member of a fixed top 10 with
probability about 0.0006, so two is not luck.

Usage: set -a; . ./.env; set +a; python3 scripts/recall_probe_0am.py      (writes results/recall_probe_0am.jsonl)
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import envs as E, landscape as L, llm, prompts                  # noqa: E402
import recall_probe as RP                                                    # noqa: E402
import grid                                                                  # noqa: E402

OUT = os.path.join(ROOT, "results", "recall_probe_0am.jsonl")
MODELS = [m for _r, m, _d in grid.MODELS]
MAX_TOKENS = 6000             # the grid's; Gemini 2.5 Flash spends tokens reasoning before it answers

# The existing PROMPT with the study, the biology and the wild type replaced by what a campaign on the
# abstract framing is told. Nothing else in the wording changes.
PROMPT_ABSTRACT = """In {system}, all 20^4 = 160,000 {candidate_word}s over the symbols {alphabet} at four positions have a {metric}.
The reference point is "{parent}", which reads about {reading}.

From any knowledge you have of this system, name the {candidate_word} with the HIGHEST {metric}.
Then list your best guess at the top 10 {candidate_word}s in descending order.

Reply in exactly this format and nothing else:
BEST: XXXX
TOP10: XXXX, XXXX, XXXX, XXXX, XXXX, XXXX, XXXX, XXXX, XXXX, XXXX
CONFIDENCE: one short sentence on whether you are recalling this system or inferring."""


def tasks():
    out = []
    for name in ("gb1", "phoq"):
        ls = L.load(name)
        truth = sorted(ls.pool, key=lambda s: -ls.fitness[s])[:10]
        out.append(("%s_named" % name, RP.PROMPT.format(**RP.TASKS[name]), truth, False))
    for env in (E.gb1_scrambled(), E.phoq_scrambled()):
        t = prompts.LANDSCAPES[env.prompt_landscape]
        p = PROMPT_ABSTRACT.format(system=t["system"], candidate_word=t["candidate_word"],
                                   alphabet=env.alphabet, metric=t["metric"], parent=env.anchor,
                                   reading="%.2f" % env.reading)
        out.append((env.name, p, list(env.top10), True))
    return out


def score(text, truth):
    best, top, conf = "", [], ""
    for line in (text or "").splitlines():
        u = line.strip().upper()
        if u.startswith("BEST:"):
            tok = u.split(":", 1)[1].strip().split()
            best = tok[0][:4] if tok else ""
        elif u.startswith("TOP10:"):
            top = [x.strip()[:4] for x in u.split(":", 1)[1].split(",") if x.strip()]
        elif u.startswith("CONFIDENCE:"):
            conf = line.split(":", 1)[1].strip()
    rho, shared = RP.spearman(top, truth)
    hits = sum(1 for s in top if s in truth)
    return dict(best=best, top10=top, exact_hit=(best == truth[0]), n_in_true_top10=hits, rho=rho,
                rho_n=shared, self_report=conf)


def main():
    src, fp = grid.key_source()
    print("key source: %s (fingerprint %s)" % (src, fp))
    rows, spend, recovered = [], 0.0, []
    for name, prompt, truth, scrambled in tasks():
        print("=" * 100)
        print("%s   true best %s   true top10 %s" % (name, truth[0], " ".join(truth)))
        for m in MODELS:
            c = llm.complete(prompt, m, max_tokens=MAX_TOKENS, temperature=0.0)
            spend += c.cost_usd or 0.0
            r = dict(task=name, model=m, scrambled=scrambled, truth_best=truth[0], truth_top10=truth,
                     prompt=prompt, raw=c.text, ok=c.ok, error=c.error, cost_usd=c.cost_usd,
                     finish_reason=getattr(c, "finish_reason", None))
            r.update(score(c.text, truth) if c.ok else {})
            r["recovers"] = bool(c.ok and (r["exact_hit"] or r["n_in_true_top10"] >= 2))
            rows.append(r)
            if scrambled and r["recovers"]:
                recovered.append((name, m))
            print("  %-30s %s BEST=%-5s exact=%-5s %d/10 in true top10 rho=%s recovers=%s"
                  % (m, "ok " if c.ok else "ERR", r.get("best") or "?", r.get("exact_hit"),
                     r.get("n_in_true_top10") or 0,
                     "%.2f (n=%d)" % (r["rho"], r["rho_n"]) if r.get("rho") is not None else "n/a",
                     r["recovers"]))
            if r.get("self_report"):
                print("      self-report: %s" % r["self_report"][:110])
    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print("\nspend $%.4f over %d calls; wrote %s" % (spend, len(rows), os.path.relpath(OUT, ROOT)))
    if any(t == "gb1_scrambled" for t, _m in recovered):
        print("\nSTOP: a model recovered the scrambled GB1 landscape: %s. Nothing in 0am runs until the "
              "operator has been told." % recovered)
        return 2
    if recovered:
        print("\nRECOVERED (not GB1): %s" % recovered)
    else:
        print("\nNo model recovered either scrambled landscape under the stop rule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
