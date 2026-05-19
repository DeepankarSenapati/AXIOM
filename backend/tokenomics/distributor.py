from datetime import datetime

from sqlalchemy.orm import Session

from backend.config import (
    PLATFORM_FEE,
    TOKEN_GOV_SHARE,
    TOKEN_PUBLIC_SHARE,
    TOKEN_TECH_SHARE,
)
from backend.db.models import DBDistributionEvent, DBDistributionPayout, DBToken, DBUser
from backend.tokenomics.ledger import TokenLedger
from backend.tokenomics.models import HolderPayout, RevenueDistribution


class InvalidRevenueError(Exception):
    pass


class Distributor:
    def __init__(self, db: Session, ledger: TokenLedger) -> None:
        self.db = db
        self.ledger = ledger

    def distribute(self, bot_id: str, total_revenue: float, quarter: str = "") -> RevenueDistribution:
        if total_revenue <= 0:
            raise InvalidRevenueError(f"total_revenue must be positive, got {total_revenue}")

        if not quarter:
            now = datetime.utcnow()
            quarter = f"{now.year}-Q{(now.month - 1) // 3 + 1}"

        platform_fee = round(total_revenue * PLATFORM_FEE, 2)
        distributable = round(total_revenue - platform_fee, 2)

        public_share = round(distributable * TOKEN_PUBLIC_SHARE, 2)
        tech_share = round(distributable * TOKEN_TECH_SHARE, 2)
        gov_share = round(distributable * TOKEN_GOV_SHARE, 2)

        public_rst = self.ledger.get_holder_type_balance(bot_id, "public")
        tech_rst = self.ledger.get_holder_type_balance(bot_id, "tech")
        gov_rst = self.ledger.get_holder_type_balance(bot_id, "governance")

        balances = self.ledger.get_balances(bot_id)
        payouts: list[HolderPayout] = []

        for holder_address, balance in balances.items():
            if balance <= 0:
                continue

            row = (
                self.db.query(DBToken)
                .filter(DBToken.bot_id == bot_id, DBToken.holder_address == holder_address)
                .first()
            )
            if row is None:
                continue

            holder_type = row.holder_type
            if holder_type == "public" and public_rst > 0:
                amount = public_share * (balance / public_rst)
            elif holder_type == "tech" and tech_rst > 0:
                amount = tech_share * (balance / tech_rst)
            elif holder_type == "governance" and gov_rst > 0:
                amount = gov_share * (balance / gov_rst)
            else:
                amount = 0.0

            amount = round(amount, 4)
            payouts.append(
                HolderPayout(
                    holder_address=holder_address,
                    holder_type=holder_type,
                    amount=amount,
                    rst_balance=balance,
                )
            )

        # Persist the distribution event
        event = DBDistributionEvent(
            bot_id=bot_id,
            total_revenue=total_revenue,
            platform_fee=platform_fee,
            distributable=distributable,
            public_share=public_share,
            tech_share=tech_share,
            gov_share=gov_share,
            quarter=quarter,
            created_at=datetime.utcnow(),
        )
        self.db.add(event)
        self.db.flush()  # get event.id without full commit

        # Persist individual payouts and credit user wallets
        for payout in payouts:
            self.db.add(DBDistributionPayout(
                event_id=event.id,
                bot_id=bot_id,
                holder_address=payout.holder_address,
                holder_type=payout.holder_type,
                rst_balance=payout.rst_balance,
                amount=payout.amount,
                created_at=datetime.utcnow(),
            ))

            # Credit real user wallets for any holder that is a registered user
            user = (
                self.db.query(DBUser)
                .filter(DBUser.email == payout.holder_address)
                .first()
            )
            if user is not None:
                user.wallet_balance = round(user.wallet_balance + payout.amount, 4)

        self.db.commit()

        return RevenueDistribution(
            bot_id=bot_id,
            total_revenue=total_revenue,
            platform_fee=platform_fee,
            distributable=distributable,
            public_share=public_share,
            tech_share=tech_share,
            gov_share=gov_share,
            distributions=payouts,
        )
