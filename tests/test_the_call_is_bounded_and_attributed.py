"""Tests that an LLM call is bounded in total time and records the provider that answered it.

A socket timeout bounds each read, not the whole call, so a total deadline is enforced across attempts. An
open-weight model can be served by different providers, so the serving provider is recorded. With the new
options unused, the outgoing request body is byte-identical to the earlier one.
"""
import io, json, os, sys, time, unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import llm  # noqa: E402

PROMPT = "pick four"
MODEL = "vendor/model-x"
SENT = []


class FakeResponse(object):
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def ok_payload(provider="SomeProvider"):
    return {"model": MODEL, "provider": provider,
            "choices": [{"message": {"content": "GDIF | a\nGDIA | b"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 22, "cost": 0.001,
                      "completion_tokens_details": {"reasoning_tokens": 7}}}


class BoundedAndAttributed(unittest.TestCase):

    def setUp(self):
        SENT[:] = []
        self._real_open = urllib.request.urlopen
        self._real_key = llm._key
        llm._key = lambda _env=None: "test-not-a-real-key"
        self.addCleanup(lambda: setattr(urllib.request, "urlopen", self._real_open))
        self.addCleanup(lambda: setattr(llm, "_key", self._real_key))

    def serve(self, payload=None, delay=0.0, raise_exc=None):
        def fake(req, timeout=None):
            SENT.append(dict(body=req.data, timeout=timeout))
            if delay:
                time.sleep(delay)
            if raise_exc:
                raise raise_exc
            return FakeResponse(payload if payload is not None else ok_payload())
        urllib.request.urlopen = fake

    # ---------- the request body is unchanged ----------

    def test_the_request_body_is_byte_identical_when_the_new_options_are_unused(self):
        self.serve()
        llm.complete(PROMPT, MODEL, max_tokens=6000, temperature=0.0, env_file=None)
        # The body as built before these options existed, in the same insertion order.
        expected = json.dumps({"model": MODEL,
                               "messages": [{"role": "user", "content": PROMPT}],
                               "max_tokens": 6000, "temperature": 0.0,
                               "usage": {"include": True}}).encode()
        self.assertEqual(SENT[0]["body"], expected)
        self.assertNotIn(b"provider", SENT[0]["body"])
        self.assertNotIn(b"deadline", SENT[0]["body"])

    def test_reasoning_effort_still_lands_in_the_same_place(self):
        self.serve()
        llm.complete(PROMPT, MODEL, max_tokens=6000, env_file=None, reasoning_effort="medium")
        body = json.loads(SENT[0]["body"])
        self.assertEqual(body["reasoning"], {"effort": "medium"})
        self.assertNotIn("provider", body)

    def test_pinning_a_provider_sends_it_and_forbids_fallbacks(self):
        self.serve()
        llm.complete(PROMPT, MODEL, env_file=None, provider_order=["Fireworks"])
        body = json.loads(SENT[0]["body"])
        self.assertEqual(body["provider"], {"order": ["Fireworks"], "allow_fallbacks": False})

    # ---------- the total deadline ----------

    def test_the_total_deadline_stops_a_stall_that_the_socket_timeout_cannot(self):
        """A total deadline stops a call whose attempts each stay under the socket timeout."""
        # retries=8 keeps this test short if the deadline is removed, since llm.complete backs off
        # 1.5*(attempt+1) seconds between attempts.
        self.serve(delay=0.35, raise_exc=urllib.error.URLError("stalled"))
        t = time.time()
        c = llm.complete(PROMPT, MODEL, env_file=None, timeout=5, retries=8, deadline_s=1)
        dt = time.time() - t
        self.assertFalse(c.ok)
        self.assertIn("total deadline", c.error)
        self.assertLess(dt, 8, "the deadline did not bound the call")
        self.assertLess(len(SENT), 8, "it used every retry, so the deadline did nothing")

    def test_an_attempt_can_never_be_given_longer_than_the_deadline_leaves(self):
        """No attempt is given a socket timeout longer than the time left before the deadline."""
        self.serve(delay=0.2, raise_exc=urllib.error.URLError("stalled"))
        llm.complete(PROMPT, MODEL, env_file=None, timeout=600, retries=3, deadline_s=2)
        for rec in SENT:
            self.assertLessEqual(rec["timeout"], 2)
            self.assertGreaterEqual(rec["timeout"], 1)

    def test_the_deadline_never_shortens_a_healthy_call(self):
        self.serve()
        c = llm.complete(PROMPT, MODEL, env_file=None, timeout=180, retries=3)
        self.assertTrue(c.ok)
        self.assertEqual(SENT[0]["timeout"], 180)

    def test_deadline_zero_restores_the_old_unbounded_behaviour(self):
        """deadline_s=0 turns the total deadline off."""
        self.serve()
        llm.complete(PROMPT, MODEL, env_file=None, timeout=77, retries=1, deadline_s=0)
        self.assertEqual(SENT[0]["timeout"], 77)

    # ---------- attribution ----------

    def test_the_serving_provider_is_recorded(self):
        self.serve(ok_payload(provider="Together"))
        c = llm.complete(PROMPT, MODEL, env_file=None)
        self.assertEqual(c.provider, "Together")

    def test_a_missing_provider_field_is_empty_and_not_a_crash(self):
        p = ok_payload()
        del p["provider"]
        self.serve(p)
        c = llm.complete(PROMPT, MODEL, env_file=None)
        self.assertEqual(c.provider, "")
        self.assertTrue(c.ok)

    def test_the_provider_is_recorded_even_when_the_call_returned_empty_text(self):
        """The provider is recorded on the empty-content return path too."""
        p = ok_payload(provider="Hyperbolic")
        p["choices"][0]["message"]["content"] = ""
        self.serve(p)
        c = llm.complete(PROMPT, MODEL, env_file=None)
        self.assertFalse(c.ok)
        self.assertEqual(c.provider, "Hyperbolic")


if __name__ == "__main__":
    unittest.main()
