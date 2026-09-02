// Client for the real training-materials backend (backend/main.py's
// "Training" section) - handbook, code of conduct, etc. Read-only from
// here on purpose: uploading is a deliberately non-HR-facing admin
// action (see backend/seed_training_materials.py), not something any
// frontend page does.

import { BACKEND_URL, ORG_ID } from "./backendConfig";
import { getAuthHeader } from "./authToken";

export async function listTrainingResources() {
  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/training/${ORG_ID}`, {
    headers: authHeader || undefined,
  });

  if (!response.ok) {
    throw new Error(`Failed to load training materials (${response.status})`);
  }

  return response.json();
}

export async function downloadTrainingFile(resourceId, filename) {
  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/training/${ORG_ID}/${resourceId}/download`, {
    headers: authHeader || undefined,
  });

  if (!response.ok) {
    throw new Error(`Failed to download file (${response.status})`);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(objectUrl);
}
