"""Plan-tier gating (unchanged from earlier phases) plus a real Stripe
integration for checkout, the customer billing portal, and webhook
signature verification (`stripe.Webhook.construct_event` — genuine HMAC
verification against `STRIPE_WEBHOOK_SECRET`, not the shared-secret stand-in
this module used before). Requires real `STRIPE_SECRET_KEY`/
`STRIPE_WEBHOOK_SECRET`/`STRIPE_PRICE_ID_*` values to actually function —
none of the Stripe-calling functions here have been exercised against a
real Stripe account (no test-mode API keys were available while building
this); they're written directly against the documented stripe-python SDK
API and covered by tests that mock the SDK calls, not integration-tested
against Stripe itself. Verify against a real Stripe test-mode account
before processing real payments.
"""

import stripe
from fastapi import HTTPException, status

from app.core.config import get_settings

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "trial": {"max_mailboxes": 1, "max_seats": 3},
    "starter": {"max_mailboxes": 3, "max_seats": 10},
    "pro": {"max_mailboxes": 10, "max_seats": 50},
    "enterprise": {"max_mailboxes": 1_000_000, "max_seats": 1_000_000},
}

KNOWN_PLAN_TIERS = set(PLAN_LIMITS.keys())


def enforce_plan_limit(*, plan_tier: str, resource: str, current_count: int) -> None:
    """Raises 402 Payment Required if adding one more `resource` would
    exceed the org's plan. Call with the count *before* adding the new one
    (e.g. existing mailbox count, not existing + 1)."""
    limits = PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["trial"])
    limit_key = f"max_{resource}"
    limit = limits.get(limit_key)
    if limit is not None and current_count >= limit:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Plan '{plan_tier}' allows at most {limit} {resource}; upgrade to add more.",
        )


def _configure_stripe() -> None:
    key = get_settings().stripe_secret_key
    if not key:
        raise RuntimeError(
            "STRIPE_SECRET_KEY is not configured — billing checkout/portal endpoints "
            "cannot function without it."
        )
    stripe.api_key = key


def price_id_for_plan(plan_tier: str) -> str:
    settings = get_settings()
    mapping = {
        "starter": settings.stripe_price_id_starter,
        "pro": settings.stripe_price_id_pro,
        "enterprise": settings.stripe_price_id_enterprise,
    }
    price_id = mapping.get(plan_tier)
    if not price_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"No Stripe price configured for plan '{plan_tier}' (trial has no checkout — "
            "it's the default for new orgs, not a purchasable plan).",
        )
    return price_id


def plan_for_price_id(price_id: str) -> str | None:
    settings = get_settings()
    mapping = {
        settings.stripe_price_id_starter: "starter",
        settings.stripe_price_id_pro: "pro",
        settings.stripe_price_id_enterprise: "enterprise",
    }
    return mapping.get(price_id)


def create_checkout_session(*, org_id: str, plan_tier: str, customer_id: str | None) -> str:
    _configure_stripe()
    settings = get_settings()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id_for_plan(plan_tier), "quantity": 1}],
        customer=customer_id,
        client_reference_id=org_id,
        metadata={"org_id": org_id, "plan_tier": plan_tier},
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
    )
    return session.url


def create_billing_portal_session(*, customer_id: str) -> str:
    _configure_stripe()
    settings = get_settings()
    session = stripe.billing_portal.Session.create(
        customer=customer_id, return_url=settings.billing_portal_return_url
    )
    return session.url


def verify_and_parse_webhook_event(*, payload: bytes, signature_header: str) -> stripe.Event:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured.")
    try:
        return stripe.Webhook.construct_event(
            payload, signature_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature") from exc
