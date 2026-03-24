# /new-bot

Scaffold a complete new trading bot for AXIOM.

## Usage
/new-bot <strategy_name> <short_description>

## Example
/new-bot bollinger_bands "Mean reversion using Bollinger Band squeeze"

## What this does
1. Reads `.claude/skills/new-strategy/SKILL.md`
2. Creates `backend/bots/strategies/<strategy_name>.py` from template
3. Registers in `backend/bots/registry.py`
4. Creates `tests/strategies/test_<strategy_name>.py`
5. Reports checklist status

Always follow the BaseStrategy contract. Always blind.
