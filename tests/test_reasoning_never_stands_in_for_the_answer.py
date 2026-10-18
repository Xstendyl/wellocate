"""Tests that a reply with no answer text is an empty call, whatever reasoning text came with it.

The call is returned empty with an error, so the existing failure path handles it, and the reasoning is kept
in its own field.
"""
import io, json, os, sys, unittest, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import llm, llm_policy                                         # noqa: E402


class FakeResponse(io.BytesIO):

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def payload(content, reasoning, completion=169, reasoning_tokens=169):
    return {"model": "vendor/fake", "provider": "Fake", "choices": [{"finish_reason": "stop", "message": {
        "content": content, "reasoning": reasoning}}],
        "usage": {"prompt_tokens": 300, "completion_tokens": completion, "cost": 0.001,
                  "completion_tokens_details": {"reasoning_tokens": reasoning_tokens}}}


class ReasoningIsNeverTheAnswer(unittest.TestCase):

    def setUp(self):
        self._open, self._key = urllib.request.urlopen, llm._key
        llm._key = lambda _env=None: "test-not-a-real-key"
        self.addCleanup(lambda: setattr(urllib.request, "urlopen", self._open))
        self.addCleanup(lambda: setattr(llm, "_key", self._key))

    def call(self, p):
        urllib.request.urlopen = lambda req, timeout=None: FakeResponse(json.dumps(p).encode())
        return llm.complete("prompt", "vendor/fake")

    def test_empty_content_with_reasoning_comes_back_empty(self):
        c = self.call(payload("", "x"))
        self.assertEqual(c.text, "")
        self.assertFalse(c.ok, "an empty answer is an error, so the existing failure path takes it")
        self.assertIn("empty content", c.error)
        self.assertEqual(c.reasoning_text, "x", "the reasoning is kept, in its own field")
        self.assertEqual(c.visible_tokens, 0)
        self.assertTrue(llm_policy.call_fields(c)["empty_text"])

    def test_an_answer_keeps_its_reasoning_apart(self):
        c = self.call(payload("GDIF | x", "thinking", completion=200, reasoning_tokens=150))
        self.assertTrue(c.ok)
        self.assertEqual(c.text, "GDIF | x")
        self.assertEqual((c.reasoning_text, c.visible_tokens), ("thinking", 50))
        f = llm_policy.call_fields(c)
        self.assertEqual((f["reasoning_text"], f["visible_tokens"], f["empty_text"]), ("thinking", 50, False))


if __name__ == "__main__":
    unittest.main()
