from fastapi import APIRouter

from app.api.v1 import auth, billing, cells, digests, drafts, mailboxes, orgs, skill_settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(mailboxes.router)
api_router.include_router(drafts.router)
api_router.include_router(digests.router)
api_router.include_router(skill_settings.router)
api_router.include_router(cells.router)
api_router.include_router(orgs.router)
api_router.include_router(billing.router)
