import { useState } from "react";
import Button from "../components/ui/Button";
import { Field, Input } from "../components/ui/FormControls";
import { demoLogin } from "../Data/demoAuth";

function Login({ onSignedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!email.trim() || loading) return;

    setLoading(true);
    setError("");

    try {
      const user = await demoLogin(email.trim());
      onSignedIn(user);
    } catch (err) {
      setError(err.message || "Sign-in failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-brand-panel">
          <div className="login-wordmark">
            Policy
            <br />
            Guardian
          </div>
          <div className="login-subtitle">AI Policy Generator</div>
          <p className="login-lede">
            Sign in to continue — which dashboard you land on depends on the
            role tied to your account.
          </p>
        </div>

        <div className="login-form-panel">
          <h2>Sign in</h2>
          <p className="login-form-lede">
            Enter your organization email to continue.
          </p>

          <form onSubmit={handleSubmit} className="dev-login-form">
            <Field label="Email">
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@quadranttechnologies.com"
                required
              />
            </Field>

            <Field label="Password">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>

            {error && <p style={{ color: "var(--color-danger, #c0392b)" }}>{error}</p>}

            <Button variant="primary" block type="submit" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default Login;
