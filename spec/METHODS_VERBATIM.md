# Sentences that must appear in the paper's methods verbatim

Not paraphrased, not moved to an appendix, not softened. These are the lines that make the
environment defensible, and their value comes from a reader being able to check them.

## On the noise model

> The noise model was not changed to reach the tuning target at any point. Its two constants are
> derived from the published read depth of the assay that produced the landscape: 557 input and 285
> selected reads per variant give Var(log w) = 1/285 + 1/557 and hence a coefficient of variation of
> 7.3%, and one post-selection read is worth (1/557)/0.512 = 0.0035 fitness units and hence the
> noise floor. Tuning the physics to the measurement would invert the point of deriving them.

## On why the landscape is tuned at all

> The generated landscape is tuned for MEASURABILITY, not for failure. A campaign is informative
> about a decision rule only when two candidate rules would choose differently; when they agree, the
> campaign cannot distinguish them. Measured under its own assay's noise model, GB1 is informative in
> 14% of campaigns, so 86% of GB1 campaigns cannot distinguish any two decision rules and cannot
> measure a decision rule at all. Every scripted policy and the agent run in the same landscape under
> the same noise field, so the informative rate is a property of the environment and not of any
> policy, and it is reported for all five scripted baselines alongside the agent.

## On the benchmark not decaying

> The benchmark ships as a seeded generator and not as a fixed table, so every user evaluates on a
> fresh landscape with an optimum no model has seen. The two biological landscapes ship as the
> contaminated reference cases, which is their honest role: on GB1 a frontier model proposes the
> global optimum before any measurement exists.

## On the clock result's power

> The power of the campaign-length experiment comes from the threefold lever on the horizon and not
> from precision within any cell. A campaign's crossing round is the first round in which at least
> half of that round's orders are re-measurements; the threshold is stated as "at least half" and not
> "more than half" because a round's replication fraction is a multiple of one over the slot count, so
> "more than half" would mean 100% at two slots and 62.5% at eight and would not be comparable across
> batch sizes. Regressing crossing round on campaign length over all 60 campaigns at 20 per length
> gives a CAMPAIGN-LEVEL ordinary-least-squares slope of -0.024 with a standard error of 0.025. An absolute clock predicts a slope of zero
> and sits 1.0 standard errors away; a budget-fraction heuristic predicts a slope equal to the
> fraction, estimated as 0.357 from the length-15 cell, and sits 15.4 standard errors away; a
> rounds-remaining heuristic predicts a slope of one and sits 41.3 away.

> A weighted least-squares fit to the three cell means, with weights one over the squared standard
> error, gives -0.027 with a standard error of 0.027 and distances of 1.0, 14.5 and 38.7. The paper
> quotes the campaign-level fit, because it uses every campaign and requires no weighting choice, and
> the two agree on every verdict.

> An earlier version of this paragraph reported +0.011 with a standard error of 0.086 and distances of
> 0.1, 4.6 and 11.5. Those came from five campaigns per length on the pre-fix parser and under the
> "more than half" threshold. The conclusion is unchanged and every competing hypothesis is now
> rejected by a wider margin.

## On what the contamination diagnostic cannot do

> The diagnostic compares round-one proposals against the known optimum, so it requires ground truth.
> That makes it a tool for auditing an existing benchmark and not for detecting contamination on a
> novel target in the field.


## On what the agent is

> Throughout, the agent is a MINIMAL AGENT: one stateless model call per round, which sees its full
> measurement history re-rendered into the prompt, chooses which measurements to order, and names its
> own final answer. It has no tools, no memory beyond the rendered history, and no code execution.
> We study the bare policy because every scaffold is built on it, and the contribution of any one piece
> of scaffolding is only measurable against the policy without that piece. The Aggregated condition is
> a controlled test of the piece a scaffold would most obviously supply, per-variant means and standard
> errors, holding everything else fixed. A result about a minimal agent is not a result about a
> production system, and two scaffolded conditions, an extended-thinking cell and a tool-using cell
> with a persistent conversation, measure how far it carries.
