from pydantic import BaseModel


class CheckoutSessionRequest(BaseModel):
    plan_tier: str  # "starter" | "pro" | "enterprise" — trial has no checkout


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class PortalSessionResponse(BaseModel):
    portal_url: str
