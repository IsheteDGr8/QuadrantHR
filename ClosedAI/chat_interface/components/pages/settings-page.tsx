"use client"

import { useEffect, useState, type ReactNode } from "react"
import { Sliders, Cpu, Wrench, Shield, KeyRound, Database, Bot, SlidersHorizontal, User } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { OptionMenu } from "@/components/option-menu"
import { MODELS } from "@/lib/chat-store"
import { PageContainer, PageHeader } from "@/components/management/shared"
import { initialsFromName, signOut, updateAuthProfile, useAuthProfile } from "@/lib/auth-profile"
import { loadGuardrailPrefs, saveGuardrailPrefs } from "@/lib/guardrail-prefs"

const SECTIONS = [
  { id: "profile", label: "Profile", icon: User },
  { id: "general", label: "General", icon: Sliders },
  { id: "model", label: "Model", icon: Cpu },
  { id: "tools", label: "Tool Permissions", icon: Wrench },
  { id: "security", label: "Security", icon: Shield },
  { id: "auth", label: "Authentication", icon: KeyRound },
  { id: "data", label: "Data Access", icon: Database },
  { id: "behavior", label: "Agent Behavior", icon: Bot },
]

export function SettingsPage() {
  const profile = useAuthProfile()
  const [displayName, setDisplayName] = useState(profile?.name || "")
  const [workEmail, setWorkEmail] = useState(profile?.email || "")

  // General
  const [agentName, setAgentName] = useState("Vera")
  const [description, setDescription] = useState("Enterprise HR operations assistant for the platform team.")
  const [defaultModel, setDefaultModel] = useState(MODELS[0].label)

  // Model config
  const [temperature, setTemperature] = useState([0.7])
  const [maxTokens, setMaxTokens] = useState([8192])
  const [streaming, setStreaming] = useState(true)

  // Tools — persisted guardrails (applied on next New Chat)
  const [autoApprove, setAutoApprove] = useState(false)
  const [readOnly, setReadOnly] = useState(false)
  const [parallelTools, setParallelTools] = useState(true)

  // Security
  const [dataRetention, setDataRetention] = useState("30 days")
  const [auditLog, setAuditLog] = useState(true)
  const [piiRedaction, setPiiRedaction] = useState(true)

  useEffect(() => {
    const prefs = loadGuardrailPrefs()
    setAutoApprove(prefs.autoApprove)
    setReadOnly(prefs.readOnly)
    setPiiRedaction(prefs.piiRedaction)
  }, [])

  const persistGuardrails = (patch: {
    autoApprove?: boolean
    readOnly?: boolean
    piiRedaction?: boolean
  }) => {
    saveGuardrailPrefs(patch)
    if (patch.autoApprove !== undefined) setAutoApprove(patch.autoApprove)
    if (patch.readOnly !== undefined) setReadOnly(patch.readOnly)
    if (patch.piiRedaction !== undefined) setPiiRedaction(patch.piiRedaction)
  }

  // Auth
  const [ssoOnly, setSsoOnly] = useState(true)
  const [mfa, setMfa] = useState(true)
  const [sessionTimeout, setSessionTimeout] = useState("8 hours")

  // Data access
  const [webAccess, setWebAccess] = useState(true)
  const [dbAccess, setDbAccess] = useState(true)
  const [fileAccess, setFileAccess] = useState(false)

  // Behavior
  const [tone, setTone] = useState("Professional")
  const [verbosity, setVerbosity] = useState("Balanced")
  const [systemPrompt, setSystemPrompt] = useState(
    "You are a helpful, precise HR operations assistant. Cite sources, respect data-access policies, and confirm before taking irreversible actions.",
  )

  return (
    <PageContainer>
      <PageHeader
        title="Settings"
        icon={SlidersHorizontal}
        description="Control how the agent runs, what it can access, and how it behaves across every conversation."
        action={
          <Button
            onClick={() => {
              if (displayName.trim()) {
                updateAuthProfile({ name: displayName, email: workEmail })
              }
              toast.success("Settings saved")
            }}
            className="bg-primary text-primary-foreground transition-transform duration-200 hover:opacity-90 active:scale-95"
          >
            Save changes
          </Button>
        }
      />

      <div className="flex gap-10">
        {/* In-page nav */}
        <nav className="dream-in sticky top-0 hidden h-fit w-48 shrink-0 flex-col gap-0.5 lg:flex">
          {SECTIONS.map(({ id, label, icon: Icon }) => (
            <a
              key={id}
              href={`#${id}`}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-muted-foreground transition-colors duration-200 hover:bg-card/60 hover:text-foreground"
            >
              <Icon className="h-4 w-4" />
              {label}
            </a>
          ))}
        </nav>

        <div className="min-w-0 flex-1 space-y-6">
          <Section id="profile" title="Your profile" description="Shown in the sidebar and used after sign-in.">
            <div className="flex items-center gap-4 px-5 py-4">
              {profile?.picture ? (
                <img
                  src={profile.picture}
                  alt=""
                  referrerPolicy="no-referrer"
                  className="h-14 w-14 rounded-full border border-border object-cover"
                />
              ) : (
                <span className="flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-sm font-semibold">
                  {initialsFromName(displayName || "Employee")}
                </span>
              )}
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">{displayName || "Employee"}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {workEmail ||
                    (profile?.provider === "google"
                      ? "Google account"
                      : profile?.provider === "microsoft"
                        ? "Microsoft account"
                        : "Local sign-in")}
                </p>
                <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                  {profile?.provider === "google"
                    ? "Signed in with Google"
                    : profile?.provider === "microsoft"
                      ? "Signed in with Microsoft Entra ID"
                      : "HR ID / local account"}
                </p>
              </div>
            </div>
            <Divider />
            <FieldRow label="Display name">
              <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="bg-secondary/40" />
            </FieldRow>
            <Divider />
            <FieldRow label="Email">
              <Input
                value={workEmail}
                onChange={(e) => setWorkEmail(e.target.value)}
                className="bg-secondary/40"
                disabled={profile?.provider === "google" || profile?.provider === "microsoft"}
              />
            </FieldRow>
            <Divider />
            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <p className="text-sm font-medium">Log out</p>
                <p className="text-xs text-muted-foreground">Return to the landing page. You can sign in again anytime.</p>
              </div>
              <Button variant="outline" onClick={() => signOut()}>
                Log out
              </Button>
            </div>
          </Section>

          <Section id="general" title="General Settings" description="Identity and defaults for this agent.">
            <FieldRow label="Agent name">
              <Input value={agentName} onChange={(e) => setAgentName(e.target.value)} className="bg-secondary/40" />
            </FieldRow>
            <Divider />
            <FieldRow label="Description">
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="min-h-[64px] resize-none bg-secondary/40"
              />
            </FieldRow>
            <Divider />
            <FieldRow label="Default model">
              <Select value={defaultModel} options={MODELS.map((m) => m.label)} onChange={setDefaultModel} />
            </FieldRow>
          </Section>

          <Section id="model" title="Model Configuration" description="Tune generation parameters.">
            <SliderRow
              label="Temperature"
              hint="Higher values increase creativity and randomness."
              value={temperature[0].toFixed(2)}
            >
              <Slider value={temperature} onValueChange={setTemperature} min={0} max={1} step={0.05} />
            </SliderRow>
            <Divider />
            <SliderRow label="Max output tokens" hint="Upper bound on a single response." value={String(maxTokens[0])}>
              <Slider value={maxTokens} onValueChange={setMaxTokens} min={256} max={8192} step={256} />
            </SliderRow>
            <Divider />
            <ToggleRow
              label="Stream responses"
              description="Return tokens as they are generated."
              checked={streaming}
              onChange={setStreaming}
            />
          </Section>

          <Section
            id="tools"
            title="Tool Permissions"
            description="Govern how the agent invokes connected MCP tools."
          >
            <ToggleRow
              label="Auto-approve tool calls"
              description="Does not skip Approve & Send. Email, Slack, Teams, and record writes always wait for confirmation — even on existing chats."
              checked={autoApprove}
              onChange={(v) => persistGuardrails({ autoApprove: v })}
            />
            <Divider />
            <ToggleRow
              label="Read-only mode"
              description="Block sends and record writes — lookups and policy search only. Takes effect on the next New Chat."
              checked={readOnly}
              onChange={(v) => persistGuardrails({ readOnly: v })}
            />
            <Divider />
            <ToggleRow
              label="Parallel tool execution"
              description="Allow independent tools to run simultaneously."
              checked={parallelTools}
              onChange={setParallelTools}
            />
          </Section>

          <Section id="security" title="Security Settings" description="Protect sensitive data and maintain audit trails.">
            <FieldRow label="Data retention">
              <Select
                value={dataRetention}
                options={["7 days", "30 days", "90 days", "1 year", "Indefinite"]}
                onChange={setDataRetention}
              />
            </FieldRow>
            <Divider />
            <ToggleRow
              label="Audit logging"
              description="Record every tool call and data access event."
              checked={auditLog}
              onChange={setAuditLog}
            />
            <Divider />
            <ToggleRow
              label="PII redaction"
              description="Automatically mask personal data in chat, Tasks, Work, and WebSocket events."
              checked={piiRedaction}
              onChange={(v) => persistGuardrails({ piiRedaction: v })}
            />
          </Section>

          <Section id="auth" title="Authentication" description="How members sign in and stay authenticated.">
            <ToggleRow
              label="SSO required"
              description="Enforce single sign-on for all workspace members."
              checked={ssoOnly}
              onChange={setSsoOnly}
            />
            <Divider />
            <ToggleRow
              label="Multi-factor authentication"
              description="Require a second factor at sign-in."
              checked={mfa}
              onChange={setMfa}
            />
            <Divider />
            <FieldRow label="Session timeout">
              <Select
                value={sessionTimeout}
                options={["1 hour", "4 hours", "8 hours", "24 hours"]}
                onChange={setSessionTimeout}
              />
            </FieldRow>
          </Section>

          <Section id="data" title="Data Access Controls" description="Choose which sources the agent may reach.">
            <ToggleRow
              label="Web access"
              description="Allow live web search and page retrieval."
              checked={webAccess}
              onChange={setWebAccess}
            />
            <Divider />
            <ToggleRow
              label="Database access"
              description="Permit queries against connected databases."
              checked={dbAccess}
              onChange={setDbAccess}
            />
            <Divider />
            <ToggleRow
              label="Filesystem access"
              description="Allow reading and writing files in the workspace."
              checked={fileAccess}
              onChange={setFileAccess}
            />
          </Section>

          <Section id="behavior" title="Agent Behavior" description="Shape the agent's default voice and reasoning.">
            <FieldRow label="Tone">
              <Select
                value={tone}
                options={["Professional", "Friendly", "Concise", "Technical", "Casual"]}
                onChange={setTone}
              />
            </FieldRow>
            <Divider />
            <FieldRow label="Verbosity">
              <Select value={verbosity} options={["Terse", "Balanced", "Detailed"]} onChange={setVerbosity} />
            </FieldRow>
            <Divider />
            <FieldRow label="System prompt">
              <Textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="min-h-[120px] resize-none bg-secondary/40 font-mono text-[13px] leading-relaxed"
              />
            </FieldRow>
          </Section>
        </div>
      </div>
    </PageContainer>
  )
}

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <section id={id} className="dream-in scroll-mt-8 rounded-2xl border border-border/60 bg-card/40">
      <div className="border-b border-border/60 px-6 py-5">
        <h2 className="font-heading text-base font-semibold text-foreground">{title}</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">{description}</p>
      </div>
      <div className="px-6 py-2">{children}</div>
    </section>
  )
}

function Divider() {
  return <div className="h-px bg-border/60" />
}

function FieldRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between sm:gap-8">
      <label className="pt-1.5 text-[14px] font-medium text-foreground sm:w-40 sm:shrink-0">{label}</label>
      <div className="w-full sm:max-w-sm">{children}</div>
    </div>
  )
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-6 py-4">
      <div>
        <p className="text-[14px] font-medium text-foreground">{label}</p>
        <p className="mt-0.5 text-[13px] text-muted-foreground">{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} aria-label={label} />
    </div>
  )
}

function SliderRow({
  label,
  hint,
  value,
  children,
}: {
  label: string
  hint: string
  value: string
  children: ReactNode
}) {
  return (
    <div className="py-4">
      <div className="flex items-center justify-between">
        <p className="text-[14px] font-medium text-foreground">{label}</p>
        <span className="font-mono text-[13px] text-foreground">{value}</span>
      </div>
      <p className="mt-0.5 mb-3 text-[13px] text-muted-foreground">{hint}</p>
      {children}
    </div>
  )
}

function Select({
  value,
  options,
  onChange,
}: {
  value: string
  options: string[]
  onChange: (v: string) => void
}) {
  return (
    <OptionMenu
      options={options}
      value={value}
      onChange={onChange}
      trigger={
        <button className="flex h-9 w-full items-center justify-between rounded-md border border-border/60 bg-secondary/40 px-3 text-sm text-foreground transition-colors hover:bg-secondary/60">
          {value}
          <span className="text-muted-foreground">▾</span>
        </button>
      }
    />
  )
}
