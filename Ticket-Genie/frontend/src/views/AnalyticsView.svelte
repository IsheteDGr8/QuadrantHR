<script>
  import { onMount } from 'svelte';
  import { checkAuthGuard, userStore, isSuperAdmin } from '../lib/stores/auth.js';
  import { activeTab, selectedTicket } from '../lib/stores/tickets.js';
  import { apiFetchAIUsage, apiFetchDepartmentHealth } from '../lib/api.js';

  let analytics = null;
  let loading = true;
  let errorMessage = '';
  let aiUsage = null;
  let aiUsageError = '';
  let mounted = false;
  let loadedKey = Symbol('initial');

  $: userDept = $userStore?.department || (isSuperAdmin($userStore) ? 'Upper Executive Management' : 'IT Operations');
  $: isDeptView = $activeTab === 'dept-analytics';
  $: requestedDepartment = isDeptView ? userDept : null;
  $: viewKey = isDeptView ? `department:${requestedDepartment}` : 'enterprise';
  $: if (mounted && viewKey !== loadedKey) loadAnalytics();

  $: kpis = analytics?.kpis || {};
  $: trends = analytics?.ticket_trends || [];
  $: chartMax = Math.max(1, ...trends.flatMap((point) => [point.created, point.resolved]));
  $: createdPoints = chartPoints(trends, 'created');
  $: resolvedPoints = chartPoints(trends, 'resolved');

  onMount(() => {
    if (!checkAuthGuard(isDeptView ? 'ticketer' : 'admin')) return;
    mounted = true;
  });

  async function loadAnalytics() {
    const key = viewKey;
    loadedKey = key;
    loading = true;
    errorMessage = '';
    aiUsageError = '';
    try {
      if (isDeptView) {
        analytics = await apiFetchDepartmentHealth(requestedDepartment);
        aiUsage = null;
      } else {
        const [healthResult, usageResult] = await Promise.allSettled([
          apiFetchDepartmentHealth(requestedDepartment),
          apiFetchAIUsage(30)
        ]);
        if (healthResult.status === 'rejected') throw healthResult.reason;
        analytics = healthResult.value;
        if (usageResult.status === 'fulfilled') {
          aiUsage = usageResult.value;
        } else {
          aiUsage = null;
          aiUsageError = usageResult.reason?.message || 'Azure AI usage is unavailable.';
        }
      }
    } catch (error) {
      errorMessage = error.message || 'Unable to load department analytics.';
      analytics = null;
    } finally {
      if (loadedKey === key) loading = false;
    }
  }

  function chartPoints(points, field) {
    if (!points?.length) return '';
    return points.map((point, index) => {
      const x = 38 + (index * 644 / Math.max(points.length - 1, 1));
      const y = 180 - ((point[field] || 0) / chartMax * 140);
      return `${x},${y}`;
    }).join(' ');
  }

  function trendText(value) {
    if (value === 0) return 'No change';
    return `${value > 0 ? '+' : ''}${value}% vs prior 30d`;
  }

  function formatNumber(value) {
    return Number(value || 0).toLocaleString();
  }

  function openTicket(ticket) {
    $selectedTicket = ticket;
    $activeTab = 'inbox';
  }
</script>

<div class="analytics-view animate-fade">
  <div class="view-header">
    <div>
      <div class="eyebrow"><i class="ph-bold ph-sparkle"></i> AI OPERATIONS INTELLIGENCE</div>
      <h1>{isDeptView ? `${analytics?.department || userDept} Health` : 'Enterprise Department Health'}</h1>
      <p>Calculated queue health, issue velocity, SLA exposure, and prioritized actions from persisted tickets.</p>
    </div>
    <div class="header-actions">
      {#if analytics}<span class:data-synthetic={analytics.data_mode !== 'live'} class="data-badge"><i class="ph-bold ph-database"></i> {analytics.data_mode} data · {analytics.record_count} tickets</span>{/if}
      <button class="refresh-button" on:click={loadAnalytics} disabled={loading}><i class="ph-bold ph-arrows-clockwise"></i> Refresh</button>
    </div>
  </div>

  {#if loading}
    <div class="loading-panel"><i class="ph-bold ph-spinner animate-spin"></i><strong>Calculating department intelligence...</strong><span>Scoring SLA exposure and emerging issue patterns</span></div>
  {:else if errorMessage}
    <div class="error-panel"><i class="ph-bold ph-warning-circle"></i><div><strong>Analytics unavailable</strong><p>{errorMessage}</p></div><button on:click={loadAnalytics}>Try again</button></div>
  {:else if analytics}
    <section class="kpi-grid">
      <article class="kpi-card health-card">
        <div class="kpi-top"><span>Department health</span><i class="ph-duotone ph-heartbeat"></i></div>
        <div class="kpi-value">{kpis.health_score}<small>/100</small></div>
        <div class:healthy={kpis.health_label === 'Healthy'} class:watch={kpis.health_label === 'Watch'} class:risk={kpis.health_label === 'At Risk'} class="status-pill">{kpis.health_label}</div>
        <div class="score-track"><span style={`width:${kpis.health_score}%`}></span></div>
      </article>
      <article class="kpi-card">
        <div class="kpi-top"><span>Ticket volume</span><i class="ph-duotone ph-ticket"></i></div>
        <div class="kpi-value">{kpis.tickets_30d}</div>
        <div class:negative={kpis.volume_change_pct > 0} class="kpi-change"><i class={`ph-bold ${kpis.volume_change_pct > 0 ? 'ph-trend-up' : 'ph-trend-down'}`}></i> {trendText(kpis.volume_change_pct)}</div>
      </article>
      <article class="kpi-card">
        <div class="kpi-top"><span>Open backlog</span><i class="ph-duotone ph-stack"></i></div>
        <div class="kpi-value">{kpis.open_backlog}</div>
        <div class="kpi-caption">{kpis.overdue_open} overdue · {kpis.critical_open} critical</div>
      </article>
      <article class="kpi-card">
        <div class="kpi-top"><span>SLA compliance</span><i class="ph-duotone ph-shield-check"></i></div>
        <div class="kpi-value">{kpis.sla_compliance_pct}<small>%</small></div>
        <div class="kpi-caption">Across open and resolved tickets</div>
      </article>
      <article class="kpi-card">
        <div class="kpi-top"><span>Mean resolution</span><i class="ph-duotone ph-timer"></i></div>
        <div class="kpi-value">{kpis.mttr_hours}<small>h</small></div>
        <div class="kpi-caption">Submission to verified resolution</div>
      </article>
    </section>

    {#if !isDeptView}
      <section class="panel ai-usage-panel">
        <div class="panel-header ai-usage-header">
          <div>
            <span class="section-label">AZURE APPLICATION INSIGHTS</span>
            <h2>AI model usage · last 30 days</h2>
            <p>Historical Genie and classifier consumption queried directly from Azure Monitor.</p>
          </div>
          {#if aiUsage}<span class="azure-source-badge"><i class="ph-bold ph-cloud-check"></i> Azure data</span>{/if}
        </div>
        {#if aiUsageError}
          <div class="ai-usage-error"><i class="ph-bold ph-warning-circle"></i><span>{aiUsageError}</span></div>
        {:else if aiUsage}
          <div class="ai-usage-grid">
            <div><span>Model calls</span><strong>{formatNumber(aiUsage.totals.calls)}</strong></div>
            <div><span>Prompt tokens</span><strong>{formatNumber(aiUsage.totals.prompt_tokens)}</strong></div>
            <div><span>Completion tokens</span><strong>{formatNumber(aiUsage.totals.completion_tokens)}</strong></div>
            <div><span>Total tokens</span><strong>{formatNumber(aiUsage.totals.total_tokens)}</strong></div>
            <div><span>Estimated cost</span><strong>${Number(aiUsage.totals.estimated_cost_usd || 0).toFixed(6)}</strong></div>
          </div>
          {#if aiUsage.daily.length}
            <div class="usage-days">
              {#each aiUsage.daily.slice(-14) as day}
                <div class="usage-day">
                  <span>{day.day}</span>
                  <div class="usage-track"><i style={`width:${Math.max(3, (day.total_tokens / Math.max(...aiUsage.daily.map(item => item.total_tokens), 1)) * 100)}%`}></i></div>
                  <strong>{formatNumber(day.total_tokens)} tokens</strong>
                </div>
              {/each}
            </div>
          {:else}
            <div class="empty-panel">Azure has no AI usage traces for this period yet.</div>
          {/if}
        {/if}
      </section>
    {/if}

    <section class="brief-card">
      <div class="brief-orb"><i class="ph-fill ph-sparkle"></i></div>
      <div class="brief-content">
        <div class="section-label">AI DEPARTMENT BRIEF</div>
        <h2>{analytics.brief.headline}</h2>
        <p>{analytics.brief.summary}</p>
        <div class="recommendations">
          {#each analytics.brief.recommendations as recommendation}
            <div><i class="ph-bold ph-arrow-circle-right"></i><span>{recommendation}</span></div>
          {/each}
        </div>
        <small><i class="ph-bold ph-info"></i> {analytics.brief.method}</small>
      </div>
    </section>

    <section class="main-grid">
      <article class="panel trend-panel">
        <div class="panel-header">
          <div><span class="section-label">VOLUME & VELOCITY</span><h2>Ticket trends</h2></div>
          <div class="legend"><span><i class="created-dot"></i>Created</span><span><i class="resolved-dot"></i>Resolved</span></div>
        </div>
        <div class="chart-wrap">
          <svg viewBox="0 0 720 220" role="img" aria-label="Weekly created and resolved ticket trend">
            <line x1="38" y1="40" x2="682" y2="40" class="grid-line" />
            <line x1="38" y1="110" x2="682" y2="110" class="grid-line" />
            <line x1="38" y1="180" x2="682" y2="180" class="grid-line" />
            <polyline points={createdPoints} class="chart-line created-line" />
            <polyline points={resolvedPoints} class="chart-line resolved-line" />
            {#each trends as point, index}
              <circle cx={38 + (index * 644 / Math.max(trends.length - 1, 1))} cy={180 - (point.created / chartMax * 140)} r="3.5" class="created-point"><title>{point.label}: {point.created} created</title></circle>
              <circle cx={38 + (index * 644 / Math.max(trends.length - 1, 1))} cy={180 - (point.resolved / chartMax * 140)} r="3.5" class="resolved-point"><title>{point.label}: {point.resolved} resolved</title></circle>
              {#if index % 2 === 0}<text x={38 + (index * 644 / Math.max(trends.length - 1, 1))} y="207" text-anchor="middle">{point.label}</text>{/if}
            {/each}
          </svg>
        </div>
      </article>

      <article class="panel issues-panel">
        <div class="panel-header"><div><span class="section-label">PATTERN DETECTION</span><h2>Emerging issues</h2></div><i class="ph-duotone ph-radar"></i></div>
        {#if analytics.emerging_issues.length}
          <div class="issue-list">
            {#each analytics.emerging_issues as issue, index}
              <div class="issue-row">
                <div class="issue-rank">{index + 1}</div>
                <div class="issue-copy"><strong>{issue.category}</strong><span>{issue.current_count} in 14d · {issue.open_count} still open</span></div>
                <div class:rising={issue.signal === 'Rising'} class="signal-pill">{issue.change_pct > 0 ? '+' : ''}{issue.change_pct}%</div>
              </div>
            {/each}
          </div>
        {:else}<div class="empty-panel">No statistically meaningful issue clusters detected.</div>{/if}
      </article>
    </section>

    <section class="panel attention-panel">
      <div class="panel-header">
        <div><span class="section-label">AI ATTENTION QUEUE</span><h2>What should be resolved right now</h2><p>Ranked by priority, SLA exposure, age, and classifier confidence.</p></div>
        <i class="ph-duotone ph-siren attention-icon"></i>
      </div>
      {#if analytics.attention_queue.length}
        <div class="attention-list">
          {#each analytics.attention_queue as ticket, index}
            <button class="attention-row" on:click={() => openTicket(ticket)}>
              <span class="attention-rank">{index + 1}</span>
              <span class="ticket-main"><strong>{ticket.id} · {ticket.title}</strong><small>{ticket.category} · {ticket.age_hours} hours open</small></span>
              <span class={`priority ${ticket.priority.toLowerCase()}`}>{ticket.priority}</span>
              <span class="attention-reason">{ticket.reason}</span>
              <span class="attention-score">{ticket.attention_score}<small>score</small></span>
              <i class="ph-bold ph-arrow-right"></i>
            </button>
          {/each}
        </div>
      {:else}<div class="empty-panel">The queue is clear—no tickets currently need immediate attention.</div>{/if}
    </section>
  {/if}
</div>

<style>
  .analytics-view { padding: 28px; display: flex; flex-direction: column; gap: 22px; height: 100%; overflow-y: auto; background: #f6f7fb; }
  .analytics-view > * { flex-shrink: 0; }
  .view-header { display: flex; justify-content: space-between; align-items: flex-end; gap: 20px; }
  .eyebrow, .section-label { color: #6d5bd0; font-size: 0.68rem; font-weight: 800; letter-spacing: 0.1em; }
  .view-header h1 { margin-top: 4px; color: var(--text-main); font-size: 1.65rem; letter-spacing: -0.025em; }
  .view-header p { margin-top: 5px; color: var(--text-muted); font-size: 0.84rem; }
  .header-actions { display: flex; align-items: center; gap: 10px; }
  .data-badge { padding: 8px 11px; border: 1px solid #bbf7d0; border-radius: 9px; color: #047857; background: #ecfdf5; font-size: 0.72rem; font-weight: 700; text-transform: capitalize; }
  .data-badge.data-synthetic { border-color: #ddd6fe; color: #6d28d9; background: #f5f3ff; }
  .refresh-button { padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 9px; color: var(--text-main); background: white; font-size: 0.76rem; font-weight: 700; cursor: pointer; }
  .loading-panel, .error-panel { min-height: 280px; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 8px; border: 1px solid var(--border-color); border-radius: 16px; background: white; color: var(--text-muted); }
  .loading-panel i { color: #6d5bd0; font-size: 1.6rem; }.loading-panel strong { color: var(--text-main); }.loading-panel span { font-size: 0.8rem; }
  .error-panel i { color: #dc2626; font-size: 1.6rem; }.error-panel strong { color: #991b1b; }.error-panel p { font-size: 0.8rem; }.error-panel button { margin-top: 8px; border: 0; border-radius: 8px; padding: 8px 13px; background: #6d5bd0; color: white; cursor: pointer; }
  .kpi-grid { display: grid; grid-template-columns: 1.15fr repeat(4, 1fr); gap: 14px; }
  .kpi-card { min-width: 0; padding: 18px; border: 1px solid #e7e8ee; border-radius: 14px; background: white; box-shadow: 0 3px 12px rgba(28, 31, 43, 0.04); }
  .health-card { background: linear-gradient(145deg, #29203d, #42345f); border-color: #42345f; color: white; }
  .kpi-top { display: flex; align-items: center; justify-content: space-between; color: var(--text-muted); font-size: 0.73rem; font-weight: 700; }.health-card .kpi-top { color: #d8d2e8; }.kpi-top i { font-size: 1.2rem; color: #7665d5; }
  .kpi-value { margin-top: 12px; color: var(--text-main); font-size: 1.85rem; font-weight: 800; letter-spacing: -0.04em; }.health-card .kpi-value { color: white; }.kpi-value small { margin-left: 3px; color: var(--text-muted); font-size: 0.75rem; font-weight: 600; }.health-card .kpi-value small { color: #c9c0dc; }
  .kpi-change, .kpi-caption { margin-top: 9px; color: #059669; font-size: 0.68rem; font-weight: 700; }.kpi-change.negative { color: #dc2626; }.kpi-caption { color: var(--text-muted); font-weight: 600; }
  .status-pill { display: inline-block; margin-top: 5px; padding: 3px 8px; border-radius: 20px; background: #ede9fe; color: #7c3aed; font-size: 0.65rem; font-weight: 800; }.status-pill.healthy { background: #d1fae5; color: #047857; }.status-pill.watch { background: #fef3c7; color: #b45309; }.status-pill.risk { background: #fee2e2; color: #b91c1c; }
  .score-track { height: 4px; margin-top: 11px; overflow: hidden; border-radius: 5px; background: rgba(255,255,255,.15); }.score-track span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #a78bfa, #5eead4); }
  .brief-card { position: relative; overflow: hidden; display: flex; gap: 24px; padding: 28px; border-radius: 18px; color: white; background: radial-gradient(circle at 90% 10%, rgba(129, 108, 214, .55), transparent 36%), linear-gradient(120deg, #251c35, #3a2c55 64%, #263855); box-shadow: 0 14px 35px rgba(42, 31, 67, .18); }
  .brief-orb { flex: 0 0 54px; width: 54px; height: 54px; display: grid; place-items: center; border: 1px solid rgba(255,255,255,.2); border-radius: 16px; background: rgba(255,255,255,.1); color: #d8b4fe; font-size: 1.45rem; }
  .brief-content { max-width: 950px; }.brief-content .section-label { color: #c4b5fd; }.brief-content h2 { margin-top: 6px; font-size: 1.35rem; }.brief-content > p { margin-top: 8px; color: #ded8e9; font-size: 0.88rem; line-height: 1.6; }
  .recommendations { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 17px; }.recommendations div { display: flex; gap: 8px; padding: 10px; border: 1px solid rgba(255,255,255,.12); border-radius: 9px; background: rgba(255,255,255,.06); color: #f4f1f8; font-size: 0.74rem; line-height: 1.4; }.recommendations i { flex-shrink: 0; color: #a7f3d0; font-size: 1rem; }.brief-content small { display: block; margin-top: 13px; color: #aaa2b8; font-size: 0.65rem; }
  .main-grid { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(300px, .85fr); gap: 16px; }
  .panel { padding: 22px; border: 1px solid #e7e8ee; border-radius: 15px; background: white; box-shadow: 0 3px 12px rgba(28,31,43,.04); }
  .panel-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }.panel-header h2 { margin-top: 3px; color: var(--text-main); font-size: 1.04rem; }.panel-header p { margin-top: 4px; color: var(--text-muted); font-size: 0.72rem; }
  .legend { display: flex; gap: 14px; color: var(--text-muted); font-size: 0.68rem; font-weight: 700; }.legend span { display: flex; align-items: center; gap: 5px; }.legend i { width: 7px; height: 7px; border-radius: 50%; }.created-dot { background: #6d5bd0; }.resolved-dot { background: #18a999; }
  .chart-wrap { margin-top: 13px; }.chart-wrap svg { display: block; width: 100%; height: 225px; overflow: visible; }.grid-line { stroke: #ececf2; stroke-width: 1; }.chart-line { fill: none; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }.created-line { stroke: #6d5bd0; }.resolved-line { stroke: #18a999; }.created-point { fill: white; stroke: #6d5bd0; stroke-width: 2; }.resolved-point { fill: white; stroke: #18a999; stroke-width: 2; }.chart-wrap text { fill: #8b8d9a; font-size: 9px; }
  .issues-panel > .panel-header > i { color: #6d5bd0; font-size: 1.5rem; }.issue-list { display: flex; flex-direction: column; margin-top: 14px; }.issue-row { display: flex; align-items: center; gap: 10px; padding: 12px 0; border-top: 1px solid #f0f0f4; }.issue-rank { width: 24px; height: 24px; display: grid; place-items: center; border-radius: 7px; color: #6d5bd0; background: #f0edff; font-size: 0.68rem; font-weight: 800; }.issue-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; }.issue-copy strong { overflow: hidden; color: var(--text-main); font-size: 0.78rem; text-overflow: ellipsis; white-space: nowrap; }.issue-copy span { margin-top: 2px; color: var(--text-muted); font-size: 0.65rem; }.signal-pill { padding: 4px 7px; border-radius: 7px; color: #b45309; background: #fffbeb; font-size: 0.65rem; font-weight: 800; }.signal-pill.rising { color: #b91c1c; background: #fef2f2; }
  .attention-icon { color: #dc5a5a; font-size: 1.7rem; }.attention-list { display: flex; flex-direction: column; margin-top: 13px; }.attention-row { width: 100%; display: grid; grid-template-columns: 30px minmax(220px, 1.3fr) 76px minmax(210px, 1fr) 55px 18px; align-items: center; gap: 12px; padding: 12px 8px; border: 0; border-top: 1px solid #eeeef3; color: inherit; background: transparent; text-align: left; cursor: pointer; }.attention-row:hover { border-radius: 9px; background: #faf9ff; }.attention-rank { color: #9a9ca8; font-size: 0.75rem; font-weight: 800; }.ticket-main { min-width: 0; display: flex; flex-direction: column; }.ticket-main strong { overflow: hidden; color: var(--text-main); font-size: 0.78rem; text-overflow: ellipsis; white-space: nowrap; }.ticket-main small { margin-top: 3px; color: var(--text-muted); font-size: 0.65rem; }.priority { justify-self: start; padding: 4px 8px; border-radius: 7px; color: #475569; background: #f1f5f9; font-size: 0.64rem; font-weight: 800; text-transform: uppercase; }.priority.high { color: #b45309; background: #fffbeb; }.priority.critical { color: #b91c1c; background: #fee2e2; }.attention-reason { color: #666978; font-size: 0.68rem; line-height: 1.35; }.attention-score { color: #6d5bd0; font-size: 1rem; font-weight: 800; text-align: center; }.attention-score small { display: block; color: #9a9ca8; font-size: 0.55rem; font-weight: 600; }.attention-row > i { color: #aaa5bb; }
  .empty-panel { padding: 34px 10px; color: var(--text-muted); font-size: 0.78rem; text-align: center; }
  .ai-usage-panel { display: flex; flex-direction: column; gap: 18px; }
  .ai-usage-header { align-items: center; }
  .azure-source-badge { display: inline-flex; align-items: center; gap: 6px; padding: 7px 10px; border: 1px solid #bae6fd; border-radius: 20px; color: #0369a1; background: #f0f9ff; font-size: .68rem; font-weight: 800; }
  .ai-usage-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
  .ai-usage-grid > div { padding: 14px; border: 1px solid #ececf2; border-radius: 11px; background: #fafaff; }
  .ai-usage-grid span { display: block; color: var(--text-muted); font-size: .67rem; font-weight: 700; }
  .ai-usage-grid strong { display: block; margin-top: 7px; color: var(--text-main); font-size: 1.12rem; }
  .ai-usage-error { display: flex; align-items: center; gap: 8px; padding: 13px; border: 1px solid #fed7aa; border-radius: 10px; color: #9a3412; background: #fff7ed; font-size: .76rem; }
  .usage-days { display: flex; flex-direction: column; gap: 8px; }
  .usage-day { display: grid; grid-template-columns: 92px 1fr 110px; align-items: center; gap: 12px; color: var(--text-muted); font-size: .68rem; }
  .usage-day strong { color: var(--text-main); text-align: right; }
  .usage-track { height: 7px; overflow: hidden; border-radius: 7px; background: #eeeaf9; }
  .usage-track i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #6d5bd0, #18a999); }
  @media (max-width: 1100px) { .kpi-grid { grid-template-columns: repeat(3, 1fr); }.ai-usage-grid { grid-template-columns: repeat(3, 1fr); }.main-grid { grid-template-columns: 1fr; }.recommendations { grid-template-columns: 1fr; }.attention-row { grid-template-columns: 28px 1fr 70px 50px 16px; }.attention-reason { display: none; } }
  @media (max-width: 700px) { .analytics-view { padding: 18px; }.view-header { align-items: flex-start; flex-direction: column; }.header-actions { width: 100%; flex-wrap: wrap; }.kpi-grid, .ai-usage-grid { grid-template-columns: repeat(2, 1fr); }.health-card { grid-column: span 2; }.usage-day { grid-template-columns: 78px 1fr; }.usage-day strong { grid-column: 2; }.brief-card { flex-direction: column; }.attention-row { grid-template-columns: 24px 1fr 60px 16px; }.attention-score { display: none; } }
</style>
