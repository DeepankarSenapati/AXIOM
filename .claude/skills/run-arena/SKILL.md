---
name: run-arena
description: Use when running the AXIOM bot arena, starting a simulation, running bots against each other, or executing a backtest. Triggers on phrases like "run the arena", "start simulation", "backtest this bot", "run all bots", "compare bots".
---

# Running the AXIOM Arena

## Quick run (all active bots, mock data)
```bash
cd backend
python -m engine.arena --mode paper --duration 1000
```

## Backtest a single bot
```bash
python -m engine.backtester --bot-id <bot_id> --data mock --candles 5000
```

## Arena modes
| Mode | Data source | Notes |
|------|-------------|-------|
| `paper` | Mock real-time feed | Bots run live, no real money |
| `backtest` | Historical mock data | Blind — bots don't know it's historical |
| `replay` | Saved candle file (.csv) | For reproducible benchmarks |

## Reading results
Results written to `backend/data/arena_results/` as JSON.
Each file: `{run_id}_{timestamp}.json`

Schema:
```json
{
  "run_id": "...",
  "mode": "backtest",
  "bots": [
    {
      "bot_id": "...",
      "strategy": "simple_ma",
      "pnl": 1234.56,
      "trades": 42,
      "win_rate": 0.61,
      "sharpe": 1.4
    }
  ]
}
```

## Interpreting bot performance
- **PnL**: absolute profit/loss in simulated USDT
- **Win rate**: % of trades that closed profitable
- **Sharpe ratio**: risk-adjusted return (>1.0 is good, >2.0 is great)
- **Max drawdown**: worst peak-to-trough loss (lower is better)

## Adding a new bot to the arena
See `.claude/skills/new-strategy/SKILL.md`

## Troubleshooting
- `BotNotFoundError` → check bot is registered in `STRATEGY_MAP`
- `MarketFeedError` → check mock feed is running (`python -m engine.market_feed`)
- All bots HOLD → strategy logic not firing, check param values
