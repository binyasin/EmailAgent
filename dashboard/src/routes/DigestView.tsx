import { useEffect, useState } from "react";
import { api, DigestRun } from "../api/client";

export default function DigestView() {
  const [digests, setDigests] = useState<DigestRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listDigests()
      .then(setDigests)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load digests"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2>Digests</h2>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}
      {loading ? (
        <p>Loading...</p>
      ) : digests.length === 0 ? (
        <p>No digests generated yet.</p>
      ) : (
        digests.map((digest) => (
          <div className="card" key={digest.id}>
            <strong>{digest.period}</strong>{" "}
            <span style={{ color: "#666" }}>
              {new Date(digest.created_at).toLocaleString()}
            </span>
            <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", marginTop: "0.5rem" }}>
              {digest.summary_text}
            </pre>
          </div>
        ))
      )}
    </div>
  );
}
