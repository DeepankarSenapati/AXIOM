# Subagent Lanes

When spawning subagents for parallel work, assign strictly by lane.
Agents must NOT touch files outside their lane.

## Lane Assignments

| Agent | Owns | Reads (not writes) |
|-------|------|--------------------|
| `engine-agent` | `backend/engine/` | `backend/bots/strategies/base.py` |
| `strategy-agent` | `backend/bots/strategies/` | `backend/engine/` (base classes only) |
| `tokenomics-agent` | `backend/tokenomics/` | `backend/db/models.py` |
| `governance-agent` | `backend/governance/` | `backend/db/models.py` |
| `api-agent` | `backend/api/` | All backend modules (read only) |
| `db-agent` | `backend/db/` | `backend/config.py` |
| `test-agent` | `tests/` | All backend modules (read only) |
| `frontend-agent` | `frontend/` | `backend/api/` (for API contracts) |

## Spawn Order (dependencies matter)
```
Round 1 (parallel, no deps):
  engine-agent + tokenomics-agent + governance-agent + db-agent

Round 2 (after Round 1 finishes):
  strategy-agent + api-agent

Round 3 (after Round 2 finishes):
  test-agent + frontend-agent
```

## Subagent Prompt Template
When spawning, always include:
1. "Read CLAUDE.md and `.claude/rules/architecture.md` first."
2. "You are the `{lane}` agent. Only write files in `{owned_dirs}`."
3. "Do not implement anything from `.claude/rules/phase-guard.md` Phase 2+."
4. The specific task.

## Conflict Resolution
If two agents need to share a model/type:
- Define it in `backend/db/models.py` (owned by db-agent)
- Both agents import from there
- Never duplicate model definitions
