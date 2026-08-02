import uuid

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.internal.billing_webhook import router as internal_billing_router
from app.api.internal.digests_ingest import router as internal_digests_router
from app.api.internal.drafts_ingest import router as internal_drafts_router
from app.api.internal.token_broker import router as internal_tokens_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.db.session import get_db

configure_logging()
settings = get_settings()

app = FastAPI(title="AI Email Agent — Control Plane", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def bind_request_log_context(request: Request, call_next):
    """Tags every log line emitted while handling this request with a
    request_id and (best-effort) org_id, so a support engineer can grep one
    request's full story out of aggregate logs. The JWT is decoded WITHOUT
    signature verification here — this is purely for log context, not an
    auth decision (every route still enforces real auth via its own
    Depends(get_current_user) chain); a forged token could only mislabel a
    log line, never bypass authorization."""
    request_id = uuid.uuid4().hex
    org_id = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        try:
            payload = jwt.decode(
                auth_header[7:], key="", options={"verify_signature": False, "verify_exp": False}
            )
            org_id = payload.get("org_id")
        except Exception:  # noqa: BLE001 — log-context best-effort, never block the request
            pass

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id, org_id=org_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.include_router(api_router)
app.include_router(internal_drafts_router)
app.include_router(internal_tokens_router)
app.include_router(internal_digests_router)
app.include_router(internal_billing_router)


@app.get("/healthz")
def healthz():
    """Liveness — process is up. Deliberately does not touch the database;
    see /readyz for that."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    """Readiness — process is up AND can reach its database."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
