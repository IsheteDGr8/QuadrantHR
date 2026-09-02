"use client"

/**
 * ui-block-canvas.tsx
 *
 * The generative UI rendering layer for the Side Canvas.
 *
 * The server-side Canvas pipeline emits structured UI blocks
 * ({type, version, props}) after a completed agent turn.
 * This module:
 *   1. Maps each block type to a pre-built React component via REGISTRY
 *   2. Renders blocks as the matching component
 *   3. Falls back to a visible error card for unknown/malformed blocks — never crashes
 *
 * Adapted from agent-ui-block-pack-v2.jsx (58 block types) with light peach theme
 * tokens matching the app's design system.
 *
 * EXPORTS (public surface):
 *   UiBlockCanvas({ blocks: CanvasBlock[] }): JSX.Element
 *   REGISTRY: Record<string, React.ComponentType<{ props: any }>>
 */

import React, { useEffect, useState } from "react"
import { DocumentPreview as WorkspaceDocPreview } from "@/components/document-preview"
import type { CanvasBlock } from "@/lib/canvas-types"
import {
  downloadWorkspaceFile,
  fileBasename,
  fileExt,
  friendlyFileTitle,
} from "@/lib/workspace-files"
import {
  ListChecks, Mail, Table2, CheckCircle2, Circle, ChevronRight,
  Code2, AlertTriangle, Send, Trash2, Check, X, Clock, User,
  Users, BarChart3, LineChart as LineChartIcon, PieChart as PieChartIcon,
  Gauge as GaugeIcon, GitBranch, MessageSquare, Info, Quote as QuoteIcon,
  FileCode2, Tag, LayoutGrid, TrendingUp, TrendingDown, Minus, Plus,
  Briefcase, Calendar, Star, Paperclip, MapPin, Download, Mail as MailIcon,
  Phone, Activity, Sparkles, FileText, Search, HelpCircle, PenTool,
  ToggleLeft, Wallet, Flag, MessageCircle, Layers, ClipboardList,
  ArrowLeftRight, ListTodo, Link2, ChevronDown, Inbox, ListOrdered, Loader2,
} from "lucide-react"
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts"

/* ---------------------------------------------------------------------- */
/*  LIGHT PEACH BLOCK SHELL (token-based)                                  */
/* ---------------------------------------------------------------------- */

// Named tones mapped to light peach theme accent classes
const TONE_CLASSES: Record<string, string> = {
  violet: "border-primary/30 text-primary",
  teal:   "border-success/30 text-success",
  amber:  "border-warning/30 text-warning",
  emerald:"border-success/30 text-success",
  red:    "border-destructive/30 text-destructive",
  blue:   "border-navy/30 text-navy",
  pink:   "border-primary/30 text-primary",
  slate:  "border-border text-muted-foreground",
}

function toneAccent(tone?: string): string {
  if (!tone) return TONE_CLASSES.violet
  if (TONE_CLASSES[tone]) return TONE_CLASSES[tone]
  // hex color — use inline style instead (returned separately, caller handles)
  return "border-border text-muted-foreground"
}

const CHART_COLORS = ["#FF6B4A", "#1F4E79", "#F5A623", "#2E9E7C", "#E08A5B", "#8B5CF6"]
const STATUS_DOT: Record<string, string> = {
  active: "bg-success", away: "bg-warning", pto: "bg-muted-foreground", offline: "bg-muted-foreground/60"
}
const STATUS_LABEL: Record<string, string> = {
  active: "Active now", away: "Away", pto: "On leave", offline: "Offline"
}

function initials(name: string): string {
  return (name || "?").split(" ").map((p: string) => p[0]).filter(Boolean).slice(0, 2).join("").toUpperCase()
}

function Avatar({ name, size = "w-9 h-9", status, textSize = "text-xs" }: {
  name: string; size?: string; status?: string; textSize?: string
}) {
  return (
    <div className={`relative ${size} rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center ${textSize} font-medium text-primary shrink-0`}>
      {initials(name)}
      {status && <span className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ring-2 ring-card ${STATUS_DOT[status] || "bg-muted-foreground"}`} />}
    </div>
  )
}

// Light peach shell that wraps every block
function BlockShell({ icon: Icon, label, children }: {
  icon: React.ComponentType<{ className?: string }>; label: string; children: React.ReactNode
}) {
  const showCatalogChip = Boolean(label) && !/·\s*v\d+/i.test(label) && !/^(freeform|data-table|ui-block)/i.test(label)
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-[0_1px_2px_rgba(42,36,32,0.04)]">
      {showCatalogChip && (
        <div className="flex items-center gap-2 border-b border-border/80 bg-secondary/30 px-3.5 py-2">
          <Icon className="h-3.5 w-3.5 text-primary" />
          <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  )
}

// Error / unknown-type fallback card
function UnknownBlock({ error, raw }: { error: string; raw?: string }) {
  return (
    <div className="rounded-xl border border-warning/30 bg-warning/10 p-3">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-3.5 h-3.5 text-warning" />
        <span className="text-[11px] font-medium text-warning">ui-block error — {error}</span>
      </div>
      {raw && (
        <pre className="text-[10px] font-mono text-muted-foreground overflow-x-auto whitespace-pre-wrap break-words leading-relaxed">
          {raw}
        </pre>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/*  PEOPLE BLOCKS                                                           */
/* ---------------------------------------------------------------------- */

function EmployeeCardCompact({ props }: { props: any }) {
  const { name, role, status = "active" } = props
  return (
    <BlockShell icon={User} label="employee-card-compact · v1">
      <div className="flex items-center gap-3">
        <Avatar name={name} status={status} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground truncate">{name}</div>
          <div className="text-xs text-muted-foreground truncate">{role}</div>
        </div>
      </div>
    </BlockShell>
  )
}

function EmployeeCardDetailed({ props }: { props: any }) {
  const {
    name,
    role,
    team,
    status = "active",
    email,
    tenure,
    projects,
    manager,
    location,
    employeeId,
    phone,
  } = props
  const details = [
    tenure ? { label: "Start / tenure", value: tenure } : null,
    employeeId ? { label: "Employee ID", value: employeeId } : null,
    manager ? { label: "Manager", value: manager } : null,
    location ? { label: "Location", value: location } : null,
    projects != null && projects !== "" ? { label: "Projects", value: String(projects) } : null,
    email ? { label: "Email", value: email, wide: true, mono: true } : null,
    phone ? { label: "Phone", value: phone, wide: true } : null,
  ].filter(Boolean) as { label: string; value: string; wide?: boolean; mono?: boolean }[]
  return (
    <BlockShell icon={User} label="employee-card-detailed · v1">
      <div className="flex items-center gap-3 mb-3">
        <Avatar name={name} status={status} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground truncate">{name}</div>
          <div className="text-xs text-muted-foreground truncate">{role}{team ? ` · ${team}` : ""}</div>
        </div>
      </div>
      {details.length > 0 && (
        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-border">
          {details.map((item) => (
            <div key={item.label} className={item.wide ? "col-span-2" : undefined}>
              <div className="text-[10px] text-muted-foreground">{item.label}</div>
              <div className={`text-xs text-foreground ${item.mono ? "font-mono text-muted-foreground" : ""}`}>
                {item.value}
              </div>
            </div>
          ))}
        </div>
      )}
    </BlockShell>
  )
}

function EmployeeCardAvailability({ props }: { props: any }) {
  const { name, role, week = [] } = props
  return (
    <BlockShell icon={Calendar} label="employee-card-availability · v1">
      <div className="flex items-center gap-3 mb-3">
        <Avatar name={name} size="w-8 h-8" textSize="text-[10px]" />
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground truncate">{name}</div>
          <div className="text-xs text-muted-foreground truncate">{role}</div>
        </div>
      </div>
      <div className="flex gap-1.5">
        {week.map((d: any, i: number) => (
          <div key={i} className="flex-1 text-center">
            <div className="text-[9px] text-muted-foreground mb-1">{d.day}</div>
            <div className={`h-6 rounded ${d.free ? "bg-success/15 border border-success/30" : "bg-secondary/40 border border-border"}`} />
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function EmployeeCardContact({ props }: { props: any }) {
  const { name, role, email, phone, status = "active" } = props
  return (
    <BlockShell icon={Phone} label="employee-card-contact · v1">
      <div className="flex items-center gap-3 mb-3">
        <Avatar name={name} status={status} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground truncate">{name}</div>
          <div className="text-xs text-muted-foreground truncate">{role} · {STATUS_LABEL[status] || status}</div>
        </div>
      </div>
      <div className="space-y-1.5">
        {email && <div className="flex items-center gap-2 text-xs text-muted-foreground"><MailIcon className="w-3 h-3 text-muted-foreground" /><span className="font-mono">{email}</span></div>}
        {phone && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Phone className="w-3 h-3 text-muted-foreground" /><span className="font-mono">{phone}</span></div>}
      </div>
    </BlockShell>
  )
}

function EmployeeCardStats({ props }: { props: any }) {
  const { name, role, stats = [] } = props
  return (
    <BlockShell icon={Briefcase} label="employee-card-stats · v1">
      <div className="flex items-center gap-3 mb-3">
        <Avatar name={name} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground truncate">{name}</div>
          <div className="text-xs text-muted-foreground truncate">{role}</div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {stats.map((s: any, i: number) => (
          <div key={i} className="text-center rounded-lg bg-secondary/40 border border-border py-2">
            <div className="text-sm font-medium text-foreground">{s.value}</div>
            <div className="text-[10px] text-muted-foreground">{s.label}</div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function TeamRoster({ props }: { props: any }) {
  const { title, members = [] } = props
  return (
    <BlockShell icon={Users} label="team-roster · v1">
      {title && <h4 className="text-sm font-medium text-foreground mb-3">{title}</h4>}
      <div className="space-y-2.5">
        {members.map((m: any, i: number) => (
          <div key={i} className="flex items-center gap-2.5">
            <Avatar name={m.name} size="w-7 h-7" textSize="text-[10px]" status={m.status || "active"} />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-foreground truncate">{m.name}</div>
              <div className="text-[11px] text-muted-foreground truncate">{m.role}</div>
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function OrgNode({ props }: { props: any }) {
  const { name, role, reports = [] } = props
  return (
    <BlockShell icon={GitBranch} label="org-node · v1">
      <div className="flex items-center gap-3 mb-4">
        <Avatar name={name} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground">{name}</div>
          <div className="text-xs text-muted-foreground">{role}</div>
        </div>
      </div>
      {reports.length > 0 && (
        <div className="pl-3 border-l border-border space-y-2">
          {reports.map((r: any, i: number) => (
            <div key={i} className="flex items-center gap-2">
              <Avatar name={r.name} size="w-6 h-6" textSize="text-[9px]" />
              <div className="min-w-0">
                <div className="text-xs text-foreground truncate">{r.name}</div>
                <div className="text-[10px] text-muted-foreground truncate">{r.role}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </BlockShell>
  )
}

function AvatarGroup({ props }: { props: any }) {
  const { names = [], label } = props
  return (
    <BlockShell icon={Users} label="avatar-group · v1">
      <div className="flex items-center gap-3">
        <div className="flex -space-x-2">
          {names.slice(0, 6).map((n: string, i: number) => (
            <Avatar key={i} name={n} size="w-8 h-8" textSize="text-[10px]" />
          ))}
          {names.length > 6 && (
            <div className="w-8 h-8 rounded-full bg-secondary/60 border border-border flex items-center justify-center text-[10px] text-muted-foreground">
              +{names.length - 6}
            </div>
          )}
        </div>
        {label && <span className="text-xs text-muted-foreground">{label}</span>}
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  DATA & CHART BLOCKS                                                     */
/* ---------------------------------------------------------------------- */

function StatGrid({ props }: { props: any }) {
  const { title, stats = [] } = props
  return (
    <BlockShell icon={BarChart3} label="stat-grid · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3 uppercase tracking-wide">{title}</h4>}
      <div className="grid grid-cols-2 gap-2">
        {stats.map((s: any, i: number) => (
          <div key={i} className="rounded-lg bg-secondary/40 border border-border p-3">
            <div className="text-lg font-semibold text-foreground tabular-nums">{s.value}</div>
            <div className="text-[10px] text-muted-foreground mt-0.5">{s.label}</div>
            {s.delta && (
              <div className={`flex items-center gap-1 text-[10px] mt-1 ${s.delta > 0 ? "text-success" : "text-destructive"}`}>
                {s.delta > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {Math.abs(s.delta)}%
              </div>
            )}
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function StatHero({ props }: { props: any }) {
  const { value, label, sub, tone } = props
  return (
    <BlockShell icon={Activity} label="stat-hero · v1">
      <div className="text-center py-2">
        <div className="text-4xl font-bold text-foreground tabular-nums">{value}</div>
        <div className="text-sm text-foreground mt-1">{label}</div>
        {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
      </div>
    </BlockShell>
  )
}

function BarChartBlock({ props }: { props: any }) {
  const { title, data = [], xKey = "label", yKey = "value" } = props
  return (
    <BlockShell icon={BarChart3} label="bar-chart · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: "#8A7160" }} />
          <YAxis tick={{ fontSize: 10, fill: "#8A7160" }} />
          <Tooltip contentStyle={{ backgroundColor: "#FFFFFF", border: "1px solid #F0DBCB", color: "#2A1E16", borderRadius: 8, fontSize: 11 }} />
          <Bar dataKey={yKey} fill="#a78bfa" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </BlockShell>
  )
}

function LineChartBlock({ props }: { props: any }) {
  const { title, data = [], xKey = "label", yKey = "value" } = props
  return (
    <BlockShell icon={LineChartIcon} label="line-chart · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: "#8A7160" }} />
          <YAxis tick={{ fontSize: 10, fill: "#8A7160" }} />
          <Tooltip contentStyle={{ backgroundColor: "#FFFFFF", border: "1px solid #F0DBCB", color: "#2A1E16", borderRadius: 8, fontSize: 11 }} />
          <Line type="monotone" dataKey={yKey} stroke="#a78bfa" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </BlockShell>
  )
}

function AreaChartBlock({ props }: { props: any }) {
  const { title, data = [], xKey = "label", yKey = "value" } = props
  return (
    <BlockShell icon={LineChartIcon} label="area-chart · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="areag" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: "#8A7160" }} />
          <YAxis tick={{ fontSize: 10, fill: "#8A7160" }} />
          <Tooltip contentStyle={{ backgroundColor: "#FFFFFF", border: "1px solid #F0DBCB", color: "#2A1E16", borderRadius: 8, fontSize: 11 }} />
          <Area type="monotone" dataKey={yKey} stroke="#a78bfa" strokeWidth={2} fill="url(#areag)" />
        </AreaChart>
      </ResponsiveContainer>
    </BlockShell>
  )
}

function DonutChart({ props }: { props: any }) {
  const { title, slices = [], data = [] } = props
  const chartData = slices.length ? slices : data
  return (
    <BlockShell icon={PieChartIcon} label="donut-chart · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-2">{title}</h4>}
      <div className="flex items-center gap-4">
        <ResponsiveContainer width={100} height={100}>
          <PieChart>
            <Pie data={chartData} cx="50%" cy="50%" innerRadius={28} outerRadius={44} dataKey="value" strokeWidth={0}>
              {chartData.map((_: any, i: number) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="space-y-1.5">
          {chartData.map((s: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
              <span className="text-muted-foreground">{s.label || s.name}</span>
              <span className="text-foreground font-medium tabular-nums">{s.value}</span>
            </div>
          ))}
        </div>
      </div>
    </BlockShell>
  )
}

function GaugeBlock({ props }: { props: any }) {
  const { value, max = 100, label, tone } = props
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <BlockShell icon={GaugeIcon} label="gauge · v1">
      <div className="space-y-2">
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">{label}</span>
          <span className="text-foreground font-medium tabular-nums">{value} / {max}</span>
        </div>
        <div className="h-3 rounded-full bg-secondary/60 overflow-hidden">
          <div className="h-full rounded-full bg-violet-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
        <div className="text-right text-[10px] text-muted-foreground">{Math.round(pct)}%</div>
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  WORKFLOW BLOCKS                                                          */
/* ---------------------------------------------------------------------- */

function Checklist({ props }: { props: any }) {
  const { title, items = [] } = props
  return (
    <BlockShell icon={ListChecks} label="checklist · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="space-y-2">
        {items.map((item: any, i: number) => (
          <div key={i} className="flex items-start gap-2.5">
            {item.done
              ? <CheckCircle2 className="w-4 h-4 text-success shrink-0 mt-0.5" />
              : <Circle className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />}
            <span className={`text-xs leading-relaxed ${item.done ? "line-through text-muted-foreground" : "text-foreground"}`}>
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function VerticalStepper({ props }: { props: any }) {
  const { title, steps = [] } = props
  return (
    <BlockShell icon={ListChecks} label="vertical-stepper · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="relative space-y-3">
        {steps.map((step: any, i: number) => {
          const isDone = step.status === "done"
          const isActive = step.status === "active"
          return (
            <div key={i} className="flex items-start gap-3">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-medium border ${
                isDone ? "bg-success/15 border-emerald-500/40 text-success"
                : isActive ? "bg-primary/15 border-primary/30 text-primary"
                : "bg-secondary/40 border-border text-muted-foreground"
              }`}>
                {isDone ? <Check className="w-3 h-3" /> : i + 1}
              </div>
              <div className="min-w-0">
                <div className={`text-xs font-medium ${isActive ? "text-primary" : isDone ? "text-muted-foreground line-through" : "text-foreground"}`}>{step.label}</div>
                {step.sub && <div className="text-[10px] text-muted-foreground mt-0.5">{step.sub}</div>}
              </div>
            </div>
          )
        })}
      </div>
    </BlockShell>
  )
}

function HorizontalStepper({ props }: { props: any }) {
  const { steps = [] } = props
  return (
    <BlockShell icon={ArrowLeftRight} label="horizontal-stepper · v1">
      <div className="flex items-center gap-2">
        {steps.map((step: any, i: number) => {
          const isDone = step.status === "done"
          const isActive = step.status === "active"
          return (
            <React.Fragment key={i}>
              <div className="flex flex-col items-center gap-1 min-w-0">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium border ${
                  isDone ? "bg-success/15 border-emerald-500/40 text-success"
                  : isActive ? "bg-primary/15 border-primary/30 text-primary"
                  : "bg-secondary/40 border-border text-muted-foreground"
                }`}>
                  {isDone ? <Check className="w-3 h-3" /> : i + 1}
                </div>
                <div className={`text-[9px] text-center ${isActive ? "text-primary" : "text-muted-foreground"}`}>{step.label}</div>
              </div>
              {i < steps.length - 1 && <div className={`flex-1 h-px ${isDone ? "bg-success/40" : "bg-secondary/60"}`} />}
            </React.Fragment>
          )
        })}
      </div>
    </BlockShell>
  )
}

function ApprovalCard({ props }: { props: any }) {
  const { title, body, approve_label = "Approve", reject_label = "Reject", tone } = props
  const [decided, setDecided] = useState<"approved" | "rejected" | null>(null)
  return (
    <BlockShell icon={CheckCircle2} label="approval-card · v1">
      <h4 className="text-sm font-medium text-foreground mb-2">{title}</h4>
      {body && <p className="text-xs text-muted-foreground leading-relaxed mb-4">{body}</p>}
      {decided ? (
        <div className={`text-xs font-medium ${decided === "approved" ? "text-success" : "text-destructive"}`}>
          {decided === "approved" ? "✓ Approved" : "✗ Rejected"}
        </div>
      ) : (
        <div className="flex gap-2">
          <button onClick={() => setDecided("approved")} className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-success/15 border border-success/30 text-success hover:bg-success/30 transition-colors">
            {approve_label}
          </button>
          <button onClick={() => setDecided("rejected")} className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-destructive/10 border border-red-500/20 text-destructive hover:bg-destructive/15 transition-colors">
            {reject_label}
          </button>
        </div>
      )}
    </BlockShell>
  )
}

function ApprovalCompact({ props }: { props: any }) {
  return <ApprovalCard props={{ ...props, _compact: true }} />
}

function Timeline({ props }: { props: any }) {
  const { title, events = [] } = props
  return (
    <BlockShell icon={Clock} label="timeline · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="space-y-3">
        {events.map((e: any, i: number) => (
          <div key={i} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className="w-2 h-2 rounded-full bg-violet-500 shrink-0 mt-1" />
              {i < events.length - 1 && <div className="w-px flex-1 bg-secondary/60 mt-1" />}
            </div>
            <div className="min-w-0 pb-3">
              <div className="text-xs font-medium text-foreground">{e.label}</div>
              {e.when && <div className="text-[10px] text-muted-foreground">{e.when}</div>}
              {e.body && <div className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">{e.body}</div>}
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function ProgressBar({ props }: { props: any }) {
  const { label, value, max = 100, show_pct = true } = props
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <BlockShell icon={Activity} label="progress-bar · v1">
      <div className="space-y-2">
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">{label}</span>
          {show_pct && <span className="text-foreground font-medium tabular-nums">{Math.round(pct)}%</span>}
        </div>
        <div className="h-2 rounded-full bg-secondary/60 overflow-hidden">
          <div className="h-full rounded-full bg-violet-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  CONTENT BLOCKS                                                          */
/* ---------------------------------------------------------------------- */

function EmailPreview({ props }: { props: any }) {
  const { from, to, subject, body, date } = props
  return (
    <BlockShell icon={Mail} label="email-preview · v1">
      <div className="space-y-2">
        <div className="flex justify-between">
          <span className="text-xs font-medium text-foreground">{subject}</span>
          {date && <span className="text-[10px] text-muted-foreground">{date}</span>}
        </div>
        <div className="text-[10px] text-muted-foreground">
          {from && <span className="mr-3">From: <span className="font-mono">{from}</span></span>}
          {to && <span>To: <span className="font-mono">{to}</span></span>}
        </div>
        {body && (
          <div className="pt-2 border-t border-border">
            <p className="text-xs text-foreground leading-relaxed whitespace-pre-wrap">{body}</p>
          </div>
        )}
      </div>
    </BlockShell>
  )
}

function ChatThread({ props }: { props: any }) {
  const { messages = [] } = props
  return (
    <BlockShell icon={MessageSquare} label="chat-thread · v1">
      <div className="space-y-3">
        {messages.map((m: any, i: number) => (
          <div key={i} className={`flex gap-2 ${m.align === "right" ? "flex-row-reverse" : ""}`}>
            <Avatar name={m.author} size="w-7 h-7" textSize="text-[9px]" />
            <div className={`max-w-[80%] rounded-lg px-2.5 py-1.5 ${m.align === "right" ? "bg-primary/15 border border-violet-500/20" : "bg-secondary/50 border border-border"}`}>
              <div className="text-[10px] text-muted-foreground mb-0.5">{m.author}</div>
              <div className="text-xs text-foreground leading-relaxed">{m.body}</div>
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function AlertBanner({ props }: { props: any }) {
  const { title, body, severity = "info" } = props
  const colors: Record<string, string> = {
    info: "border-navy/30 bg-blue-500/[0.06] text-navy",
    warning: "border-warning/30 bg-warning/[0.06] text-warning",
    error: "border-destructive/30 bg-red-500/[0.06] text-destructive",
    success: "border-success/30 bg-success/[0.06] text-success",
  }
  const icons: Record<string, any> = { info: Info, warning: AlertTriangle, error: AlertTriangle, success: CheckCircle2 }
  const Icon = icons[severity] || Info
  return (
    <div className={`rounded-xl border p-3 ${colors[severity] || colors.info}`}>
      <div className="flex items-start gap-2">
        <Icon className="w-4 h-4 shrink-0 mt-0.5" />
        <div>
          {title && <div className="text-xs font-medium mb-0.5">{title}</div>}
          {body && <div className="text-xs opacity-80 leading-relaxed">{body}</div>}
        </div>
      </div>
    </div>
  )
}

function cellText(value: unknown): string {
  if (value == null) return ""
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function normalizeTable(columns: unknown, rows: unknown): { columns: string[]; rows: string[][] } {
  const list = Array.isArray(rows) ? rows : []
  const objectRows = list.filter((r) => r && typeof r === "object" && !Array.isArray(r)) as Record<string, unknown>[]
  let cols: string[] = Array.isArray(columns)
    ? columns.map((c) => (typeof c === "string" ? c : cellText(c))).filter(Boolean)
    : []
  if (cols.length === 0 && objectRows.length > 0) {
    const seen = new Set<string>()
    for (const row of objectRows) {
      for (const key of Object.keys(row)) {
        if (!seen.has(key)) {
          seen.add(key)
          cols.push(key)
        }
      }
    }
  }
  const out: string[][] = []
  for (const row of list) {
    if (Array.isArray(row)) {
      out.push(cols.length ? cols.map((_, i) => cellText(row[i])) : row.map(cellText))
    } else if (row && typeof row === "object") {
      const record = row as Record<string, unknown>
      out.push((cols.length ? cols : Object.keys(record)).map((c) => cellText(record[c])))
    }
  }
  if (cols.length === 0 && out[0]) {
    cols = out[0].map((_, i) => `Col ${i + 1}`)
  }
  return { columns: cols, rows: out }
}

function DataTable({ props }: { props: any }) {
  const { title } = props
  const { columns, rows } = normalizeTable(props.columns, props.rows)
  if (rows.length === 0) {
    return (
      <BlockShell icon={Table2} label="data-table · v1">
        {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
        <p className="text-xs text-muted-foreground">No rows to display.</p>
      </BlockShell>
    )
  }
  return (
    <BlockShell icon={Table2} label="data-table · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              {columns.map((c: string, i: number) => (
                <th key={i} className="text-left text-[10px] font-medium text-muted-foreground pb-2 pr-4 uppercase tracking-wide">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-t border-border">
                {row.map((cell, j) => (
                  <td key={j} className="py-2 pr-4 text-foreground">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </BlockShell>
  )
}

function Quote({ props }: { props: any }) {
  const { text, attribution } = props
  return (
    <BlockShell icon={QuoteIcon} label="quote · v1">
      <blockquote className="border-l-2 border-primary/30 pl-3">
        <p className="text-sm text-foreground italic leading-relaxed">{text}</p>
        {attribution && <footer className="text-[10px] text-muted-foreground mt-2">— {attribution}</footer>}
      </blockquote>
    </BlockShell>
  )
}

function CodeBlock({ props }: { props: any }) {
  const { language, code } = props
  return (
    <BlockShell icon={Code2} label="code-block · v1">
      {language && <div className="text-[10px] text-primary font-mono mb-2">{language}</div>}
      <pre className="text-[11.5px] font-mono text-foreground overflow-x-auto whitespace-pre leading-relaxed">
        {code}
      </pre>
    </BlockShell>
  )
}

function BadgeRow({ props }: { props: any }) {
  const { items = [] } = props
  return (
    <BlockShell icon={Tag} label="badge-row · v1">
      <div className="flex flex-wrap gap-1.5">
        {items.map((b: any, i: number) => (
          <span key={i} className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-border bg-secondary/50 text-foreground">
            {typeof b === "string" ? b : b.label}
          </span>
        ))}
      </div>
    </BlockShell>
  )
}

function RatingBlock({ props }: { props: any }) {
  const { score, max = 5, label } = props
  return (
    <BlockShell icon={Star} label="rating · v1">
      <div className="flex items-center gap-3">
        <div className="flex gap-0.5">
          {Array.from({ length: max }).map((_, i) => (
            <Star key={i} className={`w-4 h-4 ${i < score ? "text-warning fill-warning" : "text-muted-foreground/40"}`} />
          ))}
        </div>
        {label && <span className="text-xs text-muted-foreground">{label}</span>}
      </div>
    </BlockShell>
  )
}

function resolveBlockFilePath(props: any): string | null {
  const candidates = [props?.path, props?.file_path, props?.filepath, props?.filename, props?.name]
  for (const c of candidates) {
    if (typeof c === "string" && c.trim() && /\.(pdf|docx|xlsx|pptx|txt|csv|md)$/i.test(c)) {
      return c.trim().replace(/\\/g, "/")
    }
  }
  return null
}

function AttachmentBlock({ props }: { props: any }) {
  const filePath = resolveBlockFilePath(props)
  const filename = fileBasename(filePath || props.filename || props.name || "Document")
  const title = friendlyFileTitle(filePath || filename)
  const ext = fileExt(filePath || filename).replace(".", "").toUpperCase() || "FILE"
  const size = props.size
  const mime = props.mime
  const [previewOpen, setPreviewOpen] = useState(false)
  const [downloading, setDownloading] = useState(false)

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    if (!filePath) return
    setDownloading(true)
    try {
      await downloadWorkspaceFile(filePath)
    } catch {
      window.location.href = `/api/workspace/files?path=${encodeURIComponent(filePath)}&download=1`
    } finally {
      setDownloading(false)
    }
  }

  return (
    <>
      <BlockShell icon={Paperclip} label="attachment">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => filePath && setPreviewOpen(true)}
            disabled={!filePath}
            className="flex min-w-0 flex-1 items-center gap-3 rounded-lg p-1 text-left transition-colors hover:bg-secondary/50 disabled:cursor-default disabled:hover:bg-transparent"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-stone-900 text-[#f5e6d3]">
              <FileText className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-medium text-foreground">{title}</div>
              <div className="mt-0.5 text-[10px] text-muted-foreground">
                {ext}
                {size ? ` · ${size}` : ""}
                {mime ? ` · ${mime}` : ""}
                {filePath ? " · Click to open" : ""}
              </div>
            </div>
          </button>
          {filePath && (
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              title="Download"
              aria-label={`Download ${title}`}
            >
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            </button>
          )}
        </div>
      </BlockShell>
      <WorkspaceDocPreview
        filePath={filePath}
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        initialMode="popup"
      />
    </>
  )
}

function CalendarEvent({ props }: { props: any }) {
  const { title, date, time, location, attendees = [] } = props
  return (
    <BlockShell icon={Calendar} label="calendar-event · v1">
      <div className="space-y-2">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {date && <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{date}</span>}
          {time && <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{time}</span>}
          {location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{location}</span>}
        </div>
        {attendees.length > 0 && (
          <div className="pt-2 border-t border-border">
            <div className="text-[10px] text-muted-foreground mb-1.5">Attendees</div>
            <div className="flex -space-x-2">
              {attendees.slice(0, 5).map((name: string, i: number) => (
                <Avatar key={i} name={name} size="w-7 h-7" textSize="text-[9px]" />
              ))}
              {attendees.length > 5 && (
                <div className="w-7 h-7 rounded-full bg-secondary/60 border border-border flex items-center justify-center text-[9px] text-muted-foreground">
                  +{attendees.length - 5}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  FORM & INPUT BLOCKS                                                     */
/* ---------------------------------------------------------------------- */

function FieldSummary({ props }: { props: any }) {
  const { title, fields = [] } = props
  return (
    <BlockShell icon={ClipboardList} label="field-summary · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="space-y-2.5">
        {fields.map((f: any, i: number) => (
          <div key={i} className="flex justify-between gap-4">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wide shrink-0">{f.label}</span>
            <span className="text-xs text-foreground text-right">{f.value ?? <em className="text-muted-foreground">—</em>}</span>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function Poll({ props }: { props: any }) {
  const { question, options = [] } = props
  const [voted, setVoted] = useState<number | null>(null)
  return (
    <BlockShell icon={LayoutGrid} label="poll · v1">
      <h4 className="text-sm font-medium text-foreground mb-3">{question}</h4>
      <div className="space-y-2">
        {options.map((o: any, i: number) => (
          <button key={i} onClick={() => setVoted(i)}
            className={`w-full text-left text-xs px-3 py-2 rounded-lg border transition-colors ${
              voted === i
                ? "border-primary/30 bg-primary/10 text-primary"
                : "border-border bg-card text-foreground hover:bg-secondary/60"
            }`}>
            {typeof o === "string" ? o : o.label}
          </button>
        ))}
      </div>
    </BlockShell>
  )
}

function SignatureBlock({ props }: { props: any }) {
  const { name, role, date, signed = false } = props
  return (
    <BlockShell icon={PenTool} label="signature-block · v1">
      <div className="space-y-3">
        <div className="h-12 rounded-lg border border-dashed border-border bg-secondary/30 flex items-center justify-center">
          {signed
            ? <span className="text-sm font-medium text-success italic">{name}</span>
            : <span className="text-xs text-muted-foreground">Signature required</span>}
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{name}{role ? ` · ${role}` : ""}</span>
          {date && <span>{date}</span>}
        </div>
      </div>
    </BlockShell>
  )
}

function ToggleSetting({ props }: { props: any }) {
  const { label, description, on = false } = props
  const [enabled, setEnabled] = useState(on)
  return (
    <BlockShell icon={ToggleLeft} label="toggle-setting · v1">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs font-medium text-foreground">{label}</div>
          {description && <div className="text-[10px] text-muted-foreground mt-0.5">{description}</div>}
        </div>
        <button onClick={() => setEnabled(!enabled)}
          className={`relative w-9 h-5 rounded-full transition-colors shrink-0 ${enabled ? "bg-violet-500" : "bg-secondary/70"}`}>
          <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${enabled ? "translate-x-4" : "translate-x-0.5"}`} />
        </button>
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  DIRECTORY BLOCKS                                                        */
/* ---------------------------------------------------------------------- */

function DocumentPreview({ props }: { props: any }) {
  const filePath = resolveBlockFilePath(props)
  const filename = fileBasename(filePath || props.filename || "Document")
  const title = friendlyFileTitle(filePath || filename)
  const { excerpt, pages, type } = props
  const [previewOpen, setPreviewOpen] = useState(false)
  const [downloading, setDownloading] = useState(false)

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!filePath) return
    setDownloading(true)
    try {
      await downloadWorkspaceFile(filePath)
    } catch {
      window.location.href = `/api/workspace/files?path=${encodeURIComponent(filePath)}&download=1`
    } finally {
      setDownloading(false)
    }
  }

  return (
    <>
      <BlockShell icon={FileText} label="document">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={() => filePath && setPreviewOpen(true)}
            disabled={!filePath}
            className="flex min-w-0 flex-1 items-start gap-3 rounded-lg p-1 text-left transition-colors hover:bg-secondary/50 disabled:cursor-default"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-stone-900 text-[#f5e6d3]">
              <FileText className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-medium text-foreground">{title}</div>
              {(type || pages || filePath) && (
                <div className="mt-0.5 text-[10px] text-muted-foreground">
                  {type}
                  {type && pages ? " · " : ""}
                  {pages ? `${pages} pages` : ""}
                  {filePath ? `${type || pages ? " · " : ""}Click to open` : ""}
                </div>
              )}
              {excerpt && <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{excerpt}</p>}
            </div>
          </button>
          {filePath && (
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground"
              title="Download"
              aria-label={`Download ${title}`}
            >
              {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            </button>
          )}
        </div>
      </BlockShell>
      <WorkspaceDocPreview
        filePath={filePath}
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        initialMode="popup"
      />
    </>
  )
}

function SearchResults({ props }: { props: any }) {
  const { title, results = [] } = props
  return (
    <BlockShell icon={Search} label="search-results · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="space-y-3">
        {results.map((r: any, i: number) => (
          <div key={i} className="space-y-0.5">
            <div className="text-xs font-medium text-primary">{r.title}</div>
            {r.url && <div className="text-[10px] font-mono text-muted-foreground truncate">{r.url}</div>}
            {r.excerpt && <div className="text-[11px] text-muted-foreground leading-relaxed">{r.excerpt}</div>}
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function FaqBlock({ props }: { props: any }) {
  const { items = [] } = props
  const [open, setOpen] = useState<number | null>(null)
  return (
    <BlockShell icon={HelpCircle} label="faq · v1">
      <div className="space-y-2">
        {items.map((item: any, i: number) => (
          <div key={i} className="border border-border rounded-lg overflow-hidden">
            <button onClick={() => setOpen(open === i ? null : i)}
              className="w-full flex justify-between items-center px-3 py-2 text-xs font-medium text-foreground hover:bg-secondary/40 transition-colors">
              {item.q}
              <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform ${open === i ? "rotate-180" : ""}`} />
            </button>
            {open === i && (
              <div className="px-3 py-2 border-t border-border">
                <p className="text-[11px] text-muted-foreground leading-relaxed">{item.a}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function KeyValue({ props }: { props: any }) {
  const { title, pairs = [] } = props
  return (
    <BlockShell icon={Layers} label="key-value · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <dl className="space-y-2">
        {pairs.map((p: any, i: number) => (
          <div key={i} className="flex justify-between gap-4 text-xs">
            <dt className="text-muted-foreground shrink-0">{p.key}</dt>
            <dd className="text-foreground text-right font-medium">{p.value}</dd>
          </div>
        ))}
      </dl>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  METRICS BLOCKS                                                          */
/* ---------------------------------------------------------------------- */

function BalanceMeter({ props }: { props: any }) {
  const { label, left, right, value, max = 100 } = props
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <BlockShell icon={Wallet} label="balance-meter · v1">
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{left}</span>
          <span>{right}</span>
        </div>
        <div className="h-3 rounded-full bg-secondary/60 overflow-hidden">
          <div className="h-full rounded-full bg-violet-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
        {label && <div className="text-center text-[10px] text-muted-foreground">{label}</div>}
      </div>
    </BlockShell>
  )
}

function SpendBreakdown({ props }: { props: any }) {
  return <DonutChart props={props} />
}

function BeforeAfter({ props }: { props: any }) {
  const { title, before, after } = props
  return (
    <BlockShell icon={ArrowLeftRight} label="before-after · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-card border border-border p-3">
          <div className="text-[10px] text-muted-foreground mb-1 uppercase tracking-wide">Before</div>
          <div className="text-sm font-medium text-foreground">{before}</div>
        </div>
        <div className="rounded-lg bg-violet-500/[0.08] border border-violet-500/20 p-3">
          <div className="text-[10px] text-primary mb-1 uppercase tracking-wide">After</div>
          <div className="text-sm font-medium text-primary">{after}</div>
        </div>
      </div>
    </BlockShell>
  )
}

function Milestones({ props }: { props: any }) {
  const { title, items = [] } = props
  return (
    <BlockShell icon={Flag} label="milestones · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="space-y-2.5">
        {items.map((m: any, i: number) => (
          <div key={i} className="flex items-center gap-3">
            <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${m.done ? "bg-success/15 border border-emerald-500/40" : "bg-secondary/40 border border-border"}`}>
              {m.done ? <Check className="w-3 h-3 text-success" /> : <span className="w-2 h-2 rounded-full bg-muted-foreground/40" />}
            </div>
            <div className="min-w-0 flex-1">
              <div className={`text-xs font-medium ${m.done ? "text-muted-foreground line-through" : "text-foreground"}`}>{m.label}</div>
              {m.date && <div className="text-[10px] text-muted-foreground">{m.date}</div>}
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  GENERAL PURPOSE BLOCKS                                                  */
/* ---------------------------------------------------------------------- */

function OverviewCard({ props }: { props: any }) {
  const { title, subtitle, body } = props
  const stats = Array.isArray(props.stats) ? props.stats : []
  if (stats.length > 0) return <StatGrid props={{ title, stats }} />
  const text = typeof body === "string" ? body.trim() : ""
  if (!title && !text) return null
  return (
    <BlockShell icon={FileText} label="Overview">
      <div className="space-y-1.5">
        {title && <div className="text-sm font-medium text-foreground">{title}</div>}
        {subtitle && <div className="text-xs text-muted-foreground">{subtitle}</div>}
        {text && (
          <p className="text-xs text-foreground leading-relaxed whitespace-pre-wrap">
            {text.length > 360 ? `${text.slice(0, 360).trim()}…` : text}
          </p>
        )}
      </div>
    </BlockShell>
  )
}

function StatStrip({ props }: { props: any }) {
  const { stats = [] } = props
  return (
    <BlockShell icon={BarChart3} label="stat-strip · v1">
      <div className="flex divide-x divide-white/[0.06]">
        {stats.map((s: any, i: number) => (
          <div key={i} className={`flex-1 text-center ${i > 0 ? "pl-3" : ""} ${i < stats.length - 1 ? "pr-3" : ""}`}>
            <div className="text-base font-semibold text-foreground tabular-nums">{s.value}</div>
            <div className="text-[10px] text-muted-foreground">{s.label}</div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function IconList({ props }: { props: any }) {
  const { title, items = [] } = props
  const icons: Record<string, any> = {
    check: CheckCircle2, x: X, warning: AlertTriangle, info: Info, star: Star,
    clock: Clock, flag: Flag, user: User, briefcase: Briefcase, sparkles: Sparkles,
  }
  return (
    <BlockShell icon={ListChecks} label="icon-list · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="space-y-2">
        {items.map((item: any, i: number) => {
          const Icon = (item.icon && icons[item.icon]) || CheckCircle2
          return (
            <div key={i} className="flex items-start gap-2.5">
              <Icon className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
              <div>
                <div className="text-xs text-foreground">{item.label}</div>
                {item.meta && <div className="text-[10px] text-muted-foreground">{item.meta}</div>}
              </div>
            </div>
          )
        })}
      </div>
    </BlockShell>
  )
}

function LinkPreview({ props }: { props: any }) {
  const { title, url, description, domain } = props
  return (
    <BlockShell icon={Link2} label="link-preview · v1">
      <div className="space-y-1">
        {(domain || url) && <div className="text-[10px] font-mono text-muted-foreground">{domain || url}</div>}
        {title && <div className="text-xs font-medium text-primary">{title}</div>}
        {description && <div className="text-[11px] text-muted-foreground leading-relaxed">{description}</div>}
      </div>
    </BlockShell>
  )
}

function AccordionBlock({ props }: { props: any }) {
  const { title, defaultOpen = 0, items = [] } = props
  const [openIndex, setOpenIndex] = useState<number>(defaultOpen)
  return (
    <BlockShell icon={ChevronDown} label="accordion · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="space-y-1.5">
        {items.map((item: any, i: number) => (
          <div key={i} className="border border-border rounded-lg overflow-hidden">
            <button onClick={() => setOpenIndex(openIndex === i ? -1 : i)}
              className="w-full flex justify-between items-center px-3 py-2 text-xs font-medium text-foreground hover:bg-secondary/40 transition-colors">
              {item.title}
              <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform ${openIndex === i ? "rotate-180" : ""}`} />
            </button>
            {openIndex === i && (
              <div className="px-3 py-2 border-t border-border">
                <p className="text-[11px] text-muted-foreground leading-relaxed">{item.body}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

function TagCloud({ props }: { props: any }) {
  const { title, tags = [] } = props
  return (
    <BlockShell icon={Tag} label="tag-cloud · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-2">{title}</h4>}
      <div className="flex flex-wrap gap-1.5">
        {tags.map((t: any, i: number) => {
          const label = typeof t === "string" ? t : t.label
          return (
            <span key={i} className="px-2 py-0.5 rounded-full text-[10px] font-medium border border-border bg-secondary/50 text-foreground">
              {label}
            </span>
          )
        })}
      </div>
    </BlockShell>
  )
}

function EmptyState({ props }: { props: any }) {
  const { icon: iconName, title, message, cta } = props
  const icons: Record<string, any> = { sparkles: Sparkles, inbox: Inbox, search: Search, users: Users }
  const Icon = (iconName && icons[iconName]) || Inbox
  return (
    <BlockShell icon={Icon} label="empty-state · v1">
      <div className="flex flex-col items-center text-center gap-2 py-4">
        <Icon className="w-8 h-8 text-muted-foreground" />
        {title && <div className="text-sm font-medium text-foreground">{title}</div>}
        {message && <div className="text-xs text-muted-foreground leading-relaxed max-w-[200px]">{message}</div>}
        {cta && (
          <button className="mt-1 text-[11px] font-medium px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/20 text-primary hover:bg-violet-500/25 transition-colors">
            {cta}
          </button>
        )}
      </div>
    </BlockShell>
  )
}

function DividerLabel({ props }: { props: any }) {
  const { label } = props
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="flex-1 h-px bg-secondary/60" />
      <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
      <div className="flex-1 h-px bg-secondary/60" />
    </div>
  )
}

function CustomList({ props }: { props: any }) {
  const { title, items = [], ordered = false } = props
  return (
    <BlockShell icon={ordered ? ListOrdered : ListTodo} label="custom-list · v1">
      {title && <h4 className="text-xs font-medium text-muted-foreground mb-3">{title}</h4>}
      <div className="space-y-2">
        {items.map((item: any, i: number) => (
          <div key={i} className="flex items-start gap-2.5">
            <span className="text-[10px] text-muted-foreground mt-0.5 shrink-0 tabular-nums w-4">{ordered ? `${i + 1}.` : "•"}</span>
            <div className="min-w-0">
              <div className="text-xs text-foreground">{item.label}</div>
              {item.meta && <div className="text-[10px] text-muted-foreground">{item.meta}</div>}
            </div>
          </div>
        ))}
      </div>
    </BlockShell>
  )
}

/* ---------------------------------------------------------------------- */
/*  REGISTRY                                                               */
/* ---------------------------------------------------------------------- */

export const REGISTRY: Record<string, React.ComponentType<{ props: any }>> = {
  // People
  "employee-card-compact": EmployeeCardCompact,
  "employee-card-detailed": EmployeeCardDetailed,
  "employee-card-availability": EmployeeCardAvailability,
  "employee-card-contact": EmployeeCardContact,
  "employee-card-stats": EmployeeCardStats,
  "team-roster": TeamRoster,
  "org-node": OrgNode,
  "avatar-group": AvatarGroup,
  // Data & charts
  "stat-grid": StatGrid,
  "stat-hero": StatHero,
  "bar-chart": BarChartBlock,
  "line-chart": LineChartBlock,
  "area-chart": AreaChartBlock,
  "donut-chart": DonutChart,
  "gauge": GaugeBlock,
  // Workflow
  "checklist": Checklist,
  "vertical-stepper": VerticalStepper,
  "horizontal-stepper": HorizontalStepper,
  "approval-card": ApprovalCard,
  "approval-compact": ApprovalCompact,
  "timeline": Timeline,
  "progress-bar": ProgressBar,
  // Content
  "email-preview": EmailPreview,
  "chat-thread": ChatThread,
  "alert-banner": AlertBanner,
  "data-table": DataTable,
  "quote": Quote,
  "code-block": CodeBlock,
  "badge-row": BadgeRow,
  "rating": RatingBlock,
  "attachment": AttachmentBlock,
  "calendar-event": CalendarEvent,
  // Forms & input
  "field-summary": FieldSummary,
  "poll": Poll,
  "signature-block": SignatureBlock,
  "toggle-setting": ToggleSetting,
  // Directory
  "document-preview": DocumentPreview,
  "search-results": SearchResults,
  "faq": FaqBlock,
  "key-value": KeyValue,
  // Metrics
  "balance-meter": BalanceMeter,
  "spend-breakdown": SpendBreakdown,
  "before-after": BeforeAfter,
  "milestones": Milestones,
  // General purpose
  "freeform-card": OverviewCard,
  "stat-strip": StatStrip,
  "icon-list": IconList,
  "link-preview": LinkPreview,
  "accordion": AccordionBlock,
  "tag-cloud": TagCloud,
  "empty-state": EmptyState,
  "divider-label": DividerLabel,
  "custom-list": CustomList,
  
  // Aliases for block-catalog.md discrepancies
  "key-value-list": KeyValue,
  "amount-breakdown": SpendBreakdown,
  "approval": ApprovalCard,
  "badge-list": BadgeRow,
  "code-snippet": CodeBlock,
  "comment-thread": ChatThread,
  "comparison-two-column": BeforeAfter,
  "directory-search-result": SearchResults,
  "email": EmailPreview,
  "faq-expandable": FaqBlock,
  "file-attachment": AttachmentBlock,
  "form-field-group": FieldSummary,
  "horizontal-bar-chart": BarChartBlock,
  "metric-comparison": BeforeAfter,
  "milestone-tracker": Milestones,
  "stepper": VerticalStepper,
  "stepper-horizontal": HorizontalStepper,
  "summary-card": OverviewCard,
  "survey-poll": Poll,
  "table": DataTable,
  "task-card": OverviewCard,
  "toggle-settings": ToggleSetting,
}

/* ---------------------------------------------------------------------- */
/*  CANVAS RENDERER                                                         */
/* ---------------------------------------------------------------------- */

export function UiBlockCanvas({
  blocks,
  conversationId,
  turnId,
}: {
  blocks: CanvasBlock[]
  conversationId?: string | null
  turnId?: string | null
}) {
  useEffect(() => {
    if (!blocks.length) return
    console.info('[canvas-trace]', JSON.stringify({
      conversationId: conversationId ?? null,
      turnId: turnId ?? null,
      stage: 'block rendered',
      timestamp: new Date().toISOString(),
      status: 'success',
      count: blocks.length,
    }))
  }, [blocks, conversationId, turnId])

  return (
    <div className="space-y-3">
      {blocks.filter((block) => block.type !== "freeform-card" && block.type !== "chat-thread").map((block, i) => {
        const Component = REGISTRY[block.type]
        if (!Component) {
          return <UnknownBlock key={i} error={`no renderer for "${block.type}"`} raw={JSON.stringify(block, null, 2)} />
        }
        return <Component key={i} props={block.props} />
      })}
    </div>
  )
}
