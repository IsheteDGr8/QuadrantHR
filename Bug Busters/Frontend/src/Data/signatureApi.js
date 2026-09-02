// Client for the real policy-signature backend contract:
//   POST /policies/{org_id}/{policy_id}/sign   body: { signed_name }
//   GET  /policies/{org_id}/{policy_id}/signed-by-me
//   GET  /policies/{org_id}/{policy_id}/signatures
//
// One real gap here, flagged rather than papered over: the real endpoint
// only accepts `signed_name` (a string) — there's no field for a drawn
// signature image. This UI supports drawing anyway, and the drawn image
// is captured and displayed locally, but only the typed name currently
// has anywhere to go on the real backend. Raise with backend if the
// drawn image needs to be persisted server-side too.
//
// The other gap that used to be here - the real endpoint signs one
// policy_id at a time, but the UI signs one bundled *assignment* that
// can cover several sections - is resolved on the caller's side
// (PolicyViewer.jsx calls this once per part.backendPolicyId in the
// bundle, not once for the whole assignment), not by changing this
// client's contract.

import { BACKEND_URL, ORG_ID } from "./backendConfig";
import { getAuthHeader } from "./authToken";

export async function signPolicy(policyId, signedName, orgId = ORG_ID) {
  const authHeader = await getAuthHeader();

  const response = await fetch(`${BACKEND_URL}/policies/${orgId}/${policyId}/sign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(authHeader || {}),
    },
    body: JSON.stringify({ signed_name: signedName }),
  });

  if (!response.ok) {
    throw new Error(`Failed to sign policy (${response.status})`);
  }

  return response.json();
}
