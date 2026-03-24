from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import arena, bots, governance, tokenomics
from backend.db.session import init_db

app = FastAPI(title="AXIOM", description="Autonomous eXchange for Intelligent Operations & Markets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(bots.router)
app.include_router(arena.router)
app.include_router(tokenomics.router)
app.include_router(governance.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
