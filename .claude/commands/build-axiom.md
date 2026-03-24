# /build-axiom

Spawn subagents to build all Phase 1 modules in parallel.

## Usage
/build-axiom

## What this does
Reads `.claude/rules/subagents.md` for lane assignments, then:

### Round 1 (parallel)
- engine-agent → builds `backend/engine/`
- tokenomics-agent → builds `backend/tokenomics/`
- governance-agent → builds `backend/governance/`
- db-agent → builds `backend/db/`

### Round 2 (after Round 1)
- strategy-agent → builds `backend/bots/strategies/` (simple_ma + rsi)
- api-agent → builds `backend/api/` routers

### Round 3 (after Round 2)
- test-agent → writes all tests in `tests/`
- frontend-agent → scaffolds React dashboard

## Each agent prompt must include
"Read CLAUDE.md and .claude/rules/architecture.md first.
You are the {lane} agent. Only write files in {owned_dirs}.
Do not build anything listed in .claude/rules/phase-guard.md Phase 2+."
