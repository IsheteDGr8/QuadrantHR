// Saves the exact, currently-edited section content to the backend
// (not a regenerated version — see PolicyRequest.content on the backend)
// and downloads it as a PDF or DOCX.

import { BACKEND_URL, ORG_ID, POLICY_TYPE_MAP, COMPANY_NAME } from "./backendConfig";
import { getAuthHeader } from "./authToken";
import { roleLabel } from "./store";

// If this section has already been saved to the backend once (has a
// backendPolicyId), PATCH it instead of POSTing a new record each time —
// that's what actually builds real version history via GET .../history,
// instead of leaving a trail of disconnected one-off saves.
//
// Exported (not just used internally by exportSection) so assignment
// flows can call it directly to guarantee a real policy_id exists
// before assigning - assigning requires a real backend policy_id, and a
// section that's never been exported/saved before won't have one yet.
export async function saveSectionToBackend(section) {
  const authHeader = await getAuthHeader();

  if (section.backendPolicyId) {
    const response = await fetch(
      `${BACKEND_URL}/policies/${ORG_ID}/${section.backendPolicyId}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(authHeader || {}),
        },
        body: JSON.stringify({
          content: section.content,
          edited_by: "HR",
        }),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to update saved policy (${response.status})`);
    }

    return response.json();
  }

  // section.answers values aren't always plain strings - PolicyChatCreate.jsx
  // stores { conversation: [...messages] }, an array. Object.values()
  // doesn't flatten that, so without this the backend was being sent
  // requirements: [["msg1", "msg2", ...]] - one array nested inside the
  // list instead of a list of strings, which it rejects outright
  // (a completely different 422 than the title one, and the actual
  // failure for every section made through the primary chat-creation
  // flow, independent of whether title is set correctly).
  const requirements = Object.values(section.answers || {})
    .flatMap((value) => (Array.isArray(value) ? value : [value]))
    .filter((value) => typeof value === "string" && value.trim());

  if (requirements.length === 0) {
    requirements.push(section.title || "Policy");
  }

  const response = await fetch(`${BACKEND_URL}/policies?org_id=${ORG_ID}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(authHeader || {}),
    },
    body: JSON.stringify({
      company_name: COMPANY_NAME,
      policy_type: POLICY_TYPE_MAP[section.sectionType] || "Custom Section",
      // Required by the backend whenever policy_type resolves to "Custom
      // Section" (see PolicyRequest.validate_custom_section_has_title) -
      // that's every section not in POLICY_TYPE_MAP, which as of
      // PolicyChatCreate.jsx (sectionType "chat") is most of them now.
      // Always a real, non-empty string (never undefined/blank) - some
      // existing sections predate title being reliably set, and sending
      // an empty one 422s exactly the same way omitting it does.
      title: (section.title && section.title.trim())
        || (section.role && `${roleLabel(section.role)} Policy`)
        || "Untitled Policy",
      tone: section.tone || "Professional",
      requirements,
      content: section.content,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to save policy for export (${response.status})`);
  }

  return response.json();
}

export async function getPolicyHistory(policyId) {
  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/policies/${ORG_ID}/${policyId}/history`, {
    headers: authHeader || undefined,
  });

  if (!response.ok) {
    throw new Error(`Failed to load version history (${response.status})`);
  }

  return response.json();
}

async function downloadBlob(url, filename) {
  const authHeader = await getAuthHeader();
  const response = await fetch(url, {
    headers: authHeader || undefined,
  });

  if (!response.ok) {
    throw new Error(`Failed to export file (${response.status})`);
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

export async function exportSection(section, format) {
  const saved = await saveSectionToBackend(section);
  const filename = `${(section.title || "policy").replace(/[^a-z0-9-_ ]/gi, "").trim()}.${format}`;

  await downloadBlob(
    `${BACKEND_URL}/policies/${ORG_ID}/${saved.id}/export/${format}`,
    filename
  );

  return saved;
}
