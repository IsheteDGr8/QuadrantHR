import { useEffect, useState } from "react";
import { listTrainingResources, downloadTrainingFile } from "../Data/trainingApi";
import Button from "../components/ui/Button";
import Tag from "../components/ui/Tag";

function TrainingMaterials() {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloadingId, setDownloadingId] = useState(null);

  useEffect(() => {
    let cancelled = false;

    listTrainingResources()
      .then((data) => {
        if (!cancelled) setResources(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load training materials.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleDownload(resource) {
    setDownloadingId(resource.id);
    try {
      await downloadTrainingFile(resource.id, resource.original_filename || resource.title);
    } catch (err) {
      setError(err.message || "Failed to download file.");
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <div className="content">
      <div className="page-kicker">Materials</div>
      <h1 style={{ margin: "0 0 6px" }}>Training &amp; Reference Materials</h1>
      <p className="page-lede">
        The employee handbook and other reference material — for reading, not signing.
      </p>

      {loading ? (
        <p className="sidebar-empty">Loading…</p>
      ) : error ? (
        <p className="sign-error">{error}</p>
      ) : resources.length === 0 ? (
        <p className="sidebar-empty">No materials have been added yet.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 720 }}>
          {resources.map((resource) => (
            <div key={resource.id} className="card panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <strong>{resource.title}</strong>
                  <Tag variant="neutral">{resource.category}</Tag>
                </div>
                <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-muted)" }}>
                  {resource.description}
                </p>
              </div>

              {resource.resource_type === "file" ? (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={downloadingId === resource.id}
                  onClick={() => handleDownload(resource)}
                >
                  {downloadingId === resource.id ? "Downloading…" : "Download"}
                </Button>
              ) : (
                <Button variant="secondary" size="sm" onClick={() => window.open(resource.url, "_blank")}>
                  Open link
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default TrainingMaterials;
