// Three-arc signature coverage donut for the Manager dashboard — same
// technique as the design mockup's hand-drawn SVG, but with the arc
// lengths and rotations computed from real counts instead of hardcoded.
function ManagerCoverageDonut({ signed, pending, notSent }) {
  const total = signed + pending + notSent;
  const circumference = 2 * Math.PI * 40;

  const arcLength = (count) => (total === 0 ? 0 : (count / total) * circumference);
  const signedLen = arcLength(signed);
  const pendingLen = arcLength(pending);
  const notSentLen = arcLength(notSent);

  const rotationAt = (offset) => -90 + (offset / circumference) * 360;

  return (
    <div>
      <svg
        viewBox="0 0 100 100"
        style={{ width: 150, height: 150, display: "block" }}
        role="img"
        aria-label={`${signed} of ${total} signed, ${pending} pending, ${notSent} not sent`}
      >
        <circle
          cx="50" cy="50" r="40" fill="none" stroke="#6b4ce6" strokeWidth="20"
          strokeDasharray={`${signedLen} ${circumference}`}
          transform={`rotate(${rotationAt(0)} 50 50)`}
        />
        <circle
          cx="50" cy="50" r="40" fill="none" stroke="#e8c477" strokeWidth="20"
          strokeDasharray={`${pendingLen} ${circumference}`}
          transform={`rotate(${rotationAt(signedLen)} 50 50)`}
        />
        <circle
          cx="50" cy="50" r="40" fill="none" stroke="#ded3fb" strokeWidth="20"
          strokeDasharray={`${notSentLen} ${circumference}`}
          transform={`rotate(${rotationAt(signedLen + pendingLen)} 50 50)`}
        />
      </svg>

      <div className="donut-legend">
        <div>
          <span className="donut-swatch" style={{ background: "#6b4ce6" }} />
          Signed · {signed}
        </div>
        <div>
          <span className="donut-swatch" style={{ background: "#e8c477" }} />
          Pending · {pending}
        </div>
        <div>
          <span className="donut-swatch" style={{ background: "#ded3fb" }} />
          Not sent · {notSent}
        </div>
      </div>
    </div>
  );
}

export default ManagerCoverageDonut;
