# AXIOM — Technical Reference Document

> Autonomous eXchange for Intelligent Operations & Markets  
> Founder: Deepankar Senapati | Phase 1 — Local MVP  
> Stack: Python 3.11 · FastAPI · SQLAlchemy · SQLite · React · Vite · TailwindCSS

---

## 1. What AXIOM Is

AXIOM is a **bot-only algorithmic trading exchange**. No human ever places an order. Every market position is opened and closed by a registered algorithm. The platform has three interconnected systems:

1. **Trading Engine** — simulated market environment where strategies execute against real or mock historical price data, producing a fully auditable, immutable trade log.
2. **Tokenomics Layer** — every approved bot's revenue is split among token holders (70% public / 15% tech company / 15% governance company) through Revenue Share Tokens (RST).
3. **Governance Layer** — a three-stage progressive governance system that automatically transfers control from a central governance company to token holders if a bot consistently underperforms.

The platform is designed for Phase 1 simulation only. All money is fake, all tokens are SQLite rows, all "blockchain" is a database table. Phase 2 will migrate to real smart contracts; the business logic is identical.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────┐
│                    FastAPI Backend                   │
│  /auth  /bots  /arena  /tokenomics  /governance      │
└────────────────────┬─────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                        │
┌───────▼──────────┐    ┌────────▼────────────┐
│  Trading Engine  │    │  Tokenomics Layer   │
│  BotRunner       │    │  Ledger             │
│  Backtester      │    │  Distributor        │
│  Arena (multi)   │    └────────┬────────────┘
│  MarketFeed      │             │
└───────┬──────────┘    ┌────────▼────────────┐
        │               │  Governance Layer   │
        │               │  VotingManager      │
        └───────────────►  StageManager       │
                        └─────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     SQLite Database     │
                    │  (axiom.db — 12 tables) │
                    └─────────────────────────┘
```

### Module Responsibilities

| Module | Owns | Never Touches |
|--------|------|---------------|
| `engine/bot_runner.py` | Execute strategy tick-by-tick | Token balances, governance |
| `engine/backtester.py` | Replay history through BotRunner, compute metrics | Strategy internals |
| `engine/arena.py` | Run multiple bots simultaneously, persist results | Ranking or scoring |
| `engine/market_feed.py` | Generate mock OHLCV candles | Trading logic |
| `tokenomics/distributor.py` | Split revenue 70/15/15 | Trading logic |
| `tokenomics/ledger.py` | Read/write RST balances in `tokens` table | Distribution math |
| `governance/voting.py` | Record votes, close polls, compute satisfaction rate | Stage transitions |
| `governance/stages.py` | Determine current stage from poll history | Vote recording |
| `bots/strategies/` | Implement `on_candle()` signal logic | Execution, portfolio |
| `api/` | FastAPI routes, request/response validation | Business logic |
| `db/models.py` | SQLAlchemy ORM models | Business logic |

---

## 3. The BaseStrategy Contract

Every trading algorithm must implement exactly one method:

```python
class BaseStrategy:
    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        raise NotImplementedError
```

**The fundamental law:** `on_candle` receives only candles up to and including the current time step. It never receives future data. The BotRunner enforces this by slicing `candles[:i+1]` before calling the strategy.

```python
# BotRunner tick loop (bot_runner.py:19-27)
for i in range(len(candles)):
    window = candles[: i + 1]          # strategy sees history only
    action = self.strategy.on_candle(window, portfolio)
    portfolio, record = self._execute(action, candle, portfolio)
```

This means the same strategy produces the same result on the same data every time. Backtests are deterministic.

---

## 4. Trading Engine — Mechanics

### 4.1 PnL Calculation

PnL is computed on every tick (every candle, not just on trades):

```
equity(t) = cash(t) + Σ(positions[symbol] × current_price)
PnL(t)    = equity(t) - starting_cash
```

This means PnL fluctuates every candle as prices move, even between trades. The `TradeRecord` stores the PnL at the moment of action.

### 4.2 Position Sizing

Every strategy uses the same position sizing rule from `config.py`:

```
quantity = (portfolio.cash × MAX_POSITION_SIZE) / current_price
MAX_POSITION_SIZE = 0.30
```

A bot never risks more than 30% of available cash on a single trade. This is a hard cap, not advisory.

### 4.3 Trade Execution

| Action | Effect |
|--------|--------|
| BUY | `cash -= price × quantity`; `positions[symbol] += quantity` |
| SELL | `cash += price × min(quantity, held)`; `positions[symbol] -= executed_qty` |
| HOLD | No state change; record written with reason |

Partial sells are supported: if a strategy tries to sell more than held, only the held amount is sold.

### 4.4 Trade Log — Append-Only Invariant

Every candle produces exactly one `TradeRecord`. Records are NEVER updated or deleted. This is the audit backbone of the platform — governance token holders can inspect the complete decision history of any bot.

```python
# db/models.py — enforced by code comment and architecture
class DBTrade(Base):
    """APPEND-ONLY. Never UPDATE or DELETE rows in this table."""
```

---

## 5. Performance Metrics — All Formulas

### 5.1 Final PnL

```
final_pnl = last_record.pnl
           = (cash_final + position_value_final) - starting_cash
```

### 5.2 Win Rate

Computed from completed BUY→SELL round trips only. A "win" is when the SELL price exceeds the BUY price for that lot:

```
win_rate = profitable_round_trips / total_completed_round_trips
```

Range: [0.0, 1.0]. HOLD records are not counted. If no round trips completed, win_rate = 0.0.

### 5.3 Sharpe Ratio (Annualised)

Computed from the per-tick equity series (every candle, not just trades):

```
equity(t)  = starting_cash + pnl(t)
return(t)  = (equity(t) - equity(t-1)) / equity(t-1)

mean_r     = Σ return(t) / n
std_r      = sqrt( Σ(return(t) - mean_r)² / (n-1) )   ← sample std dev

sharpe     = (mean_r / std_r) × sqrt(252)              ← annualised for daily candles
```

The `sqrt(252)` annualisation factor assumes daily candles (252 trading days/year). For hourly candles this would be `sqrt(252 × 6.5)`, but for Phase 1 the annualisation is kept as 252 for simplicity.

### 5.4 Maximum Drawdown

```
peak(t)       = max(equity(0), equity(1), ..., equity(t))
drawdown(t)   = (equity(t) - peak(t)) / peak(t)
max_drawdown  = min(drawdown(t)) for all t
```

Always a negative number (or zero if equity never declined). A value of -0.15 means the worst point was 15% below the prior peak.

### 5.5 Risk Rating

Derived from max_drawdown at the API layer:

| Max Drawdown | Risk Rating |
|---|---|
| > -5% | Low |
| -5% to -15% | Medium |
| < -15% | High |
| No runs yet | Unrated |

### 5.6 Buy-and-Hold Benchmark

Every backtest is compared to the passive buy-and-hold strategy on the same price series:

```
shares         = starting_cash / first_candle_close
benchmark_pnl  = (last_candle_close - first_candle_close) × shares
```

This represents how much money a passive investor would have made buying at the start and selling at the end with the same starting capital.

### 5.7 Alpha

Alpha measures a bot's outperformance vs. the benchmark:

```
alpha = final_pnl - benchmark_pnl
```

Positive alpha means the bot beat buy-and-hold. Negative alpha means a passive investor would have done better.

---

## 6. Trading Strategies — Implemented Algorithms

### 6.1 Simple Moving Average (SMA) Crossover

**File:** `backend/bots/strategies/simple_ma.py`  
**Strategy key:** `simple_ma`  
**Default params:** `short_window=5`, `long_window=20`

**Formula:**
```
SMA_short(t) = mean(close[t-short_window+1 : t+1])
SMA_long(t)  = mean(close[t-long_window+1 : t+1])

Golden cross (BUY):  SMA_short(t-1) ≤ SMA_long(t-1)  AND  SMA_short(t) > SMA_long(t)
Death cross  (SELL): SMA_short(t-1) ≥ SMA_long(t-1)  AND  SMA_short(t) < SMA_long(t)
```

The crossover is detected by comparing current MAs to the previous candle's MAs. This prevents acting on MAs that were already crossed (avoids re-entry on the same signal).

**Warm-up:** Requires at least `long_window` candles before producing any signal.

---

### 6.2 Relative Strength Index (RSI)

**File:** `backend/bots/strategies/rsi.py`  
**Strategy key:** `rsi`  
**Default params:** `period=14`, `oversold=30`, `overbought=70`

**Formula (Wilder's smoothed RSI):**
```
delta(t) = close(t) - close(t-1)

avg_gain = mean(max(delta, 0) for t in window[-period:])
avg_loss = mean(max(-delta, 0) for t in window[-period:])

RS  = avg_gain / avg_loss
RSI = 100 - (100 / (1 + RS))

BUY  when RSI < oversold   (default 30)
SELL when RSI > overbought (default 70) AND held > 0
```

**Edge case:** If `avg_loss = 0`, RSI = 100 (no losing candles in window → maximally overbought).

**Warm-up:** Requires `period + 1` candles (need one delta calculation per period candle).

---

### 6.3 Bollinger Bands

**File:** `backend/bots/strategies/bollinger_bands.py`  
**Strategy key:** `bollinger_bands`  
**Default params:** `window=20`, `num_std=2.0`

**Formula (population standard deviation):**
```
middle(t) = mean(close[t-window : t])
variance  = Σ(close[i] - middle)² / window    ← population std dev (divide by N, not N-1)
std       = sqrt(variance)

upper(t)  = middle(t) + num_std × std
lower(t)  = middle(t) - num_std × std

BUY  when close(t) ≤ lower(t-1)              ← price touches lower band
SELL when close(t) ≥ upper(t-1) AND held > 0 ← price touches upper band
```

Bands are computed on the previous window (excluding current candle) to avoid look-ahead bias.

**Warm-up:** Requires `window + 1` candles.

---

### 6.4 MACD (Moving Average Convergence Divergence)

**File:** `backend/bots/strategies/macd.py`  
**Strategy key:** `macd`  
**Default params:** `fast=12`, `slow=26`, `signal=9`

**Formula:**
```
EMA(values, period):
  k   = 2 / (period + 1)
  EMA seeded with SMA of first `period` values
  EMA(t) = close(t) × k + EMA(t-1) × (1 - k)

MACD_line(t)   = EMA(close, fast)(t) - EMA(close, slow)(t)
Signal_line(t) = EMA(MACD_line, signal)(t)
Histogram(t)   = MACD_line(t) - Signal_line(t)

Bullish crossover (BUY):  Histogram(t-1) ≤ 0  AND  Histogram(t) > 0
Bearish crossover (SELL): Histogram(t-1) ≥ 0  AND  Histogram(t) < 0  AND  held > 0
```

**Warm-up:** Requires `slow + signal - 1` candles to produce the first signal (34 candles with defaults).

---

### 6.5 Momentum with Stop-Loss

**File:** `backend/bots/strategies/momentum.py`  
**Strategy key:** `momentum`  
**Default params:** `window=10`, `threshold=0.02`, `stop_loss=0.03`

**Formula:**
```
gain(t) = (close(t) - close(t - window)) / close(t - window)

Momentum BUY:  gain(t) ≥ threshold (default 2%)
Stop-loss SELL: held > 0  AND  (close(t) - entry_price) / entry_price ≤ -stop_loss (default -3%)
```

Entry price is recorded at the moment of the BUY. Stop-loss takes priority over momentum signals on every subsequent tick.

**Warm-up:** Requires `window` candles.

---

## 7. Market Data — Price Sources

### 7.1 Mock Market Feed

Random-walk OHLCV generator. Used when `data_source = "mock"`.

```
price(0)   = start_price
price(t)   = price(t-1) × (1 + N(0, 0.02))    ← ±2% Gaussian random walk
open       = previous close
high       = max(open, close) × (1 + |N(0, 0.005)|)
low        = min(open, close) × (1 - |N(0, 0.005)|)
volume     = Uniform(1000, 10000)
```

With a fixed `seed`, results are fully deterministic and reproducible.

### 7.2 CCXT Live Historical Data

Fetches real OHLCV from Binance public API (no API key required, no orders). Used when `data_source = "ccxt"` or `data_source = "live"`.

- Exchange: Binance (public endpoints only)
- Supported timeframes: `1h`, `4h`, `1d`
- Falls back to mock data if network unavailable
- Returns the most recent `n` candles for the requested symbol and timeframe

---

## 8. Tokenomics — Economic Model

### 8.1 RST Token Structure

Every approved bot gets exactly **1,000,000 Revenue Share Tokens (RST)**:

| Pool | Allocation | Tokens |
|------|-----------|--------|
| Public (investors) | 70% | 700,000 RST |
| Tech Company | 15% | 150,000 RST |
| Governance Company | 15% | 150,000 RST |

**RST Price (Phase 1):** $0.01 per RST (simulated, fixed)

### 8.2 Revenue Distribution

When a bot generates revenue (e.g., backtest PnL is distributed as a reward event):

```
platform_fee  = total_revenue × 0.02         ← 2% retained by AXIOM
distributable = total_revenue - platform_fee  ← 98% distributed

public_share  = distributable × 0.70
tech_share    = distributable × 0.15
gov_share     = distributable × 0.15
```

Each RST holder within a pool receives a pro-rata share based on their fraction of that pool's total balance:

```
payout(holder) = pool_share × (holder_rst_balance / total_pool_rst_balance)
```

**Example:**  
Revenue = $1,000. Platform fee = $20. Distributable = $980.  
Public pool share = $686. If investor A holds 100,000 of 700,000 public RST:  
`payout(A) = $686 × (100,000 / 700,000) = $98`

### 8.3 Token Purchase

A user (token holder role) buys RST from the public pool:

```
cost = amount_rst × RST_PRICE ($0.01)
user.wallet_balance -= cost
public_pool.balance -= amount_rst
user.rst_balance[bot_id] += amount_rst
```

The public pool has a finite supply (700,000 RST). Once exhausted, no more can be purchased.

### 8.4 Token Sell-Back

A token holder sells RST back to the public pool:

```
exit_fee = amount_rst × RST_PRICE × EXIT_FEE     ← 2% fee
proceeds = (amount_rst × RST_PRICE) - exit_fee
user.wallet_balance += proceeds
public_pool.balance += amount_rst
user.rst_balance[bot_id] -= amount_rst
```

The 2% exit fee discourages rapid in-and-out trading.

---

## 9. Governance — Progressive Control Model

### 9.1 Stage Definitions

| Stage | ID | Trigger | Controller |
|-------|----|---------|-----------|
| Normal | 1 | Default — no polls or satisfaction ≥ 50% | Governance company |
| Review | 2 | Satisfaction < 50% for 2 consecutive quarters | Governance company on notice; audits required |
| Community | 3 | Satisfaction < 50% for 4 consecutive quarters | Direct token-holder control |

### 9.2 Stage Transition Logic

After each quarterly poll closes, the `StageManager` evaluates the trailing poll history:

```python
def _trailing_below(rates, threshold=0.50) -> int:
    count = 0
    for rate in reversed(rates):   # iterate newest → oldest
        if rate < threshold:
            count += 1
        else:
            break                   # stop at first passing quarter
    return count

if trailing_below >= 4:  → Stage 3 (COMMUNITY)
if trailing_below >= 2:  → Stage 2 (REVIEW)
else:                    → Stage 1 (NORMAL)
```

Transitions are **automatic**. No admin action required. If a previously failing bot recovers (satisfaction ≥ 50%), the trailing count resets and the stage drops back to Normal.

### 9.3 Satisfaction Rate Formula

```
satisfaction_rate = satisfied_token_weight / total_token_weight
```

Where `token_weight` is the number of RST tokens held by the voter. Votes are weighted by token holdings — holders with more skin in the game have more influence.

**One vote per voter per quarter per bot.** Duplicate vote attempts return HTTP 409.

### 9.4 Governance Audit System

When a bot is in Stage 2 or Stage 3, governance company users can submit structured audit reports:

```
POST /governance/{bot_id}/audit
{
  "quarter": "2026-Q2",
  "finding": "Strategy over-exposes to volatile assets",
  "recommendation": "Reduce MAX_POSITION_SIZE to 0.15",
  "severity": "high" | "medium" | "low"
}
```

Audits are stored immutably (append-only like trades) and publicly viewable via `GET /governance/{bot_id}/audits`.

---

## 10. Role-Based Access Control

| Role | Can Do |
|------|--------|
| `admin` | Approve/reject bot submissions; view all users; platform-wide stats |
| `tech_company` | Submit bots; run backtests on own bots; view tech dashboard |
| `governance_company` | Submit votes; close polls; submit audits; view governance page |
| `token_holder` | Buy/sell RST tokens; view portfolio; cast governance votes |

All endpoints require JWT Bearer authentication (except `/auth/login` and `/auth/register`). Tokens expire after 480 minutes (8 hours).

---

## 11. Authentication — JWT Flow

```
POST /auth/register  → creates user, stores bcrypt-hashed password
POST /auth/login     → validates credentials, returns signed JWT
GET  /auth/me        → returns current user profile from token claims
```

JWT payload: `{ "sub": user_email, "exp": <expiry> }`  
Algorithm: HS256  
Secret: `AXIOM_SECRET_KEY` environment variable (falls back to dev key with warning)

---

## 12. Bot Lifecycle

```
tech_company submits bot
        ↓
status: pending_approval
        ↓
admin reviews (GET /admin/bots → PATCH /admin/bots/{id}/approve or /reject)
        ↓
status: approved
        ↓
admin initializes tokens (POST /tokenomics/init-tokens)
status: live
        ↓
backtests run (POST /arena/run or POST /bots/{id}/backtest)
        ↓
revenue distributed (POST /tokenomics/distribute-revenue)
        ↓
token holders vote (POST /governance/vote → POST /governance/poll/close)
        ↓
stage evaluated automatically
```

---

## 13. Database Schema

| Table | Purpose |
|-------|---------|
| `users` | All registered users (all roles) |
| `bots` | Registered trading bots with approval status |
| `trades` | Append-only trade log (every candle action) |
| `tokens` | RST token balances per holder per bot |
| `backtest_runs` | Persisted backtest results with all metrics |
| `satisfaction_polls` | Closed quarterly polls with satisfaction rates |
| `governance_votes` | Individual votes (voter, bot, quarter, weight) |
| `governance_audits` | Audit reports submitted for Stage 2+ bots |
| `distribution_events` | Revenue distribution summaries per quarter |
| `distribution_payouts` | Individual payout records per holder per event |

---

## 14. Key Constants (config.py)

| Constant | Value | Meaning |
|----------|-------|---------|
| `TOTAL_RST_PER_BOT` | 1,000,000 | RST tokens minted per bot |
| `TOKEN_PUBLIC_SHARE` | 0.70 | 70% of tokens go to public pool |
| `TOKEN_TECH_SHARE` | 0.15 | 15% to tech company |
| `TOKEN_GOV_SHARE` | 0.15 | 15% to governance company |
| `RST_PRICE` | $0.01 | Simulated RST price in Phase 1 |
| `PLATFORM_FEE` | 0.02 | 2% of every revenue distribution |
| `EXIT_FEE` | 0.02 | 2% fee on RST sell-back |
| `MAX_POSITION_SIZE` | 0.30 | Max 30% of cash per trade |
| `DEFAULT_STARTING_CASH` | $10,000 | Default backtest starting capital |
| `STAGE2_TRIGGER_THRESHOLD` | 0.50 | Satisfaction below 50% triggers stage up |
| `STAGE2_CONSECUTIVE_QUARTERS` | 2 | Quarters below threshold to reach Stage 2 |
| `STAGE3_CONSECUTIVE_QUARTERS` | 4 | Quarters below threshold to reach Stage 3 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 480 | JWT lifespan (8 hours) |

---

## 15. API Surface

| Method | Path | Role Required | Description |
|--------|------|---------------|-------------|
| POST | `/auth/register` | None | Create account |
| POST | `/auth/login` | None | Get JWT token |
| GET | `/auth/me` | Any | Current user profile |
| GET | `/bots/` | Any | List approved bots |
| POST | `/bots/` | tech_company | Submit new bot |
| GET | `/bots/{id}` | Any | Bot details |
| GET | `/bots/{id}/backtest-history` | Any | All runs for this bot |
| POST | `/bots/{id}/backtest` | Any | Run single-bot backtest |
| GET | `/admin/bots` | admin | All bots with status |
| PATCH | `/admin/bots/{id}/approve` | admin | Approve bot |
| PATCH | `/admin/bots/{id}/reject` | admin | Reject bot |
| GET | `/admin/users` | admin | All users |
| GET | `/admin/stats` | admin | Platform statistics |
| POST | `/arena/run` | Any | Multi-bot arena backtest |
| GET | `/arena/history` | Any | All backtest runs |
| GET | `/arena/history/{id}` | Any | Single run with trade records |
| GET | `/arena/leaderboard` | Any | Strategy leaderboard by Sharpe |
| POST | `/tokenomics/init-tokens` | admin | Create RST token pool for bot |
| POST | `/tokenomics/distribute-revenue` | admin | Distribute revenue to holders |
| GET | `/tokenomics/balances/{bot_id}` | Any | RST balance breakdown |
| POST | `/tokenomics/purchase` | token_holder | Buy RST tokens |
| GET | `/tokenomics/my-holdings` | token_holder | All token holdings |
| POST | `/tokenomics/sell` | token_holder | Sell RST back to pool |
| GET | `/tokenomics/my-earnings` | token_holder | Historical payouts |
| GET | `/tokenomics/platform-revenue` | admin | Total platform fees collected |
| POST | `/governance/vote` | Any (auth) | Submit quarterly vote |
| POST | `/governance/poll/close` | Any (auth) | Close quarterly poll |
| GET | `/governance/{bot_id}/stage` | Any | Current governance stage |
| GET | `/governance/{bot_id}/stage/transition` | Any | Last stage transition event |
| GET | `/governance/{bot_id}/polls` | Any | Full poll history |
| POST | `/governance/{bot_id}/audit` | governance_company | Submit audit report |
| GET | `/governance/{bot_id}/audits` | Any | All audits for bot |
| GET | `/tech/dashboard` | tech_company | Tech company analytics |
| GET | `/bots/{id}/profile` | Any | Full bot due-diligence profile |

---

## 16. Design Decisions

### Pydantic everywhere, raw dicts nowhere

All data crossing module boundaries (engine → API, engine → tokenomics, governance) is a typed Pydantic model. This makes the system auditable: every field has a name, a type, and an explicit definition.

### Strategies are stateless between runs

`BotRunner` and `Backtester` are stateless — the same inputs always produce the same outputs. Momentum strategy tracks `_entry_price` as instance state, but each Backtester instantiates a fresh strategy, so this is reset per run.

### PnL tracked on every tick, not just trades

Recording PnL on every candle (not just BUY/SELL) is what makes the Sharpe ratio and max drawdown calculations accurate. A HOLD during a market crash is a real drawdown that should appear in the metrics.

### Win rate from round trips, not ticks

Win rate counts completed BUY→SELL pairs. A SELL that was profitable vs. the cost of the matched BUY counts as a win. An open position at end-of-backtest is not counted (it's still unrealised).

### Population vs. sample standard deviation in Bollinger Bands

The Bollinger Bands implementation uses population std dev (`/ N`) rather than sample std dev (`/ (N-1)`). This matches the industry standard for Bollinger Bands as originally specified by John Bollinger.

### Alpha as a first-class metric

Every backtest result includes `benchmark_pnl` (what buy-and-hold would have returned) and `alpha` (bot's outperformance). This forces honest performance reporting — a bot that beats mock random data may still have negative alpha vs. the underlying trend.

### Governance stages are computed, not stored

The current stage is derived by inspecting the last N poll results — it is never stored in the database. This means stage history is always accurate even if polls are added retroactively, and there is no possibility of a stage mismatch between the DB and the computed state.

---

## 17. Phase 1 Boundaries

The following are **deliberately excluded** from Phase 1:

- Real blockchain / smart contracts (Phase 2)
- Real exchange orders or live trading (Phase 2)
- CCXT live orders — CCXT read-only historical data is Phase 1 (no API keys, no orders)
- KYC / AML identity verification (Phase 2)
- Email / SMS notifications (Phase 2)
- PostgreSQL — SQLite is sufficient for Phase 1
- No-code drag-and-drop bot builder UI (Phase 2)
- Real payment processing (Phase 2)
- On-chain token offerings (Phase 3)

The Phase 1 constraint is enforced via `.claude/rules/phase-guard.md`. Any request to implement Phase 2+ features is logged to `ROADMAP.md` and not implemented.
