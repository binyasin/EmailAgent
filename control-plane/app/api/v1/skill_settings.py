from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import get_session
from app.core.security import CurrentUser, require_org_admin, require_org_scope
from app.models.org_skill_setting import OrgSkillSetting
from app.models.vip_rule import VipRule
from app.schemas.skill_settings import (
    KNOWN_SKILL_NAMES,
    OrgSkillSettingOut,
    OrgSkillSettingUpdate,
    VipRuleCreate,
    VipRuleOut,
)
from app.services.audit import record_audit_event

router = APIRouter(tags=["skill-settings"])


@router.get("/skill-settings", response_model=list[OrgSkillSettingOut])
def list_skill_settings(db=Depends(get_session), user: CurrentUser = Depends(require_org_scope)):
    return db.scalars(
        select(OrgSkillSetting).where(OrgSkillSetting.org_id == user.org_id)
    ).all()


@router.put("/skill-settings/{skill_name}", response_model=OrgSkillSettingOut)
def upsert_skill_setting(
    skill_name: str,
    payload: OrgSkillSettingUpdate,
    db=Depends(get_session),
    user: CurrentUser = Depends(require_org_admin),
):
    if skill_name not in KNOWN_SKILL_NAMES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown skill_name '{skill_name}'")

    setting = db.scalar(
        select(OrgSkillSetting).where(
            OrgSkillSetting.org_id == user.org_id, OrgSkillSetting.skill_name == skill_name
        )
    )
    if setting is None:
        setting = OrgSkillSetting(org_id=user.org_id, skill_name=skill_name)
        db.add(setting)

    setting.enabled = payload.enabled
    setting.params = payload.params
    db.flush()

    record_audit_event(
        db,
        org_id=user.org_id,
        actor_type="user",
        actor_id=user.user_id,
        action="skill_setting.updated",
        resource_type="org_skill_setting",
        resource_id=setting.id,
        metadata={"skill_name": skill_name, "enabled": payload.enabled},
    )
    return setting


@router.get("/vip-rules", response_model=list[VipRuleOut])
def list_vip_rules(db=Depends(get_session), user: CurrentUser = Depends(require_org_scope)):
    return db.scalars(
        select(VipRule).where(VipRule.org_id == user.org_id).order_by(VipRule.priority.desc())
    ).all()


@router.post("/vip-rules", response_model=VipRuleOut, status_code=status.HTTP_201_CREATED)
def create_vip_rule(
    payload: VipRuleCreate,
    db=Depends(get_session),
    user: CurrentUser = Depends(require_org_admin),
):
    rule = VipRule(org_id=user.org_id, sender_pattern=payload.sender_pattern, priority=payload.priority)
    db.add(rule)
    db.flush()

    record_audit_event(
        db,
        org_id=user.org_id,
        actor_type="user",
        actor_id=user.user_id,
        action="vip_rule.created",
        resource_type="vip_rule",
        resource_id=rule.id,
        metadata={"sender_pattern": payload.sender_pattern},
    )
    return rule


@router.delete("/vip-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vip_rule(
    rule_id: str, db=Depends(get_session), user: CurrentUser = Depends(require_org_admin)
):
    rule = db.scalar(
        select(VipRule).where(VipRule.id == rule_id, VipRule.org_id == user.org_id)
    )
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "VIP rule not found")

    db.delete(rule)
    record_audit_event(
        db,
        org_id=user.org_id,
        actor_type="user",
        actor_id=user.user_id,
        action="vip_rule.deleted",
        resource_type="vip_rule",
        resource_id=rule_id,
    )
