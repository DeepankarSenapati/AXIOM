---
name: new-strategy
description: Use when adding a new trading strategy or bot to AXIOM. Triggers on phrases like "add a strategy", "create a bot", "new trading algorithm", "implement RSI", "add moving average bot". Covers file creation, registration, and testing of a new strategy.
---

# Adding a New Strategy to AXIOM

## Step 1 — Create the strategy file
Path: `backend/bots/strategies/<strategy_name>.py`

```python
from backend.bots.strategies.base import BaseStrategy
from backend.engine.models import Candle, Portfolio, Action, ActionType
from backend.config import settings

class MyStrategy(BaseStrategy):
    """
    One-line description of what this strategy does.
    """

    def __init__(self, params: dict):
        # Store config params. Validate with Pydantic if complex.
        self.params = params

    def on_candle(self, candle: Candle, portfolio: Portfolio) -> Action:
        """
        Called once per candle. Return BUY, SELL, or HOLD.
        YOU ONLY SEE: candle (current), portfolio (current state).
        YOU NEVER SEE: future candles, backtest flag, other bots.
        """
        # Your logic here
        return Action(
            type=ActionType.HOLD,
            amount=0.0,
            reason="No signal"
        )
```

## Step 2 — Register in bot registry
In `backend/bots/registry.py`, add to `STRATEGY_MAP`:
```python
from backend.bots.strategies.my_strategy import MyStrategy
STRATEGY_MAP["my_strategy"] = MyStrategy
```

## Step 3 — Write the test
Path: `tests/strategies/test_<strategy_name>.py`

Test checklist:
- [ ] Returns valid Action on every candle type (normal, gap, zero volume)
- [ ] Never raises an exception on empty portfolio
- [ ] HOLD when insufficient data (e.g. not enough candles for MA window)
- [ ] BUY signal fires under correct conditions
- [ ] SELL signal fires under correct conditions

## Step 4 — Register bot in DB (for arena use)
Use the `/api/bots` POST endpoint or insert directly in dev:
```python
bot = DBBot(
    name="My Strategy Bot",
    strategy_key="my_strategy",
    params={"window": 20},
    status="pending_audit"
)
```

## Checklist before done
- [ ] Strategy file created with full type hints
- [ ] Registered in STRATEGY_MAP
- [ ] Test file written and passing
- [ ] No future data accessed in on_candle()
- [ ] params validated (Pydantic or explicit checks)
