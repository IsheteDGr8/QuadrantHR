import { NextResponse } from "next/server"
import {
  buildGoogleAuthorizeUrl,
  getGoogleAuthConfig,
  isGoogleAuthConfigured,
  newOAuthState,
} from "@/lib/google-auth"

export const runtime = "nodejs"

const STATE_COOKIE = "google_oauth_state"

export async function GET() {
  const cfg = getGoogleAuthConfig()
  if (!isGoogleAuthConfigured()) {
    return NextResponse.redirect(
      `${cfg.frontendUrl}/intake?auth_error=${encodeURIComponent("google_not_configured")}`,
    )
  }

  const state = newOAuthState()
  const url = buildGoogleAuthorizeUrl({
    clientId: cfg.clientId,
    redirectUri: cfg.redirectUri,
    state,
  })

  const res = NextResponse.redirect(url)
  res.cookies.set(STATE_COOKIE, state, {
    httpOnly: true,
    sameSite: "lax",
    secure: cfg.frontendUrl.startsWith("https://"),
    path: "/",
    maxAge: 600,
  })
  return res
}
