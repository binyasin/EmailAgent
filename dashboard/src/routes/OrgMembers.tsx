import { FormEvent, useEffect, useState } from "react";
import { api, OrgMember } from "../api/client";

export default function OrgMembers() {
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [lastInvite, setLastInvite] = useState<{ email: string; password: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    api
      .listMembers()
      .then(setMembers)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load members"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function invite(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const result = await api.inviteMember(email, role);
      setMembers((prev) => [...prev, result.user]);
      setLastInvite({ email: result.user.email, password: result.temporary_password });
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to invite member");
    }
  }

  async function changeRole(memberId: string, newRole: string) {
    try {
      const updated = await api.changeMemberRole(memberId, newRole);
      setMembers((ms) => ms.map((m) => (m.id === memberId ? updated : m)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change role");
    }
  }

  async function remove(memberId: string) {
    const previous = members;
    setMembers((ms) => ms.filter((m) => m.id !== memberId));
    try {
      await api.removeMember(memberId);
    } catch (err) {
      setMembers(previous);
      setError(err instanceof Error ? err.message : "Failed to remove member");
    }
  }

  return (
    <div>
      <h2>Org Members</h2>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}
      {lastInvite && (
        <div className="card">
          Invited <strong>{lastInvite.email}</strong>. One-time temporary password (share this
          out-of-band — it will not be shown again):{" "}
          <code>{lastInvite.password}</code>
        </div>
      )}

      {loading ? (
        <p>Loading...</p>
      ) : (
        members.map((m) => (
          <div className="card" key={m.id}>
            {m.email} —{" "}
            <select value={m.role} onChange={(e) => changeRole(m.id, e.target.value)}>
              <option value="member">member</option>
              <option value="org_admin">org_admin</option>
            </select>{" "}
            <button className="danger" onClick={() => remove(m.id)}>
              Remove
            </button>
          </div>
        ))
      )}

      <form onSubmit={invite} className="card">
        <h3>Invite a member</h3>
        <input
          type="email"
          placeholder="email@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />{" "}
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="member">member</option>
          <option value="org_admin">org_admin</option>
        </select>{" "}
        <button className="primary" type="submit">
          Invite
        </button>
      </form>
    </div>
  );
}
