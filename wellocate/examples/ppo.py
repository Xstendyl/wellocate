#!/usr/bin/env python3
"""A small neural policy trained with PPO through Wellocate's released interface, and its transfer.

    python3 wellocate/examples/ppo.py train --run A --seed 0        (grid train only)
    python3 wellocate/examples/ppo.py train --run B --seed 0        (grid train plus GB1 train scrambles)
    python3 wellocate/examples/ppo.py test --run A                  (once, after all three seeds have trained)
    python3 wellocate/examples/ppo.py time                          (throughput of rollouts and updates, no learning)

Training writes checkpoints and a log under training/out/b11/; `test` writes results/b11_test_<run>.json with each
selected checkpoint's SHA-256.

The policy sees Wellocate's Observation without its `view` field, which holds the oracle's pool of viable candidates:
the history (round, candidate, outcome, reading), the budget, the reference point, its stated reading and the
alphabet. It never sees a true value. The reward, the nominee's true value over the landscape's best, is the training
signal only.

At each order the policy picks one entry from a candidate set built from the history:
  re-test     any candidate ordered before that was not rejected
  new         any single-letter substitution of the reference point or of the 8 candidates with the highest mean
              reading that has never been ordered
  random      one entry standing for a candidate drawn uniformly from the candidates never ordered
so every candidate can be ordered. A round's slots are picked one after another without repeats. At the end a second
head nominates one measured candidate. Every feature is scale-free (readings over the reference reading, z-scores
and ranks within the episode), so a policy trained on the grid can be applied to a protein.

The network is three small MLPs (two hidden layers of 64): an order head that scores each entry of the candidate set,
a nominate head that scores each measured candidate, and a critic on the episode's global features.
"""
import argparse, collections, dataclasses, hashlib, json, math, os, sys, time

import numpy as np
import torch
import torch.nn as nn

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from wellocate import baselines as B                                         # noqa: E402
from wellocate import env as W                                               # noqa: E402
from wellocate import landscapes as LS                                       # noqa: E402
from wellocate import scorecard as SC                                        # noqa: E402
from wellocate import splits as SP                                           # noqa: E402

OUT = os.path.join(ROOT, "training", "out", "b11")
K_PARENTS = 8
HIDDEN = 64
G_DIM, C_DIM = 11, 26
D = G_DIM + C_DIM

# The pre-registered training settings.
CONFIG = dict(episodes_per_update=32, instances_per_update=4, updates=1500, validate_every=50, ppo_epochs=4,
              minibatch=256, lr=3e-4, clip=0.2, gae_lambda=0.95, entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
              val_episodes_per_family=200, wall_limit_h=11.5)
RUNS = dict(A=dict(train=["nk:train"], validation=["nk:validation"], test=["nk:test", "gb1:test", "phoq:test"]),
            B=dict(train=["nk:train", "gb1:train"], validation=["nk:validation", "gb1:validation"], test=["phoq:test"]))


# -- features ---------------------------------------------------------------------------------------------------------
class State(object):
    """What the history says, built once per decision from the public observation."""

    def __init__(self, obs):
        self.alpha = obs.alphabet
        self.idx = {c: i for i, c in enumerate(obs.alphabet)}
        self.a = float(obs.anchor_reading)
        self.anchor = obs.anchor
        reads, failed, rejected, ordered = collections.defaultdict(list), collections.Counter(), set(), set()
        n_orders = n_failed = 0
        for r in obs.history:
            if r.outcome == "ok":
                reads[r.seq].append(float(r.observed))
            elif r.outcome == "failed":
                failed[r.seq] += 1
            elif r.outcome == "rejected":
                rejected.add(r.seq)
            else:
                continue                                   # bookkeeping of a lost slot or round; nothing was ordered
            ordered.add(r.seq)
            n_orders += 1
            n_failed += r.outcome == "failed"
        self.reads, self.failed, self.rejected, self.ordered = reads, failed, rejected, ordered
        self.means = {s: sum(v) / len(v) for s, v in reads.items()}
        vals = list(self.means.values())
        floor = 0.05 * abs(self.a) + 1e-9
        self.scale = max(float(np.std(vals)) if len(vals) > 1 else 0.0, floor)
        ranked = sorted(self.means, key=lambda s: (-self.means[s], s))
        self.rank = {s: (1.0 - i / max(1, len(ranked) - 1)) if len(ranked) > 1 else 1.0 for i, s in enumerate(ranked)}
        self.best = ranked[0] if ranked else None
        self.parents = ranked[:K_PARENTS]
        cvs = [np.std(v) / abs(np.mean(v)) for v in reads.values() if len(v) > 1 and np.mean(v) != 0]
        # position x letter: viable measured candidates carrying the letter, their mean z, and rejections
        self.pl_n, self.pl_z, self.pl_rej = np.zeros((4, 20)), np.zeros((4, 20)), np.zeros((4, 20))
        for s, m in self.means.items():
            for p, ch in enumerate(s):
                self.pl_n[p, self.idx[ch]] += 1
                self.pl_z[p, self.idx[ch]] += self.z(m)
        for s in rejected:
            for p, ch in enumerate(s):
                self.pl_rej[p, self.idx[ch]] += 1
        self.pl_z = np.divide(self.pl_z, self.pl_n, out=np.zeros_like(self.pl_z), where=self.pl_n > 0)
        self.n_orders, self.n_failed = n_orders, n_failed
        self.cv = float(np.mean(cvs)) if cvs else 0.0
        self.obs = obs

    def z(self, x):
        return float(np.clip((x - self.a) / self.scale, -10, 10))

    def logratio(self, x):
        return float(np.clip(math.log(max(x, 1e-6) / max(self.a, 1e-6)), -5, 5))

    def glob(self, slots_left, chosen_retests):
        o = self.obs
        best = self.means[self.best] if self.best else self.a
        return [o.slots_used / max(1, o.slots_total), o.round / max(1, o.rounds), slots_left / 4.0,
                float(o.phase == "replacement"), len(self.means) / 60.0, len(self.rejected) / max(1, self.n_orders),
                self.z(best) / 10.0, (len(self.reads[self.best]) if self.best else 0) / 4.0, min(self.cv * 10, 5.0),
                self.n_failed / max(1, self.n_orders), chosen_retests / 4.0]

    def measured_row(self, s):
        """Candidate features of a candidate ordered before (re-test), or of a nominee."""
        v = self.reads.get(s, [])
        m = self.means.get(s)
        bestz = self.z(self.means[self.best]) if self.best else 0.0
        mz = self.z(m) if m is not None else 0.0
        cv = (np.std(v) / abs(np.mean(v))) if len(v) > 1 and np.mean(v) != 0 else 0.0
        row = np.zeros(C_DIM)
        row[0] = 1.0
        row[3] = float(s == self.anchor)
        row[4] = len(v) / 4.0
        row[5] = mz / 10.0
        row[6] = self.rank.get(s, 0.0)
        row[7] = float(s == self.best)
        row[8] = (bestz - mz) / 10.0 if m is not None else 0.0
        row[9] = min(cv * 10, 5.0)
        row[10] = self.failed[s] / 4.0
        row[11] = self.logratio(m) if m is not None else 0.0
        row[24] = self.ham(s, self.anchor) / 4.0
        row[25] = self.ham(s, self.best) / 4.0 if self.best else 0.0
        return row

    @staticmethod
    def ham(a, b):
        return sum(x != y for x, y in zip(a, b))


POS = np.repeat(np.arange(4), 20)
LET = np.tile(np.arange(20), 4)


def candidate_set(st, exclude, chosen):
    """(sequences, feature rows) of the order head's choices; the last entry is the random action (sequence None)."""
    seqs, rows = [], []
    blocked = set(exclude) | set(chosen) | st.rejected
    for s in sorted(st.ordered - blocked):                         # re-tests
        seqs.append(s)
        rows.append(st.measured_row(s))
    parents = [st.anchor] + [p for p in st.parents if p != st.anchor]
    seen = set(seqs)
    bestz = st.z(st.means[st.best]) if st.best else 0.0
    letters = np.asarray(list(st.alpha))
    anc = np.asarray([st.idx[c] for c in st.anchor])
    best = np.asarray([st.idx[c] for c in st.best]) if st.best else None
    for par in parents:
        pm = st.means.get(par, st.a)
        prow = (st.z(pm) / 10.0, st.rank.get(par, 0.5), len(st.reads.get(par, [])) / 4.0, float(par == st.best),
                float(par == st.anchor), st.logratio(pm))
        if par not in st.ordered and par not in blocked and par not in seen:   # the reference itself, never ordered
            row = np.zeros(C_DIM)
            row[1], row[3] = 1.0, 1.0
            row[12:18] = prow
            seqs.append(par)
            rows.append(row)
            seen.add(par)
        pi = np.asarray([st.idx[c] for c in par])
        keep = LET != pi[POS]
        pos, let = POS[keep], LET[keep]
        mut = np.repeat(pi[None], len(pos), 0)
        mut[np.arange(len(pos)), pos] = let
        strs = ["".join(r) for r in letters[mut]]
        rej = np.asarray([x in st.rejected for x in strs])
        ordd = np.asarray([x in st.ordered for x in strs])
        nb_rej = np.bincount(pos[rej], minlength=4)
        nb_ord = int(ordd.sum())
        ok = np.asarray([not (o or x in blocked or x in seen) for x, o in zip(strs, ordd)])
        if not ok.any():
            continue
        pos, let, mut = pos[ok], let[ok], mut[ok]
        m = len(pos)
        block = np.zeros((m, C_DIM))
        block[:, 1] = 1.0
        block[:, 3] = (mut == anc).all(1)
        block[:, 8] = (bestz - st.z(pm)) / 10.0
        block[:, 12:18] = prow
        block[:, 18] = st.pl_n[pos, let] / 10.0
        block[:, 19] = st.pl_z[pos, let] / 10.0
        block[:, 20] = st.pl_n[pos, let] > 0
        block[:, 21] = st.pl_rej[pos, let] / 10.0
        block[:, 22] = nb_rej[pos] / 5.0
        block[:, 23] = nb_ord / 10.0
        block[:, 24] = (mut != anc).sum(1) / 4.0
        block[:, 25] = (mut != best).sum(1) / 4.0 if best is not None else 0.0
        new = [x for x, k in zip(strs, ok) if k]
        seqs.extend(new)
        seen.update(new)
        rows.extend(block)
    row = np.zeros(C_DIM)
    row[2] = 1.0
    seqs.append(None)
    rows.append(row)
    return seqs, np.asarray(rows, dtype=np.float32)


def random_candidate(st, rng, blocked):
    for _ in range(10000):
        s = "".join(st.alpha[i] for i in rng.integers(0, len(st.alpha), size=4))
        if s not in blocked:
            return s
    raise RuntimeError("no unordered candidate found")


# -- the network ------------------------------------------------------------------------------------------------------
def mlp(n_in):
    return nn.Sequential(nn.Linear(n_in, HIDDEN), nn.Tanh(), nn.Linear(HIDDEN, HIDDEN), nn.Tanh(), nn.Linear(HIDDEN, 1))


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.order, self.nominate, self.critic = mlp(D), mlp(D), mlp(G_DIM)


def logits(head, x, mask):
    """x: [N, C, D] padded candidate features, mask: [N, C] True where a candidate exists."""
    out = head(x).squeeze(-1)
    return out.masked_fill(~mask, -1e9)


class Policy(object):
    """Acts through the public observation; `record` collects (head, features, action, logp, value) for PPO."""

    def __init__(self, net, greedy=False):
        self.net, self.greedy = net, greedy

    def _pick(self, head, g, rows, rng):
        x = torch.from_numpy(np.hstack([np.repeat(np.asarray([g], np.float32), len(rows), 0), rows]))
        with torch.no_grad():
            lg = getattr(self.net, head)(x).squeeze(-1)
            lp = torch.log_softmax(lg, 0).numpy().astype(np.float64)
            v = float(self.net.critic(torch.tensor([g], dtype=torch.float32)).item())
        if self.greedy:
            i = int(np.argmax(lp))
        else:
            p = np.exp(lp - lp.max())
            i = int(rng.choice(len(p), p=p / p.sum()))
        return i, float(lp[i]), v, x.numpy()

    def choose(self, obs, rng, record):
        st, chosen, out = State(obs), [], []
        retests = 0
        for k in range(obs.n_slots):
            g = st.glob(obs.n_slots - k, retests)
            seqs, rows = candidate_set(st, obs.exclude, chosen)
            i, lp, v, x = self._pick("order", g, rows, rng)
            s = seqs[i] if seqs[i] is not None else random_candidate(st, rng, st.ordered | set(chosen) | set(obs.exclude))
            retests += s in st.ordered
            chosen.append(s)
            if record is not None:
                record.append(("order", x, i, lp, v, g))
        return chosen

    def nominate(self, obs, rng, record):
        st = State(obs)
        seqs = sorted(st.means)
        if not seqs:
            return None
        g = st.glob(0, 0)
        rows = np.asarray([st.measured_row(s) for s in seqs], dtype=np.float32)
        i, lp, v, x = self._pick("nominate", g, rows, rng)
        if record is not None:
            record.append(("nominate", x, i, lp, v, g))
        return seqs[i]


def public(obs):
    """The observation without its view: the view holds the oracle's pool of viable candidates."""
    return dataclasses.replace(obs, view=None)


def play(env, policy, rng, record=None):
    obs = env.observation
    while obs.phase in ("round", "replacement"):
        obs, _r, _d, _i = env.step(policy.choose(public(obs), rng, record))
    _o, _r, _d, info = env.nominate(policy.nominate(public(obs), rng, record))
    return info


# -- episodes ---------------------------------------------------------------------------------------------------------
class Landscapes(object):
    """Built landscapes, kept while in use: building an NK instance costs about 0.65 s and 18 MB."""

    def __init__(self, keep=16):
        self.keep, self.cache = keep, collections.OrderedDict()

    def get(self, name):
        if name not in self.cache:
            if len(self.cache) >= self.keep:
                self.cache.popitem(last=False)
            self.cache[name] = LS.instance(name)
        self.cache.move_to_end(name)
        return self.cache[name]


def episode_rng(*key):
    return np.random.default_rng([int(k) for k in key])


def train_batches(splits, seed):
    """Endless batches of (split, instance, campaign seed): each batch takes `instances_per_update` instances in a
    seeded order (split evenly across the training splits) and episodes_per_update / instances of each one's episodes,
    in split order. An instance's episodes are used once each before any repeats."""
    per = CONFIG["episodes_per_update"] // CONFIG["instances_per_update"]
    pools = {}
    for sp in splits:
        by = collections.OrderedDict()
        for inst, cs in SP.episodes(sp):
            by.setdefault(inst, []).append(cs)
        pools[sp] = by
    rng = np.random.default_rng([seed, 11])
    cursor = {sp: collections.Counter() for sp in splits}
    orders = {sp: [] for sp in splits}
    while True:
        batch = []
        for k in range(CONFIG["instances_per_update"]):
            sp = splits[k % len(splits)]
            if not orders[sp]:
                orders[sp] = list(rng.permutation(list(pools[sp])))
            inst = orders[sp].pop()
            seeds = pools[sp][inst]
            for _ in range(per):
                batch.append((sp, inst, seeds[cursor[sp][inst] % len(seeds)]))
                cursor[sp][inst] += 1
        yield batch


def validation_episodes(split):
    return SP.episodes(split, CONFIG["val_episodes_per_family"])


def evaluate(net, episodes, lands, key, greedy=False):
    """Mean pick and pick over the landscape's best on (instance, campaign seed) episodes, actions sampled with
    keyed generators so every policy evaluated with the same key meets the same random numbers."""
    pol, rows = Policy(net, greedy), []
    for n, (inst, cs) in enumerate(sorted(episodes, key=lambda e: e[0])):
        env = W.Wellocate(lands.get(inst), seed=cs)
        info = play(env, pol, episode_rng(key, cs))
        sc = info["scorecard"]
        rows.append(dict(instance=inst, campaign_seed=cs, pick=sc["pick"], norm=sc["pick"] / sc["global_best"],
                         share=sc["share_budget"], exploration=sc["exploration_shortfall"],
                         selection=sc["selection_shortfall"], distinct=sc["distinct"], lost=sc["lost_slots"],
                         fallback=info["nomination_fallback"]))
    return rows


# -- PPO --------------------------------------------------------------------------------------------------------------
def rollout(net, batch, lands, seed, update):
    """Play the batch; returns per-decision tuples with advantages and returns, and the batch's mean reward."""
    pol, decisions, rewards = Policy(net), [], []
    for j, (sp, inst, cs) in enumerate(batch):
        env = W.Wellocate(lands.get(inst), seed=cs)
        rec = []
        info = play(env, pol, episode_rng(seed, update, j), rec)
        R = info["nominee_true"] / env.global_best                   # the training signal only
        rewards.append(R)
        vals = [r[4] for r in rec] + [0.0]
        adv, last = [0.0] * len(rec), 0.0
        for t in reversed(range(len(rec))):
            nxt = R if t == len(rec) - 1 else vals[t + 1]
            delta = nxt - vals[t]
            last = delta + CONFIG["gae_lambda"] * last
            adv[t] = last
        for t, r in enumerate(rec):
            decisions.append(dict(head=r[0], x=r[1], a=r[2], logp=r[3], g=r[5], adv=adv[t], ret=adv[t] + vals[t]))
    return decisions, float(np.mean(rewards))


def ppo_update(net, opt, decisions, gen):
    adv = np.asarray([d["adv"] for d in decisions])
    adv = (adv - adv.mean()) / (adv.std() + 1e-8)
    for d, a in zip(decisions, adv):
        d["nadv"] = a
    stats = collections.defaultdict(list)
    for _ in range(CONFIG["ppo_epochs"]):
        order = gen.permutation(len(decisions))
        for s in range(0, len(order), CONFIG["minibatch"]):
            mb = [decisions[i] for i in order[s:s + CONFIG["minibatch"]]]
            loss = 0.0
            for head in ("order", "nominate"):
                part = [d for d in mb if d["head"] == head]
                if not part:
                    continue
                C = max(len(d["x"]) for d in part)
                x = np.zeros((len(part), C, D), np.float32)
                mask = np.zeros((len(part), C), bool)
                for i, d in enumerate(part):
                    x[i, :len(d["x"])] = d["x"]
                    mask[i, :len(d["x"])] = True
                lg = logits(getattr(net, head), torch.from_numpy(x), torch.from_numpy(mask))
                logp_all = torch.log_softmax(lg, 1)
                a = torch.tensor([d["a"] for d in part])
                logp = logp_all.gather(1, a[:, None]).squeeze(1)
                ratio = torch.exp(logp - torch.tensor([d["logp"] for d in part], dtype=torch.float32))
                na = torch.tensor([d["nadv"] for d in part], dtype=torch.float32)
                pg = -torch.min(ratio * na, torch.clamp(ratio, 1 - CONFIG["clip"], 1 + CONFIG["clip"]) * na).mean()
                p_all = torch.exp(logp_all).masked_fill(~torch.from_numpy(mask), 0.0)
                ent = -(p_all * logp_all.masked_fill(~torch.from_numpy(mask), 0.0)).sum(1).mean()
                loss = loss + pg * len(part) / len(mb) - CONFIG["entropy_coef"] * ent * len(part) / len(mb)
                stats["%s_entropy" % head].append(float(ent.detach()))
                stats["%s_clipfrac" % head].append(float(((ratio - 1).abs() > CONFIG["clip"]).float().mean()))
            g = torch.tensor(np.asarray([d["g"] for d in mb], np.float32))
            ret = torch.tensor([d["ret"] for d in mb], dtype=torch.float32)
            vloss = ((net.critic(g).squeeze(-1) - ret) ** 2).mean()
            loss = loss + CONFIG["value_coef"] * vloss
            stats["value_loss"].append(float(vloss.detach()))
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), CONFIG["max_grad_norm"])
            opt.step()
    return {k: float(np.mean(v)) for k, v in stats.items()}


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def train(run, seed, updates=None, out=OUT):
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    net = Net()
    d = os.path.join(out, "%s_s%d" % (run, seed))
    os.makedirs(d, exist_ok=True)
    torch.save(net.state_dict(), os.path.join(d, "init.pt"))
    opt = torch.optim.Adam(net.parameters(), lr=CONFIG["lr"])
    lands, vlands = Landscapes(16), Landscapes(64)
    val = {sp: validation_episodes(sp) for sp in RUNS[run]["validation"]}
    batches = train_batches(RUNS[run]["train"], seed)
    gen = np.random.default_rng([seed, 7])
    log = open(os.path.join(d, "log.jsonl"), "a")
    t0, best, episodes = time.time(), None, 0
    updates = CONFIG["updates"] if updates is None else updates
    for u in range(updates + 1):
        if u % CONFIG["validate_every"] == 0 or u == updates:
            per = {sp: evaluate(net, eps, vlands, key=900 + i) for i, (sp, eps) in enumerate(sorted(val.items()))}
            score = float(np.mean([np.mean([r["norm"] for r in rows]) for rows in per.values()]))
            path = os.path.join(d, "ckpt_%05d.pt" % u)
            torch.save(net.state_dict(), path)
            entry = dict(kind="validation", update=u, episodes=episodes, wall_s=time.time() - t0, score=score,
                         **{"%s_pick" % sp: float(np.mean([r["pick"] for r in rows])) for sp, rows in per.items()},
                         **{"%s_share" % sp: float(np.mean([r["share"] for r in rows])) for sp, rows in per.items()})
            if best is None or score > best["score"]:
                best = dict(update=u, score=score, path=path)
            entry["best_update"] = best["update"]
            log.write(json.dumps(entry) + "\n")
            log.flush()
            print(json.dumps(entry), flush=True)
        if u == updates or time.time() - t0 > CONFIG["wall_limit_h"] * 3600:
            break
        batch = next(batches)
        decisions, mean_r = rollout(net, batch, lands, seed, u)
        stats = ppo_update(net, opt, decisions, gen)
        episodes += len(batch)
        log.write(json.dumps(dict(kind="update", update=u, episodes=episodes, reward=mean_r, decisions=len(decisions),
                                  wall_s=time.time() - t0, **stats)) + "\n")
    summary = dict(run=run, seed=seed, best_update=best["update"], best_score=best["score"], best_path=best["path"],
                   best_sha256=sha256(best["path"]), init_sha256=sha256(os.path.join(d, "init.pt")),
                   updates_done=u, episodes=episodes, wall_s=time.time() - t0, config=CONFIG)
    log.close()
    with open(os.path.join(d, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    return summary


# -- the test (once per run, after all three seeds have trained) -------------------------------------------------------
TEST_KEY = {"nk:test": 5001, "gb1:test": 5002, "phoq:test": 5003}
VAL_OF = {"nk:test": "nk:validation", "gb1:test": "gb1:validation", "phoq:test": "phoq:validation"}
SEEDS = (0, 1, 2)
REPS = 10000


def scripted(policy, episodes, lands):
    """wellocate.scorecard.run_episode on cached landscapes: the shrinkage rule nominates; None marks a collapse."""
    rows = []
    for inst, cs in episodes:
        sc = SC.run_episode(policy, lands.get(inst), cs)
        rows.append(None if sc is None else dict(
            instance=inst, campaign_seed=cs, pick=sc["pick"], norm=sc["pick"] / sc["global_best"],
            share=sc["share_budget"], exploration=sc["exploration_shortfall"], selection=sc["selection_shortfall"],
            distinct=sc["distinct"], lost=sc["lost_slots"]))
    return rows


def load_net(path):
    net = Net()
    net.load_state_dict(torch.load(path))
    return net


def boot_index(key, n, reps=None):
    return np.random.default_rng([4111, key]).integers(0, n, size=(REPS if reps is None else reps, n))


def quantile(sorted_draws, f):
    """The f-quantile of sorted bootstrap draws, indexed by their own count."""
    return float(sorted_draws[min(len(sorted_draws) - 1, int(f * len(sorted_draws)))])


def beats(trained, other, key):
    """The pre-registered comparison: per seed, the paired mean difference in pick over the episodes where neither policy
    collapsed; the mean over seeds with a 95% (and a Bonferroni 99.375%) interval from one keyed resample of
    episodes shared by all seeds."""
    keep = [j for j in range(len(other[0])) if all(o[j] is not None for o in other)]
    diffs = np.asarray([[t[j]["pick"] - o[j]["pick"] for j in keep] for t, o in zip(trained, other)])
    idx = boot_index(key, len(keep))
    draws = np.sort(diffs[:, idx].mean(axis=2).mean(axis=0))
    q = lambda f: quantile(draws, f)
    per_seed = [float(d.mean()) for d in diffs]
    mean = float(diffs.mean())
    ci, ci_bonf = [q(0.025), q(0.975)], [q(0.003125), q(0.996875)]
    return dict(mean=mean, ci=ci, ci_bonferroni8=ci_bonf, per_seed=per_seed, episodes=len(keep),
                dropped_collapsed=len(other[0]) - len(keep),
                holds=bool(ci[0] > 0 and all(x > 0 for x in per_seed)),
                holds_bonferroni8=bool(ci_bonf[0] > 0 and all(x > 0 for x in per_seed)))


def table(per_seed_rows, key):
    """Pick, re-testing share, exploration and selection loss: per seed with a 95% interval over episodes, and over
    seeds by a two-level bootstrap (seeds, then episodes)."""
    out = {}
    cols = ("pick", "norm", "share", "exploration", "selection", "distinct", "lost")
    rng = np.random.default_rng([4112, key])
    for c in cols:
        mats = [np.asarray([r[c] for r in rows if r is not None]) for rows in per_seed_rows]
        seeds = []
        for m in mats:
            d = np.sort(m[boot_index(key, len(m), 2000)].mean(axis=1))
            seeds.append(dict(mean=float(m.mean()), ci=[quantile(d, 0.025), quantile(d, 0.975)]))
        two = []
        for _ in range(2000):
            pick = rng.integers(0, len(mats), size=len(mats))
            two.append(np.mean([mats[i][rng.integers(0, len(mats[i]), size=len(mats[i]))].mean() for i in pick]))
        two = np.sort(two)
        out[c] = dict(mean=float(np.mean([m.mean() for m in mats])), ci_two_level=[quantile(two, 0.025),
                                                                          quantile(two, 0.975)],
                      per_seed=seeds)
    return out


def test(run, out=OUT, seeds=SEEDS, path=None, splits=None):
    """The test of one run: every seed's selected checkpoint and initialisation, and the scripted policies, on all
    1,500 episodes of each test split. With the defaults it writes results/b11_test_<run>.json; other seeds, splits or
    an output path serve the post-hoc runs and never write that file."""
    torch.set_num_threads(1)
    seeds, splits = tuple(seeds), list(splits or RUNS[run]["test"])
    path = path or os.path.join(ROOT, "results", "b11_test_%s.json" % run)
    if (seeds != SEEDS or splits != RUNS[run]["test"] or out != OUT) and \
            os.path.abspath(path) == os.path.abspath(os.path.join(ROOT, "results", "b11_test_%s.json" % run)):
        raise ValueError("a non-registered test must not write the registered result file")
    sums = [json.load(open(os.path.join(out, "%s_s%d" % (run, sd), "summary.json"))) for sd in seeds]
    for sm in sums:
        if sha256(sm["best_path"]) != sm["best_sha256"]:
            raise RuntimeError("checkpoint %s changed since training" % sm["best_path"])
    nets = {"trained": [load_net(sm["best_path"]) for sm in sums],
            "initialisation": [load_net(os.path.join(os.path.dirname(sm["best_path"]), "init.pt")) for sm in sums]}
    # Checkpoint paths are recorded relative to the repo root.
    res = dict(run=run, preregistration="spec/B11_PREREGISTRATION.md", splits={},
               checkpoints=[dict(sm, best_path=os.path.relpath(sm["best_path"], ROOT)) for sm in sums])
    for split in splits:
        t0 = time.time()
        eps = sorted(SP.episodes(split), key=lambda e: e[0])
        lands = Landscapes(64)
        rows = {name: [evaluate(n, eps, lands, key=TEST_KEY[split]) for n in ns] for name, ns in nets.items()}
        val = validation_episodes(VAL_OF[split])
        chosen, every_k = {}, {}
        for rule, make in (("guessing", B.guessing), ("informed", B.informed)):
            vk = {k: np.mean([r["pick"] for r in scripted(make(k), val, lands) if r is not None]) for k in range(5)}
            chosen[rule] = max(sorted(vk), key=lambda k: vk[k])
            for k in range(5):
                every_k["%s k=%d" % (rule, k)] = scripted(make(k), eps, lands)
        comps = {"random": scripted(B.random(), eps, lands),
                 "guessing": every_k["guessing k=%d" % chosen["guessing"]],
                 "informed": every_k["informed k=%d" % chosen["informed"]],
                 "model-guided": scripted(B.model_guided(1, True), eps, lands)}
        key = TEST_KEY[split]
        rep = dict(episodes=len(eps), validation_k=chosen,
                   comparisons={"vs initialisation": beats(rows["trained"], rows["initialisation"], key),
                                "vs random": beats(rows["trained"], [comps["random"]] * len(seeds), key + 10)},
                   versus_scripted={n: beats(rows["trained"], [c] * len(seeds), key + 20 + i)
                                    for i, (n, c) in enumerate(sorted(comps.items()))},
                   table={n: table(r, key) for n, r in rows.items()},
                   scripted={n: table([c], key) for n, c in sorted(list(comps.items()) + list(every_k.items()))},
                   wall_s=time.time() - t0)
        best = max(rep["scripted"], key=lambda n: rep["scripted"][n]["pick"]["mean"])
        rep["best_scripted_on_test"] = dict(policy=best, share=rep["scripted"][best]["share"]["mean"],
                                            pick=rep["scripted"][best]["pick"]["mean"])
        rep["per_episode"] = dict(trained=rows["trained"], initialisation=rows["initialisation"], **comps)
        res["splits"][split] = rep
        print(json.dumps(dict(split=split, **rep["comparisons"])), flush=True)
    res["curves"] = {sd: [json.loads(l) for l in open(os.path.join(out, "%s_s%d" % (run, sd), "log.jsonl"))
                          if '"validation"' in l] for sd in seeds}
    with open(path, "w") as f:
        json.dump(res, f, indent=1)
    return path


def time_it(n_updates=3):
    """Throughput only: rollouts and PPO updates of an untrained network on grid train episodes, no validation."""
    torch.manual_seed(0)
    torch.set_num_threads(1)
    net, lands = Net(), Landscapes(16)
    opt = torch.optim.Adam(net.parameters(), lr=CONFIG["lr"])
    batches, gen = train_batches(["nk:train"], 0), np.random.default_rng(0)
    for u in range(n_updates):
        batch = next(batches)
        t = time.time()
        for _sp, inst, _cs in batch:
            lands.get(inst)
        tb = time.time() - t
        t = time.time()
        decisions, r = rollout(net, batch, lands, 0, u)
        tr = time.time() - t
        t = time.time()
        ppo_update(net, opt, decisions, gen)
        print("update %d: build %.1f s, rollout %.1f s (%d decisions, %.0f candidates per order), update %.1f s" % (
            u, tb, tr, len(decisions), np.mean([len(d["x"]) for d in decisions if d["head"] == "order"]),
            time.time() - t), flush=True)


def apply_sets(sets):
    """CONFIG overrides for a post-hoc run, typed as the default value; an unknown key is refused."""
    for kv in sets:
        k, v = kv.split("=", 1)
        if k not in CONFIG:
            raise ValueError("unknown CONFIG key %r" % k)
        CONFIG[k] = type(CONFIG[k])(v)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "test", "time"])
    ap.add_argument("--run", choices=sorted(RUNS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--updates", type=int, default=None)
    # post-hoc runs only; the defaults are the pre-registered settings
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--set", nargs="*", default=[], help="CONFIG overrides, key=value")
    ap.add_argument("--seeds", default=None, help="test: comma-separated seeds")
    ap.add_argument("--splits", default=None, help="test: comma-separated splits")
    ap.add_argument("--path", default=None, help="test: output file")
    a = ap.parse_args(argv)
    apply_sets(a.set)
    if a.cmd == "time":
        time_it()
    elif a.cmd == "train":
        print(json.dumps(train(a.run, a.seed, a.updates, out=a.out)))
    else:
        print(test(a.run, out=a.out, seeds=tuple(int(x) for x in a.seeds.split(",")) if a.seeds else SEEDS,
                   path=a.path, splits=a.splits.split(",") if a.splits else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
