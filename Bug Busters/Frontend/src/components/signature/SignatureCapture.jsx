import { useRef, useState } from "react";
import Segmented from "../ui/Segmented";
import { Input } from "../ui/FormControls";

const MODES = [
  { value: "type", label: "Type" },
  { value: "draw", label: "Draw" },
];

// DocuSign-style signature capture: type your name (rendered in a script
// font as a live preview) or draw it on a canvas. Mode/typed-name/drawing
// are all reported up via callbacks rather than held here, so the parent
// (PolicyViewer) can decide when the whole thing counts as "signed" and
// what to actually submit — this component only knows how to capture.
function SignatureCapture({ mode, onModeChange, typedName, onTypedNameChange, onDrawingChange }) {
  const canvasRef = useRef(null);
  const drawingRef = useRef(false);
  const [hasDrawing, setHasDrawing] = useState(false);

  function getPoint(e) {
    const rect = canvasRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function styleContext(ctx) {
    ctx.strokeStyle = "#1d1633";
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }

  function handlePointerDown(e) {
    canvasRef.current.setPointerCapture(e.pointerId);
    drawingRef.current = true;
    const ctx = canvasRef.current.getContext("2d");
    styleContext(ctx);
    const { x, y } = getPoint(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
  }

  function handlePointerMove(e) {
    if (!drawingRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    const { x, y } = getPoint(e);
    ctx.lineTo(x, y);
    ctx.stroke();
    if (!hasDrawing) setHasDrawing(true);
  }

  function handlePointerUp() {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    onDrawingChange(hasDrawing ? canvasRef.current.toDataURL("image/png") : null);
  }

  function handleClear() {
    const canvas = canvasRef.current;
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawing(false);
    onDrawingChange(null);
  }

  return (
    <div className="signature-capture">
      <Input
        placeholder="Type your full legal name"
        value={typedName}
        onChange={(e) => onTypedNameChange(e.target.value)}
        style={{ maxWidth: 320 }}
      />

      <Segmented name="signature-mode" options={MODES} value={mode} onChange={onModeChange} />

      {mode === "type" ? (
        typedName.trim() && <div className="signature-preview">{typedName}</div>
      ) : (
        <div className="signature-draw-pane">
          <canvas
            ref={canvasRef}
            className="signature-canvas"
            width={480}
            height={140}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerLeave={handlePointerUp}
          />
          <div className="signature-draw-actions">
            <span className="signature-draw-hint">Draw your signature above</span>
            <button type="button" className="link-button" onClick={handleClear}>
              Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default SignatureCapture;
