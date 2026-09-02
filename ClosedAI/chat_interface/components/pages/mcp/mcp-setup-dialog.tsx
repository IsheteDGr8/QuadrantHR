"use client"

import { useEffect, useState } from "react"
import { KeyRound, Loader2, ShieldCheck } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { substitutePlaceholders, useMcp } from "@/lib/mcp-store"
import * as mcpApi from "@/lib/mcp-api"
import { SetupFields } from "./mcp-setup-form"
import type { LibraryServer, McpConnection } from "./mcp-types"

/** A few names don't title-case cleanly from their kebab-case id. */
const DISPLAY_NAME_OVERRIDES: Record<string, string> = {
  github: "GitHub",
  "microsoft-365": "Microsoft 365",
}

/** "google-drive" -> "Google Drive", used only for the button label
 *  ("Connect Gmail") — never shown as a description. */
function displayName(id: string): string {
  return DISPLAY_NAME_OVERRIDES[id] ?? id.split("-").map((w) => w[0]?.toUpperCase() + w.slice(1)).join(" ")
}

/** Convert an integration's .mcp.json server template (after ${VAR}
 *  substitution) into a POST /api/mcp/test spec. Uses the same normalization
 *  the store applies to connections: streamable-http -> http. */
function templateToProbeSpec(
  template: Record<string, unknown>,
  values: Record<string, string | boolean>,
): mcpApi.McpTestServerSpec | null {
  const t = JSON.parse(JSON.stringify(template)) as Record<string, unknown>
  substitutePlaceholders(t, values)
  if (t.transport === "stdio" || (typeof t.command === "string" && t.command)) {
    if (typeof t.command !== "string" || !t.command) return null
    return {
      type: "stdio",
      command: t.command,
      args: Array.isArray(t.args) ? (t.args as string[]) : [],
      ...(t.env && typeof t.env === "object" ? { env: t.env as Record<string, string> } : {}),
    }
  }
  if (typeof t.url !== "string" || !t.url) return null
  const remote: Record<string, unknown> = { type: "http", url: t.url }
  if (t.headers && typeof t.headers === "object" && Object.keys(t.headers as object).length > 0) {
    remote.headers = t.headers
  }
  if (t.auth && typeof t.auth === "object") {
    remote.auth = t.auth
  }
  return remote as mcpApi.McpTestServerSpec
}

export function McpSetupDialog({
  server,
  connection,
  onOpenChange,
}: {
  server: LibraryServer | null
  connection: McpConnection | null
  onOpenChange: (open: boolean) => void
}) {
  const { saveSecret, patchServerConfig, startOAuth, completeOAuth, load } = useMcp()
  const isOpen = server !== null && connection !== null

  const [values, setValues] = useState<Record<string, string | boolean>>({})
  const [oauthState, setOauthState] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setValues({})
    setOauthState(null)
  }, [server?.id, connection?.id])

  if (!server || !connection) return null

  const schema = server.setup
  const templates = server.servers ?? {}
  const serverNames = Object.keys(templates)
  const firstTemplate = serverNames.length > 0 ? (templates[serverNames[0]] as Record<string, unknown> | undefined) : undefined

  const auth = schema?.auth
  const isOAuth = auth?.method === "oauth2"
  const providerReady = !isOAuth || !auth?.provider || auth.provider_configured === true
  const oauthJustConnected = oauthState !== null
  const name = displayName(connection.id)
  const nonAuthFields = (schema?.fields ?? []).filter((f) => f.name !== auth?.token_field)

  const runOAuthFlow = async () => {
    if (!firstTemplate) return
    const spec = templateToProbeSpec(firstTemplate, values)
    if (!spec) return
    setBusy(true)
    try {
      const jobId = await startOAuth(spec, { verifyToolCall: auth?.verify_tool_call })
      if (!jobId) return
      const result = await completeOAuth(jobId, (state) => {
        setOauthState(state)
        void patchServerConfig(connection.id, { auth: { strategy: "oauth2", state } })
      })
      if (result !== "ok") toast.error("Failed to connect — try again")
    } finally {
      setBusy(false)
    }
  }

  const handleSave = async () => {
    setBusy(true)
    try {
      for (const field of nonAuthFields) {
        if (field.required && !String(values[field.name] ?? "").trim()) {
          toast.error(`${field.label} is required`)
          return
        }
      }
      for (const [fieldName, value] of Object.entries(values)) {
        if (typeof value === "string" && value.trim()) {
          await saveSecret(fieldName, value.trim())
        }
      }
      await load()
      toast.success(`${name} connected`)
      onOpenChange(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : `Failed to save ${name}`)
    } finally {
      setBusy(false)
    }
  }

  const handleClick = () => {
    if (isOAuth && !oauthJustConnected) void runOAuthFlow()
    else void handleSave()
  }

  const label = !isOAuth ? "Connect" : oauthJustConnected ? "Save & finish" : busy ? "Connecting…" : `Connect ${name}`
  const disabled = busy || (isOAuth && !providerReady)

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 overflow-hidden border-border/60 bg-card p-0 sm:max-w-lg">
        <div className="bg-gradient-to-r from-[#FF8F6B] to-[#FF6B4A] px-6 py-5 text-white">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/20">
              <KeyRound className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <DialogHeader className="space-y-1 text-left">
                <DialogTitle className="font-heading text-lg text-white">
                  Set up {name}
                </DialogTitle>
                <DialogDescription className="text-[13px] text-white/85">
                  {isOAuth
                    ? `Sign in so Vera can use ${name} on your behalf. Credentials stay on the server.`
                    : `Enter the required details so ${name} can connect.`}
                </DialogDescription>
              </DialogHeader>
            </div>
          </div>
        </div>

        <div className="space-y-4 px-6 py-5">
          {!providerReady ? (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-[13px] leading-relaxed text-amber-200">
              An administrator still needs to finish backend configuration for this provider before you can connect.
            </div>
          ) : (
            <>
              {isOAuth && (
                <div className="flex items-start gap-2.5 rounded-xl border border-border/60 bg-secondary/40 px-4 py-3">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#FF6B4A]" />
                  <p className="text-[13px] leading-relaxed text-muted-foreground">
                    You&apos;ll complete a short browser sign-in. When it finishes, click{" "}
                    <span className="font-medium text-foreground">Save &amp; finish</span> here.
                  </p>
                </div>
              )}
              {(!isOAuth || nonAuthFields.length > 0) && (
                <SetupFields fields={nonAuthFields} values={values} onChange={setValues} disabled={busy} />
              )}
            </>
          )}
        </div>

        <DialogFooter className="gap-2 border-t border-border/60 bg-secondary/20 px-6 py-4 sm:justify-between">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={busy} className="text-muted-foreground">
            Cancel
          </Button>
          <Button
            onClick={handleClick}
            disabled={disabled}
            className="min-w-[160px] gap-2 bg-[#FF6B4A] text-white hover:bg-[#E85A3A]"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {label}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
