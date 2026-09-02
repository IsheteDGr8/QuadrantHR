import { Fragment, useRef, useState } from "react";
import AIResponsePanel from "../components/ai/AIResponsePanel";
import PolicyHistoryPanel from "../components/PolicyHistoryPanel";
import CitationsPanel from "../components/CitationsPanel";
import Button from "../components/ui/Button";
import { saveSection, restoreSectionVersion } from "../Data/store";
import { SECTION_TEMPLATES } from "../Data/policyTemplates";
import { exportSection } from "../Data/policyExport";

// Edits one section of one role's policy. Uses a <textarea>, not
// rendered text, so it can't use the Highlighter component
// (window.getSelection doesn't see into form inputs). Instead it
// tracks selectionStart/selectionEnd directly.

function SectionEditor({ section, onUpdated, onBack }) {
  const [content, setContent] = useState(section.content);
  const [selection, setSelection] = useState({ text: "", start: 0, end: 0 });
  // Only one side panel can be open at a time — opening one closes any other.
  const [activePanel, setActivePanel] = useState(null); // null | "ask" | "reword" | "history" | "citations"
  const [savedNote, setSavedNote] = useState(false);
  const [currentSection, setCurrentSection] = useState(section);
  const [exporting, setExporting] = useState(null); // null | "pdf" | "docx"
  const textareaRef = useRef(null);
  const template = SECTION_TEMPLATES[section.sectionType];
  const citations = template?.citations || [];

  function handleSelect() {
    const el = textareaRef.current;
    if (!el) return;

    setSelection({
      text: el.value.slice(el.selectionStart, el.selectionEnd),
      start: el.selectionStart,
      end: el.selectionEnd,
    });
  }

  function handleSave() {
    const updated = { ...currentSection, content, updatedAt: new Date().toISOString() };
    const saved = saveSection(updated);
    setCurrentSection(saved);
    onUpdated(saved);
    setSavedNote(true);
    setTimeout(() => setSavedNote(false), 2000);
  }

  function handleApplyReword(newText) {
    setContent(
      (prev) => prev.slice(0, selection.start) + newText + prev.slice(selection.end)
    );
    setActivePanel(null);
  }

  function handleRestore(historyIndex) {
    const restored = restoreSectionVersion(currentSection.id, historyIndex);
    if (!restored) return;
    setCurrentSection(restored);
    setContent(restored.content);
    onUpdated(restored);
    setActivePanel(null);
  }

  async function handleExport(format) {
    if (exporting) return;

    setExporting(format);
    try {
      // Export exactly what's on screen, including unsaved edits. The
      // first export creates a backend record; every export after that
      // PATCHes it instead, so version history actually builds up.
      const saved = await exportSection({ ...currentSection, content }, format);
      const updated = saveSection({ ...currentSection, content, backendPolicyId: saved.id });
      setCurrentSection(updated);
      onUpdated(updated);
    } catch (err) {
      console.error(err);
      alert(`Failed to export as ${format.toUpperCase()}. Please try again.`);
    } finally {
      setExporting(null);
    }
  }

  return (
    <Fragment>
      <div className="nav editor-header-bar">
        {onBack && (
          <Button variant="secondary" size="sm" onClick={onBack}>
            ← Back to Policies
          </Button>
        )}
        <div className="nav-brand" style={{ fontSize: 19 }}>
          {section.title}
          <span className="nav-brand-sub" style={{ textTransform: "none", letterSpacing: 0 }}>
            {currentSection.tone || "Professional"} tone · draft
          </span>
        </div>
        <Button variant="secondary" size="sm" onClick={handleSave}>
          Save draft
        </Button>
      </div>

      <div className="policy-editor">
      <p className="editor-hint">
        {section.role} section · Highlight text below, then ask AI about it or have AI reword it.
      </p>

      <textarea
        ref={textareaRef}
        className="policy-editor-textarea"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onSelect={handleSelect}
      />

      <div className="ai-selection-actions">
        <Button variant="secondary" size="sm" disabled={!selection.text} onClick={() => setActivePanel("ask")}>
          Ask AI about selection
        </Button>
        <Button variant="secondary" size="sm" disabled={!selection.text} onClick={() => setActivePanel("reword")}>
          Reword selection
        </Button>
      </div>

      <div className="policy-editor-actions">
        <Button variant="primary" onClick={handleSave}>
          Save
        </Button>
        <Button variant="secondary" onClick={() => setActivePanel("history")}>
          History{(currentSection.history || []).length > 0 && ` (${currentSection.history.length})`}
        </Button>
        {citations.length > 0 && (
          <Button variant="secondary" onClick={() => setActivePanel("citations")}>
            Citations ({citations.length})
          </Button>
        )}
        <Button variant="secondary" disabled={!!exporting} onClick={() => handleExport("pdf")}>
          {exporting === "pdf" ? "Exporting…" : "Download PDF"}
        </Button>
        <Button variant="secondary" disabled={!!exporting} onClick={() => handleExport("docx")}>
          {exporting === "docx" ? "Exporting…" : "Download DOCX"}
        </Button>
      </div>

      {savedNote && <p className="sent-confirmation">Saved.</p>}

      {(activePanel === "ask" || activePanel === "reword") && (
        <AIResponsePanel
          mode={activePanel}
          highlightedText={selection.text}
          allowApply
          onClose={() => setActivePanel(null)}
          onApplyReword={handleApplyReword}
        />
      )}

      {activePanel === "history" && (
        <PolicyHistoryPanel
          section={currentSection}
          onClose={() => setActivePanel(null)}
          onRestore={handleRestore}
        />
      )}

      {activePanel === "citations" && (
        <CitationsPanel
          label={template?.label || section.title}
          citations={citations}
          onClose={() => setActivePanel(null)}
        />
      )}

      </div>
    </Fragment>
  );
}

export default SectionEditor;
