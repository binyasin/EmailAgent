from types import SimpleNamespace

import pytest
import stripe

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.org import Org
from app.models.user import User
from app.services.billing import plan_for_price_id, price_id_for_plan


def _configure_price_ids(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_price_id_starter", "price_starter")
    monkeypatch.setattr(settings, "stripe_price_id_pro", "price_pro")
    monkeypatch.setattr(settings, "stripe_price_id_enterprise", "price_enterprise")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")


def _seed_org(db_session, *, suffix: str, customer_id: str | None = None):
    org = Org(id=f"org-{suffix}", name="Bill Org", plan_tier="trial", stripe_customer_id=customer_id)
    admin = User(
        id=f"admin-{suffix}", org_id=org.id, email=f"admin-{suffix}@example.com",
        hashed_password="unused", role="org_admin",
    )
    db_session.add_all([org, admin])
    db_session.commit()
    return org, admin


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def test_price_id_for_plan_and_reverse_mapping(monkeypatch):
    _configure_price_ids(monkeypatch)
    assert price_id_for_plan("pro") == "price_pro"
    assert plan_for_price_id("price_pro") == "pro"
    assert plan_for_price_id("price_unknown") is None


def test_price_id_for_unconfigured_plan_raises_400(monkeypatch):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        price_id_for_plan("starter")
    assert exc_info.value.status_code == 400


def test_webhook_rejects_invalid_signature(client, db_session, monkeypatch):
    _configure_price_ids(monkeypatch)
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        staticmethod(lambda *a, **k: (_ for _ in ()).throw(stripe.SignatureVerificationError("bad", "sig"))),
    )

    resp = client.post(
        "/internal/v1/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "bad-sig"},
    )
    assert resp.status_code == 400


def test_webhook_checkout_completed_sets_customer_and_plan(client, db_session, monkeypatch):
    _configure_price_ids(monkeypatch)
    org, _admin = _seed_org(db_session, suffix="checkout")

    fake_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": org.id,
                "customer": "cus_123",
                "subscription": "sub_123",
                "metadata": {"org_id": org.id, "plan_tier": "pro"},
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda *a, **k: fake_event))

    resp = client.post(
        "/internal/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "sig"}
    )
    assert resp.status_code == 200
    db_session.refresh(org)
    assert org.plan_tier == "pro"
    assert org.stripe_customer_id == "cus_123"
    assert org.stripe_subscription_id == "sub_123"


def test_webhook_subscription_updated_changes_plan(client, db_session, monkeypatch):
    _configure_price_ids(monkeypatch)
    org, _admin = _seed_org(db_session, suffix="subupdate", customer_id="cus_456")

    fake_event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "customer": "cus_456",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_starter"}}]},
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda *a, **k: fake_event))

    resp = client.post(
        "/internal/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "sig"}
    )
    assert resp.status_code == 200
    db_session.refresh(org)
    assert org.plan_tier == "starter"


def test_webhook_subscription_deleted_downgrades_to_trial(client, db_session, monkeypatch):
    _configure_price_ids(monkeypatch)
    org, _admin = _seed_org(db_session, suffix="subdelete", customer_id="cus_789")
    org.plan_tier = "pro"
    org.stripe_subscription_id = "sub_789"
    db_session.commit()

    fake_event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"customer": "cus_789"}},
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda *a, **k: fake_event))

    resp = client.post(
        "/internal/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "sig"}
    )
    assert resp.status_code == 200
    db_session.refresh(org)
    assert org.plan_tier == "trial"
    assert org.stripe_subscription_id is None


def test_checkout_session_creates_customer_when_missing(client, db_session, monkeypatch):
    _configure_price_ids(monkeypatch)
    org, admin = _seed_org(db_session, suffix="newcustomer")

    monkeypatch.setattr(
        stripe.Customer, "create", staticmethod(lambda **k: SimpleNamespace(id="cus_new"))
    )
    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        staticmethod(lambda **k: SimpleNamespace(url="https://checkout.stripe.com/session/xyz")),
    )

    resp = client.post(
        "/api/v1/billing/checkout-session", json={"plan_tier": "pro"}, headers=_headers(admin)
    )
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/session/xyz"
    db_session.refresh(org)
    assert org.stripe_customer_id == "cus_new"


def test_member_cannot_start_checkout(client, db_session, monkeypatch):
    _configure_price_ids(monkeypatch)
    org, _admin = _seed_org(db_session, suffix="memberco")
    member = User(
        id="member-memberco", org_id=org.id, email="m@example.com", hashed_password="x", role="member"
    )
    db_session.add(member)
    db_session.commit()

    resp = client.post(
        "/api/v1/billing/checkout-session", json={"plan_tier": "pro"}, headers=_headers(member)
    )
    assert resp.status_code == 403


def test_portal_session_requires_existing_customer(client, db_session, monkeypatch):
    _configure_price_ids(monkeypatch)
    org, admin = _seed_org(db_session, suffix="noportal")

    resp = client.post("/api/v1/billing/portal-session", headers=_headers(admin))
    assert resp.status_code == 404


def test_portal_session_returns_url_for_existing_customer(client, db_session, monkeypatch):
    _configure_price_ids(monkeypatch)
    org, admin = _seed_org(db_session, suffix="hasportal", customer_id="cus_existing")

    monkeypatch.setattr(
        stripe.billing_portal.Session,
        "create",
        staticmethod(lambda **k: SimpleNamespace(url="https://billing.stripe.com/portal/xyz")),
    )

    resp = client.post("/api/v1/billing/portal-session", headers=_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["portal_url"] == "https://billing.stripe.com/portal/xyz"
