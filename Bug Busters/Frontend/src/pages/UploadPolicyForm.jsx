import { useState } from "react";
import { createSection, roleLabel } from "../Data/store";
import { Field, Input } from "../components/ui/FormControls";
import Button from "../components/ui/Button";
import { extractTextFromFile } from "../Data/policyUpload";

// Lets HR bring an existing policy document into the app as a normal
// section, so it gets the same editor, AI features (ask/reword), and
// history tracking as an AI-generated one. .txt/.md are read directly
// in the browser; .pdf/.docx go through the backend's real parser
// (pypdf/python-docx) since there's no reliable way to extract that
// text client-side.

const TEXT_EXTENSIONS = [".txt", ".md"];

function UploadPolicyForm({ role, onSectionCreated, onCancel }) {
  const [fileName, setFileName] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [extracting, setExtracting] = useState(false);

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;

    setError("");
    setContent("");
    setFileName(file.name);
    setTitle(file.name.replace(/\.[^/.]+$/, ""));

    const isPlainText = TEXT_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext));

    if (isPlainText) {
      const reader = new FileReader();
      reader.onload = () => setContent(reader.result);
      reader.onerror = () => setError("Couldn't read that file. Try a plain .txt or .md file.");
      reader.readAsText(file);
      return;
    }

    setExtracting(true);
    try {
      const text = await extractTextFromFile(file, "uploaded");
      setContent(text);
    } catch (err) {
      setError(err.message || "Couldn't extract text from that file.");
    } finally {
      setExtracting(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!content) return;

    const section = createSection({
      role,
      sectionType: "uploaded",
      title: title || fileName || "Uploaded Policy",
      content,
      tone: "Professional",
      answers: {},
    });
    onSectionCreated(section);
  }

  return (
    <div className="questionnaire-page">
      {onCancel && (
        <Button variant="secondary" size="sm" onClick={onCancel} style={{ marginBottom: 8 }}>
          ← Back to Policies
        </Button>
      )}
      <h1>Upload Existing Policy</h1>
      <p className="editor-hint">
        {roleLabel(role)} · Upload a .pdf, .docx, .txt, or .md policy document to bring it into
        the editor alongside generated sections.
      </p>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 600 }}>
        <Field label="File">
          <input
            type="file"
            accept=".txt,.md,.pdf,.docx,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={handleFileChange}
            disabled={extracting}
          />
        </Field>

        {extracting && <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>Extracting text from {fileName}…</p>}

        {error && <p className="ai-suggestion-note">{error}</p>}

        {content && (
          <>
            <Field label="Section title">
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Existing Remote Work Policy"
              />
            </Field>

            <Field label="Preview">
              <p className="upload-preview">{content}</p>
            </Field>
          </>
        )}

        <Button variant="primary" type="submit" disabled={!content} style={{ alignSelf: "flex-start" }}>
          Add to Policies
        </Button>
      </form>
    </div>
  );
}

export default UploadPolicyForm;
