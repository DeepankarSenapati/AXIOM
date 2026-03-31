import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.auth.security import hash_password
from backend.db.models import DBUser

logger = logging.getLogger(__name__)

_SEED_USERS: list[dict] = [
    {
        "email": "admin@axiom.com",
        "password": "admin123",
        "role": "admin",
        "company_name": None,
    },
    {
        "email": "tech@botbuilders.com",
        "password": "tech123",
        "role": "tech_company",
        "company_name": "BotBuilders Inc",
    },
    {
        "email": "gov@oversight.com",
        "password": "gov123",
        "role": "governance_company",
        "company_name": "Oversight DAO",
    },
    {
        "email": "buyer@demo.com",
        "password": "buyer123",
        "role": "token_holder",
        "company_name": None,
    },
]


def seed_users(db: Session) -> None:
    """Insert default users if the users table is empty."""
    count = db.query(DBUser).count()
    if count > 0:
        return

    logger.info("Seeding %d default users", len(_SEED_USERS))
    for u in _SEED_USERS:
        user = DBUser(
            id=str(uuid4()),
            email=u["email"],
            password_hash=hash_password(u["password"]),
            role=u["role"],
            company_name=u["company_name"],
            wallet_balance=10000.0,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(user)
    db.commit()
    logger.info("Default users seeded successfully")
