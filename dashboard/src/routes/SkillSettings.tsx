import { FormEvent, useEffect, useState } from "react";
import { api, KNOWN_SKILL_NAMES, OrgSkillSetting, VipRule } from "../api/client";

export default function SkillSettings() {
  const [settings, setSettings] = useState<OrgSkillSetting[]>([]);
  const [vipRules, setVipRules] = useState<VipRule[]>([]);
  const [newVipPattern, setNewVipPattern] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    Promise.all([api.listSkillSettings(), api.listVipRules()])
      .then(([s, v]) => {
        setSettings(s);
        setVipRules(v);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load settings"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  function isEnabled(skillName: string): boolean {
    const found = settings.find((s) => s.skill_name === skillName);
    // triage/draft-reply are the safe Phase 1 default when unconfigured.
    return found ? found.enabled : skillName === "triage" || skillName === "draft-reply";
  }

  async function toggleSkill(skillName: string) {
    try {
      const updated = await api.updateSkillSetting(skillName, !isEnabled(skillName));
      setSettings((prev) => [updated, ...prev.filter((s) => s.skill_name !== skillName)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update skill setting");
    }
  }

  async function addVipRule(e: FormEvent) {
    e.preventDefault();
    if (!newVipPattern.trim()) return;
    try {
      const rule = await api.createVipRule(newVipPattern.trim());
      setVipRules((prev) => [rule, ...prev]);
      setNewVipPattern("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add VIP rule");
    }
  }

  async function removeVipRule(id: string) {
    const previous = vipRules;
    setVipRules((rs) => rs.filter((r) => r.id !== id));
    try {
      await api.deleteVipRule(id);
    } catch (err) {
      setVipRules(previous);
      setError(err instanceof Error ? err.message : "Failed to remove VIP rule");
    }
  }

  if (loading) return <p>Loading...</p>;

  return (
    <div>
      <h2>Skill Settings</h2>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}

      <div className="card">
        <h3>Skills</h3>
        {KNOWN_SKILL_NAMES.map((name) => (
          <div key={name} style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
            <input
              type="checkbox"
              id={`skill-${name}`}
              checked={isEnabled(name)}
              onChange={() => toggleSkill(name)}
            />
            <label htmlFor={`skill-${name}`}>{name}</label>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>VIP senders</h3>
        <p style={{ color: "#666" }}>
          Exact email address or <code>@domain.com</code>. Matching senders are always escalated
          by the vip-escalation skill.
        </p>
        {vipRules.map((rule) => (
          <div key={rule.id} style={{ marginBottom: "0.4rem" }}>
            {rule.sender_pattern}{" "}
            <button className="danger" onClick={() => removeVipRule(rule.id)}>
              Remove
            </button>
          </div>
        ))}
        <form onSubmit={addVipRule} style={{ marginTop: "0.5rem" }}>
          <input
            type="text"
            placeholder="ceo@example.com or @board.example.com"
            value={newVipPattern}
            onChange={(e) => setNewVipPattern(e.target.value)}
          />{" "}
          <button className="primary" type="submit">
            Add
          </button>
        </form>
      </div>
    </div>
  );
}
