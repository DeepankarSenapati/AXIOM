# Token distribution
TOKEN_PUBLIC_SHARE: float = 0.70
TOKEN_TECH_SHARE: float = 0.15
TOKEN_GOV_SHARE: float = 0.15
TOTAL_RST_PER_BOT: int = 1_000_000

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
SECRET_KEY: str = "axiom-dev-secret-key-change-in-prod"
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
