from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import get_session
from app.models.org import Org
from app.services.audit import record_audit_event
from app.services.billing import plan_for_price_id, verify_and_parse_webhook_event

router = APIRouter(prefix="/internal/v1/billing", tags=["internal"])


def _find_org_by_customer_id(db, customer_id: str) -> Org | None:
    return db.scalar(select(Org).where(Org.stripe_customer_id == customer_id))


@router.post("/webhook")
async def billing_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    db=Depends(get_session),
):
    payload = await request.body()
    event = verify_and_parse_webhook_event(payload=payload, signature_header=stripe_signature)
    data = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        org_id = data.get("client_reference_id") or (data.get("metadata") or {}).get("org_id")
        plan_tier = (data.get("metadata") or {}).get("plan_tier")
        org = db.get(Org, org_id) if org_id else None
        if org is None or plan_tier is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown org_id in checkout session")

        org.stripe_customer_id = data.get("customer")
        org.stripe_subscription_id = data.get("subscription")
        previous_tier = org.plan_tier
        org.plan_tier = plan_tier
        record_audit_event(
            db, org_id=org.id, actor_type="system", actor_id="stripe_webhook",
            action="billing.checkout_completed", resource_type="org", resource_id=org.id,
            metadata={"previous_tier": previous_tier, "new_tier": plan_tier},
        )

    elif event["type"] == "customer.subscription.updated":
        org = _find_org_by_customer_id(db, data["customer"])
        if org is not None:
            price_id = data["items"]["data"][0]["price"]["id"]
            new_tier = plan_for_price_id(price_id)
            if data["status"] in ("canceled", "unpaid", "incomplete_expired"):
                new_tier = "trial"
            if new_tier is not None:
                previous_tier = org.plan_tier
                org.plan_tier = new_tier
                record_audit_event(
                    db, org_id=org.id, actor_type="system", actor_id="stripe_webhook",
                    action="billing.subscription_updated", resource_type="org", resource_id=org.id,
                    metadata={"previous_tier": previous_tier, "new_tier": new_tier, "status": data["status"]},
                )

    elif event["type"] == "customer.subscription.deleted":
        org = _find_org_by_customer_id(db, data["customer"])
        if org is not None:
            previous_tier = org.plan_tier
            org.plan_tier = "trial"
            org.stripe_subscription_id = None
            record_audit_event(
                db, org_id=org.id, actor_type="system", actor_id="stripe_webhook",
                action="billing.subscription_canceled", resource_type="org", resource_id=org.id,
                metadata={"previous_tier": previous_tier},
            )

    return {"status": "ok"}
