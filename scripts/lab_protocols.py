#!/usr/bin/env python3
"""Three scripted lab protocols as extra reference points. Simulation only, no API calls; not a human baseline.

  python3 scripts/lab_protocols.py

Each spends the same 60-slot budget the way a wet lab is often run and hill-climbs as the reference does
(champion by mean reading, new candidates are its single-letter neighbours). Only the schedule differs.

  (a) triplicate-everything   20 distinct candidates, 3 readings each
  (b) duplicate-everything    30 distinct candidates, 2 readings each
  (c) screen-then-confirm     rounds 1-12 single readings of 48 neighbours, then rounds 13-15 confirm

Each protocol fills a round's slots from a queue of (candidate, copies remaining) and appends a fresh
neighbour of the current champion when the queue empties. In rounds 13-15 of (c), each round orders the top 3
by mean and spends its fourth slot on the leader. Landscape, anchor, n and seeds match
`scripts/fair_reference_curve.py`, so every number is paired with the reference curve.
"""
import json, math, os, random, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import campaign as C, policies as P                        # noqa: E402
import repdef.rng as R                                                 # noqa: E402
from fair_reference_curve import FairGreedy, landscape, anchor_of, CV, FLOOR, N, SEED0  # noqa: E402

BOOT = 2000


class QueueProtocol(P.GreedyWithReplication):
    """A protocol whose slots come from a queue of (candidate, copies remaining).

    It inherits the reference's champion rule and exploration; `copies` is the protocol's repeat count.
    """

    def __init__(self, copies, anchor, space, fair, seed=0):
        if fair:
            FairGreedy.__init__(self, 0, anchor, space, seed=seed)
        else:
            P.GreedyWithReplication.__init__(self, 0, seed=seed, explore_scope="pool",
                                             fallback="fresh_pool")
        # Neighbours are drawn over the landscape's own letters, in both scopes.
        self.alphabet = P.alphabet_of(space)
        self.copies = copies
        self.fair = fair
        self._anchor = anchor
        self._queue = []
        self.name = "protocol_x%d_%s" % (copies, "fair" if fair else "pool")

    def _fresh(self, view, exclude):
        """One new candidate: a neighbour of the champion, through the scope this protocol runs under."""
        champ = self.champion(view)
        if champ is None:
            champ = self._anchor
        got = self._explore(view, champ, 1, exclude)
        return got[0] if got else champ

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        if kind == "replacement":
            # A rejected order is refilled with a fresh candidate, never with an extra repeat, so a
            # rejection cannot inflate the replication share.
            return [self._fresh(view, exclude) for _ in range(n_slots)]
        out = []
        while len(out) < n_slots:
            if not self._queue:
                self._queue.append([self._fresh(view, set(exclude) | set(out)), self.copies])
            cand, left = self._queue[0]
            out.append(cand)
            left -= 1
            if left <= 0:
                self._queue.pop(0)
            else:
                self._queue[0][1] = left
        return out


class ScreenThenConfirm(QueueProtocol):
    """Single readings while screening, then three confirming rounds on the leaders."""

    SCREEN_ROUNDS = 12

    def __init__(self, anchor, space, fair, seed=0):
        QueueProtocol.__init__(self, 1, anchor, space, fair, seed=seed)
        self.name = "protocol_screen_confirm_%s" % ("fair" if fair else "pool")

    def _top_by_mean(self, view, n):
        means = {}
        for h in view.history:
            if h.outcome == "ok":
                means.setdefault(h.seq, []).append(h.observed)
        ranked = sorted(means, key=lambda s: -st.mean(means[s]))
        return ranked[:n]

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        if view.current_round <= self.SCREEN_ROUNDS or kind == "replacement":
            return QueueProtocol.propose(self, view, n_slots, exclude, kind)
        top = self._top_by_mean(view, 3)
        if not top:
            return QueueProtocol.propose(self, view, n_slots, exclude, kind)
        picks = list(top)[:n_slots]
        while len(picks) < n_slots:
            picks.append(top[0])
        return picks


def boot_ci(vals, reps=BOOT, seed=13):
    rnd = random.Random(seed)
    means = sorted(st.mean(rnd.choices(vals, k=len(vals))) for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


def run_protocol(make, fit, pool, ps, space, anchor, fair, n):
    nom, dis, rep, rej, lost, dead = [], [], [], [], [], 0
    for i in range(n):
        pol = make()
        try:
            r = C.run(fit, pool, pol, 0.0, SEED0 + i, 0.15, pool_sorted=ps,
                      nomination="mean", prior="empirical",
                      noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
        except C.UnusableSigma:
            dead += 1
            continue
        ok = [h for h in r.history if h.outcome == "ok"]
        seen = set()
        for h in ok:
            seen.add(h.seq)
        # Replication share over slots used (replication_count / slots_used), as grid.py computes it for agents.
        nom.append(r.nominated_true)
        dis.append(len(seen))
        rep.append(100.0 * r.replication_count / r.slots_used if r.slots_used else float("nan"))
        rej.append(sum(1 for h in r.history if h.outcome == "rejected"))
        lost.append(sum(1 for h in r.history if h.outcome == "abandoned"))
    lo, hi = boot_ci(nom) if len(nom) > 1 else (float("nan"),) * 2
    return dict(mean=st.mean(nom), lo=lo, hi=hi,
                se=st.stdev(nom) / math.sqrt(len(nom)),
                replication=st.mean(rep), distinct=st.mean(dis),
                rejections=st.mean(rej), lost=st.mean(lost), n=len(nom), collapsed=dead)


def main():
    n = int(os.environ.get("LP_N", str(N)))
    fit, pool = landscape()
    ps = tuple(sorted(pool))
    space = tuple(sorted(fit))
    anchor = anchor_of(fit, pool)
    out = dict(n=n, seed0=SEED0, anchor=anchor, note=(
        "scripted lab protocols, not a human baseline; a real human study is future work"), rows={})
    print("=" * 108)
    print("SCRIPTED LAB PROTOCOLS (0aj)   n=%d per cell   seeds %d..%d   anchor=%s" %
          (n, SEED0, SEED0 + n - 1, anchor))
    print("These are scripted protocols. Nobody ran them. A real human study is future work.")
    print("=" * 108)
    print("  %-26s %-6s %9s %20s %8s %9s %9s %8s"
          % ("protocol", "scope", "mean", "95% CI", "repl %", "distinct", "rejects", "lost"))
    protos = [("(a) triplicate-everything", lambda a, s, f: QueueProtocol(3, a, s, f)),
              ("(b) duplicate-everything", lambda a, s, f: QueueProtocol(2, a, s, f)),
              ("(c) screen-then-confirm", lambda a, s, f: ScreenThenConfirm(a, s, f))]
    for label, make in protos:
        for scope in ("pool", "fair"):
            fair = (scope == "fair")
            r = run_protocol(lambda: make(anchor, space, fair), fit, pool, ps, space, anchor, fair, n)
            out["rows"]["%s|%s" % (label, scope)] = r
            print("  %-26s %-6s %9.4f [%8.4f,%8.4f] %8.1f %9.2f %9.2f %8.2f"
                  % (label, scope, r["mean"], r["lo"], r["hi"], r["replication"], r["distinct"],
                     r["rejections"], r["lost"]))
    json.dump(out, open(os.path.join(ROOT, "results", "lab_protocols.json"), "w"), indent=1)
    print("\n  wrote results/lab_protocols.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
