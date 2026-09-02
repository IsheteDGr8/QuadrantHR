import Tag from "../ui/Tag";

const ICONS = {
  on_time: "✓",
  overdue: "⚠",
  due_soon: "⏰",
  new: "🆕",
};

// Renders one badge from Data/badgesApi.js's getBadgesForEmployee response
// — {badge, label, variant}. A thin wrapper around Tag so it looks
// consistent with every other status pill in the app, plus an icon so it
// reads as a badge rather than a plain label.
function PolicyBadge({ badge, label, variant }) {
  return (
    <Tag variant={variant}>
      {ICONS[badge] || ""} {label}
    </Tag>
  );
}

export default PolicyBadge;
