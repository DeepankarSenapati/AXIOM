# AXIOM: a founder's vision for the competition

Research checked: 21 November 2026.

**Working idea:** make the hidden assumptions behind an automated strategy
visible *before* someone relies on it. Start with trading strategies, then
consider whether the same review workflow can help people evaluate other
automated decisions. This is a product hypothesis, not a proven market or moat.

## What exists today

Survival Lab runs built-in, rule-based strategies on locally generated daily
prices. A user can inject one hypothetical gap, change fees and slippage,
compare a buy-pause guard, inspect decisions and next-open fills, explore
seeded worlds and a shock/fee grid, and export or replay a passport and HTML
briefing. The guard does not force a sale or guarantee a loss limit. The
benchmark has different exposure from the bot.

The lab is **synthetic and local**. It does not accept a customer's strategy,
prove historical or live performance, or place real orders. A matching
fingerprint helps compare a rerun; it is not proof that the file, source code,
results, or execution are authentic. The older token and governance screens
are separate simulated workflows, not real ownership, distributions or control.
See [the demo guide](SURVIVAL_LAB.md) for the precise assumptions.

## The first customer to investigate

Start with a small systematic-trading research team: a strategy developer
prepares an evaluation and a research lead decides whether it is ready for
further investigation. The untested hypothesis is that their review process
is fragmented across code, charts and conversations, and that they would pay
to identify and explain failure cases faster. A university trading lab is a
useful second interview group, but it is a different buyer with a different
budget. Do not claim either group needs AXIOM until they show the problem in
their own workflow.

The question to validate is not “Do you like this dashboard?” Ask: **“Show me
the last strategy review. What almost changed your decision, and how did you
reproduce it?”** Observe what evidence they actually prepare, who signs off,
and what takes time. Seek introductions to researchers and reviewers rather
than treating friends' enthusiasm as demand.

## The ambitious product direction

If the interviews support the problem, build toward a **strategy challenge
room**: a researcher brings a versioned strategy and a reviewer asks, “What
would change my decision?” The system makes the assumptions, exposure, costs,
decisions and unresolved questions inspectable in one place. Three possible
extensions are experiments to validate, not features already built:

1. **Counterfactual replay.** Compare the same strategy under a documented
   market event, missing data, delayed fills or wider spreads; reveal the exact
   decision and exposure that caused the divergence. Historical data rights,
   trustworthy timestamps and realistic execution models would be necessary.
2. **Challenge cards.** A reviewer proposes a scenario, the author responds,
   and both can revisit the same inputs and limitations. A future signed
   evidence bundle might include source and data provenance, but independent
   verification and trustworthy identity would have to be designed and tested.
3. **Failure map.** Show where a strategy's behavior changes across a declared
   set of conditions, including where a safeguard helps and where it hurts.
   Such maps describe chosen tests; they do not estimate real-world failure
   probabilities or certify safety.

Longer term, a human-led review could invite specialized software agents to
propose challenges, critique assumptions and produce evidence. Their output
would remain a hypothesis for humans to inspect, not an autonomous approval or
trading recommendation. Only pursue this after proving the narrower workflow.

## Competitive reality

Backtesting and explainability are established fields. [QuantConnect](https://www.quantconnect.com/docs/v2/research-environment/meta-analysis/key-concepts)
already supports analysis of backtests and comparisons with live outcomes;
[Composer](https://help.composer.trade/article/78-slippage-and-fees) documents
backtest fees and slippage; [Alpaca](https://docs.alpaca.markets/us/docs/paper-trading)
offers real-time paper trading and explains important simulation omissions.
AXIOM should not claim it invented these capabilities or is more accurate.
The proposed wedge is a focused, understandable **challenge-and-review
workflow** across existing tools. Validate that it saves time or changes a
real review decision before calling it differentiation.

The [probability of backtest overfitting](https://escholarship.org/uc/item/4w1110bb)
research illustrates why selecting attractive historical results can mislead.
Changing synthetic seeds does not solve that problem. [FINRA's algorithmic
trading guidance](https://www.finra.org/sites/default/files/notice_doc_file_ref/Notice_Regulatory_15-09.pdf)
discusses testing and change-management practices for relevant firms; it is
not evidence that AXIOM meets any regulatory requirement or that its rules
apply to this prototype.

## The competition story

**Opening:** “A beautiful backtest can hide what actually caused the result.
What if the reviewer could interrogate the strategy, not just admire its
curve?”

**Demonstration:** run the default RSI scenario, jump to the simulated shock,
and show the signal and the guard blocking a buy. Then set **Number of worlds**
to 12 and generate the seeded Worlds: with the default experiment settings,
the guard ends higher in 3, lower in 8,
and approximately equal in 1. These are *this generator's samples*, not
probabilities. Explain that the safeguard can also hurt the outcome. Open the
shock grid and note the position before the gap; a flat bot was not necessarily
resilient. Export the passport and replay it, explaining the fingerprint's
limits. Finish with the proposed customer and next validation milestone.

**Ask:** seek introductions to systematic-strategy researchers and reviewers,
and funding for a time-bound validation phase. Before naming a funding amount,
prepare a real budget and milestones for interviews, data rights, engineering,
and independent review. Do not present invented users, revenue, market size,
or performance. Keep a pre-run local demo and the briefing available if the
room's network fails.

## A 90-day validation plan

These are proposed targets, not results or statistically representative proof.

| When | Work | Evidence needed to continue |
|---|---|---|
| Days 1–30 | Interview 15–20 strategy developers and review leads; ask at least 5 to walk through a real, shareable review artifact. Record current tools, time, constraints and the person who can buy. | At least 5 independently describe a costly review or handoff problem and agree to a follow-up using their workflow. If not, refine the customer or stop this wedge. |
| Days 31–60 | With permission and licensed data, compare ordinary and AXIOM-assisted reviews on matched challenges, counterbalancing their order. Use a preset scoring rubric and, where practical, an independent evaluator; record time, findings, misses and a negative case. | At least 3 teams complete the exercise, and reviewers can explain the finding and limitations without the founder prompting them. If not, simplify the workflow before adding features. |
| Days 61–90 | Offer 2–3 scoped design-partner pilots with agreed success criteria, data handling and a clear end date. Ask about a paid next step only after useful repeat use. | Obtain repeated use and at least one concrete paid-pilot proposal or documented procurement path. If interest remains only verbal, revisit positioning or the buyer. |

Parallel prerequisites: independent engine review, careful historical and
out-of-sample evaluation, licensing and data-quality checks, and a privacy and
security design appropriate to private strategy code. User research does not
prove predictive power. Seek qualified legal advice before making public
investment-performance claims or offering financial products; requirements
depend on jurisdiction and use. For example, the
[SEC's investment adviser marketing guidance](https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/investment-adviser-marketing)
describes conditions for certain hypothetical-performance advertisements by
covered advisers; it is not a determination of AXIOM's obligations.

If teams demonstrate sustained value, test team-based pricing through actual
pilot conversations. Track reviewer time saved, repeated reviews, willingness
to share or import data, compute/data costs per review, and whether someone
with budget accepts responsibility for a purchase. These are hypotheses to
measure, not current business metrics.
