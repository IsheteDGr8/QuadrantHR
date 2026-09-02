import { useEffect, useRef, useState } from "react";

// Wraps plain rendered text (NOT form inputs) and shows a floating
// "Ask AI / Reword" toolbar when the user selects some of it.
// Uses window.getSelection, which only works on real DOM text —
// for a <textarea> use selectionStart/selectionEnd instead
// (see SectionEditor.jsx).
//
// Improvements over a basic version:
// - toolbar position is clamped so it can't render off the left/top
//   edge of the container on short or edge-of-screen selections
// - closes on outside click, Escape, or scroll, instead of only ever
//   being replaced by the next selection
// - small fade/slide-in so it doesn't just pop into existence

const TOOLBAR_HEIGHT = 44;
const TOOLBAR_MIN_WIDTH = 140;

function Highlighter({ children, onAskAI, onReword }) {
  const containerRef = useRef(null);
  const [toolbar, setToolbar] = useState(null); // { text, top, left }

  function computeToolbar() {
    const selection = window.getSelection();
    const text = selection ? selection.toString().trim() : "";

    if (!text || !containerRef.current || selection.rangeCount === 0) {
      setToolbar(null);
      return;
    }

    const range = selection.getRangeAt(0);
    if (!containerRef.current.contains(range.commonAncestorContainer)) {
      setToolbar(null);
      return;
    }

    const rect = range.getBoundingClientRect();
    const containerRect = containerRef.current.getBoundingClientRect();

    let top = rect.top - containerRect.top - TOOLBAR_HEIGHT;
    let left = rect.left - containerRect.left;

    // Clamp so the toolbar never renders above or to the left of the
    // container (e.g. selecting the very first word/line).
    if (top < 0) top = rect.bottom - containerRect.top + 8;
    if (left < 0) left = 0;
    const maxLeft = containerRect.width - TOOLBAR_MIN_WIDTH;
    if (maxLeft > 0 && left > maxLeft) left = maxLeft;

    setToolbar({ text, top, left });
  }

  function handleMouseUp() {
    // Defer a tick so window.getSelection() reflects the just-finished drag.
    setTimeout(computeToolbar, 0);
  }

  useEffect(() => {
    function handleOutsideClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setToolbar(null);
      }
    }
    function handleKeyDown(e) {
      if (e.key === "Escape") setToolbar(null);
    }
    function handleScroll() {
      setToolbar(null);
    }

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", handleScroll, true);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, []);

  return (
    <div className="highlighter" ref={containerRef} onMouseUp={handleMouseUp}>
      {children}

      {toolbar && (
        <div className="highlight-toolbar" style={{ top: toolbar.top, left: toolbar.left }}>
          <button
            onClick={() => {
              onAskAI(toolbar.text);
              setToolbar(null);
            }}
          >
            Ask AI
          </button>
          {onReword && (
            <button
              onClick={() => {
                onReword(toolbar.text);
                setToolbar(null);
              }}
            >
              Reword
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default Highlighter;
