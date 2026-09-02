// Applies saved appearance prefs as CSS custom properties / attributes
// on the document root, so theme/typeface/text-size are one re-render
// away from taking effect anywhere in the app.

export const FONT_STACKS = {
  sans: '"IBM Plex Sans", system-ui, sans-serif',
  serif: '"Source Serif 4", Georgia, serif',
  mono: 'ui-monospace, Menlo, monospace',
};

const TEXT_SIZE_PX = { sm: 14, md: 16, lg: 18 };

export function applyPrefs(prefs) {
  const root = document.documentElement;

  if (prefs.theme === "light" || prefs.theme === "dark") {
    root.setAttribute("data-theme", prefs.theme);
  } else {
    root.removeAttribute("data-theme");
  }

  const stack = FONT_STACKS[prefs.typeface] || FONT_STACKS.sans;
  root.style.setProperty("--font-body", stack);
  root.style.setProperty("--font-heading", stack);

  root.style.fontSize = `${TEXT_SIZE_PX[prefs.textSize] || TEXT_SIZE_PX.md}px`;
}
