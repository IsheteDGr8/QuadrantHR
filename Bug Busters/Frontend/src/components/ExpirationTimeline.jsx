import { getExpirationInfo } from "../Data/store";

const STATUS_COLOR = {
  ok: "#16a34a",
  soon: "#d97706",
  overdue: "#dc2626",
};

// Mirrors the "Expiration timeline" panel from the design prototype —
// one row per section, with a progress bar showing how much of its
// review cycle has elapsed.
function ExpirationTimeline({ sections }) {
  if (sections.length === 0) return null;

  return (
    <div className="expiration-panel">
      <div className="expiration-panel-title">Expiration timeline</div>
      {sections.map((section) => {
        const info = getExpirationInfo(section);
        return (
          <div className="tl-row" key={section.id}>
            <div className="tl-label">{section.title}</div>
            <div className="tl-track">
              <div
                className="tl-fill"
                style={{ width: `${info.percentElapsed}%`, background: STATUS_COLOR[info.status] }}
              />
            </div>
            <div className="tl-days">
              {info.status === "overdue" ? "Review overdue" : `${info.daysRemaining}d left`}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default ExpirationTimeline;
