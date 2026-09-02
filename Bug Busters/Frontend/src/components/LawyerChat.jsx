import { useState } from "react";
import { askLawyer } from "../Data/aiMock";

// A floating button, available across the HR dashboard, that opens a
// slide-over chat for legal questions about policy language.
function LawyerChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const question = input;
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setLoading(true);

    const answer = await askLawyer(question);
    setMessages((prev) => [...prev, { role: "lawyer", text: answer }]);
    setLoading(false);
  }

  return (
    <>
      <button className="lawyer-button" onClick={() => setOpen(true)}>
        ⚖ Lawyer
      </button>

      {open && (
        <div className="ai-panel lawyer-panel">
          <div className="ai-panel-header">
            <h3>Ask a Lawyer</h3>
            <button className="ai-panel-close" onClick={() => setOpen(false)}>
              ×
            </button>
          </div>

          <p className="lawyer-disclaimer">
            Placeholder legal assistant for prototyping — not real legal advice.
          </p>

          <div className="lawyer-messages">
            {messages.length === 0 && (
              <p className="lawyer-empty">Ask a question about a policy or clause.</p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "msg msg-user" : "msg msg-lawyer"}>
                {m.text}
              </div>
            ))}
            {loading && <div className="msg msg-lawyer msg-thinking">Thinking…</div>}
          </div>

          <form className="ai-panel-form" onSubmit={handleSubmit}>
            <input
              placeholder="Ask a legal question..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button disabled={loading}>{loading ? "Thinking..." : "Ask"}</button>
          </form>
        </div>
      )}
    </>
  );
}

export default LawyerChat;
