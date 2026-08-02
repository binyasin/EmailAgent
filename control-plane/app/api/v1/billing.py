import stripe
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_session
from app.core.security import CurrentUser, require_org_admin
from app.models.org import Org
from app.schemas.billing import CheckoutSessionRequest, CheckoutSessionResponse, PortalSessionResponse
from app.services.audit import record_audit_event
from app.services.billing import (
    KNOWN_PLAN_TIERS,
    create_billing_portal_session,
    create_checkout_session,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
def start_checkout(
    payload: CheckoutSessionRequest,
    db=Depends(get_session),
    user: CurrentUser = Depends(require_org_admin),
):
    if payload.plan_tier not in (KNOWN_PLAN_TIERS - {"trial"}):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot check out for '{payload.plan_tier}'")

    org = db.get(Org, user.org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Org not found")

    if org.stripe_customer_id is None:
        try:
            customer = stripe.Customer.create(name=org.name, metadata={"org_id": org.id})
        except Exception as exc:  # noqa: BLE001 — surface as a clean 502, not a raw Stripe traceback
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stripe error: {exc}") from exc
        org.stripe_customer_id = customer.id

    try:
        checkout_url = create_checkout_session(
            org_id=org.id, plan_tier=payload.plan_tier, customer_id=org.stripe_customer_id
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stripe error: {exc}") from exc

    record_audit_event(
        db, org_id=org.id, actor_type="user", actor_id=user.user_id,
        action="billing.checkout_started", resource_type="org", resource_id=org.id,
        metadata={"plan_tier": payload.plan_tier},
    )
    return CheckoutSessionResponse(checkout_url=checkout_url)


@router.post("/portal-session", response_model=PortalSessionResponse)
def start_portal_session(
    db=Depends(get_session), user: CurrentUser = Depends(require_org_admin)
):
    org = db.get(Org, user.org_id)
    if org is None or org.stripe_customer_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No Stripe customer for this org yet — check out a plan first"
        )

    try:
        portal_url = create_billing_portal_session(customer_id=org.stripe_customer_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stripe error: {exc}") from exc

    return PortalSessionResponse(portal_url=portal_url)
