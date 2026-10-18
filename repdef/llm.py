"""OpenRouter chat-completion client.

The API key is read at runtime from the environment or an env file and is only used for the
Authorization header. It is never logged, stored, returned or included in an error message.
"""

import json
import os
import time
import urllib.error
import urllib.request

URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_ENV_FILE = ".env"


class LLMError(Exception):
    """Raised with a message that is guaranteed to contain no credential material."""


def _key(env_file=None):
    k = os.environ.get("OPENROUTER_API_KEY")
    if k:
        return k.strip()
    path = env_file or DEFAULT_ENV_FILE
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENROUTER_API_KEY="):
                    v = line.split("=", 1)[1].strip().strip("'\"")
                    if v:
                        return v
    except OSError:
        pass
    raise LLMError("no OPENROUTER_API_KEY in the environment or in %s" % path)


class Call(object):
    """One model call and everything about it except the credential."""

    # reasoning_tokens and finish_reason show when a reasoning model spent its budget without answering.
    # provider records which upstream provider served the call; it is read from the response only.
    # reasoning_text is kept separate from the answer; visible_tokens = completion - reasoning tokens.
    __slots__ = ("text", "model", "prompt_tokens", "completion_tokens", "reasoning_tokens",
                 "finish_reason", "cost_usd", "latency_ms", "error", "raw", "provider",
                 "reasoning_text", "visible_tokens")

    def __init__(self, text="", model="", prompt_tokens=0, completion_tokens=0,
                 reasoning_tokens=0, finish_reason="",
                 cost_usd=0.0, latency_ms=0, error=None, raw=None, provider="", reasoning_text=""):
        self.text = text
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.reasoning_tokens = reasoning_tokens
        self.finish_reason = finish_reason
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.error = error
        self.raw = raw
        self.provider = provider
        self.reasoning_text = reasoning_text
        self.visible_tokens = int(completion_tokens or 0) - int(reasoning_tokens or 0)

    @property
    def ok(self):
        return self.error is None


def complete(prompt, model, max_tokens=3000, temperature=0.0, env_file=None,
             timeout=180, retries=3, reasoning_effort=None, provider_order=None,
             deadline_s=900):
    """max_tokens defaults high because reasoning models spend tokens before emitting text.

    A reply with spent tokens and empty content is reported as an error."""
    """One completion. Returns a Call; transport failures come back as Call.error, never raise.

    temperature 0 by default, to hold one thing fixed across cells. It does NOT make the provider
    deterministic: pairwise agreement between two calls of a byte-identical prompt is 0.265
    (results/step6_temperature_zero_determinism.json). Sampling noise is present and lands in the
    between-campaign variance, which the grid's analysis already measures, so it is a limitation to
    state and not a confound to remove."""
    payload_in = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "usage": {"include": True},
    }
    if reasoning_effort:
        payload_in["reasoning"] = {"effort": reasoning_effort}
    # Optional provider pinning, off by default. When None the provider field is not sent.
    if provider_order:
        payload_in["provider"] = {"order": list(provider_order), "allow_fallbacks": False}
    body = json.dumps(payload_in).encode()
    try:
        auth = _key(env_file)
    except LLMError as e:
        return Call(model=model, error=str(e))

    last = None
    # Total deadline across attempts, since urlopen's timeout bounds each socket read, not the call.
    # It is set well above normal call times so it only fires on a stalled response.
    started = time.time()
    for attempt in range(retries):
        t0 = time.time()
        if deadline_s and (t0 - started) >= deadline_s:
            return Call(model=model, error="total deadline %ds exceeded after %d attempt(s); last "
                                           "error: %s" % (deadline_s, attempt, last))
        # Cap the per-attempt socket timeout at the time left before the deadline.
        attempt_timeout = timeout if not deadline_s else max(1, min(timeout,
                                                                   int(deadline_s - (t0 - started))))
        req = urllib.request.Request(URL, data=body, headers={
            "Authorization": "Bearer " + auth,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Xstendyl/wellocate",
            "X-Title": "repdef",
        })
        try:
            with urllib.request.urlopen(req, timeout=attempt_timeout) as r:
                payload = json.loads(r.read().decode())
            ms = int(1000 * (time.time() - t0))
            ch = (payload.get("choices") or [{}])[0]
            msg = ch.get("message") or {}
            text = msg.get("content") or ""
            reasoning = msg.get("reasoning") or ""
            u = payload.get("usage") or {}
            # HTTP 200 with finish_reason "error" is an incomplete call; setting error makes Call.ok False.
            if str(ch.get("finish_reason") or "") == "error":
                return Call(model=payload.get("model") or model,
                            prompt_tokens=int(u.get("prompt_tokens") or 0),
                            completion_tokens=int(u.get("completion_tokens") or 0),
                            reasoning_tokens=int((u.get("completion_tokens_details") or {}).get(
                                "reasoning_tokens") or 0),
                            finish_reason="error",
                            cost_usd=float(u.get("cost") or 0.0),
                            provider=str(payload.get("provider") or ""),
                            latency_ms=ms, raw=payload,
                            error="provider reported finish_reason=error with HTTP 200 after %d "
                                  "completion tokens; the call did not complete"
                                  % int(u.get("completion_tokens") or 0))
            if not text.strip():
                # An empty answer is reported as an error. Reasoning text never stands in for the answer.
                spent_ct = int(u.get("completion_tokens") or 0)
                return Call(model=payload.get("model") or model,
                            prompt_tokens=int(u.get("prompt_tokens") or 0),
                            completion_tokens=spent_ct,
                            reasoning_tokens=int((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0),
                            finish_reason=str(ch.get("finish_reason") or ""),
                            cost_usd=float(u.get("cost") or 0.0),
                            latency_ms=int(1000 * (time.time() - t0)), raw=payload,
                            provider=str(payload.get("provider") or ""), reasoning_text=reasoning,
                            error="empty content after %d completion tokens%s "
                                  "(finish_reason=%s): raise max_tokens or lower reasoning "
                                  "effort" % (spent_ct, ", reasoning text present" if reasoning.strip() else "",
                                              ch.get("finish_reason")))
            return Call(text=text, model=payload.get("model") or model,
                        reasoning_tokens=int((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0),
                        finish_reason=str(ch.get("finish_reason") or ""),
                        prompt_tokens=int(u.get("prompt_tokens") or 0),
                        completion_tokens=int(u.get("completion_tokens") or 0),
                        cost_usd=float(u.get("cost") or 0.0),
                        provider=str(payload.get("provider") or ""),
                        latency_ms=ms, raw=payload, reasoning_text=reasoning)
        except urllib.error.HTTPError as e:
            # Read the body for the reason, but never echo a header.
            try:
                detail = e.read().decode()[:300]
            except Exception:                        # noqa: BLE001
                detail = ""
            last = "HTTP %s: %s" % (e.code, detail)
            if e.code in (400, 401, 403, 404):       # not transient, do not burn retries
                break
        except Exception as e:                       # noqa: BLE001
            last = "%s: %s" % (type(e).__name__, e)
        time.sleep(1.5 * (attempt + 1))
    return Call(model=model, error=last or "unknown transport failure")
