---
name: governance
description: Use when working on governance features, voting, stage transitions, satisfaction polls, or replacing a governance company. Triggers on phrases like "governance vote", "satisfaction poll", "stage transition", "replace governance company", "community control", "token-weighted vote".
---

# AXIOM Governance System

## Three Stages (automatic transitions)

### Stage 1 — Normal Operation
- Governance company manages all decisions
- Token holders submit anonymous suggestions
- Quarterly satisfaction vote (simple 1-person-1-vote)
- Monthly transparency report published

### Stage 2 — Underperformance Review
Trigger: satisfaction vote < 50% for **2 consecutive quarters**
Actions (all automatic):
1. Governance company placed on notice
2. Tech company mandated to audit + update bot within 60 days
3. Independent technical review commissioned (gov company pays)
4. Replacement shortlisting initiated in parallel

### Stage 3 — Direct Community Control
Trigger: satisfaction vote < 50% for **4 consecutive quarters**
Actions (all automatic):
1. Governance company replaced via mandatory token-weighted vote
2. Bot parameters opened to direct token-holder input
3. Enhanced monitoring + real-time public reporting

## Vote Types

### Satisfaction Poll (quarterly, Stage 1)
- Who votes: all RST holders
- Method: 1 person = 1 vote
- Threshold: 50%
- Result stored in `governance_polls` table

### Major Decisions (token-weighted)
Covers: replacing governance company, changing revenue split,
modifying bot strategy, triggering emergency audit
- Weight: proportional to RST held
- Supermajority required for governance company removal (>66%)
- Mandatory cooling-off: 30 days after successful removal

## DB Tables involved
- `governance_proposals` — proposal text, type, status
- `governance_votes` — voter_id, proposal_id, weight, choice
- `satisfaction_polls` — quarter, yes_count, no_count, result
- `stage_history` — bot_id, from_stage, to_stage, triggered_at, reason

## Stage transition code location
`backend/governance/stages.py` → `StageManager.evaluate_transition()`

## Adding a governance proposal
```python
from governance.voting import VotingEngine

engine = VotingEngine(db_session)
proposal = engine.create_proposal(
    bot_id="bot_001",
    type=ProposalType.REPLACE_GOVERNANCE,
    text="Replace current governance company due to Q3/Q4 underperformance",
    proposed_by="token_holder_xyz"
)
```

## Checking current stage
```python
from governance.stages import StageManager

manager = StageManager(db_session)
stage = manager.get_current_stage(bot_id="bot_001")
# Returns: Stage.ONE | Stage.TWO | Stage.THREE
```
