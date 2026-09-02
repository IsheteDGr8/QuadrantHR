// Renders a policy section's raw text with numbered headings (the
// "1. Policy title" / "2. Purpose" / ... outline backend/prompt_builder.py
// asks the AI to follow) styled as bold subheadings, real paragraphs
// getting normal spacing, and blank lines collapsed instead of turning
// into empty, gappy <p> tags. Shared by every place that renders a
// section's content as-is: PolicyOverall.jsx, PolicyViewer.jsx,
// SignedRecord.jsx.
const SECTION_HEADING_PATTERN = /^\d+\.\s+\S.{0,80}$/;

function isSectionHeading(line) {
  return SECTION_HEADING_PATTERN.test(line.trim());
}

function PolicyContent({ content }) {
  const lines = content.split("\n").filter((line) => line.trim() !== "");

  return (
    <>
      {lines.map((line, i) =>
        isSectionHeading(line) ? (
          <p className="policy-section-heading" key={i}>
            {line.trim()}
          </p>
        ) : (
          <p key={i}>{line}</p>
        )
      )}
    </>
  );
}

export default PolicyContent;
