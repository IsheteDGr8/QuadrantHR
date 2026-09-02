"use client"

import {
  PublicClientApplication,
  type AuthenticationResult,
  type Configuration,
} from "@azure/msal-browser"
import { applyMicrosoftLogin } from "@/lib/auth-profile"

// App registration values come from env so credentials never live in source.
//   NEXT_PUBLIC_ENTRA_CLIENT_ID  — Application (client) ID of the SPA app reg
//   NEXT_PUBLIC_ENTRA_TENANT_ID  — Directory (tenant) ID, or "common" /
//                                  "organizations" for multi-tenant.
const CLIENT_ID = process.env.NEXT_PUBLIC_ENTRA_CLIENT_ID?.trim() || ""
const TENANT_ID = process.env.NEXT_PUBLIC_ENTRA_TENANT_ID?.trim() || "common"

// Scopes requested at sign-in. openid/profile/email give us the ID-token
// claims (name + email); User.Read lets us optionally fetch the Graph photo.
const LOGIN_SCOPES = ["openid", "profile", "email", "User.Read"]

/** Whether an Entra app registration is configured for this build. */
export function isEntraConfigured(): boolean {
  return CLIENT_ID.length > 0
}

let instance: PublicClientApplication | null = null
let initialized = false

async function getInstance(): Promise<PublicClientApplication> {
  if (!CLIENT_ID) {
    throw new Error(
      "Microsoft sign-in is not configured. Set NEXT_PUBLIC_ENTRA_CLIENT_ID (and optionally NEXT_PUBLIC_ENTRA_TENANT_ID).",
    )
  }
  if (!instance) {
    const config: Configuration = {
      auth: {
        clientId: CLIENT_ID,
        authority: `https://login.microsoftonline.com/${TENANT_ID}`,
        redirectUri: typeof window !== "undefined" ? window.location.origin : undefined,
      },
      cache: { cacheLocation: "localStorage", storeAuthStateInCookie: false },
    }
    instance = new PublicClientApplication(config)
  }
  if (!initialized) {
    await instance.initialize()
    initialized = true
  }
  return instance
}

async function fetchGraphPhoto(accessToken: string): Promise<string | null> {
  try {
    const res = await fetch("https://graph.microsoft.com/v1.0/me/photo/$value", {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return null
    const blob = await res.blob()
    return await new Promise<string | null>((resolve) => {
      const reader = new FileReader()
      reader.onloadend = () => resolve(typeof reader.result === "string" ? reader.result : null)
      reader.onerror = () => resolve(null)
      reader.readAsDataURL(blob)
    })
  } catch {
    return null
  }
}

/**
 * Launch the Entra ID popup sign-in and persist the resulting profile.
 * Resolves once the auth store has been updated; the caller should then
 * navigate into the app.
 */
export async function signInWithEntra(): Promise<void> {
  const pca = await getInstance()
  const result: AuthenticationResult = await pca.loginPopup({
    scopes: LOGIN_SCOPES,
    prompt: "select_account",
  })

  const account = result.account
  const name = account?.name?.trim() || ""
  const email = (account?.username || "").trim()

  let picture: string | null = null
  if (result.accessToken) {
    picture = await fetchGraphPhoto(result.accessToken)
  }

  applyMicrosoftLogin({
    idToken: result.idToken || result.accessToken || "entra-session",
    name,
    email,
    picture,
  })
}
