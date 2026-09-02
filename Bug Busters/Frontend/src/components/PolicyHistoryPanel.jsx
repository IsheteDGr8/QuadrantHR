import { useState } from "react";
import Button from "./ui/Button";

// Slide-out panel listing a section's past versions (most recent
// first), each restorable back into the editor. Reuses the .ai-panel
// shell styling so it looks consistent with the AI Ask/Reword panel.

function formatDate(iso) {
  if (!iso) return "Unknown time";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function PolicyHistoryPanel({ section, onClose, onRestore }) {
  const [expandedIndex, setExpandedIndex] = useState(null);
  const history = section.history || [];
  // Most recent past version first; current version shown separately at top.
  const reversed = history.map((entry, i) => ({ entry, index: i })).reverse();

  return (
    <div className="ai-panel">
      <div className="ai-panel-header">
        <h3>Policy History</h3>
        <button className="ai-panel-close" onClick={onClose}>
          ×
        </button>
      </div>

      <div className="history-entry history-entry-current">
        <div className="history-entry-meta">
          <span className="history-entry-label">Current version</span>
          <span className="history-entry-date">{formatDate(section.updatedAt)}</span>
        </div>
        <div className="history-entry-tone">{section.tone || "Professional"} tone</div>
      </div>

      {reversed.length === 0 ? (
        <p className="sidebar-empty">No earlier versions yet — edits will show up here.</p>
      ) : (
        <div className="history-list">
          {reversed.map(({ entry, index }) => {
            const isOpen = expandedIndex === index;
            return (
              <div className="history-entry" key={index}>
                <button
                  className="history-entry-meta history-entry-toggle"
                  onClick={() => setExpandedIndex(isOpen ? null : index)}
                >
                  <span className="history-entry-label">
                    {isOpen ? "▾" : "▸"} Changed {formatDate(entry.updatedAt)}
                  </span>
                </button>
                <div className="history-entry-tone">{entry.tone || "Professional"} tone</div>

                {isOpen && (
                  <>
                    <p className="history-entry-preview">{entry.content}</p>
                    <Button variant="primary" size="sm" onClick={() => onRestore(index)}>
                      Restore this version
                    </Button>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default PolicyHistoryPanel;
