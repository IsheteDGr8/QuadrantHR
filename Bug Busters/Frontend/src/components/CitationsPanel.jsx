// Slide-out panel listing the government/regulatory requirements
// relevant to a section's policy type (e.g. HIPAA for Security, FMLA
// for PTO). Reuses the .ai-panel shell so it looks consistent with
// the AI Ask/Reword and History panels. Citations are a fixed list
// per template for now — same placeholder approach as generate() in
// data/policyTemplates.js, not pulled from a real legal database.

function CitationsPanel({ label, citations, onClose }) {
  return (
    <div className="ai-panel">
      <div className="ai-panel-header">
        <h3>Citations</h3>
        <button className="ai-panel-close" onClick={onClose}>
          ×
        </button>
      </div>

      <p className="ai-suggestion-note">
        Government and regulatory requirements commonly relevant to a {label} policy. Not legal
        advice — confirm applicability with legal/compliance before publishing.
      </p>

      <div className="history-list">
        {citations.map((citation) => (
          <div className="history-entry" key={citation.law}>
            <div className="history-entry-label">{citation.law}</div>
            <p className="history-entry-preview">{citation.note}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CitationsPanel;
