import { useEffect, useState } from "react";
import { api, AgentCell } from "../api/client";

export default function AdminCells() {
  const [cells, setCells] = useState<AgentCell[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    api
      .listCells()
      .then(setCells)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load cells"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function restart(orgId: string) {
    try {
      const updated = await api.restartCell(orgId);
      setCells((cs) => cs.map((c) => (c.org_id === orgId ? updated : c)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restart cell");
      load(); // status may have flipped to "error" server-side even on failure
    }
  }

  return (
    <div>
      <h2>Agent Cells (platform admin)</h2>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}
      {loading ? (
        <p>Loading...</p>
      ) : cells.length === 0 ? (
        <p>No cells provisioned yet.</p>
      ) : (
        cells.map((cell) => (
          <div className="card" key={cell.id}>
            <strong>{cell.org_id}</strong> — {cell.tenant_key}{" "}
            <span style={{ color: cell.status === "running" ? "#2f9e44" : "#c0392b" }}>
              ({cell.status})
            </span>
            <p style={{ color: "#666", fontSize: "0.85rem" }}>
              {cell.image_ref} · port {cell.host_port ?? "?"} · config v{cell.config_version}
            </p>
            <button className="primary" onClick={() => restart(cell.org_id)}>
              Restart
            </button>
          </div>
        ))
      )}
    </div>
  );
}
