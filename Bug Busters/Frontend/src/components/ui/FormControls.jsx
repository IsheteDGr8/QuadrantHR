// Thin wrappers around the design system's .field / .input classes
// (see App.css "DESIGN SYSTEM — SHARED PRIMITIVES").

export function Field({ label, className = "", children }) {
  return (
    <div className={["field", className].filter(Boolean).join(" ")}>
      {label && <label>{label}</label>}
      {children}
    </div>
  );
}

export function Input({ className = "", ...rest }) {
  return <input className={["input", className].filter(Boolean).join(" ")} {...rest} />;
}

export function Textarea({ className = "", ...rest }) {
  return <textarea className={["input", className].filter(Boolean).join(" ")} {...rest} />;
}

export function Select({ className = "", children, ...rest }) {
  return (
    <select className={["input", className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </select>
  );
}
