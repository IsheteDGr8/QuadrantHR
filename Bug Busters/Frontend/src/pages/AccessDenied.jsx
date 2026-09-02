import Button from "../components/ui/Button";
import MiniChatWidget from "../components/chat/MiniChatWidget";

// Shown when a signed-in Entra account has no roles claim, or has one or
// more roles that don't map to anything in roleConfig.js. Not an error —
// someone genuinely hasn't been assigned an app role yet, or the mapping
// needs updating once the real Entra role values are filled in.
function AccessDenied({ roles, onLogout }) {
  return (
    <div className="login-shell">
      <div className="login-card" style={{ gridTemplateColumns: "1fr", maxWidth: 560, minHeight: 0 }}>
        <div className="login-form-panel">
          <h2>Access denied</h2>
          <p className="login-form-lede">
            {roles && roles.length > 0
              ? "Your account doesn't have a role that's set up in this app yet."
              : "Your account hasn't been assigned a role for this app yet."}{" "}
            Contact your admin if you think this is a mistake.
          </p>
          <Button variant="primary" onClick={onLogout}>
            Log out
          </Button>
        </div>
      </div>

      <MiniChatWidget title="Buggy" placeholder="Ask a question..." currentScreen="access-denied" />
    </div>
  );
}

export default AccessDenied;
