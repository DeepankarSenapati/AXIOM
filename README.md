# AXIOM
**Autonomous eXchange for Intelligent Operations & Markets**

A simulated, bot-only algorithmic trading platform. Strategies make decisions
against historical or simulated data. The prototype also models simulated token
allocations, user-entered revenue distributions, and governance escalation.

> **Phase 1 — Local simulation MVP.** No real money, no blockchain, no live exchange orders.

### Investor-demo prototype: Survival Lab

The `holylarp` prototype adds a local, deterministic laboratory for testing
rule-based strategies on synthetic markets. It shows a simulated shock,
fees, slippage, a buy-pause guard, decision-by-decision replay, and a
reproducibility passport. Synthetic Worlds compares a small set of seeded
scenarios, and Shock Landscape explores a grid of shocks and fees on one
synthetic seed. These are experiments, not forecasts or evidence of live results.
See [the demo guide](docs/SURVIVAL_LAB.md) and
[experiment notes](docs/EXPERIMENT_NOTES.md) for instructions and limitations;
[investor notes](docs/INVESTOR_NOTES.md) and the [founder vision](docs/FOUNDER_VISION.md)
describe the unvalidated product thesis and proposed validation plan.

---

## Table of Contents

1. [What AXIOM Does](#what-axiom-does)
2. [Tech Stack](#tech-stack)
3. [Setup and Running](#setup-and-running)
4. [Full Simulation Walkthrough](#full-simulation-walkthrough)
5. [Trading Strategies — Formulas](#trading-strategies--formulas)
6. [Engine — How Backtesting Works](#engine--how-backtesting-works)
7. [Performance Metrics — Formulas](#performance-metrics--formulas)
8. [Tokenomics — Economic Model](#tokenomics--economic-model)
9. [Governance — Progressive Decentralisation](#governance--progressive-decentralisation)
10. [Role-Based Access](#role-based-access)
11. [API Reference](#api-reference)
12. [Database Schema](#database-schema)

---

## What AXIOM Does

AXIOM is a platform where:

- **Algorithms trade, humans participate in the simulation.** Tech companies
  submit bots; simulated token holders can buy Revenue Share Tokens (RST) and
  receive modeled distributions when an authorized user enters revenue.
- **Decisions can be inspected.** Survival Lab returns a per-candle event trace
  and downloadable JSON for the current experiment. This prototype does not
  provide an independently verified or tamper-proof trade audit.
- **Entered revenue is split in the simulation.** The model records a 2%
  platform fee and allocates the remainder across public, tech and governance
  pools. Placeholder-pool allocations do not credit a user's wallet.
- **Governance displays an escalation indicator.** Consecutive low-satisfaction
  quarters change the simulated stage. This prototype does not transfer control
  or implement binding governance.
- **Strategies receive only the current and earlier candles.** This does not
  prevent overfitting or make a simulated result evidence of future returns.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11/3.12, FastAPI, SQLAlchemy 2, Pydantic v2, SQLite |
| Frontend | React 18, Vite, TailwindCSS, React Router v7, Recharts |
| Market Data | CCXT (Binance public API), yfinance (NSE India), MockMarketFeed |
| Auth | JWT (HS256), bcrypt password hashing |
| Testing | pytest |

---

## Setup and Running

### Prerequisites

- Python 3.11 or 3.12
- Node.js 20.19+ within the 20.x line, or 22.12+ (as required by Vite)

On a fresh machine, install [Python 3.12](https://www.python.org/downloads/release/python-31210/)
(choose the macOS universal2 or Windows 64-bit installer) and
[Node.js](https://nodejs.org/en/download), then open a new terminal. On macOS
or Linux, check the versions with `python3.12 --version`, `node --version`,
and `npm --version`. On Windows, use `py -3.12 --version` instead of the
Python command. If Python 3.12 is not found, install it before continuing.
Python 3.11 is also supported; substitute `3.11` in the commands below.

### Quick start with an existing macOS setup

If the existing `venv` and frontend dependencies are already installed, open
Terminal and run:

```bash
cd ~/Desktop/AXIOM  # Adjust this path if you moved the project
source venv/bin/activate
python --version    # Should show Python 3.11 or 3.12
python scripts/demo.py
```

Open the printed URL, choose **Explore demo credentials** to sign in, and
press Ctrl+C in the terminal when finished. If dependencies are missing,
follow the installation steps below. Install and rehearse before the event;
the Survival Lab runs locally after setup, while historical market data
requires an internet connection.

### 1. Install backend dependencies

From the project root, create and activate the virtual environment:

```bash
# macOS / Linux
python3.12 -m venv venv
source venv/bin/activate
```

```powershell
# Windows PowerShell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
```

Then, with the environment activated, install the backend dependencies:

```bash
python -m pip install -r requirements.txt
```

If your working copy has moved this file to `backend/requirements.txt`, use
`python -m pip install -r backend/requirements.txt` instead.

### 2. Install frontend dependencies

```bash
cd frontend
npm ci
cd ..
```

On macOS or Linux, for a disposable one-command rehearsal after installing
dependencies, activate the virtual environment and run this command from the
project root:

```bash
python scripts/demo.py
```

It starts both local services with a temporary database; see the
[demo guide](docs/SURVIVAL_LAB.md) for what persists and how to stop it.
On Windows, use the two-terminal steps below instead.

### 3. Start the backend

```powershell
# Windows PowerShell — must run from project root
$env:PYTHONPATH = "."
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# macOS / Linux
PYTHONPATH=. uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

API available at `http://127.0.0.1:8000`
Interactive docs at `http://127.0.0.1:8000/docs`

### 4. Start the frontend

```bash
cd frontend
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`.

### 5. Run the test suite

```bash
pytest tests/ -v
```

---

## Full Simulation Walkthrough

This is the complete end-to-end path through the platform, in order.

### Step 1 — Sign in to the local demo

On a fresh local database the app seeds one demo account for each role; use
**Explore demo credentials** on the sign-in screen. Public registration is
limited to token holders. Privileged demo roles use the seeded accounts.

| Role | What they do |
|---|---|
| `admin` | Approves bots, views platform revenue |
| `tech_company` | Submits trading bots; a placeholder pool receives the modeled tech allocation |
| `governance_company` | Oversees bots, submits audit reports, manages voting |
| `token_holder` | Buys RST tokens, votes, and receives a proportional simulated public-pool payout |

Each new user gets **$10,000 simulated wallet balance** on creation.

### Step 2 — Submit a bot (tech_company)

Navigate to **Tech Dashboard** → Submit New Bot.

- Choose a strategy (`simple_ma`, `rsi`, `bollinger_bands`, `macd`, `momentum`)
- Set strategy parameters (e.g. RSI period, MA windows)
- Bot is created with status `pending_approval`

### Step 3 — Approve the bot (admin)

Navigate to **Admin Dashboard** → pending bots list → Approve.

Status changes to `approved`. The bot can now be backtested.

### Step 4 — Run a backtest (Bot Arena)

Navigate to **Bot Arena** → Single Bot Backtest or Arena (multiple bots).

Options:
- **Symbol**: BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT (Binance) or 12 NSE India symbols
- **Data source**: `mock` (random price walk, reproducible when a seed is supplied through the API) or `live` (historical Binance/NSE data)
- **Candles**: number of OHLCV bars to replay (10–1000)
- **Starting cash**: simulated portfolio size (default $10,000)

After running, you see:
- Final PnL, End Cash, Sharpe Ratio, Max Drawdown, Win Rate
- **Buy & Hold** benchmark — what a passive investor would have made on the same data
- **Alpha** — bot's PnL minus the benchmark (positive = bot beat passive)
- Equity curve chart (portfolio value over time)
- Trade log (BUY / SELL records with reasons) and per-candle equity records

### Step 5 — Initialize tokens (admin or tech_company)

Sign in as admin, open **Tokenomics**, and select **Initialize Tokens** on the
bot's card. Alternatively, an admin or the owning tech company can call
`POST /tokenomics/init` with `bot_id`. This creates **1,000,000 simulated RST**:

```
700,000 RST → public_pool   (available for investors to buy)
150,000 RST → tech_wallet   (tech company's allocation)
150,000 RST → gov_wallet    (governance company's allocation)
```

Cost: 1 RST = $0.01 (simulated).

### Step 6 — Buy tokens (token_holder)

Navigate to **Market Dashboard** → click a bot card → Buy button.

- Each RST costs $0.01; new purchases use whole positive tokens
- Purchase deducts from wallet balance
- Tokens move from `public_pool` to the investor's address in the `tokens` table
- New purchases are unavailable if a bot is deactivated; existing simulated
  holdings can still be sold back.

### Step 7 — Distribute revenue (admin or governance_company)

Sign in as admin, open **Tokenomics**, and enter a revenue amount on the bot's
card. This is user-entered simulated revenue, not revenue calculated from the
backtest. The screen uses the current UTC quarter; an admin or governance
company can also supply a quarter through `POST /tokenomics/distribute`.

Before rounding, the distributor targets this split:

```
distributable = total_revenue × (1 − PLATFORM_FEE)
             = total_revenue × 0.98

public_share  = distributable × 0.70
tech_share    = distributable × 0.15
gov_share     = distributable × 0.15
```

New simulated distributions allocate whole cents by largest remainder and
split each pool among holders to 0.0001 cash units. Remainder ties use a fixed
pool order and then holder-address order. Historical events are not rewritten.
The 2% platform fee is rounded to cents before allocating the pools.
The `public_pool`, `tech_wallet`, and `gov_wallet` are placeholders; their
recorded allocations do not credit a registered user's wallet.

Each registered holder's approximate pre-rounding share is:
```
payout = public_share × (investor_rst_balance / total_public_rst)
```

Payouts are credited to user wallet balances immediately.

### Step 8 — View earnings (token_holder)

Navigate to **Market Dashboard** → My Portfolio → My Earnings tab.

Shows per-bot earnings by quarter, total earned, RST balance.

### Step 9 — Sell tokens (token_holder)

Navigate to **Market Dashboard** → My Portfolio → Sell button.

```
proceeds = tokens_sold × RST_PRICE × (1 − EXIT_FEE)
         = tokens_sold × 0.01 × 0.98
```

The simulated 2% exit fee is deducted from proceeds; the platform-revenue
dashboard does not include exit fees. Tokens return to `public_pool`.

### Step 10 — Submit satisfaction votes

Navigate to **Governance** → select a bot → Submit Vote.

- The signed-in account must have a positive simulated RST balance for the bot
- The server records the account's token balance at vote time
- Choose: Satisfied / Not Satisfied
- Specify which quarter (e.g. `2026-Q2`)

### Step 11 — Close a poll and check stage

Sign in as admin or governance company, then navigate to **Governance** →
Close Poll and enter the quarter. An empty poll cannot be closed.

The system:
1. Calculates `satisfaction_rate = satisfied_weight / total_weight`
2. Records the poll result
3. Calculates the current stage from the poll history

The historical `stage_at_close` value is the stage before that poll's result.
Token balances can be transferred after a vote, so the same tokens can be
counted again; this is a simulation, not secure or binding governance.

### Step 12 — Audit a Stage 2 bot (governance_company)

If a bot reaches Stage 2 (two consecutive failed quarters), an amber banner appears.

Fill in the Audit Report form:
- Quarter, Severity (low / medium / high)
- Findings (what went wrong)
- Recommendations (what should be done)

Submitted audits are stored in `governance_audits` and visible on the bot's governance card.

### Step 13 — View the leaderboard

Navigate to **Leaderboard**. Strategies ranked by average Sharpe ratio.

Columns: Rank, Strategy, Runs, Avg Sharpe, Avg PnL, **Avg Alpha**, Best PnL, Avg Win Rate.

---

## Trading Strategies — Formulas

All strategies inherit `BaseStrategy` and implement `on_candle(candles, portfolio) -> Action`. They only ever see `candles[:i+1]` — no lookahead.

Desired BUY signal size (applies to all strategies when cash is available):
```
quantity = (portfolio.cash × MAX_POSITION_SIZE) / current_price
         = (portfolio.cash × 0.30) / current_price
```

Survival Lab may reduce the eventual fill for costs, available cash, or its
separate position cap. The legacy Bot Arena uses different fill assumptions.

### 1. Simple Moving Average (`simple_ma`)

**Signal**: Golden cross / Death cross.

```
short_MA(t) = mean(close[t-short_window+1 : t+1])
long_MA(t)  = mean(close[t-long_window+1  : t+1])

BUY  if short_MA(t-1) ≤ long_MA(t-1) AND short_MA(t) > long_MA(t), with available cash
SELL if short_MA(t-1) ≥ long_MA(t-1) AND short_MA(t) < long_MA(t), with a holding
HOLD otherwise
```

Default parameters: `short_window=5`, `long_window=20`
`long_window` candles (20 by default) are needed to calculate the averages;
the earliest possible crossover needs one additional candle (21 by default).

### 2. RSI — Relative Strength Index (`rsi`)

**Signal**: Oversold / Overbought.

RSI using the simple mean of gains and losses in the latest period:
```
delta(i) = close(i) - close(i-1)
gain(i)  = max(delta(i), 0)
loss(i)  = max(-delta(i), 0)

avg_gain = mean(gain[t-period+1 : t+1])
avg_loss = mean(loss[t-period+1 : t+1])

if avg_loss == 0: RSI = 100
otherwise:
  RS  = avg_gain / avg_loss
  RSI = 100 - (100 / (1 + RS))

BUY  if RSI < oversold   (default: 30) AND cash is available
SELL if RSI > overbought (default: 70) AND holding > 0
HOLD otherwise
```

Default parameters: `period=14`, `oversold=30`, `overbought=70`
Minimum candles required: `period + 1` (15)
The zero-loss rule also makes RSI 100 when all prices are flat; with a
holding and the default thresholds, that produces a SELL signal.

### 3. Bollinger Bands (`bollinger_bands`)

**Signal**: Price touches lower or upper band.

```
history = close[t-window : t]                  ← excludes current close
middle = mean(history)
σ      = sqrt( mean( (history[i] - middle)² ) )   ← population std dev

upper  = middle + num_std × σ
lower  = middle - num_std × σ

if close(t) ≤ lower: BUY if cash is available; otherwise HOLD
else if close(t) ≥ upper: SELL if holding > 0; otherwise HOLD
else: HOLD
```

Default parameters: `window=20`, `num_std=2.0`
Minimum candles required: `window + 1` (21)
When the preceding prices are flat and the current close equals both bands,
the lower-band condition is checked first, so it can produce a BUY even if a
position is already held.

### 4. MACD — Moving Average Convergence Divergence (`macd`)

**Signal**: MACD line crosses signal line.

```
EMA(values, period):
  k   = 2 / (period + 1)
  seed = mean(values[:period])
  EMA(t) = values(t) × k + EMA(t-1) × (1 - k)

fast_EMA  = EMA(close, fast)    default fast=12
slow_EMA  = EMA(close, slow)    default slow=26
MACD_line = fast_EMA - slow_EMA

signal_line = EMA(MACD_line, signal)   default signal=9
histogram   = MACD_line - signal_line

BUY  if histogram(t-1) ≤ 0 AND histogram(t) > 0   ← bullish crossover, cash available
SELL if histogram(t-1) ≥ 0 AND histogram(t) < 0   ← bearish crossover, holding > 0
HOLD otherwise
```

Default parameters: `fast=12`, `slow=26`, `signal=9`
Minimum candles required for a crossover: `slow + signal = 35` with defaults.

### 5. Momentum (`momentum`)

**Signal**: Price rose ≥ threshold% over window, exit on stop-loss.

```
gain = (close(t) - close(t - window + 1)) / close(t - window + 1)

SELL if held > 0, entry_price is known, and (close(t) - entry_price) / entry_price ≤ -stop_loss
else BUY if gain ≥ threshold (default: 2%) and cash is available
HOLD otherwise
```

Default parameters: `window=10`, `threshold=0.02`, `stop_loss=0.03`
Minimum candles required: `window` (10)
The stop-loss check takes precedence over a new BUY. The legacy Bot Arena
records the latest BUY signal's close as the entry; Survival Lab tracks the
latest actual simulated BUY fill instead. Neither uses average cost here.

---

## Engine — How Backtesting Works

### BotRunner (`backend/engine/bot_runner.py`)

Tick-by-tick execution loop:

```python
for i in range(len(candles)):
    window = candles[:i + 1]          # strategy sees only past + current
    action = strategy.on_candle(window, portfolio)
    portfolio, record = _execute(action, candle, portfolio)
```

Portfolio state after each tick:
```
cash after BUY  = cash - (price × quantity)
cash after SELL = cash + (price × quantity_sold)

position_value = sum(qty × current_price  for all held positions)
PnL(t)         = (cash(t) + position_value(t)) - starting_cash
```

### Market Feeds

| Source | Used when | Description |
|---|---|---|
| `MockMarketFeed` | `data_source="mock"` | Uniform ±2% random walk, reproducible with a seed |
| `CCXTFeed` | `data_source="live"`, crypto symbol | Real OHLCV from Binance public API via CCXT (read-only, no API key) |
| `YFinanceFeed` | `data_source="live"`, `.NS` / `^` symbol | Historical OHLCV for Indian symbols via Yahoo Finance |

Yahoo Finance does not provide native 4-hour candles through this integration;
choose 1 hour or 1 day for those symbols. Historical runs can use fewer bars
than requested when the provider supplies less data; new history records store
the actual count. Older saved rows are not rewritten. Arena results use each
market's quote units, with no currency conversion or exposure matching.

### Buy-and-Hold Benchmark

Computed on every backtest from the same candle sequence:
```
shares          = starting_cash / close(first_candle)
benchmark_PnL   = (close(last_candle) - close(first_candle)) × shares

alpha           = bot_final_PnL - benchmark_PnL
```

---

## Performance Metrics — Formulas

Computed by `backend/engine/backtester.py` after `BotRunner.run()` completes.

### Final PnL
```
final_PnL = (cash_final + position_value_final) - starting_cash
```

### Win Rate
In the legacy Bot Arena, the fraction of nonzero sell fills whose price exceeds
the weighted-average entry price of the position. Multiple buys and partial
sells update the remaining cost basis. Legacy fills exclude costs.
```
win_rate = profitable_sell_fills / nonzero_sell_fills
```

### Sharpe Ratio
Risk-adjusted return, computed from the per-tick PnL series:
```
equity(t)  = starting_cash + PnL(t)
returns(t) = (equity(t) - equity(t-1)) / equity(t-1)
mean_r     = mean(returns)
std_r      = sample_std(returns)

Sharpe = mean_r / std_r × sqrt(252)   (if std_r > 0, else 0)
```

This legacy estimate assumes 252 periods per year regardless of the data
timeframe and should not be treated as a universal quality or safety rating.

### Max Drawdown
Largest peak-to-trough drop in portfolio value:
```
equity(t) = starting_cash + PnL(t)
peak(t)   = max(equity[0..t])
drawdown(t) = (equity(t) - peak(t)) / peak(t)   ← negative number

max_drawdown = min(drawdown)   ← most negative value
```

Reported as a fraction (e.g. -0.12 = 12% drawdown).

### Risk Rating (Bot Profile)
Derived from avg Sharpe and avg drawdown across all backtest runs:
```
"Low"    if avg_sharpe ≥ 1.0  AND abs(avg_drawdown) ≤ 0.15
"Medium" if avg_sharpe ≥ 0.3  AND abs(avg_drawdown) ≤ 0.30
"High"   otherwise
"Unrated" if no runs or either metric is unavailable
```

This is a historical heuristic, potentially mixing markets and timeframes;
it is not a prediction of risk or a substitute for analysis.

---

## Tokenomics — Economic Model

### RST Allocation (per bot)

```
TOTAL_RST = 1,000,000

public_pool  = 700,000  (70%)   → available for investors to buy
tech_wallet  = 150,000  (15%)   → tech company that built the bot
gov_wallet   = 150,000  (15%)   → governance company overseeing the bot
```

Token price (Phase 1 simulation):
```
RST_PRICE = $0.01 per token
```

### Revenue Distribution Formula

On each `POST /tokenomics/distribute`, before rounding:
```
distributable = total_revenue × (1 - PLATFORM_FEE)
              = total_revenue × 0.98        ← 2% to AXIOM platform

public_pool_share = distributable × 0.70
tech_share        = distributable × 0.15
gov_share         = distributable × 0.15

Each investor payout:
  payout(investor) ≈ public_pool_share × (investor_rst / total_public_rst)
```

`total_public_rst` includes the unsold `public_pool`. Allocations are rounded as
described above. Registered holders' simulated wallets are credited; placeholder
pool allocations are recorded without a wallet credit. Events are stored in the
`distribution_events` and `distribution_payouts` tables.

### Token Purchase

```
cost = tokens_to_buy × RST_PRICE
     = tokens_to_buy × $0.01

user.wallet_balance -= cost
tokens table: public_pool balance -= tokens_to_buy
tokens table: investor balance    += tokens_to_buy
```

### Token Sell-Back (Exit Fee)

```
gross_proceeds = tokens_to_sell × RST_PRICE
exit_fee       = gross_proceeds × EXIT_FEE
               = gross_proceeds × 0.02

net_proceeds   = gross_proceeds - exit_fee
              = gross_proceeds × 0.98

user.wallet_balance += net_proceeds
tokens table: investor balance    -= tokens_to_sell
tokens table: public_pool balance += tokens_to_sell
```

The simulated exit fee is deducted from proceeds and is not included in the
platform-revenue dashboard's distribution-fee total.

---

## Governance — Progressive Decentralisation

### Satisfaction Voting

Token holders submit weighted votes each quarter:
```
satisfaction_rate = satisfied_weight / total_weight
```

### Stage Transition Logic

```
Stage 1 (Normal):
  → No action if satisfaction_rate ≥ 0.50 or streak < 2

Stage 1 → Stage 2 (Review):
  Trigger: satisfaction_rate < 0.50 for 2 CONSECUTIVE quarters
  Effect: simulated Review indicator; audit reports may be submitted

Stage 2 → Stage 3 (Community):
  Trigger: satisfaction_rate < 0.50 for 4 CONSECUTIVE quarters
  Effect: simulated Community indicator; no actual control transfer

Stage 2 / 3 → Stage 1:
  Trigger: satisfaction_rate ≥ 0.50 (community satisfied again)
  Effect: stage resets to Normal
```

The current indicator is derived from closed poll history. Missing or empty
quarters break a failed streak. There is no separate immutable transition log,
and the SQLite records are not tamper-proof.

### Audit Reports (Stage 2+)

When a bot is in Stage 2 or Stage 3, governance companies can submit formal audit reports:
```
POST /governance/{bot_id}/audit
  Fields: quarter, finding, recommendation, severity (low/medium/high)
```

Stored in `governance_audits` table, visible per bot in the Governance page.

---

## Role-Based Access

| Role | Permissions |
|---|---|
| `admin` | Approve/reject bots, view all users, view platform revenue |
| `tech_company` | Submit bots, view modeled tech-pool allocations, run backtests |
| `governance_company` | Close polls, submit audit reports, run backtests; vote with a positive RST balance |
| `token_holder` | Buy/sell RST, vote with a positive RST balance, view own portfolio and earnings, run backtests |

All routes requiring auth use JWT Bearer tokens. 8-hour token expiry.

---

## API Reference

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create a token-holder account |
| POST | `/auth/login` | Login, get JWT |
| GET | `/auth/me` | Current user profile |

### Bots
| Method | Path | Description |
|---|---|---|
| POST | `/bots/` | Submit a new bot |
| GET | `/bots/` | List all bots |
| GET | `/bots/{id}` | Get bot details |
| DELETE | `/bots/{id}` | Deactivate bot |
| GET | `/bots/{id}/profile` | Full due-diligence profile (risk rating, token distribution, recent runs) |

### Arena
| Method | Path | Description |
|---|---|---|
| POST | `/arena/run` | Run multiple bots head-to-head |
| POST | `/arena/backtest/{id}` | Single-bot backtest |
| GET | `/arena/history` | Backtest run history (filterable) |
| GET | `/arena/history/{run_id}` | Single run details |
| GET | `/arena/leaderboard` | Strategy rankings by Sharpe + Alpha |

### Tokenomics
| Method | Path | Description |
|---|---|---|
| POST | `/tokenomics/init` | Mint RST for a bot (70/15/15 split) |
| GET | `/tokenomics/{bot_id}/balances` | Token balances per holder |
| POST | `/tokenomics/purchase` | Buy RST tokens |
| POST | `/tokenomics/sell` | Sell RST tokens (2% exit fee) |
| POST | `/tokenomics/distribute` | Distribute revenue (2% platform fee + 70/15/15) |
| GET | `/tokenomics/my-holdings` | My RST holdings |
| GET | `/tokenomics/my-earnings` | My payout history |

### Governance
| Method | Path | Description |
|---|---|---|
| POST | `/governance/vote` | Submit satisfaction vote |
| POST | `/governance/poll/close` | Close quarter poll, trigger stage check |
| GET | `/governance/{id}/stage` | Current stage for a bot |
| GET | `/governance/{id}/polls` | Poll history |
| POST | `/governance/{id}/audit` | Submit audit report (Stage 2+ only) |
| GET | `/governance/{id}/audits` | List audit reports |

### Admin
| Method | Path | Description |
|---|---|---|
| GET | `/admin/stats` | Platform-wide statistics |
| GET | `/admin/users` | All users |
| POST | `/admin/bots/{id}/approve` | Approve a pending bot |
| POST | `/admin/bots/{id}/reject` | Reject a pending bot |
| GET | `/admin/platform-revenue` | Total platform fees collected |

### Tech
| Method | Path | Description |
|---|---|---|
| GET | `/tech/my-dashboard` | Tech company's bots + earnings summary |

---

## Database Schema

All tables use SQLite. New columns added via `ALTER TABLE` in `init_db()`.

| Table | Key columns |
|---|---|
| `users` | id, email, password_hash, role, company_name, wallet_balance, is_active |
| `bots` | id, name, strategy_name, params (JSON), status, tech_company_id, description |
| `trades` | id, bot_id, symbol, action_type, quantity, price, timestamp, reason, cash_after, pnl |
| `tokens` | id, bot_id, holder_address, balance, holder_type |
| `governance_votes` | id, bot_id, quarter, voter_address, vote, token_weight, timestamp |
| `satisfaction_polls` | id, bot_id, quarter, satisfied_weight, total_weight, satisfaction_rate, stage_at_close, closed_at |
| `backtest_runs` | id, bot_id, symbol, timeframe, data_source, final_pnl, benchmark_pnl, sharpe_ratio, max_drawdown, win_rate, created_at |
| `distribution_events` | id, bot_id, total_revenue, platform_fee, distributable, public_share, tech_share, gov_share, quarter |
| `distribution_payouts` | id, event_id, bot_id, holder_address, rst_balance, amount |
| `governance_audits` | id, bot_id, quarter, submitted_by, finding, recommendation, severity, created_at |

---

## Key Design Decisions

**Are trade histories permanently recorded?**
The schema defines a trades table, but the current backtest API does not persist
each trade to it. Survival Lab returns decisions in its response and export;
neither is independently verified or protected against modification.

**Why blind backtesting?**
AXIOM feeds built-in strategies candles up to the current point. This prevents
the strategy from seeing later candles in the replay, but does not prevent
overfitting during strategy selection or parameter tuning.

**Why 2% platform fee and 2% exit fee?**
These are illustrative simulation parameters. The distribution fee is recorded;
the exit fee is deducted from simulated proceeds. Neither represents real funds.

**Why progressive governance?**
The staged indicator illustrates one possible oversight mechanism. The prototype
does not transfer control or demonstrate binding democratic accountability.

---

## Built by

**Deepankar Senapati** — Ocean AI Intern | Founded March 2026
