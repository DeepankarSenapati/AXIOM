# Coding Standards

## Hard Rules (never break these)

1. **Blind strategies** — BotRunner enforces data isolation by design, not trust.
   Feed strategies one candle at a time. Index-based slicing only.

2. **Append-only trade log** — Never `UPDATE` or `DELETE` trade records in DB.
   If a correction is needed, insert a compensating record.

3. **Pydantic everywhere** — All data crossing module boundaries = Pydantic model.
   No raw dicts between `engine/`, `tokenomics/`, `governance/`.

4. **No magic numbers** — All thresholds/percentages live in `config.py`.
   Never hardcode `0.70`, `0.50`, `1_000_000` in logic files.

5. **Type hints on all functions** — Every parameter and return value.
   No `Any` unless truly unavoidable (document why).

6. **Fail loudly** — Raise explicit named exceptions with clear messages.
   Never `except: pass`. AXIOM must be auditable.

7. **One responsibility per file** — If a file hits 300 lines, split it.

8. **Tests for engine, not strategy performance** — Test BotRunner, Backtester,
   Distributor correctness. Not whether a strategy makes money.

## Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE` (all in config.py)
- Pydantic models: `PascalCase` with clear noun names (`TradeAction`, `Candle`, `Portfolio`)
- DB models: prefix with `DB` → `DBTrade`, `DBBot`, `DBToken`

## Error Handling Pattern
```python
# Good
class BotNotFoundError(Exception):
    pass

raise BotNotFoundError(f"Bot '{bot_id}' not found in registry")

# Bad
raise Exception("not found")
# Also bad
return None  # silently failing
```

## Import Order
1. stdlib
2. third-party (fastapi, pydantic, sqlalchemy)
3. local (`from engine.bot_runner import ...`)

## Testing Conventions
- One test file per module: `test_bot_runner.py` tests `bot_runner.py`
- Use pytest fixtures for DB setup/teardown
- Name tests: `test_<what>_<expected_outcome>`
  e.g. `test_on_candle_returns_hold_when_no_signal`
