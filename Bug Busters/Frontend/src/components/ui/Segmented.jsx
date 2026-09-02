// A segmented control — options=[{ value, label }].
function Segmented({ name, options, value, onChange }) {
  return (
    <div className="seg" role="radiogroup">
      {options.map((opt) => (
        <label
          key={opt.value}
          className={"seg-opt" + (value === opt.value ? " seg-opt-active" : "")}
        >
          <input
            type="radio"
            name={name}
            value={opt.value}
            checked={value === opt.value}
            onChange={() => onChange(opt.value)}
            style={{ position: "absolute", opacity: 0, width: 0, height: 0 }}
          />
          {opt.label}
        </label>
      ))}
    </div>
  );
}

export default Segmented;
