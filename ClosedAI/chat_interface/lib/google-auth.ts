import { createHmac, randomBytes } from "crypto"

export function getGoogleAuthConfig() {
  const clientId = process.env.GOOGLE_CLIENT_ID?.trim() || ""
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET?.trim() || ""
  const frontendUrl = (process.env.FRONTEND_URL || "http://localhost:3000").replace(/\/$/, "")
  // Prefer an explicit redirect, but never the old dead :8000 HR-Copilot path.
  const configuredRedirect = process.env.GOOGLE_AUTH_REDIRECT_URI?.trim() || ""
  const redirectUri =
    configuredRedirect && !/:8000\b/.test(configuredRedirect)
      ? configuredRedirect
      : `${frontendUrl}/api/auth/google/callback`
  const jwtSecret =
    process.env.JWT_SECRET?.trim() || "hr-copilot-local-dev-jwt-secret-change-in-azure"
  const expireHours = Number(process.env.JWT_EXPIRE_HOURS)
  const expireDays = Number(process.env.JWT_EXPIRE_DAYS)
  const expireSeconds =
    Number.isFinite(expireHours) && expireHours > 0
      ? expireHours * 3600
      : Number.isFinite(expireDays) && expireDays > 0
        ? expireDays * 86400
        : 7 * 86400

  return { clientId, clientSecret, frontendUrl, redirectUri, jwtSecret, expireSeconds }
}

export function isGoogleAuthConfigured(): boolean {
  const { clientId, clientSecret } = getGoogleAuthConfig()
  return Boolean(clientId && clientSecret)
}

function b64urlJson(value: unknown): string {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64url")
}

/** Mint a compact HS256 JWT the frontend can decode for name/email/picture. */
export function signSessionJwt(
  claims: { name: string; email: string; picture?: string | null; sub?: string },
  secret: string,
  expiresInSeconds: number,
): string {
  const now = Math.floor(Date.now() / 1000)
  const header = { alg: "HS256", typ: "JWT" }
  const payload = {
    ...claims,
    picture: claims.picture || undefined,
    provider: "google",
    iat: now,
    exp: now + expiresInSeconds,
  }
  const h = b64urlJson(header)
  const p = b64urlJson(payload)
  const sig = createHmac("sha256", secret).update(`${h}.${p}`).digest("base64url")
  return `${h}.${p}.${sig}`
}

export function newOAuthState(): string {
  return randomBytes(24).toString("hex")
}

export function buildGoogleAuthorizeUrl(opts: {
  clientId: string
  redirectUri: string
  state: string
}): string {
  const params = new URLSearchParams({
    client_id: opts.clientId,
    redirect_uri: opts.redirectUri,
    response_type: "code",
    scope: "openid email profile",
    access_type: "online",
    include_granted_scopes: "true",
    prompt: "select_account",
    state: opts.state,
  })
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`
}

export async function exchangeGoogleCode(opts: {
  code: string
  clientId: string
  clientSecret: string
  redirectUri: string
}): Promise<{
  access_token?: string
  id_token?: string
  error?: string
  error_description?: string
}> {
  const body = new URLSearchParams({
    code: opts.code,
    client_id: opts.clientId,
    client_secret: opts.clientSecret,
    redirect_uri: opts.redirectUri,
    grant_type: "authorization_code",
  })
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  })
  return (await res.json()) as {
    access_token?: string
    id_token?: string
    error?: string
    error_description?: string
  }
}

export async function fetchGoogleUserInfo(accessToken: string): Promise<{
  sub?: string
  name?: string
  email?: string
  picture?: string
  given_name?: string
} | null> {
  const res = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!res.ok) return null
  return (await res.json()) as {
    sub?: string
    name?: string
    email?: string
    picture?: string
    given_name?: string
  }
}
