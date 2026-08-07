import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth_utils import validate_jwt_secret
from app.database import init_db
from app.routes.analytics import router as analytics_router
from app.routes.auth import router as auth_router
from app.routes.counters import router as counters_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Validate environment & initialize database on startup."""
    validate_jwt_secret()
    init_db()
    yield


app = FastAPI(
    title="Universal Data Analytics Platform",
    description="In-memory automated analytics for CSV, XLS, and XLSX files.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — read allowed origins from env var, default to permissive for local dev
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "*").strip()
_cors_origins = (
    [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    if _cors_origins_raw != "*"
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(counters_router)


@app.get("/")
async def root() -> dict:
    return {
        "status": "online",
        "service": "Universal Data Analytics Platform",
        "storage": "in-memory only",
        "ai": False,
    }
