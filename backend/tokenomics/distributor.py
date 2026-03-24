from sqlalchemy.orm import Session

from backend.config import TOKEN_GOV_SHARE, TOKEN_PUBLIC_SHARE, TOKEN_TECH_SHARE
from backend.tokenomics.ledger import TokenLedger
from backend.tokenomics.models import HolderPayout, RevenueDistribution


class Distributor:
    def __init__(self, db: Session, ledger: TokenLedger) -> None:
        self.db = db
        self.ledger = ledger

    def distribute(self, bot_id: str, total_revenue: float) -> RevenueDistribution:
        balances = self.ledger.get_balances(bot_id)
        total_rst = sum(balances.values())

        public_share = total_revenue * TOKEN_PUBLIC_SHARE
        tech_share = total_revenue * TOKEN_TECH_SHARE
        gov_share = total_revenue * TOKEN_GOV_SHARE

        public_rst = self.ledger.get_holder_type_balance(bot_id, "public")
        tech_rst = self.ledger.get_holder_type_balance(bot_id, "tech")
        gov_rst = self.ledger.get_holder_type_balance(bot_id, "governance")

        payouts: list[HolderPayout] = []

        for holder_address, balance in balances.items():
            if balance <= 0:
                continue

            # Determine which pool this holder belongs to by comparing with type totals
            from backend.db.models import DBToken

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

            payouts.append(
                HolderPayout(
                    holder_address=holder_address,
                    holder_type=holder_type,
                    amount=amount,
                    rst_balance=balance,
                )
            )

        return RevenueDistribution(
            bot_id=bot_id,
            total_revenue=total_revenue,
            public_share=public_share,
            tech_share=tech_share,
            gov_share=gov_share,
            distributions=payouts,
        )
