# Independent one-round check

A test of the re-testing habit written apart from Wellocate, with its own landscape, prompt and scorer. It shares
no code with the environment. The design and the reading rule were fixed before the first call.

Each of 30 seeds builds a seven-round history on a simple additive landscape. Every candidate is valid, nothing is
rejected, and the best candidate so far has already been measured twice. The model chooses four candidates for
round 8 under three prompts, on the same histories:

- **A**: readings are exact, and the prompt says so;
- **B**: readings are exact, and the prompt says nothing about it;
- **C**: readings are noisy (about 7% of the true value), and the prompt says so.

Re-testing share of round 8, temperature 0, 30 histories per prompt:

| model | A, exact stated | B, exact unstated | C, noisy | C minus A |
|---|---|---|---|---|
| Opus 4.7 | 24.2% | 24.2% | 61.7% | +37.5 pp |
| Gemini 2.5 Flash | 45.0% | 50.8% | 95.0% | +50.0 pp |
| DeepSeek V3.1 | 55.8% | 49.2% | 94.2% | +38.3 pp |

With exact readings, any re-test is wasted. Stating exactness makes no detectable difference, and noise raises
re-testing sharply. By the rule fixed in advance, the check confirms the habit in Gemini 2.5 Flash and DeepSeek
V3.1, and partly in Opus 4.7. Appendix H.4 of the paper reports it.

Files: `all_prompts_and_responses*.md` hold every prompt and reply, `results_raw*.json` the same calls as data.

```bash
python3 scripts/verify_independent_test.py        # re-scores from the logged prompts and replies
python3 independent_check/score_all_models.py      # the same table from the raw results
OPENROUTER_API_KEY=... python3 independent_check/indep_vignette.py 30 anthropic/claude-opus-4.7   # new calls
```
