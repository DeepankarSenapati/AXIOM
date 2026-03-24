# AXIOM Architecture

## Core Concept
- Bot-only exchange: only algorithms place orders, no humans
- Each bot's revenue is tokenized: 70% public / 15% tech company / 15% governance company
- Governance is progressive: centralised → democratic if performance fails
- Every trade logged immutably for full transparency

## The BotRunner (most important class)
- Takes a strategy config + market data stream
- Feeds data ONE candle at a time (strategy never knows if live or historical)
- Records every decision: BUY / SELL / HOLD + timestamp + price + reason
- Tracks portfolio: cash, positions, PnL
- Stateless between runs — same input always produces same output

## BaseStrategy Contract (THE LAW)
```python
class BaseStrategy:
    def on_candle(self, candle: Candle, portfolio: Portfolio) -> Action:
        # ONLY sees current + past candles. Never future. Never knows if backtest.
        raise NotImplementedError
```
All bots MUST inherit BaseStrategy. No exceptions.

## Token Model (Phase 1: SQLite simulation)
- Each bot: 1,000,000 Revenue Share Tokens (RST) total
- 700,000 → public pool | 150,000 → tech wallet | 150,000 → governance wallet
- Profit split happens automatically via Distributor, proportional to RST held
- No real blockchain until Phase 2

## Governance Stages
| Stage | Trigger | Control |
|-------|---------|---------|
| 1 - Normal | Default | Governance company |
| 2 - Review | Satisfaction < 50% for 2 consecutive quarters | Governance on notice, audit required |
| 3 - Community | Satisfaction < 50% for 4 consecutive quarters | Direct token-holder control |

Transitions are AUTOMATIC. No manual override.

## Module Responsibilities
| Module | Does | Does NOT |
|--------|------|----------|
| `engine/bot_runner.py` | Execute strategy tick by tick | Know anything about tokens |
| `engine/backtester.py` | Replay history through BotRunner | Tell strategy it's a backtest |
| `engine/arena.py` | Run multiple bots simultaneously | Rank or score bots |
| `tokenomics/distributor.py` | Split revenue 70/15/15 | Touch trading logic |
| `governance/stages.py` | Trigger stage transitions | Override governance company |

## Data Flow
```
MarketFeed → BotRunner → TradeLog (append-only)
                ↓
           Distributor → TokenLedger
                ↓
         Governance votes → StageManager
```

## All constants live in config.py
TOKEN_PUBLIC_SHARE = 0.70
TOKEN_TECH_SHARE = 0.15
TOKEN_GOV_SHARE = 0.15
STAGE2_TRIGGER_THRESHOLD = 0.50
STAGE2_CONSECUTIVE_QUARTERS = 2
STAGE3_CONSECUTIVE_QUARTERS = 4
TOTAL_RST_PER_BOT = 1_000_000
