import { useEffect, useRef, useState } from "react";
import { TONE_OPTIONS } from "../Data/policyTemplates";
import { Input, Select } from "../components/ui/FormControls";
import Button from "../components/ui/Button";
import LoadingDots from "../components/ui/LoadingDots";
import { createSection, roleLabel } from "../Data/store";
import { BACKEND_URL, COMPANY_NAME } from "../Data/backendConfig";
import { getAuthHeader } from "../Data/authToken";

const API_BASE = BACKEND_URL;

// Agentic policy-section creation: HR describes what they want in one
// box and the assistant asks follow-up questions conversationally,
// rather than a fixed field form tied to a preset category (WFH, Code
// of Conduct, etc.). Reuses the incident-chat layout/CSS classes since
// the shape (chat on the left, generated output on the right) is the
// same interaction.
function PolicyChatCreate({ role, onSectionCreated, onCancel }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [title, setTitle] = useState("");
  const [tone, setTone] = useState(TONE_OPTIONS[0]);
  const [generating, setGenerating] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    if (!input.trim() || sending) return;

    const nextMessages = [...messages, { role: "user", text: input.trim() }];
    setMessages(nextMessages);
    setInput("");
    setSending(true);

    try {
      const authHeader = await getAuthHeader();

      const response = await fetch(`${API_BASE}/policy-chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(authHeader || {}),
        },
        body: JSON.stringify({
          messages: nextMessages.map((m) => ({ role: m.role, text: m.text })),
        }),
      });

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const data = await response.json();
      const reply =
        data.reply.trim() === "READY"
          ? 'I have enough to draft this. Set a title and tone on the right, then click "Generate Section" — or keep adding detail first.'
          : data.reply;

      setMessages((prev) => [...prev, { role: "assistant", text: reply }]);
    } catch (error) {
      console.error("Policy chat failed:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Sorry, I couldn't respond just now. Please try again." },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function handleGenerate(e) {
    e.preventDefault();
    if (generating || !title.trim()) return;

    setGenerating(true);
    try {
      const requirements = messages.filter((m) => m.role === "user").map((m) => m.text);
      const authHeader = await getAuthHeader();

      const response = await fetch(`${API_BASE}/generate-policy`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(authHeader || {}),
        },
        body: JSON.stringify({
          company_name: COMPANY_NAME,
          policy_type: "Custom Section",
          title,
          tone,
          requirements,
        }),
      });

      if (!response.ok) {
        throw new Error(`Backend returned ${response.status}`);
      }

      const data = await response.json();

      const section = createSection({
        role,
        sectionType: "chat",
        title,
        content: data.policy,
        tone,
        answers: { conversation: requirements },
      });

      onSectionCreated(section);
    } catch (error) {
      console.error("Policy generation failed:", error);
      alert("Failed to generate policy. Please try again.");
    } finally {
      setGenerating(false);
    }
  }

  const userMessageCount = messages.filter((m) => m.role === "user").length;

  return (
    <div className="incident-page">
      {onCancel && (
        <Button variant="secondary" size="sm" onClick={onCancel} style={{ marginBottom: 8 }}>
          ← Back to Policies
        </Button>
      )}
      <h1>New Policy Section</h1>
      <p className="editor-hint">
        Describe what you want this section to cover for {roleLabel(role)} — the assistant will
        ask follow-up questions, then draft it with you.
      </p>

      <div className="incident-layout">
        <div className="incident-chat panel">
          <div className="incident-messages">
            {messages.length === 0 && (
              <p className="lawyer-empty">
                Start typing below, e.g. "a policy about pets in the office."
              </p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "msg msg-user" : "msg msg-lawyer"}>
                {m.text}
              </div>
            ))}
            {sending && <div className="msg msg-lawyer msg-thinking">…</div>}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={handleSend} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <Input
              placeholder="Describe what you want, or answer the follow-up..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              autoCapitalize="sentences"
              autoCorrect="off"
              spellCheck="true"
            />
            <Button variant="primary" disabled={sending}>
              {sending ? <LoadingDots /> : "Send"}
            </Button>
          </form>
        </div>

        <div className="incident-report panel">
          <h2>Draft This Section</h2>

          <p className="sidebar-empty" style={{ color: "var(--color-text-muted)" }}>
            {userMessageCount === 0
              ? "Once you've described what you want in the chat, set a title and tone here to generate it."
              : "Set a title and tone, then generate whenever you're ready."}
          </p>

          <form
            onSubmit={handleGenerate}
            style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 16 }}
          >
            <label>
              <div style={{ fontSize: 13, marginBottom: 6, color: "var(--color-text-muted)" }}>
                Section title
              </div>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Pet Policy"
                required
              />
            </label>

            <label>
              <div style={{ fontSize: 13, marginBottom: 6, color: "var(--color-text-muted)" }}>
                Tone
              </div>
              <Select value={tone} onChange={(e) => setTone(e.target.value)} required>
                {TONE_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </Select>
            </label>

            <Button
              variant="primary"
              type="submit"
              disabled={generating || userMessageCount === 0}
              style={{ alignSelf: "flex-start" }}
            >
              {generating ? (
                <>
                  Generating (can take 30-40s) <LoadingDots />
                </>
              ) : (
                "Generate Section"
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default PolicyChatCreate;
