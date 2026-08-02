import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setStoredToken } from "../api/client";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { access_token } = await api.login(email, password);
      setStoredToken(access_token);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <div className="card">
      <h2>Log in</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label>
            Email
            <br />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
        </div>
        <div style={{ marginTop: "0.5rem" }}>
          <label>
            Password
            <br />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
        </div>
        {error && <p style={{ color: "#c0392b" }}>{error}</p>}
        <button type="submit" className="primary" style={{ marginTop: "0.75rem" }}>
          Log in
        </button>
      </form>
    </div>
  );
}
