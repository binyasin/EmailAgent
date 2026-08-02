import { useEffect, useState } from "react";
import { api, Draft } from "../api/client";

export default function ApprovalInbox() {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    api
      .listDrafts("pending_review")
      .then(setDrafts)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load drafts"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function approve(id: string) {
    const previous = drafts;
    setDrafts((ds) => ds.filter((d) => d.id !== id)); // optimistic update
    try {
      await api.approveDraft(id);
    } catch (err) {
      setDrafts(previous); // rollback on failure
      setError(err instanceof Error ? err.message : "Failed to approve draft");
    }
  }

  async function reject(id: string) {
    const previous = drafts;
    setDrafts((ds) => ds.filter((d) => d.id !== id));
    try {
      await api.rejectDraft(id);
    } catch (err) {
      setDrafts(previous);
      setError(err instanceof Error ? err.message : "Failed to reject draft");
    }
  }

  return (
    <div>
      <h2>Approval Inbox</h2>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}
      {loading ? (
        <p>Loading...</p>
      ) : drafts.length === 0 ? (
        <p>No drafts awaiting review.</p>
      ) : (
        drafts.map((draft) => (
          <div className="card" key={draft.id} data-testid="draft-card">
            <strong>{draft.subject || "(no subject)"}</strong>
            <p style={{ color: "#666" }}>{draft.snippet}</p>
            <p style={{ fontSize: "0.85rem", color: "#999" }}>
              drafted by {draft.created_by_skill}
            </p>
            <button className="primary" onClick={() => approve(draft.id)}>
              Approve &amp; send
            </button>{" "}
            <button className="danger" onClick={() => reject(draft.id)}>
              Reject
            </button>
          </div>
        ))
      )}
    </div>
  );
}
