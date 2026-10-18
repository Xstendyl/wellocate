#!/usr/bin/env python3
"""Single-prompt probes of the candidate models' reasoning settings. No campaign is run.

Each probe sends the grid's Blind round-1 prompt once, at temperature 0 and a high output budget (16,000 tokens),
with one reasoning setting, as a raw request so the answer text and the reasoning are seen apart. It records the
HTTP outcome, finish reason, prompt, completion and reasoning tokens, the cost OpenRouter reports, whether the
answer text arrived, and whether it parses as 4 candidates under the harness's own parser. The key is read by
repdef.llm._key and never printed or written.

Usage: set -a; . ./.env; set +a; python3 scripts/probe_0an7.py      (writes results/probe_0an7.json)
"""
import json, os, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import llm, llm_policy, prompts                                     # noqa: E402

OUT = os.path.join(ROOT, "results", "probe_0an7.json")
PROBES = [
    ("openai/gpt-6.1-sol", "default (no reasoning parameter)", None, True),
    ("openai/gpt-6.1-sol", "default, temperature not sent", None, False),
    ("google/gemini-3.1-pro-preview", "default (no reasoning parameter)", None, True),
    ("google/gemini-3.1-pro-preview", "reasoning enabled false", {"enabled": False}, True),
    ("google/gemini-3.1-pro-preview", "effort minimal", {"effort": "minimal"}, True),
    ("google/gemini-3.1-pro-preview", "effort low", {"effort": "low"}, True),
    ("google/gemini-3.1-pro-preview", "reasoning budget 128 tokens", {"max_tokens": 128}, True),
]

# With --extra: can GPT-6.1 Sol turn reasoning off, and does Gemini 3.1 Pro's lowest setting stay small and always
# answer on a later-round prompt with a history (three repeats)?
EXTRA = [
    ("openai/gpt-6.1-sol", "reasoning enabled false", {"enabled": False}, True, "round1"),
    ("openai/gpt-6.1-sol", "effort none", {"effort": "none"}, True, "round1"),
    ("openai/gpt-6.1-sol", "effort minimal", {"effort": "minimal"}, True, "round1"),
    ("google/gemini-3.1-pro-preview", "effort minimal, round 8 with history, repeat 1", {"effort": "minimal"}, True, "round8"),
    ("google/gemini-3.1-pro-preview", "effort minimal, round 8 with history, repeat 2", {"effort": "minimal"}, True, "round8"),
    ("google/gemini-3.1-pro-preview", "effort minimal, round 8 with history, repeat 3", {"effort": "minimal"}, True, "round8"),
]


def prompt_round8():
    """A round-8 prompt with 28 readings in its history, built by the harness's own prompt code."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import grid
    fit, pool = grid.landscape()
    near = [s for s in sorted(pool) if sum(a != b for a, b in zip(s, "GDIF")) <= 2][:10]
    rows, rnd = [], 1
    for i in range(28):
        rnd = 1 + i // 4
        s = near[i % len(near)]
        rows.append((rnd, s, "ok", round(fit[s] * (1 + 0.03 * ((i % 5) - 2)), 3)))
    return prompts.build("blind", rows, 8, 15, 4, 32, 0.0, parent="GDIF", example="ADIF", landscape="abstract",
                         noise_model="multiplicative", cv=0.073, noise_floor=0.00351, anchor_reading="6.87")


def prompt():
    return prompts.build("blind", [], 1, 15, 4, 60, 0.0, parent="GDIF", example="ADIF", landscape="abstract",
                         noise_model="multiplicative", cv=0.073, noise_floor=0.00351, anchor_reading="6.87")


def probe(model, reasoning, temperature, text):
    body = {"model": model, "messages": [{"role": "user", "content": text}], "max_tokens": 16000,
            "usage": {"include": True}}
    if temperature:
        body["temperature"] = 0.0
    if reasoning is not None:
        body["reasoning"] = reasoning
    req = urllib.request.Request(llm.URL, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + llm._key(), "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            p = json.load(r)
    except urllib.error.HTTPError as e:
        return dict(http=e.code, error=e.read().decode(errors="replace")[:400], seconds=time.time() - t0)
    if "error" in p:
        return dict(http=200, error=json.dumps(p["error"])[:400], seconds=time.time() - t0)
    ch = (p.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    u = p.get("usage") or {}
    content = msg.get("content") or ""
    got, status, _notes = llm_policy.parse(content, 4, alphabet="ABCDEFGHIJKLMNOPQRST")
    return dict(http=200, model_returned=p.get("model"), provider=p.get("provider"), finish_reason=ch.get("finish_reason"),
                prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
                reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                cost=u.get("cost"), answer_arrived=bool(content.strip()), answer_chars=len(content),
                reasoning_text_chars=len(msg.get("reasoning") or ""), parsed=[g[0] for g in got], parse_status=status,
                answer=content[:300], seconds=time.time() - t0)


def main():
    extra = "--extra" in sys.argv
    texts = {"round1": prompt(), "round8": prompt_round8()}
    text = texts["round1"]
    out = []
    plan = EXTRA if extra else [p + ("round1",) for p in PROBES]
    for model, label, reasoning, temperature, which in plan:
        r = probe(model, reasoning, temperature, texts[which])
        r.update(model=model, setting=label, reasoning_param=reasoning, temperature_sent=temperature)
        out.append(r)
        print("%-30s %-34s %s" % (model, label, {k: r.get(k) for k in ("http", "error", "finish_reason", "prompt_tokens",
                                                                        "completion_tokens", "reasoning_tokens", "cost",
                                                                        "answer_arrived", "parse_status")}), flush=True)
    path = OUT.replace(".json", "_extra.json") if extra else OUT
    json.dump(dict(prompt_chars={k: len(v) for k, v in texts.items()}, probes=out,
                   total_cost=sum(r.get("cost") or 0 for r in out)), open(path, "w"), indent=1)
    print("total cost $%.4f; wrote %s" % (sum(r.get("cost") or 0 for r in out), os.path.relpath(path, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
