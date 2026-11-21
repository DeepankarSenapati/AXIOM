import math
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction

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


_CATEGORIES = ("public", "tech", "governance")
_PLACEHOLDER_HOLDERS = frozenset({"public_pool", "tech_wallet", "gov_wallet"})
_MAX_REVENUE = Decimal("1e12")


class Distributor:
    def __init__(self, db: Session, ledger: TokenLedger) -> None:
        self.db = db
        self.ledger = ledger

    @staticmethod
    def _parse_revenue(value: object) -> Decimal:
        """Return revenue as a Decimal with exact whole cents, or raise."""
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise InvalidRevenueError(f"total_revenue must be a real number, got {value!r}")
        try:
            d = Decimal(str(value))
        except InvalidOperation:
            raise InvalidRevenueError(f"total_revenue is not a valid number: {value!r}")
        if not d.is_finite():
            raise InvalidRevenueError(f"total_revenue must be finite, got {value!r}")
        if d <= 0:
            raise InvalidRevenueError(f"total_revenue must be positive, got {value}")
        if d > _MAX_REVENUE:
            raise InvalidRevenueError(f"total_revenue must be at most 1e12, got {value}")
        cents = d * 100
        if cents != cents.to_integral_value():
            raise InvalidRevenueError(f"total_revenue must be whole cents, got {value}")
        return d

    @staticmethod
    def _largest_remainder(total: int, quotas: list[Fraction], keys: list) -> list[int]:
        """Allocate integer `total` by quotas (summing to total); ties broken by keys ascending."""
        floors = [q.numerator // q.denominator for q in quotas]
        leftover = total - sum(floors)
        order = sorted(range(len(quotas)), key=lambda i: (-(quotas[i] - floors[i]), keys[i]))
        for i in order[:leftover]:
            floors[i] += 1
        return floors

    def distribute(self, bot_id: str, total_revenue: float, quarter: str = "") -> RevenueDistribution:
        revenue = self._parse_revenue(total_revenue)

        if not quarter:
            now = datetime.utcnow()
            quarter = f"{now.year}-Q{(now.month - 1) // 3 + 1}"

        # ---- Validate everything before any DB write ----
        rows = (
            self.db.query(DBToken)
            .filter(DBToken.bot_id == bot_id)
            .order_by(DBToken.id)
            .all()
        )
        if not rows:
            raise InvalidRevenueError(f"tokens are not initialized for bot '{bot_id}'")

        seen: set[str] = set()
        holders: dict[str, list[tuple[str, Fraction, float]]] = {c: [] for c in _CATEGORIES}
        for row in rows:
            if not isinstance(row.holder_address, str) or not row.holder_address:
                raise InvalidRevenueError("holder address must be a nonempty string")
            if row.holder_address in seen:
                raise InvalidRevenueError(f"duplicate holder address '{row.holder_address}'")
            seen.add(row.holder_address)
            if row.holder_type not in holders:
                raise InvalidRevenueError(
                    f"unknown holder type '{row.holder_type}' for '{row.holder_address}'"
                )
            bal = row.balance
            if (
                isinstance(bal, bool)
                or not isinstance(bal, (int, float))
                or not math.isfinite(bal)
                or bal < 0
            ):
                raise InvalidRevenueError(
                    f"invalid balance {bal!r} for holder '{row.holder_address}'"
                )
            if bal > 0:
                holders[row.holder_type].append(
                    (row.holder_address, Fraction(Decimal(str(bal))), bal)
                )
        for cat in _CATEGORIES:
            if not holders[cat]:
                raise InvalidRevenueError(f"no positive token balance for category '{cat}'")

        # ---- Compute in exact integer cents / 0.0001 units ----
        total_cents = int(revenue * 100)
        fee_rate = Decimal(str(PLATFORM_FEE))
        if not fee_rate.is_finite() or not 0 <= fee_rate <= 1:
            raise InvalidRevenueError("invalid PLATFORM_FEE configuration")
        fee_cents = int(
            (revenue * fee_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100
        )
        dist_cents = total_cents - fee_cents

        shares = [
            Fraction(Decimal(str(TOKEN_PUBLIC_SHARE))),
            Fraction(Decimal(str(TOKEN_TECH_SHARE))),
            Fraction(Decimal(str(TOKEN_GOV_SHARE))),
        ]
        share_sum = sum(shares)
        if share_sum != 1 or any(s < 0 for s in shares):
            raise InvalidRevenueError("invalid TOKEN_*_SHARE configuration")
        quotas = [dist_cents * s for s in shares]
        bucket_cents = self._largest_remainder(dist_cents, quotas, [0, 1, 2])

        payouts: list[HolderPayout] = []
        for cat, cents in zip(_CATEGORIES, bucket_cents):
            members = holders[cat]
            units = cents * 100
            total_bal = sum(m[1] for m in members)
            member_quotas = [units * m[1] / total_bal for m in members]
            alloc = self._largest_remainder(units, member_quotas, [m[0] for m in members])
            for (addr, _frac, raw_bal), u in zip(members, alloc):
                p = HolderPayout(
                    holder_address=addr,
                    holder_type=cat,
                    amount=float(Decimal(u) / 10000),
                    rst_balance=raw_bal,
                )
                payouts.append(p)

        def money(c: int) -> float:
            return float(Decimal(c) / 100)

        platform_fee = money(fee_cents)
        distributable = money(dist_cents)
        public_share, tech_share, gov_share = (money(c) for c in bucket_cents)
        total_out = float(revenue)

        # ---- Persist atomically ----
        try:
            event = DBDistributionEvent(
                bot_id=bot_id,
                total_revenue=total_out,
                platform_fee=platform_fee,
                distributable=distributable,
                public_share=public_share,
                tech_share=tech_share,
                gov_share=gov_share,
                quarter=quarter,
                created_at=datetime.utcnow(),
            )
            self.db.add(event)
            self.db.flush()  # get event.id without commit

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

                # Simulated placeholder pools are recorded only, never credited.
                if payout.holder_address in _PLACEHOLDER_HOLDERS:
                    continue
                user = (
                    self.db.query(DBUser)
                    .filter(DBUser.email == payout.holder_address)
                    .first()
                )
                if user is not None:
                    user.wallet_balance = round(user.wallet_balance + payout.amount, 4)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return RevenueDistribution(
            bot_id=bot_id,
            total_revenue=total_out,
            platform_fee=platform_fee,
            distributable=distributable,
            public_share=public_share,
            tech_share=tech_share,
            gov_share=gov_share,
            distributions=payouts,
        )
