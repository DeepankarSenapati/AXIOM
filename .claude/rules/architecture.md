# AXIOM Architecture

## Core Concept
- Local simulation: built-in algorithms produce decisions; there are no real orders
- User-entered simulated revenue is allocated 70% public / 15% tech / 15% governance after the platform fee
- The intended design explores progressive governance; the current stages are indicators and do not transfer control
- Trade records, if stored, must be append-only. The current backtest API does not persist individual trades or provide an immutable audit

## The BotRunner (most important class)
- Takes a strategy config + market data stream
- Feeds only the current and earlier candles to a strategy; do not expose future candles
- Returns each decision in memory: BUY / SELL / HOLD + timestamp + price + reason
- Tracks portfolio: cash, positions, PnL
- Use a fresh strategy for each run; seeded inputs and the same implementation are reproducible

## BaseStrategy Contract (THE LAW)
```python
class BaseStrategy:
    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        # ONLY sees current + past candles. Never future.
        raise NotImplementedError
```
All bots MUST inherit BaseStrategy. No exceptions.

## Token Model (Phase 1: SQLite simulation)
- Each bot: 1,000,000 Revenue Share Tokens (RST) total
- 700,000 → public pool | 150,000 → tech placeholder | 150,000 → governance placeholder
- Distributor allocates manually entered simulated revenue proportional to holdings; placeholder allocations do not credit company user wallets
- No real blockchain until Phase 2

## Governance Stages
| Stage | Trigger | Current behavior |
|-------|---------|---------|
| 1 - Normal | Default | Normal indicator |
| 2 - Review | Satisfaction < 50% for 2 consecutive quarters | Review indicator; an audit can be recorded |
| 3 - Community | Satisfaction < 50% for 4 consecutive quarters | Community indicator only; no control transfer |

The indicator is derived automatically from valid, consecutive closed polls;
there is no manual override. Votes use the
account balance at vote time, but transferable tokens can be counted again;
the model is not secure or binding governance. There is no separate immutable
transition log.

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
MarketFeed → BotRunner → in-memory decision records → Backtester → stored summary
User-entered revenue → Distributor → simulated allocations and wallet credits
Governance votes → StageManager → derived stage indicator
```

## All constants live in config.py
TOKEN_PUBLIC_SHARE = 0.70
TOKEN_TECH_SHARE = 0.15
TOKEN_GOV_SHARE = 0.15
STAGE2_TRIGGER_THRESHOLD = 0.50
STAGE2_CONSECUTIVE_QUARTERS = 2
STAGE3_CONSECUTIVE_QUARTERS = 4
TOTAL_RST_PER_BOT = 1_000_000
