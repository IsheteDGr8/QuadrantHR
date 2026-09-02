import { cookies } from "next/headers"
import { NextRequest, NextResponse } from "next/server"
import {
  exchangeGoogleCode,
  fetchGoogleUserInfo,
  getGoogleAuthConfig,
  isGoogleAuthConfigured,
  signSessionJwt,
} from "@/lib/google-auth"

export const runtime = "nodejs"

const STATE_COOKIE = "google_oauth_state"

function errorRedirect(frontendUrl: string, code: string) {
  return NextResponse.redirect(
    `${frontendUrl}/intake?auth_error=${encodeURIComponent(code)}`,
  )
}

export async function GET(request: NextRequest) {
  const cfg = getGoogleAuthConfig()
  if (!isGoogleAuthConfigured()) {
    return errorRedirect(cfg.frontendUrl, "google_not_configured")
  }

  const url = request.nextUrl
  const err = url.searchParams.get("error")
  if (err) {
    return errorRedirect(cfg.frontendUrl, err)
  }

  const code = url.searchParams.get("code")
  const state = url.searchParams.get("state")
  if (!code || !state) {
    return errorRedirect(cfg.frontendUrl, "missing_code")
  }

  const jar = await cookies()
  const expected = jar.get(STATE_COOKIE)?.value
  // Clear state cookie either way
  const clearState = (res: NextResponse) => {
    res.cookies.set(STATE_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 })
    return res
  }

  if (!expected || expected !== state) {
    return clearState(errorRedirect(cfg.frontendUrl, "invalid_state"))
  }

  const tokenRes = await exchangeGoogleCode({
    code,
    clientId: cfg.clientId,
    clientSecret: cfg.clientSecret,
    redirectUri: cfg.redirectUri,
  })

  if (!tokenRes.access_token) {
    const detail = tokenRes.error_description || tokenRes.error || "token_exchange_failed"
    return clearState(errorRedirect(cfg.frontendUrl, detail))
  }

  const user = await fetchGoogleUserInfo(tokenRes.access_token)
  if (!user?.email && !user?.name) {
    return clearState(errorRedirect(cfg.frontendUrl, "userinfo_failed"))
  }

  const name = (user.name || user.given_name || "").trim()
  const email = (user.email || "").trim()
  const jwt = signSessionJwt(
    {
      sub: user.sub,
      name,
      email,
      picture: user.picture || null,
    },
    cfg.jwtSecret,
    cfg.expireSeconds,
  )

  const dest = `${cfg.frontendUrl}/intake?token=${encodeURIComponent(jwt)}`
  return clearState(NextResponse.redirect(dest))
}
