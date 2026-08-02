import { useEffect, useState } from "react";
import { api, MailboxConnection } from "../api/client";

export default function MailboxConnect() {
  const [mailboxes, setMailboxes] = useState<MailboxConnection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listMailboxes()
      .then(setMailboxes)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load mailboxes"))
      .finally(() => setLoading(false));
  }, []);

  async function connectGmail() {
    try {
      const { authorization_url } = await api.startGmailOAuth();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start Gmail OAuth");
    }
  }

  async function connectOutlook() {
    try {
      const { authorization_url } = await api.startOutlookOAuth();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start Outlook OAuth");
    }
  }

  return (
    <div>
      <h2>Mailboxes</h2>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}
      {loading ? (
        <p>Loading...</p>
      ) : mailboxes.length === 0 ? (
        <p>No mailbox connected yet.</p>
      ) : (
        mailboxes.map((mb) => (
          <div className="card" key={mb.id}>
            <strong>{mb.provider}</strong> — {mb.email_address}{" "}
            <span style={{ color: "#666" }}>({mb.status})</span>
          </div>
        ))
      )}
      <button className="primary" onClick={connectGmail}>
        Connect Gmail
      </button>{" "}
      <button className="primary" onClick={connectOutlook}>
        Connect Outlook
      </button>
    </div>
  );
}
