// Mirrors the "Compliance health" donut from the design prototype, but
// shows what % of assigned employees have signed this role's policy.
function SignaturesPieChart({ signed, total }) {
  const percent = total === 0 ? 0 : Math.round((signed / total) * 100);
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const dashoffset = circumference * (1 - percent / 100);
  const color = percent === 100 ? "#16a34a" : percent >= 50 ? "#2563eb" : "#d97706";

  return (
    <div className="signatures-chart">
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="#e5e7eb" strokeWidth="14" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeDasharray={circumference}
          strokeDashoffset={dashoffset}
          strokeLinecap="round"
          transform="rotate(-90 70 70)"
        />
        <text x="70" y="66" textAnchor="middle" fontSize="28" fontWeight="600" fill="#111827">
          {percent}%
        </text>
        <text x="70" y="86" textAnchor="middle" fontSize="10" fill="#6b7280">
          SIGNED
        </text>
      </svg>
      <p className="signatures-caption">
        {total === 0
          ? "Not sent yet"
          : `${signed} of ${total} ${total === 1 ? "person has" : "people have"} signed`}
      </p>
    </div>
  );
}

export default SignaturesPieChart;
