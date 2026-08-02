from datetime import datetime

from pydantic import BaseModel, ConfigDict

# Skills a client is allowed to toggle. Keeping this as an explicit allowlist
# (rather than accepting any string) stops a typo'd skill_name from silently
# creating a dead OrgSkillSetting row that config_renderer.py never reads.
KNOWN_SKILL_NAMES = {
    "triage",
    "draft-reply",
    "digest",
    "scheduling",
    "followup-nudge",
    "vip-escalation",
    "unsubscribe-cleanup",
    "sensitive-content-flagging",
}


class OrgSkillSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    skill_name: str
    enabled: bool
    params: dict
    created_at: datetime


class OrgSkillSettingUpdate(BaseModel):
    enabled: bool
    params: dict = {}


class VipRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sender_pattern: str
    priority: int
    created_at: datetime


class VipRuleCreate(BaseModel):
    sender_pattern: str
    priority: int = 0
