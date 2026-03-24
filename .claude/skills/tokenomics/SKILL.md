---
name: tokenomics
description: Use when working on token distribution, revenue splitting, token ledger, RST holders, or profit calculations. Triggers on phrases like "distribute revenue", "token split", "RST holders", "profit distribution", "token ledger", "who owns tokens".
---

# AXIOM Tokenomics (Phase 1 — Simulated)

## Token Model
Every bot has exactly 1,000,000 Revenue Share Tokens (RST):
- 700,000 (70%) → public_pool wallet (buyers get shares from here)
- 150,000 (15%) → tech_company wallet
- 150,000 (15%) → governance_company wallet

All constants in `config.py`. Never hardcode percentages.

## Revenue Distribution Flow
```
Bot earns profit
      ↓
Distributor.distribute(bot_id, profit_amount)
      ↓
Calculate each holder's share: (holder_rst / total_rst) * profit
      ↓
Insert records into token_distributions table
      ↓
Update holder balances in token_ledger table
```

## Key files
- `backend/tokenomics/distributor.py` — distribution logic
- `backend/tokenomics/ledger.py` — token ownership CRUD
- `backend/tokenomics/models.py` — Pydantic models

## Pydantic models
```python
class TokenHolder(BaseModel):
    holder_id: str
    bot_id: str
    rst_amount: int
    wallet_type: WalletType  # PUBLIC | TECH | GOVERNANCE

class Distribution(BaseModel):
    bot_id: str
    profit_amount: float
    distributions: list[HolderPayout]
    timestamp: datetime

class HolderPayout(BaseModel):
    holder_id: str
    rst_held: int
    payout_amount: float
    share_percentage: float
```

## Running a distribution
```python
from tokenomics.distributor import Distributor

dist = Distributor(db_session)
result = dist.distribute(bot_id="bot_001", profit=1000.00)
# result.distributions shows each holder's payout
```

## Checking a holder's balance
```python
from tokenomics.ledger import TokenLedger

ledger = TokenLedger(db_session)
balance = ledger.get_balance(holder_id="user_abc", bot_id="bot_001")
total_earned = ledger.get_total_earned(holder_id="user_abc")
```

## Phase 2 note
In Phase 2, `distribute()` will call a Solidity smart contract instead of
writing to SQLite. The interface stays identical — only the implementation changes.
Keep distributor logic clean and side-effect free for this reason.
