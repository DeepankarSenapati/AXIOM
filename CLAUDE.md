# AXIOM
> Autonomous eXchange for Intelligent Operations & Markets
> Founder: Deepankar Senapati | Started: March 2026

## What is this?
Bot-only algorithmic trading platform. Only algorithms trade. Revenue tokenized.
See `.claude/rules/architecture.md` for full system design.

## Stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy, Pydantic v2, SQLite
- Frontend: React + Vite + TailwindCSS
- Testing: pytest

## Project Structure
```
axiom/
├── backend/
│   ├── engine/        ← BotRunner, Backtester, Arena, MarketFeed
│   ├── tokenomics/    ← Ledger, Distributor
│   ├── governance/    ← Voting, Stages
│   ├── bots/          ← Registry, Validator, strategies/
│   ├── api/           ← FastAPI routers
│   └── db/            ← SQLAlchemy models, session
├── frontend/
└── tests/
```

## Current Phase
**Phase 1 — Local MVP only.** No blockchain. No real money. No real exchange.
Simulate everything. See `.claude/rules/phase-guard.md` before adding anything new.

## Commands
```bash
cd backend && uvicorn main:app --reload   # start API
pytest tests/                             # run tests
```

## Non-negotiable Rules
1. Every strategy is **blind** — `on_candle()` never receives future data. Ever.
2. Trade log is **append-only** — never UPDATE or DELETE trade records.
3. Pydantic models for **all** cross-module data.
4. Full type hints on **all** functions.
See `.claude/rules/coding-standards.md` for complete rules.

## Subagent Lanes
See `.claude/rules/subagents.md` before spawning agents.
