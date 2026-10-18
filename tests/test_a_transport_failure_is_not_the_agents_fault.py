"""Tests that a call that never happened is not charged to the agent and that its campaign is not written.

A reply that cannot be parsed is a fact about the agent and still costs the round. No reply at all (an HTTP
error, a provider error, exhausted credits) is a transport failure: it raises a named exception and the
campaign is not written.
"""
import json, os, sys, unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import llm, llm_policy as LP, view as V  # noqa: E402


def a_view(rnd=1, used=0):
    obs = tuple(V.Observation(1, "AAAA", "ok", 1.0) for _ in range(used))
    return V.CampaignView(obs, {"AAAA"}, rnd, 15, 4, used, 60, ("AAAA",),
                          campaign_seed=0, screen=None)


def policy():
    return LP.LLMPolicy("vendor/model-x", "instructed", 1.0, landscape="abstract")


class TransportIsNotBehaviour(unittest.TestCase):

    def setUp(self):
        self._real = llm.complete
        self.addCleanup(lambda: setattr(llm, "complete", self._real))

    def serve(self, call):
        llm.complete = lambda *a, **k: call

    # ---- the failure must be a named state, not an empty list ----------------------------------

    def test_a_transport_error_raises_instead_of_looking_like_a_forfeited_round(self):
        self.serve(llm.Call(model="vendor/model-x", error="URLError: connection reset"))
        with self.assertRaises(LP.TransportFailure) as cm:
            list(policy().propose(a_view(), 4))
        self.assertIn("abandoned unwritten", str(cm.exception))
        self.assertNotIsInstance(cm.exception, LP.CreditsExhausted)

    def test_a_402_raises_the_subclass_that_halts_the_whole_run(self):
        """Every further call fails the same way, so one campaign's failure is the run's failure."""
        self.serve(llm.Call(model="vendor/model-x",
                            error='HTTP 402: {"error":{"message":"in_flight_budget"}}'))
        with self.assertRaises(LP.CreditsExhausted):
            list(policy().propose(a_view(), 4))

    def test_the_nomination_call_is_covered_too(self):
        """A transport failure on the nomination call also raises, so a campaign whose outcome was never measured is not written."""
        self.serve(llm.Call(model="vendor/model-x", error="HTTP 402: no credits"))
        with self.assertRaises(LP.CreditsExhausted):
            policy().nominate(a_view(1, 4))

    # ---- and the distinction must be preserved ------------------------------------------------

    def test_a_parse_failure_is_still_charged_to_the_agent(self):
        """A reply that cannot be parsed is still charged to the agent as a lost round."""
        self.serve(llm.Call(text="I would rather not answer that.", model="vendor/model-x"))
        got = list(policy().propose(a_view(), 4))
        self.assertEqual(got, [], "an unparseable reply must still yield no proposals")

    def test_a_good_reply_still_works(self):
        self.serve(llm.Call(text="ABCD | one\nABCE | two\nABCF | three\nABCG | four",
                            model="vendor/model-x"))
        got = list(policy().propose(a_view(), 4))
        self.assertEqual(len(got), 4)

    # ---- the two states are distinguishable by type -------------------------------------------

    def test_credits_exhausted_is_catchable_as_either(self):
        """CreditsExhausted is a subclass of TransportFailure, so it can be caught as either."""
        self.assertTrue(issubclass(LP.CreditsExhausted, LP.TransportFailure))
        self.assertTrue(issubclass(LP.TransportFailure, RuntimeError))

    def test_the_error_text_names_the_model_and_the_call_kind(self):
        """The error text names the model and the call kind."""
        self.serve(llm.Call(model="vendor/model-x", error="HTTP 402: nope"))
        try:
            list(policy().propose(a_view(), 4))
        except LP.TransportFailure as e:
            self.assertEqual(e.kind, "round")
            self.assertEqual(e.model, "vendor/model-x")
            self.assertIn("vendor/model-x", str(e))
        try:
            policy().nominate(a_view(1, 4))
        except LP.TransportFailure as e:
            self.assertEqual(e.kind, "nomination")


if __name__ == "__main__":
    unittest.main()


class FakeResponse(object):
    """Minimal stand-in for an urlopen context manager."""

    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class AProviderErrorWithHttp200IsNotAnAnswer(unittest.TestCase):
    """A finish_reason of "error" with HTTP 200 is a call that did not complete, so `llm.complete` sets its error."""

    def setUp(self):
        self._real = urllib.request.urlopen
        self._key = llm._key
        llm._key = lambda _e=None: "test-key"
        self.addCleanup(lambda: setattr(urllib.request, "urlopen", self._real))
        self.addCleanup(lambda: setattr(llm, "_key", self._key))

    def serve(self, finish, text="GDIF | a"):
        payload = {"model": "vendor/model-x", "provider": "P",
                   "choices": [{"message": {"content": text}, "finish_reason": finish}],
                   "usage": {"prompt_tokens": 5, "completion_tokens": 11, "cost": 0.0,
                             "completion_tokens_details": {"reasoning_tokens": 3}}}
        urllib.request.urlopen = lambda req, timeout=None: FakeResponse(payload)

    def test_a_provider_error_is_not_ok_even_with_text_and_http_200(self):
        self.serve("error")
        c = llm.complete("pick four", "vendor/model-x", env_file=None)
        self.assertFalse(c.ok, "finish_reason=error must not read as a valid answer")
        self.assertIn("finish_reason=error", c.error)
        self.assertEqual(c.finish_reason, "error")

    def test_it_reaches_transport_failure_without_a_new_branch_in_the_policy(self):
        self.serve("error")
        pol = LP.LLMPolicy("vendor/model-x", "instructed", 1.0, landscape="abstract")
        v = V.CampaignView((), set(), 1, 15, 4, 0, 60, ("AAAA",), campaign_seed=0, screen=None)
        with self.assertRaises(LP.TransportFailure):
            list(pol.propose(v, 4))

    def test_the_provider_and_the_token_counts_survive_the_error(self):
        """An errored call keeps its provider and token counts."""
        self.serve("error")
        c = llm.complete("pick four", "vendor/model-x", env_file=None)
        self.assertEqual(c.provider, "P")
        self.assertEqual(c.completion_tokens, 11)
        self.assertEqual(c.reasoning_tokens, 3)

    def test_a_normal_stop_is_untouched(self):
        self.serve("stop")
        c = llm.complete("pick four", "vendor/model-x", env_file=None)
        self.assertTrue(c.ok)
        self.assertEqual(c.finish_reason, "stop")

    def test_a_length_finish_is_still_ok_when_text_arrived(self):
        """A length finish with usable text is still a valid answer."""
        self.serve("length")
        c = llm.complete("pick four", "vendor/model-x", env_file=None)
        self.assertTrue(c.ok)
