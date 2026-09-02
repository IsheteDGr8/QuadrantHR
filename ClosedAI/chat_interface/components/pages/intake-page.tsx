"use client";

import { Suspense, useMemo, useState } from "react";
import { LayoutGrid, ListFilter, Radar, RefreshCw, ShieldCheck, Zap } from "lucide-react";
import { toast } from "sonner";
import { ClusterCard, IntakeRow } from "@/components/intake-bits";
import {
  dispositionMeta,
  intakeClusters,
  type IntakeDisposition,
} from "@/lib/intake-data";
import { useTasks } from "@/lib/use-tasks";
import { useNavigation } from "@/lib/navigation";
import IntakeClusterDetail from "./intake-cluster-detail";
import { PageContainer, PageHeader } from "@/components/management/shared";
import { cn } from "@/lib/utils";
import { AiSummaryPanel } from "@/components/pages/ai-summary-panel";
import { Button } from "@/components/ui/button";

type View = "decide" | "clusters" | "stream";

const views: { key: View; label: string; icon: typeof LayoutGrid }[] = [
  { key: "decide", label: "By decision", icon: Zap },
  { key: "clusters", label: "By cluster", icon: LayoutGrid },
  { key: "stream", label: "Full stream", icon: ListFilter },
];

const lanes: { key: IntakeDisposition; accent: string }[] = [
  { key: "human", accent: "border-t-warning" },
  { key: "assist", accent: "border-t-navy/60" },
  { key: "auto", accent: "border-t-success" },
];

function IntakePageContent() {
  const nav = useNavigation();
  const [view, setView] = useState<View>("decide");
  const [ingesting, setIngesting] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const { items: intakeItems, stats: intakeStats, refresh, usingFallback, loading } = useTasks();
  const open = useMemo(
    () => intakeItems.filter((i) => i.state !== "handled"),
    [intakeItems],
  );
  const liveClusters = useMemo(() => {
    const ids = new Set(open.map((i) => i.clusterId));
    const known = intakeClusters.filter((c) => ids.has(c.id) || !c.discovered);
    // Include discovered clusters only when they have live items.
    const discovered = intakeClusters.filter((c) => c.discovered && ids.has(c.id));
    const base = [...known.filter((c) => !c.discovered), ...discovered];
    // Always surface clusters that currently have open items.
    for (const id of ids) {
      if (!base.some((c) => c.id === id)) {
        base.push({
          id,
          label: id.replace(/-/g, " "),
          domain: "Live",
          discovered: true,
          blurb: "Appeared from live intake.",
          trend: [0, 0, 0, 0, 0, 0, open.filter((i) => i.clusterId === id).length],
        });
      }
    }
    return base;
  }, [open]);
  const newPatterns = useMemo(
    () => liveClusters.filter((c) => c.discovered && open.some((i) => i.clusterId === c.id)).length,
    [liveClusters, open],
  );
  const inClusterDetail = Boolean(nav?.selectedClusterId);

  const ingestSources = async () => {
    setIngesting(true);
    try {
      // System events only (real Cosmos employee visas). Email requires live messages.
      const res = await fetch("/api/tasks/ingest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sources: ["system"] }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      const n = typeof data.created === "number" ? data.created : 0;
      toast.success(
        n > 0 ? `Ingested ${n} new task${n === 1 ? "" : "s"}` : "No new system tasks to ingest",
      );
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setIngesting(false);
    }
  };

  const seedDemoTickets = async () => {
    setSeeding(true);
    try {
      const res = await fetch("/api/tasks/seed-demo", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      const d = data.byDisposition || {};
      toast.success(
        `Loaded ${data.count} demo tickets`,
        {
          description: `Copilot can handle: ${d.auto ?? 0} · Drafted: ${d.assist ?? 0} · Needs judgement: ${d.human ?? 0}`,
        },
      );
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Seed failed");
    } finally {
      setSeeding(false);
    }
  };

  // Keep the briefing panel mounted for the whole Tasks visit (tabs + cluster
  // drill-ins) so it only regenerates when you leave Tasks and come back.
  return (
    <>
      {inClusterDetail ? (
        <IntakeClusterDetail clusterId={nav.selectedClusterId!} />
      ) : (
    <PageContainer>
      <PageHeader
        title="Tasks"
        icon={Radar}
        description="Intake by decision: what Copilot can run, what it drafted for approval, and what needs your judgement."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={ingesting}
              onClick={ingestSources}
              className="inline-flex items-center gap-1.5"
            >
              <RefreshCw className={cn("size-3.5", ingesting && "animate-spin")} />
              {ingesting ? "Ingesting…" : "Ingest system events"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={seeding}
              onClick={seedDemoTickets}
              className="inline-flex items-center gap-1.5"
            >
              <ShieldCheck className={cn("size-3.5", seeding && "animate-pulse")} />
              {seeding ? "Seeding…" : "Load demo tickets"}
            </Button>
            <div className="flex items-center gap-1 rounded-xl border border-border/60 bg-card/40 p-1">
              {views.map((v) => (
                <button
                  key={v.key}
                  type="button"
                  onClick={() => setView(v.key)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground",
                    view === v.key && "bg-secondary/60 text-foreground font-semibold",
                  )}
                >
                  <v.icon className="size-3.5" />
                  {v.label}
                </button>
              ))}
            </div>
          </div>
        }
      />

      <div className="dream-in">
        {usingFallback && (
          <p className="mb-3 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            Cosmos is not connected — showing an empty Tasks list (no demo data). Configure Cosmos to load real tickets.
          </p>
        )}
        {loading && open.length === 0 && (
          <p className="mb-3 text-xs text-muted-foreground">Loading intake…</p>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Arrived today" value={String(intakeStats.arrivedToday)} sub="all channels" />
          <Stat
            label="Absorbed by Copilot"
            value={String(intakeStats.autoAbsorbed)}
            sub="no human touch"
            tone="success"
          />
          <Stat
            label="Open for HR"
            value={String(intakeStats.open)}
            sub={`${intakeStats.needsJudgement} need your judgement`}
            tone="warning"
          />
          <Stat
            label="New patterns"
            value={String(newPatterns)}
            sub="clusters with no playbook"
            tone="warning"
          />
        </div>

        {view === "decide" && (
          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            {lanes.map((lane) => {
              const meta = dispositionMeta[lane.key];
              const items = open.filter((i) => i.disposition === lane.key);
              return (
                <section
                  key={lane.key}
                  className={cn(
                    "overflow-hidden rounded-xl border border-t-2 border-border/60 bg-card/40",
                    lane.accent,
                  )}
                >
                  <div className="border-b border-border/60 px-4 py-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold">{meta.label}</p>
                      <span className="rounded-md border border-border/60 bg-secondary/60 px-2 py-0.5 text-xs font-mono font-medium text-muted-foreground">
                        {items.length}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{meta.blurb}</p>
                  </div>
                  {items.length ? (
                    items.map((item) => (
                      <div key={item.id} data-intake-id={item.id}>
                        <IntakeRow item={item} />
                      </div>
                    ))
                  ) : (
                    <p className="px-4 py-8 text-center text-xs text-muted-foreground">
                      Nothing waiting here.
                    </p>
                  )}
                </section>
              );
            })}
          </div>
        )}

        {view === "clusters" && (
          <>
            <div className="mt-6 flex items-center gap-2">
              <Radar className="size-4 text-warning" />
              <h2 className="text-sm font-semibold uppercase tracking-wider">Emerging — no playbook yet</h2>
              <p className="text-xs text-muted-foreground">
                Grouped automatically from requests that didn&apos;t fit an existing category.
              </p>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {liveClusters
                .filter((c) => c.discovered)
                .map((c) => (
                  <ClusterCard
                    key={c.id}
                    cluster={c}
                    count={open.filter((i) => i.clusterId === c.id).length}
                  />
                ))}
            </div>

            <div className="mt-6 flex items-center gap-2">
              <ShieldCheck className="size-4 text-navy" />
              <h2 className="text-sm font-semibold uppercase tracking-wider">Known categories</h2>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {liveClusters
                .filter((c) => !c.discovered)
                .map((c) => (
                  <ClusterCard
                    key={c.id}
                    cluster={c}
                    count={open.filter((i) => i.clusterId === c.id).length}
                  />
                ))}
            </div>
          </>
        )}

        {view === "stream" && (
          <div className="mt-6 overflow-hidden rounded-xl border border-border/60 bg-card/40">
            <div className="flex items-center justify-between border-b border-border/60 px-4 py-2.5">
              <p className="text-xs font-medium text-muted-foreground">
                Newest first · every channel · {intakeItems.length} items
              </p>
              <p className="text-[11px] text-muted-foreground">Age</p>
            </div>
            {intakeItems.length === 0 ? (
              <p className="px-4 py-12 text-center text-sm text-muted-foreground">
                No live intake yet. Ingest system events, or wait for Copilot to need your approval.
              </p>
            ) : (
              [...intakeItems]
                .sort((a, b) => a.ageMinutes - b.ageMinutes)
                .map((item) => (
                  <div key={item.id} data-intake-id={item.id}>
                    <IntakeRow item={item} dense />
                  </div>
                ))
            )}
          </div>
        )}
      </div>
    </PageContainer>
      )}

      <div className={inClusterDetail ? "hidden" : undefined}>
        <AiSummaryPanel pageContext={open} />
      </div>
    </>
  );
}

function Stat({
  label,
  value,
  sub,
  tone = "muted",
}: {
  label: string;
  value: string;
  sub: string;
  tone?: "muted" | "success" | "warning";
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-4 transition-colors hover:border-border hover:bg-card/70">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">{label}</p>
      <p
        className={cn(
          "mt-1.5 text-2xl font-semibold",
          tone === "success" && "text-success",
          tone === "warning" && "text-warning",
          tone === "muted" && "text-foreground",
        )}
      >
        {value}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>
    </div>
  );
}

export default function IntakePage() {
  return (
    <Suspense>
      <IntakePageContent />
    </Suspense>
  );
}
