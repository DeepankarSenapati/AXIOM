# Token distribution
RST_PRICE: float = 0.01  # $0.01 per RST token (Phase 1 simulated price)
TOKEN_PUBLIC_SHARE: float = 0.70
TOKEN_TECH_SHARE: float = 0.15
TOKEN_GOV_SHARE: float = 0.15
TOTAL_RST_PER_BOT: int = 1_000_000

# Platform economics
PLATFORM_FEE: float = 0.02   # 2% of every revenue distribution retained by AXIOM
EXIT_FEE: float = 0.02       # 2% penalty on token sell-back to public pool

# Governance thresholds
STAGE2_TRIGGER_THRESHOLD: float = 0.50
STAGE2_CONSECUTIVE_QUARTERS: int = 2
STAGE3_CONSECUTIVE_QUARTERS: int = 4

# Bot defaults
DEFAULT_STARTING_CASH: float = 10_000.0
MAX_POSITION_SIZE: float = 0.30  # never risk more than 30% of available cash per trade

# DB
DATABASE_URL: str = "sqlite:///./axiom.db"

# Auth
import logging as _logging
import os as _os

_dev_key = "axiom-dev-secret-key-change-in-prod"
SECRET_KEY: str = _os.environ.get("AXIOM_SECRET_KEY", _dev_key)

if SECRET_KEY == _dev_key:
    _logging.getLogger(__name__).warning(
        "AXIOM_SECRET_KEY not set — using insecure dev key. Set env var before production."
    )

ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
