// Three bouncing dots — dropped inside a button (or anywhere) to show
// an AI call is in flight. Uses currentColor so it matches whatever
// text color the surrounding button already has, in either theme.
function LoadingDots() {
  return (
    <span className="loading-dots" role="status" aria-label="Loading">
      <span className="loading-dot" />
      <span className="loading-dot" />
      <span className="loading-dot" />
    </span>
  );
}

export default LoadingDots;
