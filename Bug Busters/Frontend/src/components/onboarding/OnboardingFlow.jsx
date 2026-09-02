import { useState } from "react";
import Button from "../ui/Button";

const STEPS = [
  {
    key: "attest",
    title: "Attest",
    body: "Before you get started, we need you to attest to a few basics: that the information in your employee profile is accurate, and that you understand you're responsible for reading and following the policies assigned to you.",
    checkboxLabel: "I attest that the above is true.",
  },
  {
    key: "train",
    title: "Train",
    body: "Take a moment to review what's expected of you: keep company information confidential, treat colleagues with respect, and reach out to HR or your manager if you're ever unsure whether something is allowed. Full policy details are available any time from your home page.",
    checkboxLabel: "I confirm I've reviewed this training material.",
  },
  {
    key: "adhere",
    title: "Adhere",
    body: "Finally, we ask you to commit to adhering to company policy going forward. Non-compliance can result in disciplinary action — if anything is ever unclear, ask before acting.",
    checkboxLabel: "I agree to adhere to company policy.",
  },
];

// Popup gating flow: each step must be individually checked off before the
// user can continue to the next one. Nothing here is submitted to a
// backend — see Data/store.js's completeOnboarding, which just records
// that this employee has been through it once.
function OnboardingFlow({ onComplete, onClose }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [checked, setChecked] = useState(false);

  const step = STEPS[stepIndex];
  const isLastStep = stepIndex === STEPS.length - 1;

  function handleContinue() {
    if (!checked) return;

    if (isLastStep) {
      onComplete();
      return;
    }

    setStepIndex((i) => i + 1);
    setChecked(false);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal onboarding-modal" onClick={(e) => e.stopPropagation()}>
        <div className="onboarding-progress">
          {STEPS.map((s, i) => (
            <span
              key={s.key}
              className={"onboarding-progress-dot" + (i <= stepIndex ? " onboarding-progress-dot-active" : "")}
            />
          ))}
        </div>

        <div className="ai-panel-header">
          <h3>
            Step {stepIndex + 1} of {STEPS.length} — {step.title}
          </h3>
          <button className="ai-panel-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <p className="onboarding-body">{step.body}</p>

        <label className="sign-agree">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
          />
          {step.checkboxLabel}
        </label>

        <Button variant="primary" block disabled={!checked} onClick={handleContinue}>
          {isLastStep ? "Finish" : "Continue"}
        </Button>
      </div>
    </div>
  );
}

export default OnboardingFlow;
