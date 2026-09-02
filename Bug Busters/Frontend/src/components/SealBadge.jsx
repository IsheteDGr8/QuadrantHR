// The one deliberate visual flourish in this app: a wax-seal-style
// badge, used only to mark a policy that's actually been signed.
// Keeping it to this single motif (rather than decorating everything)
// is what makes it read as intentional instead of decorative.
function SealBadge({ size = "md" }) {
  return (
    <span className={size === "sm" ? "seal-badge seal-badge-sm" : "seal-badge"}>
      <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="5 13 10 18 19 7" />
      </svg>
    </span>
  );
}

export default SealBadge;
