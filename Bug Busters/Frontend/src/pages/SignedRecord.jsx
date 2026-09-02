import Button from "../components/ui/Button";
import SignatureDisplay from "../components/signature/SignatureDisplay";
import PolicyContent from "../components/policy/PolicyContent";
import { roleLabel } from "../Data/store";

// A permanent, read-only record of one signature: who signed, when, and
// the exact content (and version) of each section as it existed at send
// time — assignment.parts is a snapshot taken when the policy was sent,
// so later edits to the live section never change what shows here.
function SignedRecord({ assignment, employeeName, onBack }) {
  return (
    <div className="policy-viewer">
      <Button variant="secondary" size="sm" onClick={onBack} style={{ marginBottom: 16 }}>
        ← Back
      </Button>

      <div className="policy-viewer-header">
        <h1>{roleLabel(assignment.role)} Policy — Signed Record</h1>

        {assignment.status === "signed" ? (
          <>
            <p className="signed-note">
              Signed by {assignment.signedBy || employeeName} on{" "}
              {new Date(assignment.signedAt).toLocaleString()}
            </p>
            <SignatureDisplay signature={assignment.signature} signedBy={assignment.signedBy} />
          </>
        ) : (
          <p className="pending-note">
            {employeeName} has not signed this policy yet.
          </p>
        )}
      </div>

      <p className="editor-hint">
        Recipient: <strong>{employeeName}</strong>
      </p>

      {assignment.parts.map((part) => (
        <div className="policy-text" key={part.sectionId}>
          <h2>
            {part.title}
            {part.version && <span className="tag tag-neutral" style={{ marginLeft: 10 }}>v{part.version}</span>}
          </h2>
          <PolicyContent content={part.content} />
        </div>
      ))}
    </div>
  );
}

export default SignedRecord;
