import { useEffect, useRef, useState } from "react";
import { askChatWidget } from "../../Data/chatWidgetApi";

const OPEN_STATE_KEY = "chatWidgetOpen";
const INTRO_MESSAGE = { role: "bot", text: "Hi, I'm Buggy! How can I assist you today?" };

// Small floating chat widget — a corner button that opens a slide-over
// panel. Answers "what does this screen do?" locally, switches the
// app's theme, and can navigate the dashboard for you (see
// Data/chatWidgetApi.js) — everything else goes to the real backend.
// Props let it be dropped onto any page with different copy rather than
// hardcoding one page's framing. navigateTo is optional — pages that
// don't pass one (e.g. the public Landing page) just don't get chat-
// driven navigation.
function MiniChatWidget({ title = "Buggy", placeholder = "Ask a question...", currentScreen, navigateTo }) {
  const [open, setOpen] = useState(() => sessionStorage.getItem(OPEN_STATE_KEY) === "true");
  const [messages, setMessages] = useState([INTRO_MESSAGE]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    sessionStorage.setItem(OPEN_STATE_KEY, String(open));
  }, [open]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const question = input.trim();
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setLoading(true);

    try {
      const answer = await askChatWidget(question, currentScreen, navigateTo);
      setMessages((prev) => [...prev, { role: "bot", text: answer }]);
    } catch (error) {
      console.error("Chat widget failed:", error);
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "Sorry, I couldn't respond just now. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setMessages([INTRO_MESSAGE]);
    setInput("");
  }

  return (
    <>
      {!open && (
        <button className="chat-widget-button" onClick={() => setOpen(true)}>
          <span className="chat-widget-button-icon">💬</span>
          Ask Buggy
        </button>
      )}

      {open && (
        <div className="ai-panel chat-widget-panel">
          <div className="chat-widget-header">
            <div className="chat-widget-header-left">
              <span className="chat-widget-avatar">💬</span>
              <h3>{title}</h3>
            </div>
            <div className="chat-widget-header-actions">
              <button
                className="chat-widget-icon-button"
                onClick={handleReset}
                aria-label="Reset conversation"
                title="Reset conversation"
              >
                ⟳
              </button>
              <button
                className="chat-widget-icon-button"
                onClick={() => setOpen(false)}
                aria-label="Close"
                title="Close"
              >
                ×
              </button>
            </div>
          </div>

          <div className="lawyer-messages chat-widget-messages">
            {messages.map((m, i) =>
              i === 0 && m.role === "bot" ? (
                <div key={i} className="chat-widget-greeting">
                  <div className="chat-widget-greeting-bubble">{m.text}</div>
                  <p className="chat-widget-disclaimer">
                    Internal assistant for HR policy questions — for guidance only.
                  </p>
                </div>
              ) : (
                <div key={i} className={m.role === "user" ? "msg msg-user" : "msg msg-lawyer"}>
                  {m.text}
                </div>
              )
            )}
            {loading && <div className="msg msg-lawyer msg-thinking">Thinking…</div>}
            <div ref={messagesEndRef} />
          </div>

          <form className="ai-panel-form chat-widget-form" onSubmit={handleSubmit}>
            <input
              placeholder={placeholder}
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button disabled={loading}>{loading ? "Thinking..." : "Send"}</button>
          </form>
        </div>
      )}
    </>
  );
}

export default MiniChatWidget;
