// Small formatting helpers shared by the dashboards.

export function greeting(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

// "Monday, 17 August 2026"
export function formattedToday(date = new Date()) {
  return date.toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

// "12 Aug"
export function formatShortDate(isoString) {
  if (!isoString) return "";
  return new Date(isoString).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

export function relativeTime(isoString) {
  if (!isoString) return "";

  const then = new Date(isoString).getTime();
  const diffMs = Date.now() - then;
  const hours = Math.floor(diffMs / (60 * 60 * 1000));

  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;

  return formatShortDate(isoString);
}
