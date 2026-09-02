import { useState } from "react";
import Segmented from "../components/ui/Segmented";
import Button from "../components/ui/Button";
import { getPrefs, savePrefs, DEFAULT_PREFS } from "../Data/store";
import { applyPrefs, FONT_STACKS } from "../utils/applyPrefs";

const THEME_OPTIONS = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Match system" },
];

const SIZE_OPTIONS = [
  { value: "sm", label: "Small" },
  { value: "md", label: "Default" },
  { value: "lg", label: "Large" },
];

const TYPEFACES = [
  { value: "sans", name: "Plex Sans", note: "Default · neutral, screen-first" },
  { value: "serif", name: "Source Serif", note: "Long documents, print-like" },
  { value: "mono", name: "Plex Mono", note: "Clause-by-clause review" },
];

function Settings() {
  const [prefs, setPrefs] = useState(getPrefs());
  const [savedNote, setSavedNote] = useState(false);

  function update(patch) {
    setPrefs((prev) => ({ ...prev, ...patch }));
  }

  function handleSave() {
    savePrefs(prefs);
    applyPrefs(prefs);
    setSavedNote(true);
    setTimeout(() => setSavedNote(false), 2000);
  }

  function handleReset() {
    setPrefs(DEFAULT_PREFS);
    savePrefs(DEFAULT_PREFS);
    applyPrefs(DEFAULT_PREFS);
  }

  return (
    <div className="settings-layout">
      <div>
        <h1 style={{ margin: "0 0 4px" }}>Settings</h1>
        <p className="page-lede" style={{ marginBottom: 32 }}>
          Appearance is saved per person, not per company.
        </p>

        <h4 style={{ margin: "0 0 12px" }}>Theme</h4>
        <div style={{ marginBottom: 32 }}>
          <Segmented
            name="theme"
            options={THEME_OPTIONS}
            value={prefs.theme}
            onChange={(v) => update({ theme: v })}
          />
        </div>

        <h4 style={{ margin: "0 0 4px" }}>Typeface</h4>
        <p style={{ fontSize: 13, color: "var(--color-text-muted)", margin: "0 0 12px" }}>
          Policy documents are long. Pick what you can read for an hour.
        </p>
        <div className="settings-typeface-grid" style={{ marginBottom: 32 }}>
          {TYPEFACES.map((tf) => {
            const selected = prefs.typeface === tf.value;
            return (
              <label
                key={tf.value}
                className={"radio-card" + (selected ? " radio-card-selected" : "")}
                style={{ flexDirection: "column", alignItems: "flex-start", gap: 8, padding: 14 }}
              >
                <input
                  type="radio"
                  name="typeface"
                  checked={selected}
                  onChange={() => update({ typeface: tf.value })}
                  style={{ position: "absolute", opacity: 0, width: 0, height: 0 }}
                />
                <span style={{ fontFamily: FONT_STACKS[tf.value], fontSize: 26, fontWeight: 600, lineHeight: 1 }}>
                  Aa
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="dot" />
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{tf.name}</span>
                </span>
                <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{tf.note}</span>
              </label>
            );
          })}
        </div>

        <h4 style={{ margin: "0 0 12px" }}>Text size</h4>
        <div style={{ marginBottom: 32 }}>
          <Segmented
            name="textSize"
            options={SIZE_OPTIONS}
            value={prefs.textSize}
            onChange={(v) => update({ textSize: v })}
          />
        </div>

        <div style={{ borderTop: "1px solid var(--color-divider)", paddingTop: 22, display: "flex", gap: 10, alignItems: "center" }}>
          <Button variant="primary" onClick={handleSave}>
            Save appearance
          </Button>
          <Button variant="secondary" onClick={handleReset}>
            Reset to default
          </Button>
          {savedNote && <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Saved.</span>}
        </div>
      </div>

      <div>
        <div className="page-kicker" style={{ marginBottom: 12 }}>Preview</div>

        <div style={{ border: "1px solid var(--color-divider)", borderRadius: 2, overflow: "hidden", marginBottom: 16 }}>
          <div style={{ background: "#241a45", color: "#f3f1fa", padding: "9px 12px", fontSize: 11 }}>Policy Guardian</div>
          <div style={{ padding: "14px 12px", background: "#faf9fc" }}>
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8, color: "#1d1633" }}>Work From Home</div>
            <div style={{ fontSize: 12, lineHeight: 1.6, color: "#1d1633b3" }}>
              Employees who have completed onboarding may work remotely up to two days each week.
            </div>
          </div>
        </div>

        <div style={{ border: "1px solid var(--color-divider)", borderRadius: 2, overflow: "hidden", opacity: 0.9 }}>
          <div style={{ background: "#120d24", color: "#f3f1fa", padding: "9px 12px", fontSize: 11 }}>
            Policy Guardian <span style={{ color: "#b9a6ff", marginLeft: 6 }}>dark</span>
          </div>
          <div style={{ padding: "14px 12px", background: "#1a1330", color: "#e9e6f5" }}>
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>Work From Home</div>
            <div style={{ fontSize: 12, lineHeight: 1.6, color: "rgba(233,230,245,0.72)" }}>
              Employees who have completed onboarding may work remotely up to two days each week.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Settings;
