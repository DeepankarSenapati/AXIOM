from sqlalchemy.orm import Session

from backend.config import (
    TOKEN_GOV_SHARE,
    TOKEN_PUBLIC_SHARE,
    TOKEN_TECH_SHARE,
    TOTAL_RST_PER_BOT,
)
from backend.db.models import DBToken
from backend.tokenomics.models import TokenAllocation


class InsufficientTokensError(Exception):
    pass


class TokenLedger:
    def __init__(self, db: Session) -> None:
        self.db = db

    def initialize_bot_tokens(self, bot_id: str) -> TokenAllocation:
        public_tokens = float(TOTAL_RST_PER_BOT) * TOKEN_PUBLIC_SHARE
        tech_tokens = float(TOTAL_RST_PER_BOT) * TOKEN_TECH_SHARE
        gov_tokens = float(TOTAL_RST_PER_BOT) * TOKEN_GOV_SHARE

        self.db.add(DBToken(bot_id=bot_id, holder_address="public_pool", balance=public_tokens, holder_type="public"))
        self.db.add(DBToken(bot_id=bot_id, holder_address="tech_wallet", balance=tech_tokens, holder_type="tech"))
        self.db.add(DBToken(bot_id=bot_id, holder_address="gov_wallet", balance=gov_tokens, holder_type="governance"))
        self.db.commit()

        return TokenAllocation(
            bot_id=bot_id,
            public_tokens=public_tokens,
            tech_tokens=tech_tokens,
            gov_tokens=gov_tokens,
            total=float(TOTAL_RST_PER_BOT),
        )

    def get_balances(self, bot_id: str) -> dict[str, float]:
        rows = self.db.query(DBToken).filter(DBToken.bot_id == bot_id).all()
        return {row.holder_address: row.balance for row in rows}

    def get_holder_type_balance(self, bot_id: str, holder_type: str) -> float:
        rows = (
            self.db.query(DBToken)
            .filter(DBToken.bot_id == bot_id, DBToken.holder_type == holder_type)
            .all()
        )
        return sum(row.balance for row in rows)

    def transfer(
        self,
        bot_id: str,
        from_address: str,
        to_address: str,
        amount: float,
        *,
        commit: bool = True,
    ) -> None:
        from_row = (
            self.db.query(DBToken)
            .filter(DBToken.bot_id == bot_id, DBToken.holder_address == from_address)
            .first()
        )
        if from_row is None or from_row.balance < amount:
            held = from_row.balance if from_row else 0.0
            raise InsufficientTokensError(
                f"'{from_address}' holds {held} RST for bot '{bot_id}', "
                f"cannot transfer {amount}"
            )

        to_row = (
            self.db.query(DBToken)
            .filter(DBToken.bot_id == bot_id, DBToken.holder_address == to_address)
            .first()
        )

        from_row.balance -= amount
        if to_row is None:
            # Infer holder_type from from_row for new holders
            self.db.add(
                DBToken(
                    bot_id=bot_id,
                    holder_address=to_address,
                    balance=amount,
                    holder_type=from_row.holder_type,
                )
            )
        else:
            to_row.balance += amount

        if commit:
            self.db.commit()
