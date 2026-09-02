// Renders a captured signature — a drawn image, or the signer's typed
// name in a script font — wherever a signed record needs to show it.
// signature is Data/store.js's assignment.signature shape, and may be
// null/undefined for records signed before this existed.
function SignatureDisplay({ signature, signedBy }) {
  if (signature?.mode === "draw" && signature.drawingDataUrl) {
    return (
      <img
        className="signature-display-image"
        src={signature.drawingDataUrl}
        alt={`${signedBy}'s signature`}
      />
    );
  }

  if (signedBy) {
    return <div className="signature-display-typed">{signedBy}</div>;
  }

  return null;
}

export default SignatureDisplay;
