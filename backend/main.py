import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.api import admin, arena, auth, bots, governance, tech, tokenomics
from backend.db.seed import seed_users
from backend.db.session import get_db, init_db

# ---------------------------------------------------------------------------
# Logging setup — file + console, configured once at import time
# ---------------------------------------------------------------------------

_LOG_FILE = Path(__file__).resolve().parents[1] / "app.log"
_FMT = "%(asctime)s - %(levelname)s - %(module)s - %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.DEBUG)
_console_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="AXIOM", description="Autonomous eXchange for Intelligent Operations & Markets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled exception during %s %s", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %d (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.on_event("startup")
def on_startup() -> None:
    logger.info("AXIOM starting up — initialising database")
    init_db()
    logger.info("Database ready")
    db = next(get_db())
    try:
        seed_users(db)
    finally:
        db.close()


app.include_router(auth.router)
app.include_router(bots.router)
app.include_router(arena.router)
app.include_router(tokenomics.router)
app.include_router(governance.router)
app.include_router(admin.router)
app.include_router(tech.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
