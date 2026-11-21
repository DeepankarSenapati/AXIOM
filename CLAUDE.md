# AXIOM
> Autonomous eXchange for Intelligent Operations & Markets
> Founder: Deepankar Senapati | Started: March 2026

## What is this?
Local algorithmic trading simulation platform with five built-in strategies,
optional read-only historical data (Binance + NSE), simulated 70/15/15 RST
allocations, and a three-stage governance indicator. Revenue distributions
are entered by a user; the prototype does not place live orders or transfer
governance control.
See `.claude/rules/architecture.md` for full system design.

## Stack
- Backend: Python 3.11/3.12, FastAPI, SQLAlchemy 2, Pydantic v2, SQLite
- Frontend: React 18 + React Router 7 + Vite 8 + TailwindCSS + Recharts
- Testing: pytest and Node's built-in test runner; run the suites to obtain current counts

## Project Structure
```
AXIOM/
├── backend/
│   ├── engine/        ← BotRunner, Backtester, Arena, market feeds, Survival Lab
│   ├── tokenomics/    ← TokenLedger, Distributor (70/15/15 split + 2% platform fee)
│   ├── governance/    ← VotingManager, StageManager (3-stage progressive decentralisation)
│   ├── bots/          ← Registry, 5 strategies (MA, RSI, BB, MACD, Momentum)
│   ├── api/           ← FastAPI routers: bots, arena, lab, tokenomics, governance, admin, tech, auth
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
│   ├── SurvivalLab.jsx         ← Synthetic shock replay, Worlds, Landscape, passport and briefing
│   ├── History.jsx             ← Backtest history and filters
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
# From frontend/: npm test && npm run build
```

For the full two-terminal setup, demo credentials, and macOS/Linux commands,
see `docs/SURVIVAL_LAB.md`.

## Implemented Features (Phase 1 prototype)
- 5 trading strategies with configurable parameters
- CCXT (Binance) + YFinance (NSE India) + Mock market feeds
- Backtesting: built-in strategies receive current and earlier candles, not future candles
- Multi-bot arena with head-to-head equity curve comparison
- Buy-and-hold benchmark + Alpha calculation on every backtest
- Strategy leaderboard ranked by Sharpe ratio + Avg Alpha
- Persistent backtest summaries in SQLite; the current backtest API does not persist each trade
- Synthetic Survival Lab with next-open fills, shock/fee experiments, buy-pause guard, passport replay and HTML briefing
- Simulated tokenomics: RST purchase, sell-back (2% exit fee), earnings
- 2% platform fee on every revenue distribution
- Tech company dashboard displays modeled tech-pool allocations; placeholder pools do not credit company user wallets
- Bot profile / due diligence modal: risk rating, token distribution, recent runs
- Governance: a three-stage indicator derived from closed polls; no actual control transfer or binding governance
- Audit reports (Stage 2+ only) — stored in DB, visible per bot
- Votes use the signed-in user's positive simulated holdings at vote time; transferable tokens can be counted again
- JWT auth + local demo role checks (admin, tech_company, governance_company, token_holder); public demo credentials are not production security
- Admin dashboard: platform revenue, bot approval workflow

## Key Constants (backend/config.py)
```python
TOTAL_RST_PER_BOT     = 1_000_000
TOKEN_PUBLIC_SHARE    = 0.70      # 70% to public pool
TOKEN_TECH_SHARE      = 0.15      # 15% to the placeholder tech pool
TOKEN_GOV_SHARE       = 0.15      # 15% to the placeholder governance pool
PLATFORM_FEE          = 0.02      # 2% recorded on simulated distributions
EXIT_FEE              = 0.02      # 2% penalty on token sell-back
RST_PRICE             = 0.01      # $0.01 per RST (Phase 1 simulated)
MAX_POSITION_SIZE     = 0.30      # max 30% of cash per trade
STAGE2_TRIGGER_THRESHOLD       = 0.50  # satisfaction < 50%
STAGE2_CONSECUTIVE_QUARTERS    = 2
STAGE3_CONSECUTIVE_QUARTERS    = 4
```

## Non-negotiable Rules
1. Every strategy is **blind** — `on_candle()` receives `candles[:i+1]` only. Never future.
2. Trade log is **append-only** — never UPDATE or DELETE rows in `trades` table.
   The current API does not persist backtest trades there; do not claim it does.
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
| `/auth` | api/auth.py | POST /register, POST /login, GET /me |
| `/bots` | api/bots.py | CRUD + GET /{id}/profile |
| `/arena` | api/arena.py | POST /run, POST /backtest/{id}, GET /leaderboard |
| `/arena/lab` | api/lab.py | POST /run, POST /paired, POST /worlds, POST /landscape |
| `/tokenomics` | api/tokenomics.py | POST /init, POST /purchase, POST /sell, POST /distribute |
| `/governance` | api/governance.py | POST /vote, POST /poll/close, POST /{id}/audit |
| `/admin` | api/admin.py | GET /stats, POST /approve, GET /platform-revenue |
| `/tech` | api/tech.py | GET /my-dashboard |

## Subagent Lanes
See `.claude/rules/subagents.md` before spawning agents.
