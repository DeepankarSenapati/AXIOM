# AXIOM
> Autonomous eXchange for Intelligent Operations & Markets
> Founder: Deepankar Senapati | Started: March 2026

## What is this?
Bot-only algorithmic trading simulation platform. Only algorithms trade. Revenue tokenized.
5 strategies, real market data (Binance + NSE), 70/15/15 RST split, 3-stage governance.
See `.claude/rules/architecture.md` for full system design.

## Stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2, Pydantic v2, SQLite
- Frontend: React 18 + Vite + TailwindCSS + Recharts
- Testing: pytest (148 tests passing)

## Project Structure
```
AXIOM/
├── backend/
│   ├── engine/        ← BotRunner, Backtester, Arena, MarketFeed (CCXT + YFinance + Mock)
│   ├── tokenomics/    ← TokenLedger, Distributor (70/15/15 split + 2% platform fee)
│   ├── governance/    ← VotingManager, StageManager (3-stage progressive decentralisation)
│   ├── bots/          ← Registry, 5 strategies (MA, RSI, BB, MACD, Momentum)
│   ├── api/           ← FastAPI routers: bots, arena, tokenomics, governance, admin, tech, auth
│   ├── auth/          ← JWT authentication, RBAC (4 roles)
│   ├── db/            ← SQLAlchemy models, migrations
│   ├── config.py      ← All constants (RST splits, fees, thresholds)
│   └── main.py        ← App entry point + request logging
├── frontend/src/pages/
│   ├── AdminDashboard.jsx      ← Platform stats, bot approval, platform revenue
│   ├── TechDashboard.jsx       ← Tech company bots, earnings, bot submission
│   ├── GovernanceDashboard.jsx ← (governance_company role landing)
│   ├── MarketDashboard.jsx     ← Token market, portfolio, earnings, bot profiles
│   ├── BotArena.jsx            ← Backtests, arena runs, equity curves, benchmark
│   ├── History.jsx             ← Backtest history, filters, equity replay
│   ├── Leaderboard.jsx         ← Strategy rankings by Sharpe + Alpha
│   ├── Governance.jsx          ← Satisfaction votes, audit reports, stage display
│   └── Tokenomics.jsx          ← Revenue distribution, token balances
└── tests/
```

## Current Phase
**Phase 1 — Local MVP only.** No blockchain. No real money. No real exchange orders.
See `.claude/rules/phase-guard.md` before adding anything new.

## Commands
```powershell
# Backend (from project root, PYTHONPATH must include root)
$env:PYTHONPATH = "."
python -m uvicorn backend.main:app --reload

# Frontend (separate terminal)
cd frontend && npm run dev

# Tests
pytest tests/ -v
```

## Implemented Features (Phase 1 complete)
- 5 trading strategies with configurable parameters
- CCXT (Binance) + YFinance (NSE India) + Mock market feeds
- Blind backtesting engine — strategy never knows if live or historical
- Multi-bot arena with head-to-head equity curve comparison
- Buy-and-hold benchmark + Alpha calculation on every backtest
- Strategy leaderboard ranked by Sharpe ratio + Avg Alpha
- Persistent backtest history (SQLite, append-only trade log)
- Simulated tokenomics: RST purchase, sell-back (2% exit fee), earnings
- 2% platform fee on every revenue distribution
- Tech company dashboard: earnings tracking, 15% cut visibility
- Bot profile / due diligence modal: risk rating, token distribution, recent runs
- Progressive governance: 3-stage automatic transitions
- Audit reports (Stage 2+ only) — stored in DB, visible per bot
- Auto-filled voter address + token weight from logged-in user
- JWT auth + RBAC (admin, tech_company, governance_company, token_holder)
- Admin dashboard: platform revenue, bot approval workflow

## Key Constants (backend/config.py)
```python
TOTAL_RST_PER_BOT     = 1_000_000
TOKEN_PUBLIC_SHARE    = 0.70      # 70% to public pool
TOKEN_TECH_SHARE      = 0.15      # 15% to tech company
TOKEN_GOV_SHARE       = 0.15      # 15% to governance company
PLATFORM_FEE          = 0.02      # 2% retained by AXIOM on each distribution
EXIT_FEE              = 0.02      # 2% penalty on token sell-back
RST_PRICE             = 0.01      # $0.01 per RST (Phase 1 simulated)
MAX_POSITION_SIZE     = 0.30      # max 30% of cash per trade
STAGE2_TRIGGER        = 0.50      # satisfaction < 50%
STAGE2_QUARTERS       = 2         # for 2 consecutive quarters
STAGE3_QUARTERS       = 4         # for 4 consecutive quarters
```

## Non-negotiable Rules
1. Every strategy is **blind** — `on_candle()` receives `candles[:i+1]` only. Never future.
2. Trade log is **append-only** — never UPDATE or DELETE rows in `trades` table.
3. Pydantic models for **all** cross-module data.
4. Full type hints on **all** functions.
5. All constants in `config.py` — no magic numbers in logic files.
See `.claude/rules/coding-standards.md` for complete rules.

## DB Tables
`users`, `bots`, `trades`, `tokens`, `governance_votes`, `satisfaction_polls`,
`backtest_runs`, `distribution_events`, `distribution_payouts`, `governance_audits`

## API Routers
| Prefix | File | Key endpoints |
|--------|------|---------------|
| `/auth` | auth/router.py | POST /register, POST /token, GET /me |
| `/bots` | api/bots.py | CRUD + GET /{id}/profile |
| `/arena` | api/arena.py | POST /run, POST /backtest/{id}, GET /leaderboard |
| `/tokenomics` | api/tokenomics.py | POST /init, POST /purchase, POST /sell, POST /distribute |
| `/governance` | api/governance.py | POST /vote, POST /poll/close, POST /{id}/audit |
| `/admin` | api/admin.py | GET /stats, POST /approve, GET /platform-revenue |
| `/tech` | api/tech.py | GET /my-dashboard |

## Subagent Lanes
See `.claude/rules/subagents.md` before spawning agents.
