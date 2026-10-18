"""Tests that every logged call row, of every kind, carries every field of its call.

All log sites build their rows through one function, call_fields, so a field added to `Call` reaches every
row kind.
"""
import inspect, os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import llm, llm_policy as LP  # noqa: E402


class FakeCall(object):
    """Every public attribute of llm.Call, with a distinguishable value for each."""

    def __init__(self, **kw):
        self.text = kw.get("text", "GDIF | a")
        self.model = kw.get("model", "served/model")
        self.prompt_tokens = 11
        self.completion_tokens = 22
        self.reasoning_tokens = 33
        self.finish_reason = "stop"
        self.cost_usd = 0.125
        self.latency_ms = 456
        self.error = kw.get("error", None)
        self.raw = None
        self.provider = kw.get("provider", "AtlasCloud")


class EveryRowIsAttributed(unittest.TestCase):

    def test_call_fields_covers_every_informative_slot_of_Call(self):
        """call_fields records every informative slot of Call; `raw` and `text` are recorded under their own names."""
        recorded = set(LP.call_fields(FakeCall()))
        slots = set(llm.Call.__slots__)
        allowed_absent = {"raw", "text", "latency_ms"}
        missing = slots - allowed_absent - {"model"} - recorded
        # `model` is recorded as model_returned, so map it.
        self.assertIn("model_returned", recorded)
        self.assertEqual(missing, set(),
                         "Call has field(s) %s that no row records; add them to call_fields" % missing)

    def test_both_log_sites_go_through_the_one_function(self):
        """Every log site builds its row through call_fields, counted on the source, so a site that hand-copies fields fails."""
        src = inspect.getsource(LP)
        # Resent overloaded attempts are rows too, in their own list.
        appends = len(re.findall(r"self\.calls\.append\(", src)) + len(re.findall(r"self\.transport_retries\.append\(", src))
        # The failing request an abandoned campaign keeps is a third kind of row, built through the same
        # function at each raise site.
        kept = len(re.findall(r"_raise_transport\(self\.model, call\.error, \"\w+\",\s*failed=dict\(", src))
        raises = len(re.findall(r"(?<!def )_raise_transport\(", src))
        # (?<!def ) so the function's own definition line is not counted as a use.
        uses = len(re.findall(r"(?<!def )call_fields\(call\)", src))
        self.assertGreaterEqual(appends, 2)
        self.assertEqual(kept, raises, "a raise site drops its failing request: %d of %d keep it" % (kept, raises))
        self.assertEqual(uses, appends + kept,
                         "%d row(s) are appended and %d failing request(s) kept, but call_fields is used %d "
                         "time(s); a row is hand-copying its call fields" % (appends, kept, uses))

    def test_no_site_hand_copies_a_field_the_function_owns(self):
        """No code outside call_fields sets a field that call_fields owns."""
        src = inspect.getsource(LP)
        body = inspect.getsource(LP.call_fields)
        outside = src.replace(body, "")
        for owned in ("provider", "reasoning_tokens", "finish_reason", "cost_usd",
                      "prompt_tokens", "completion_tokens", "empty_text"):
            hits = re.findall(r'"%s":\s*' % owned, outside)
            self.assertEqual(hits, [], "%r is set outside call_fields, so the rows can drift" % owned)

    def test_the_provider_survives_an_errored_call(self):
        """An errored call still records its provider."""
        f = LP.call_fields(FakeCall(error="HTTP 503", provider="Novita"))
        self.assertEqual(f["provider"], "Novita")
        self.assertEqual(f["error"], "HTTP 503")

    def test_a_call_object_without_a_provider_attribute_does_not_crash(self):
        """A Call object without a provider attribute reads as an empty provider."""
        class Old(FakeCall):
            pass
        o = Old()
        del o.provider
        self.assertEqual(LP.call_fields(o)["provider"], "")

    def test_empty_text_is_computed_and_not_copied(self):
        self.assertTrue(LP.call_fields(FakeCall(text="   "))["empty_text"])
        self.assertFalse(LP.call_fields(FakeCall(text="GDIF | a"))["empty_text"])


if __name__ == "__main__":
    unittest.main()
