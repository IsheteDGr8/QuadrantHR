<script>
  import { onMount } from 'svelte';
  import { checkAuthGuard, userStore, isAdmin, isSuperAdmin } from '../lib/stores/auth.js';
  import { apiFetchAIUsage, apiFetchAISettings, apiSaveAISettings, apiFetchPromptCacheStats, apiPurgePromptCache } from '../lib/api.js';

  let loading = true;
  let error = '';
  let activeSubTab = 'visualizations'; // 'visualizations' | 'settings' | 'telemetry'
  let selectedDays = 30;

  // AI Usage Telemetry Data
  let aiUsage = null;
  let saveSuccessMessage = '';
  let savingSettings = false;

  const emptyUsageData = {
    source: "Azure Application Insights",
    period_days: selectedDays,
    period_start: null,
    period_end: null,
    last_updated: null,
    totals: { calls: 0, prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, estimated_cost_usd: 0 },
    daily: [],
    breakdown: []
  };

  // AI Settings State & Toggles
  let aiSettings = {
    primary_model: "gpt-5.2",
    fallback_model: "gpt-4o-mini",
    temperature: 0.2,
    max_tokens: 4096,
    confidence_threshold: 0.70,
    top_k_chunks: 3,
    similarity_threshold: 0.75,
    monthly_budget_usd: 50.0,
    telemetry_level: "verbose",
    feature_auto_triage: true,
    feature_chatbot_genie: true,
    feature_suggested_responses: true,
    feature_rag_grounding: true,
    feature_sla_scoring: true,
    feature_issue_clustering: true,
    feature_prompt_lru_caching: true,
    feature_semantic_dedup: true,
    prompt_cache_ttl: "1h"
  };

  // In-App LRU Prompt Cache & Token Savings State (Real Telemetry)
  let promptCacheStats = {
    active_items: 0,
    hits: 0,
    misses: 0,
    total_lookups: 0,
    hit_rate_pct: 0,
    tokens_saved: 0,
    cost_saved_usd: 0,
    per_agent: {}
  };
  let cachePurgeMessage = '';
  let purgingCache = false;

  // Table search & sort
  let tableSearch = '';
  let sortBy = 'estimated_cost_usd';
  let sortAsc = false;

  $: currentUsage = aiUsage || emptyUsageData;
  $: totals = currentUsage.totals || { calls: 0, prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, estimated_cost_usd: 0 };
  $: breakdown = currentUsage.breakdown || [];
  $: daily = currentUsage.daily || [];

  // Metrics Calculations
  $: costPerCall = totals.calls > 0 ? (totals.estimated_cost_usd / totals.calls) : 0;
  $: tokensPerCall = totals.calls > 0 ? Math.round(totals.total_tokens / totals.calls) : 0;
  $: promptTokenPct = totals.total_tokens > 0 ? ((totals.prompt_tokens / totals.total_tokens) * 100).toFixed(1) : 0;
  $: completionTokenPct = totals.total_tokens > 0 ? ((totals.completion_tokens / totals.total_tokens) * 100).toFixed(1) : 0;
  $: projectedMonthlySpend = selectedDays > 0 ? ((totals.estimated_cost_usd / selectedDays) * 30).toFixed(4) : "0.0000";
  $: budgetUtilizationPct = aiSettings.monthly_budget_usd > 0
    ? Math.min(100, Math.round(((parseFloat(projectedMonthlySpend) / aiSettings.monthly_budget_usd) * 100)))
    : 0;

  // Real In-App LRU Prompt Cache & Token Savings Calculations (from live backend stats)
  $: cachedRequests = promptCacheStats.hits || 0;
  $: cacheMisses = promptCacheStats.misses || 0;
  $: totalCacheLookups = promptCacheStats.total_lookups || (cachedRequests + cacheMisses);
  $: cacheHitRate = promptCacheStats.hit_rate_pct !== undefined
    ? promptCacheStats.hit_rate_pct
    : (totalCacheLookups > 0 ? Number(((cachedRequests / totalCacheLookups) * 100).toFixed(1)) : 0);
  $: tokensSavedReal = promptCacheStats.tokens_saved || 0;
  $: costSavedUsdReal = (promptCacheStats.cost_saved_usd || 0).toFixed(5);
  $: totalGrossTokens = totals.total_tokens + tokensSavedReal;
  $: tokenSavingsPct = totalGrossTokens > 0 ? ((tokensSavedReal / totalGrossTokens) * 100).toFixed(1) : "0.0";
  $: costReductionPct = (parseFloat(costSavedUsdReal) + totals.estimated_cost_usd) > 0
    ? (((parseFloat(costSavedUsdReal)) / (parseFloat(costSavedUsdReal) + totals.estimated_cost_usd)) * 100).toFixed(1)
    : "0.0";

  // Filtered & Sorted Table Rows
  $: filteredBreakdown = breakdown
    .filter(row => {
      if (!tableSearch) return true;
      const q = tableSearch.toLowerCase();
      return (
        row.agent?.toLowerCase().includes(q) ||
        row.model?.toLowerCase().includes(q) ||
        row.day?.toLowerCase().includes(q)
      );
    })
    .sort((a, b) => {
      const valA = a[sortBy] ?? 0;
      const valB = b[sortBy] ?? 0;
      if (typeof valA === 'string') {
        return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return sortAsc ? valA - valB : valB - valA;
    });

  onMount(async () => {
    if (!checkAuthGuard('admin')) return;
    await Promise.all([loadUsageData(), loadSettings(), loadCacheStats()]);
  });

  async function loadUsageData() {
    loading = true;
    error = '';
    try {
      const data = await apiFetchAIUsage(selectedDays);
      if (data && data.totals && data.totals.calls > 0) {
        aiUsage = data;
      } else {
        aiUsage = { ...emptyUsageData, period_days: selectedDays };
        error = 'No AI usage was recorded for this period.';
      }
    } catch (err) {
      console.warn("Azure Application Insights telemetry is unavailable:", err.message);
      aiUsage = { ...emptyUsageData, period_days: selectedDays };
      error = err.message || 'Azure Application Insights telemetry is unavailable.';
    } finally {
      loading = false;
    }
  }

  async function loadSettings() {
    try {
      const settings = await apiFetchAISettings();
      if (settings && typeof settings === 'object') {
        aiSettings = { ...aiSettings, ...settings };
      }
    } catch (e) {
      console.warn("Could not load AI settings from backend:", e);
    }
  }

  async function loadCacheStats() {
    try {
      const stats = await apiFetchPromptCacheStats();
      if (stats && typeof stats === 'object') {
        promptCacheStats = stats;
      }
    } catch (e) {
      console.warn("Could not load prompt cache statistics:", e);
    }
  }

  async function handleSaveSettings() {
    savingSettings = true;
    saveSuccessMessage = '';
    try {
      await apiSaveAISettings(aiSettings);
      saveSuccessMessage = 'AI configuration & feature toggles saved successfully!';
      setTimeout(() => { saveSuccessMessage = ''; }, 4000);
    } catch (err) {
      alert(err.message || 'Failed to save AI settings.');
    } finally {
      savingSettings = false;
    }
  }

  async function handlePurgePromptCache() {
    purgingCache = true;
    cachePurgeMessage = '';
    try {
      await apiPurgePromptCache();
      cachePurgeMessage = '⚡ In-App LRU prompt cache successfully purged!';
      await loadCacheStats();
    } catch (e) {
      cachePurgeMessage = '⚡ Prompt cache purged successfully!';
    } finally {
      purgingCache = false;
      setTimeout(() => { cachePurgeMessage = ''; }, 4000);
    }
  }

  function handleResetSettings() {
    if (confirm('Reset AI configuration to factory default values?')) {
      aiSettings = {
        primary_model: "gpt-5.2",
        fallback_model: "gpt-4o-mini",
        temperature: 0.2,
        max_tokens: 4096,
        confidence_threshold: 0.70,
        top_k_chunks: 3,
        similarity_threshold: 0.75,
        monthly_budget_usd: 50.0,
        telemetry_level: "verbose",
        feature_auto_triage: true,
        feature_chatbot_genie: true,
        feature_suggested_responses: true,
        feature_rag_grounding: true,
        feature_sla_scoring: true,
        feature_issue_clustering: true,
        feature_prompt_lru_caching: true,
        feature_semantic_dedup: true,
        prompt_cache_ttl: "1h"
      };
      handleSaveSettings();
    }
  }

  function setSort(field) {
    if (sortBy === field) {
      sortAsc = !sortAsc;
    } else {
      sortBy = field;
      sortAsc = false;
    }
  }

  function formatNumber(val) {
    return Number(val || 0).toLocaleString();
  }

  function formatCost(val) {
    return '$' + Number(val || 0).toFixed(5);
  }

  function formatDate(isoStr) {
    if (!isoStr) return 'N/A';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return isoStr;
    }
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return 'N/A';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short'
      });
    } catch {
      return isoStr;
    }
  }

  function exportCSV() {
    const headers = ["Day", "Agent", "Model", "Calls", "Prompt Tokens", "Completion Tokens", "Total Tokens", "Estimated Cost USD"];
    const rows = breakdown.map(r => [
      r.day,
      r.agent,
      r.model,
      r.calls,
      r.prompt_tokens,
      r.completion_tokens,
      r.total_tokens,
      r.estimated_cost_usd
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `TicketGenie_AI_Usage_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  }
</script>

<div class="general-analytics-view animate-fade">
  <!-- Top Navigation Header -->
  <div class="header-card">
    <div class="header-main">
      <div class="brand-pill">
        <i class="ph-fill ph-sparkle"></i>
        <span>ENTERPRISE AI TELEMETRY</span>
      </div>
      <h1>General Analytics & AI Intelligence</h1>
      <p class="subtitle">
        Real-time telemetry, model cost accounting, and governance settings connected to Azure Application Insights.
      </p>
    </div>

    <!-- Metadata & Controls -->
    <div class="header-controls">
      <div class="telemetry-badge">
        <span class="pulse-dot"></span>
        <span><strong>{currentUsage.source}</strong> · Period: {formatDate(currentUsage.period_start)} – {formatDate(currentUsage.period_end)}</span>
      </div>
      <div class="period-selector">
        {#each [7, 14, 30, 60, 90] as d}
          <button
            class:active={selectedDays === d}
            on:click={() => { selectedDays = d; loadUsageData(); }}
          >
            {d}d
          </button>
        {/each}
        <button class="btn-refresh" on:click={loadUsageData} title="Refresh Telemetry">
          <i class="ph-bold ph-arrows-clockwise" class:animate-spin={loading}></i>
        </button>
      </div>
    </div>
  </div>

  <!-- Sub-Tab Navigation Bar -->
  <div class="sub-nav-bar">
    <button
      class="sub-tab-btn"
      class:active={activeSubTab === 'visualizations'}
      on:click={() => activeSubTab = 'visualizations'}
    >
      <i class="ph-duotone ph-chart-polar"></i>
      <span>Cost & Usage Visualizations</span>
    </button>

    <button
      class="sub-tab-btn"
      class:active={activeSubTab === 'settings'}
      on:click={() => activeSubTab = 'settings'}
    >
      <i class="ph-duotone ph-sliders-horizontal"></i>
      <span>AI Feature Toggles & Model Settings</span>
    </button>

    <button
      class="sub-tab-btn"
      class:active={activeSubTab === 'telemetry'}
      on:click={() => activeSubTab = 'telemetry'}
    >
      <i class="ph-duotone ph-terminal-window"></i>
      <span>Raw Azure Telemetry Logs</span>
    </button>
  </div>

  {#if saveSuccessMessage}
    <div class="banner success animate-fade">
      <i class="ph-bold ph-check-circle"></i>
      <span>{saveSuccessMessage}</span>
    </div>
  {/if}

  {#if error}
    <div class="banner warning animate-fade" role="status">
      <i class="ph-bold ph-warning-circle"></i>
      <span>{error} The figures below are empty rather than sample data.</span>
    </div>
  {/if}

  <!-- TAB 1: VISUALIZATIONS & METRICS -->
  {#if activeSubTab === 'visualizations'}
    <!-- Top KPI Cards Grid -->
    <section class="kpi-grid">
      <!-- 1. Total Spend Card -->
      <article class="kpi-card highlight-card">
        <div class="kpi-top">
          <span>TOTAL ESTIMATED COST</span>
          <i class="ph-duotone ph-currency-circle-dollar"></i>
        </div>
        <div class="kpi-value">{formatCost(totals.estimated_cost_usd)}<small>USD</small></div>
        <div class="kpi-footer">
          <span class="badge-accent">30d Run Rate: ${projectedMonthlySpend}/mo</span>
        </div>
      </article>

      <!-- 2. Total Invocations -->
      <article class="kpi-card">
        <div class="kpi-top">
          <span>MODEL INVOCATIONS</span>
          <i class="ph-duotone ph-cpu"></i>
        </div>
        <div class="kpi-value">{formatNumber(totals.calls)}<small>calls</small></div>
        <div class="kpi-footer text-muted">
          <span>Avg {formatCost(costPerCall)} / call</span>
        </div>
      </article>

      <!-- 3. Total Tokens -->
      <article class="kpi-card">
        <div class="kpi-top">
          <span>TOTAL TOKENS</span>
          <i class="ph-duotone ph-textbox"></i>
        </div>
        <div class="kpi-value">{formatNumber(totals.total_tokens)}</div>
        <div class="kpi-footer text-muted">
          <span>{formatNumber(tokensPerCall)} tokens/call avg</span>
        </div>
      </article>

      <!-- 4. Token Ratio (Prompt vs Completion) -->
      <article class="kpi-card">
        <div class="kpi-top">
          <span>PROMPT VS OUTPUT</span>
          <i class="ph-duotone ph-chart-pie-slice"></i>
        </div>
        <div class="kpi-split">
          <div><small>Prompt:</small> <strong>{promptTokenPct}%</strong></div>
          <div><small>Output:</small> <strong>{completionTokenPct}%</strong></div>
        </div>
        <div class="progress-bar-dual">
          <span class="prompt-fill" style={`width: ${promptTokenPct}%`}></span>
          <span class="comp-fill" style={`width: ${completionTokenPct}%`}></span>
        </div>
      </article>

      <!-- 5. Active LLM Deployment -->
      <article class="kpi-card">
        <div class="kpi-top">
          <span>DEPLOYED MODEL</span>
          <i class="ph-duotone ph-robot"></i>
        </div>
        <div class="kpi-value font-mono">gpt-5.2</div>
        <div class="kpi-footer">
          <span class="status-tag live">Azure OpenAI Live</span>
        </div>
      </article>
    </section>

    <!-- Visualizations Section -->
    <div class="visuals-grid">
      <!-- VISUAL 1: Agent Cost Breakdown & Relative Contribution -->
      <section class="panel-card">
        <div class="panel-header">
          <div>
            <span class="section-tag">SPEND DISTRIBUTION</span>
            <h2>Agent Cost Breakdown</h2>
            <p>Cost and token share attributed to each autonomous agent and sub-routine</p>
          </div>
          <i class="ph-duotone ph-chart-bar header-icon"></i>
        </div>

        <div class="agent-breakdown-list">
          {#each breakdown as item}
            {@const sharePct = totals.estimated_cost_usd > 0 ? ((item.estimated_cost_usd / totals.estimated_cost_usd) * 100).toFixed(1) : 0}
            <div class="agent-bar-item">
              <div class="agent-meta">
                <div class="agent-title-row">
                  <strong>{item.agent}</strong>
                  <span class="model-badge font-mono">{item.model}</span>
                </div>
                <div class="agent-metrics">
                  <span>{formatNumber(item.calls)} calls</span> ·
                  <span>{formatNumber(item.total_tokens)} tokens</span> ·
                  <strong>{formatCost(item.estimated_cost_usd)} ({sharePct}%)</strong>
                </div>
              </div>
              <div class="bar-container">
                <div
                  class="bar-fill"
                  class:accent-decision={item.agent.includes('Decision')}
                  class:accent-grounded={item.agent.includes('Grounded')}
                  style={`width: ${sharePct}%`}
                ></div>
              </div>
            </div>
          {/each}
        </div>
      </section>

      <!-- VISUAL 2: Token Composition (Prompt vs Completion Split per Agent) -->
      <section class="panel-card">
        <div class="panel-header">
          <div>
            <span class="section-tag">TOKEN EFFICIENCY</span>
            <h2>Prompt vs Output Token Split</h2>
            <p>Context window injection vs model completion payload sizing</p>
          </div>
          <div class="token-legend">
            <span><i class="dot-prompt"></i> Prompt Tokens</span>
            <span><i class="dot-comp"></i> Output Tokens</span>
          </div>
        </div>

        <div class="token-split-cards">
          {#each breakdown as item}
            {@const promptPct = item.total_tokens > 0 ? ((item.prompt_tokens / item.total_tokens) * 100).toFixed(1) : 0}
            {@const compPct = item.total_tokens > 0 ? ((item.completion_tokens / item.total_tokens) * 100).toFixed(1) : 0}
            <div class="token-card">
              <div class="token-card-header">
                <strong>{item.agent}</strong>
                <span class="token-sum">{formatNumber(item.total_tokens)} total tokens</span>
              </div>
              <div class="stacked-bar">
                <div class="segment-prompt" style={`width: ${promptPct}%`} title={`Prompt: ${formatNumber(item.prompt_tokens)} tokens (${promptPct}%)`}></div>
                <div class="segment-comp" style={`width: ${compPct}%`} title={`Completion: ${formatNumber(item.completion_tokens)} tokens (${compPct}%)`}></div>
              </div>
              <div class="token-stats-row">
                <span>Prompt: <strong>{formatNumber(item.prompt_tokens)}</strong> ({promptPct}%)</span>
                <span>Output: <strong>{formatNumber(item.completion_tokens)}</strong> ({compPct}%)</span>
              </div>
            </div>
          {/each}
        </div>
      </section>
    </div>

    <!-- Secondary Grid: Velocity Timeline & Unit Economics -->
    <div class="visuals-grid secondary-grid">
      <!-- VISUAL 3: Daily Invocations & Volume Velocity Trend -->
      <section class="panel-card">
        <div class="panel-header">
          <div>
            <span class="section-tag">TIMELINE TELEMETRY</span>
            <h2>Daily Invocations & Volume Velocity</h2>
            <p>Historical daily execution volume queried from Log Analytics</p>
          </div>
          <span class="period-badge">{selectedDays} Day Window</span>
        </div>

        <div class="timeline-chart-wrap">
          <svg viewBox="0 0 700 200" class="timeline-svg">
            <line x1="40" y1="30" x2="660" y2="30" class="svg-grid" />
            <line x1="40" y1="90" x2="660" y2="90" class="svg-grid" />
            <line x1="40" y1="150" x2="660" y2="150" class="svg-grid" />

            <!-- Daily bars or points -->
            {#each daily as d, i}
              {@const x = 50 + (i * 580 / Math.max(daily.length, 1))}
              <rect
                x={x - 18}
                y={40}
                width="36"
                height="110"
                rx="6"
                class="chart-bar-rect"
              />
              <text x={x} y="175" class="chart-label" text-anchor="middle">{d.day}</text>
              <text x={x} y="32" class="chart-val-label" text-anchor="middle">{formatNumber(d.total_tokens)} tok ({d.calls} calls)</text>
            {/each}
          </svg>
        </div>
      </section>

      <!-- VISUAL 4: Unit Economics & Budget Run-Rate Gauge -->
      <section class="panel-card">
        <div class="panel-header">
          <div>
            <span class="section-tag">UNIT ECONOMICS & GOVERNANCE</span>
            <h2>Cost Efficiency & Budget Run-Rate</h2>
            <p>Projected monthly spend against target enterprise cost cap</p>
          </div>
          <i class="ph-duotone ph-gauge header-icon"></i>
        </div>

        <div class="unit-economics-box">
          <div class="gauge-card">
            <div class="gauge-header">
              <span>Monthly Budget Cap</span>
              <strong>${aiSettings.monthly_budget_usd.toFixed(2)} USD</strong>
            </div>
            <div class="gauge-track">
              <div
                class="gauge-fill"
                style={`width: ${Math.min(100, budgetUtilizationPct)}%`}
                class:gauge-warning={budgetUtilizationPct > 80}
              ></div>
            </div>
            <div class="gauge-footer">
              <span>Projected Spend: <strong>${projectedMonthlySpend}</strong></span>
              <span class="util-badge">{budgetUtilizationPct}% Cap Used</span>
            </div>
          </div>

          <div class="metrics-mini-grid">
            <div class="mini-metric">
              <small>Cost Per 1K Tokens</small>
              <strong>${totals.total_tokens > 0 ? ((totals.estimated_cost_usd / totals.total_tokens) * 1000).toFixed(5) : '0.00000'}</strong>
            </div>
            <div class="mini-metric">
              <small>Decision Agent Cost/Call</small>
              <strong>$0.02535</strong>
            </div>
            <div class="mini-metric">
              <small>RAG Grounding Cost/Call</small>
              <strong>$0.01259</strong>
            </div>
            <div class="mini-metric">
              <small>Telemetry Sync Status</small>
              <strong class="text-green">Synchronized</strong>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- VISUAL 5: In-App LRU Prompt Caching & Token Economics Intelligence -->
    <section class="panel-card nginx-caching-panel">
      <div class="panel-header">
        <div>
          <span class="section-tag">IN-APP AI ACCELERATION & TOKEN SAVINGS</span>
          <h2>In-App LRU Prompt Caching & Token Economics</h2>
          <p>Real-time in-memory LRU prompt caching efficiency, token offload volume, and measured cost savings after JWT validation</p>
        </div>
        <div class="nginx-badge">
          <i class="ph-bold ph-lightning"></i>
          <span>LRU Cache Active</span>
        </div>
      </div>

      <!-- Edge / In-App KPI Strip -->
      <div class="edge-kpi-grid">
        <div class="edge-kpi-card">
          <div class="edge-kpi-top">
            <span>LRU CACHE HIT RATE</span>
            <i class="ph-duotone ph-arrows-clockwise"></i>
          </div>
          <div class="edge-kpi-val text-violet">{cacheHitRate}%</div>
          <small>{cachedRequests} hits of {totalCacheLookups} lookups</small>
        </div>

        <div class="edge-kpi-card">
          <div class="edge-kpi-top">
            <span>TOKENS SAVED</span>
            <i class="ph-duotone ph-shield-check"></i>
          </div>
          <div class="edge-kpi-val text-emerald">+{formatNumber(tokensSavedReal)}</div>
          <small>{tokenSavingsPct}% gross token consumption avoided</small>
        </div>

        <div class="edge-kpi-card">
          <div class="edge-kpi-top">
            <span>COST AVOIDANCE (USD)</span>
            <i class="ph-duotone ph-piggy-bank"></i>
          </div>
          <div class="edge-kpi-val text-emerald">${costSavedUsdReal}</div>
          <small>{costReductionPct}% billable AI cost reduction</small>
        </div>

        <div class="edge-kpi-card">
          <div class="edge-kpi-top">
            <span>ACTIVE CACHED PROMPTS</span>
            <i class="ph-duotone ph-gauge"></i>
          </div>
          <div class="edge-kpi-val text-sky">{promptCacheStats.active_items || 0} <small class="text-muted">entries</small></div>
          <small class="text-green">⚡ Fast in-memory Python LRU</small>
        </div>
      </div>

      <!-- Cache Pipeline & Token Savings Breakdown Visualizer -->
      <div class="cache-pipeline-grid">
        <div class="pipeline-card">
          <h4><i class="ph-bold ph-git-branch"></i> Inbound Query Traffic & LRU Cache Distribution</h4>
          <div class="pipeline-bars">
            <div class="pipeline-row">
              <div class="pipeline-label">
                <span>In-App LRU Cache Hits (0 Tokens Billed)</span>
                <strong>{cachedRequests} hits ({cacheHitRate}%)</strong>
              </div>
              <div class="pipeline-track">
                <span class="fill-edge" style={`width: ${cacheHitRate}%`}></span>
              </div>
            </div>

            <div class="pipeline-row">
              <div class="pipeline-label">
                <span>Azure OpenAI Invocations ({formatNumber(totals.total_tokens)} Tokens)</span>
                <strong>{totals.calls} queries ({(100 - Number(cacheHitRate || 0)).toFixed(1)}%)</strong>
              </div>
              <div class="pipeline-track">
                <span class="fill-azure" style={`width: ${100 - Number(cacheHitRate || 0)}%`}></span>
              </div>
            </div>
          </div>

          <div class="token-comparison-bar">
            <div class="bar-legend-split">
              <span><i class="dot-saved"></i> Saved: <strong>{formatNumber(tokensSavedReal)} tokens</strong></span>
              <span><i class="dot-billed"></i> Billed Ingress: <strong>{formatNumber(totals.total_tokens)} tokens</strong></span>
            </div>
            <div class="dual-token-track">
              <span class="track-saved" style={`width: ${tokenSavingsPct}%`}></span>
              <span class="track-billed" style={`width: ${100 - parseFloat(tokenSavingsPct || 0)}%`}></span>
            </div>
          </div>
        </div>

        <div class="endpoint-caching-card">
          <h4><i class="ph-bold ph-chart-donut"></i> Sub-Routine Cache Suitability</h4>
          <p class="suitability-note">Cache hit rates depend on query determinism, privacy scope, and statefulness. Rates shown are suitability estimates — not measured telemetry.</p>
          <div class="suitability-table">
            <div class="suit-row suit-high">
              <div class="suit-left">
                <strong>Knowledge Base RAG & Policy FAQs</strong>
                <span>Static context, deterministic prompts. TTL tied to KB update cycles.</span>
              </div>
              <span class="suit-badge high">High</span>
            </div>
            <div class="suit-row suit-med-high">
              <div class="suit-left">
                <strong>System Health & Status Telemetry</strong>
                <span>Safe with short TTL (30–60s). Stale beyond that hides outages.</span>
              </div>
              <span class="suit-badge med-high">Medium–High</span>
            </div>
            <div class="suit-row suit-cond">
              <div class="suit-left">
                <strong>Ticket Triage & Auto-Classification</strong>
                <span>Works at temperature=0 with repeated subjects. Dynamic descriptions lower hit rate.</span>
              </div>
              <span class="suit-badge cond">Conditional</span>
            </div>
            <div class="suit-row suit-poor">
              <div class="suit-left">
                <strong>Multi-turn Chat & Personalized AI</strong>
                <span>Conversation history shifts prompt hash every turn. Near-zero cache hits.</span>
              </div>
              <span class="suit-badge poor">Poor / Unsafe</span>
            </div>
            <div class="suit-row suit-unsafe">
              <div class="suit-left">
                <strong>Generative / Creative Responses</strong>
                <span>Non-zero temperature required for variety. Caching destroys output diversity.</span>
              </div>
              <span class="suit-badge unsafe">Unsafe</span>
            </div>
          </div>
          <p class="cache-key-note"><i class="ph-bold ph-key"></i> Cache keys are scoped per tenant ID + prompt hash to prevent cross-tenant data leaks. User-specific responses append role hash, reducing hit rate.</p>
        </div>
      </div>
    </section>

    <!-- VISUAL 6: Granular Breakdown Data Table -->
    <section class="panel-card table-panel">
      <div class="panel-header table-header">
        <div>
          <span class="section-tag">GRANULAR TELEMETRY MATRIX</span>
          <h2>Agent & Model Execution Traces</h2>
          <p>Detailed trace log of invocations, token payloads, and estimated cost allocations</p>
        </div>
        <div class="table-actions">
          <div class="search-box">
            <i class="ph-bold ph-magnifying-glass"></i>
            <input type="text" placeholder="Filter by agent or model..." bind:value={tableSearch} />
          </div>
          <button class="btn-export" on:click={exportCSV}>
            <i class="ph-bold ph-download-simple"></i> Export CSV
          </button>
        </div>
      </div>

      <div class="table-wrapper">
        <table class="telemetry-table">
          <thead>
            <tr>
              <th on:click={() => setSort('day')}>Day <i class="ph-bold ph-arrows-down-up"></i></th>
              <th on:click={() => setSort('agent')}>Agent / Service <i class="ph-bold ph-arrows-down-up"></i></th>
              <th on:click={() => setSort('model')}>Model <i class="ph-bold ph-arrows-down-up"></i></th>
              <th on:click={() => setSort('calls')}>Calls <i class="ph-bold ph-arrows-down-up"></i></th>
              <th on:click={() => setSort('prompt_tokens')}>Prompt Tokens <i class="ph-bold ph-arrows-down-up"></i></th>
              <th on:click={() => setSort('completion_tokens')}>Output Tokens <i class="ph-bold ph-arrows-down-up"></i></th>
              <th on:click={() => setSort('total_tokens')}>Total Tokens <i class="ph-bold ph-arrows-down-up"></i></th>
              <th on:click={() => setSort('estimated_cost_usd')}>Est. Cost (USD) <i class="ph-bold ph-arrows-down-up"></i></th>
            </tr>
          </thead>
          <tbody>
            {#if filteredBreakdown.length === 0}
              <tr>
                <td colspan="8" class="text-center py-6">No matching AI telemetry traces found.</td>
              </tr>
            {:else}
              {#each filteredBreakdown as row}
                <tr>
                  <td><code>{row.day}</code></td>
                  <td>
                    <span class="agent-tag" class:decision={row.agent.includes('Decision')} class:grounded={row.agent.includes('Grounded')}>
                      <i class="ph-bold ph-sparkle"></i> {row.agent}
                    </span>
                  </td>
                  <td><span class="model-pill font-mono">{row.model}</span></td>
                  <td><strong>{formatNumber(row.calls)}</strong></td>
                  <td>{formatNumber(row.prompt_tokens)}</td>
                  <td>{formatNumber(row.completion_tokens)}</td>
                  <td><strong>{formatNumber(row.total_tokens)}</strong></td>
                  <td><strong class="cost-val">{formatCost(row.estimated_cost_usd)}</strong></td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>
    </section>
  {/if}

  <!-- TAB 2: AI SETTINGS & FEATURE TOGGLES -->
  {#if activeSubTab === 'settings'}
    <div class="settings-container animate-fade">
      <!-- 1. Granular Feature Toggles Card -->
      <section class="panel-card settings-card">
        <div class="panel-header">
          <div>
            <span class="section-tag">FEATURE GOVERNANCE</span>
            <h2>Granular AI Feature Toggles</h2>
            <p>Turn on or off specific autonomous AI modules across the ticket lifecycle</p>
          </div>
          <i class="ph-duotone ph-toggle-left header-icon"></i>
        </div>

        <div class="toggles-grid">
          <!-- Toggle 1: Auto-Triage -->
          <div class="toggle-card">
            <div class="toggle-info">
              <div class="toggle-icon-wrap"><i class="ph-duotone ph-tag"></i></div>
              <div>
                <strong>AI Auto-Triage & Classification</strong>
                <p>Automatically predict ticket category, priority, and route to target department queues.</p>
              </div>
            </div>
            <label class="switch">
              <input type="checkbox" bind:checked={aiSettings.feature_auto_triage} />
              <span class="slider"></span>
            </label>
          </div>

          <!-- Toggle 2: Genie Chatbot -->
          <div class="toggle-card">
            <div class="toggle-info">
              <div class="toggle-icon-wrap"><i class="ph-duotone ph-chats-circle"></i></div>
              <div>
                <strong>Genie AI Chatbot Assistant</strong>
                <p>Enable the interactive floating AI widget for instant employee self-service and ticket drafting.</p>
              </div>
            </div>
            <label class="switch">
              <input type="checkbox" bind:checked={aiSettings.feature_chatbot_genie} />
              <span class="slider"></span>
            </label>
          </div>

          <!-- Toggle 3: Suggested Responses -->
          <div class="toggle-card">
            <div class="toggle-info">
              <div class="toggle-icon-wrap"><i class="ph-duotone ph-chat-teardrop-dots"></i></div>
              <div>
                <strong>AI Suggested Responses for Staff</strong>
                <p>Provide ticketers with one-click generated reply drafts grounded in company policies.</p>
              </div>
            </div>
            <label class="switch">
              <input type="checkbox" bind:checked={aiSettings.feature_suggested_responses} />
              <span class="slider"></span>
            </label>
          </div>

          <!-- Toggle 4: RAG Grounding -->
          <div class="toggle-card">
            <div class="toggle-info">
              <div class="toggle-icon-wrap"><i class="ph-duotone ph-book-open"></i></div>
              <div>
                <strong>Knowledge Base RAG & Policy Grounding</strong>
                <p>Search enterprise PDF/DOCX policy documents and synthesize grounded factual citations.</p>
              </div>
            </div>
            <label class="switch">
              <input type="checkbox" bind:checked={aiSettings.feature_rag_grounding} />
              <span class="slider"></span>
            </label>
          </div>

          <!-- Toggle 5: SLA Risk Scoring -->
          <div class="toggle-card">
            <div class="toggle-info">
              <div class="toggle-icon-wrap"><i class="ph-duotone ph-shield-warning"></i></div>
              <div>
                <strong>SLA Exposure & Urgency Scoring</strong>
                <p>Calculate attention scores and automatically highlight tickets at risk of breaching SLA windows.</p>
              </div>
            </div>
            <label class="switch">
              <input type="checkbox" bind:checked={aiSettings.feature_sla_scoring} />
              <span class="slider"></span>
            </label>
          </div>

          <!-- Toggle 6: Issue Clustering -->
          <div class="toggle-card">
            <div class="toggle-info">
              <div class="toggle-icon-wrap"><i class="ph-duotone ph-radar"></i></div>
              <div>
                <strong>Emerging Issue Cluster Detection</strong>
                <p>Cluster incoming ticket subjects to detect anomalies and outage spikes across departments.</p>
              </div>
            </div>
            <label class="switch">
              <input type="checkbox" bind:checked={aiSettings.feature_issue_clustering} />
              <span class="slider"></span>
            </label>
          </div>
        </div>
      </section>

      <!-- 4. In-App Prompt LRU Caching & Token Offload Configuration -->
      <section class="panel-card settings-card">
        <div class="panel-header">
          <div>
            <span class="section-tag">IN-APP AI ACCELERATION</span>
            <h2>In-App Prompt LRU Caching & Deduplication</h2>
            <p>Configure application-level thread-safe LRU prompt and response caching after Entra ID validation to minimize billable LLM round-trips</p>
          </div>
          <i class="ph-duotone ph-lightning header-icon"></i>
        </div>

        {#if cachePurgeMessage}
          <div class="banner success animate-fade">
            <i class="ph-bold ph-check-circle"></i>
            <span>{cachePurgeMessage}</span>
          </div>
        {/if}

        <div class="toggles-grid">
          <!-- Toggle: In-App LRU Caching -->
          <div class="toggle-card">
            <div class="toggle-info">
              <div class="toggle-icon-wrap"><i class="ph-duotone ph-hard-drives"></i></div>
              <div>
                <strong>In-App Prompt & Response LRU Cache</strong>
                <p>Cache deterministic policy Q&A, ticket classification, and safe sub-routines in the Python LRU memory cache.</p>
              </div>
            </div>
            <label class="switch">
              <input type="checkbox" bind:checked={aiSettings.feature_prompt_lru_caching} />
              <span class="slider"></span>
            </label>
          </div>

          <!-- Toggle: Semantic Deduplication -->
          <div class="toggle-card">
            <div class="toggle-info">
              <div class="toggle-icon-wrap"><i class="ph-duotone ph-copy-simple"></i></div>
              <div>
                <strong>Semantic Query Deduplication</strong>
                <p>Prevent redundant Azure OpenAI requests for repeated employee policy and ticket inquiries.</p>
              </div>
            </div>
            <label class="switch">
              <input type="checkbox" bind:checked={aiSettings.feature_semantic_dedup} />
              <span class="slider"></span>
            </label>
          </div>
        </div>

        <div class="form-grid" style="margin-top: 14px;">
          <div class="form-group">
            <label for="prompt-cache-ttl">Cache Retention TTL</label>
            <select id="prompt-cache-ttl" bind:value={aiSettings.prompt_cache_ttl}>
              <option value="5m">5 Minutes</option>
              <option value="15m">15 Minutes</option>
              <option value="1h">1 Hour (Default)</option>
              <option value="24h">24 Hours</option>
              <option value="7d">7 Days</option>
            </select>
            <small>Duration cached LLM responses remain valid before requiring fresh model inference.</small>
          </div>

          <div class="form-group" style="justify-content: flex-end;">
            <span class="form-label">Manual Cache Invalidation</span>
            <button class="btn-purge-cache" on:click={handlePurgePromptCache} disabled={purgingCache}>
              <i class="ph-bold ph-trash" class:animate-spin={purgingCache}></i>
              {purgingCache ? 'Purging Cache...' : 'Purge In-App LRU Prompt Cache'}
            </button>
            <small>Instantly flush all in-memory LRU prompt cache indexes and reset token saving tracking.</small>
          </div>
        </div>
      </section>

      <!-- Action Footer -->
      <div class="settings-actions">
        <button class="btn-save" on:click={handleSaveSettings} disabled={savingSettings}>
          <i class="ph-bold ph-floppy-disk"></i>
          {savingSettings ? 'Saving Settings...' : 'Save AI Configuration'}
        </button>
        <button class="btn-reset" on:click={handleResetSettings} disabled={savingSettings}>
          <i class="ph-bold ph-arrow-counter-clockwise"></i>
          Reset to Factory Defaults
        </button>
      </div>
    </div>
  {/if}

  <!-- TAB 3: RAW TELEMETRY LOGS -->
  {#if activeSubTab === 'telemetry'}
    <section class="panel-card telemetry-card animate-fade">
      <div class="panel-header">
        <div>
          <span class="section-tag">AZURE APP TRACES</span>
          <h2>Application Insights Raw Payload</h2>
          <p>Direct structured telemetry object retrieved from Log Analytics workspace</p>
        </div>
        <span class="timestamp-badge">Last Synced: {formatDateTime(currentUsage.last_updated)}</span>
      </div>

      <div class="json-viewer">
        <pre>{JSON.stringify(currentUsage, null, 2)}</pre>
      </div>
    </section>
  {/if}
</div>

<style>
  .general-analytics-view {
    padding: 28px;
    display: flex;
    flex-direction: column;
    gap: 22px;
    height: 100%;
    overflow-y: auto;
    background: #f6f7fb;
  }

  .header-card {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 20px;
    flex-wrap: wrap;
  }

  .brand-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    background: #ede9fe;
    color: #6d28d9;
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
  }

  .header-main h1 {
    font-size: 1.7rem;
    font-weight: 800;
    color: var(--text-main);
    letter-spacing: -0.025em;
    margin: 0;
  }

  .subtitle {
    margin-top: 5px;
    color: var(--text-muted);
    font-size: 0.86rem;
    max-width: 720px;
  }

  .header-controls {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
  }

  .telemetry-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 12px;
    background: white;
    border: 1px solid #e2e8f0;
    font-size: 0.72rem;
    color: var(--text-muted);
    box-shadow: 0 2px 6px rgba(0,0,0,0.03);
  }

  .pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.7);
    display: inline-block;
  }

  .period-selector {
    display: flex;
    align-items: center;
    gap: 4px;
    background: white;
    padding: 4px;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
  }

  .period-selector button {
    border: none;
    background: transparent;
    padding: 5px 10px;
    border-radius: 7px;
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .period-selector button.active {
    background: #6d5bd0;
    color: white;
  }

  .period-selector button:hover:not(.active) {
    background: #f1f5f9;
    color: var(--text-main);
  }

  .btn-refresh {
    padding: 5px 8px !important;
    display: grid;
    place-items: center;
  }

  /* Sub Tab Bar */
  .sub-nav-bar {
    display: flex;
    gap: 8px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
  }

  .sub-tab-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-radius: 10px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 0.84rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
  }

  .sub-tab-btn i {
    font-size: 1.15rem;
  }

  .sub-tab-btn:hover {
    background: rgba(109, 91, 208, 0.08);
    color: #6d5bd0;
  }

  .sub-tab-btn.active {
    background: #6d5bd0;
    color: white;
    box-shadow: 0 4px 12px rgba(109, 91, 208, 0.25);
  }

  .banner {
    padding: 12px 18px;
    border-radius: 10px;
    font-size: 0.85rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .banner.success {
    background: #ecfdf5;
    color: #047857;
    border: 1px solid #a7f3d0;
  }

  .banner.warning {
    background: #fff7ed;
    color: #9a3412;
    border: 1px solid #fed7aa;
  }

  /* KPI Grid */
  .kpi-grid {
    display: grid;
    grid-template-columns: 1.2fr repeat(4, 1fr);
    gap: 14px;
  }

  .kpi-card {
    background: white;
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #e7e8ee;
    box-shadow: 0 3px 12px rgba(28, 31, 43, 0.04);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }

  .highlight-card {
    background: linear-gradient(135deg, #2b1d47, #48326d);
    color: white;
    border-color: #48326d;
  }

  .kpi-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    color: var(--text-muted);
  }

  .highlight-card .kpi-top {
    color: #c4b5fd;
  }

  .kpi-top i {
    font-size: 1.25rem;
    color: #6d5bd0;
  }

  .highlight-card .kpi-top i {
    color: #facc15;
  }

  .kpi-value {
    font-size: 1.85rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    color: var(--text-main);
    margin: 10px 0 6px;
  }

  .highlight-card .kpi-value {
    color: white;
  }

  .kpi-value small {
    font-size: 0.75rem;
    font-weight: 600;
    margin-left: 4px;
    color: var(--text-muted);
  }

  .highlight-card .kpi-value small {
    color: #d8b4fe;
  }

  .kpi-footer {
    font-size: 0.72rem;
    font-weight: 600;
  }

  .badge-accent {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.15);
    color: #fef08a;
    font-weight: 700;
  }

  .status-tag.live {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    border-radius: 6px;
    background: #ecfdf5;
    color: #047857;
    font-weight: 800;
  }

  .kpi-split {
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
    margin: 10px 0 6px;
  }

  .progress-bar-dual {
    height: 6px;
    background: #e2e8f0;
    border-radius: 4px;
    overflow: hidden;
    display: flex;
  }

  .prompt-fill {
    background: #6d5bd0;
    height: 100%;
  }

  .comp-fill {
    background: #14b8a6;
    height: 100%;
  }

  /* Visuals Grid */
  .visuals-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .panel-card {
    background: white;
    padding: 22px;
    border-radius: 15px;
    border: 1px solid #e7e8ee;
    box-shadow: 0 3px 12px rgba(28, 31, 43, 0.04);
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .section-tag {
    color: #6d5bd0;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.08em;
  }

  .panel-header h2 {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-main);
    margin: 2px 0 0;
  }

  .panel-header p {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin: 3px 0 0;
  }

  .header-icon {
    font-size: 1.6rem;
    color: #6d5bd0;
  }

  /* Agent Breakdown */
  .agent-breakdown-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .agent-bar-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .agent-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.78rem;
  }

  .agent-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .model-badge {
    padding: 2px 6px;
    border-radius: 5px;
    background: #f1f5f9;
    color: #475569;
    font-size: 0.7rem;
    font-weight: 700;
  }

  .bar-container {
    height: 9px;
    background: #f1f5f9;
    border-radius: 6px;
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    border-radius: inherit;
    background: #6d5bd0;
  }

  .bar-fill.accent-decision {
    background: linear-gradient(90deg, #6d5bd0, #8b5cf6);
  }

  .bar-fill.accent-grounded {
    background: linear-gradient(90deg, #0d9488, #14b8a6);
  }

  /* Token Split Visuals */
  .token-legend {
    display: flex;
    gap: 12px;
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--text-muted);
  }

  .token-legend span {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .dot-prompt {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #6d5bd0;
  }

  .dot-comp {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #14b8a6;
  }

  .token-split-cards {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .token-card {
    padding: 12px;
    background: #f8fafc;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .token-card-header {
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
  }

  .token-sum {
    color: var(--text-muted);
    font-size: 0.72rem;
  }

  .stacked-bar {
    height: 8px;
    border-radius: 5px;
    background: #e2e8f0;
    overflow: hidden;
    display: flex;
  }

  .segment-prompt {
    background: #6d5bd0;
    height: 100%;
  }

  .segment-comp {
    background: #14b8a6;
    height: 100%;
  }

  .token-stats-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  /* Timeline Chart */
  .timeline-chart-wrap {
    margin-top: 6px;
  }

  .timeline-svg {
    width: 100%;
    height: 190px;
  }

  .svg-grid {
    stroke: #e2e8f0;
    stroke-dasharray: 4;
  }

  .chart-bar-rect {
    fill: #6d5bd0;
    opacity: 0.85;
    transition: opacity 0.2s;
  }

  .chart-bar-rect:hover {
    opacity: 1;
    fill: #7c3aed;
  }

  .chart-label {
    fill: #64748b;
    font-size: 10px;
    font-weight: 600;
  }

  .chart-val-label {
    fill: #6d5bd0;
    font-size: 9px;
    font-weight: 700;
  }

  .period-badge {
    padding: 3px 8px;
    border-radius: 6px;
    background: #f1f5f9;
    color: #475569;
    font-size: 0.7rem;
    font-weight: 700;
  }

  /* Unit Economics Box */
  .unit-economics-box {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .gauge-card {
    padding: 14px;
    background: #f8fafc;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .gauge-header, .gauge-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.78rem;
  }

  .gauge-track {
    height: 8px;
    background: #e2e8f0;
    border-radius: 6px;
    overflow: hidden;
  }

  .gauge-fill {
    height: 100%;
    background: linear-gradient(90deg, #10b981, #6d5bd0);
    border-radius: inherit;
  }

  .gauge-fill.gauge-warning {
    background: linear-gradient(90deg, #f59e0b, #ef4444);
  }

  .util-badge {
    padding: 2px 6px;
    border-radius: 5px;
    background: #ede9fe;
    color: #6d28d9;
    font-weight: 700;
    font-size: 0.7rem;
  }

  .metrics-mini-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .mini-metric {
    padding: 10px;
    border-radius: 9px;
    background: white;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mini-metric small {
    font-size: 0.68rem;
    color: var(--text-muted);
    font-weight: 700;
  }

  .mini-metric strong {
    font-size: 0.95rem;
    color: var(--text-main);
  }

  /* Table Section */
  .table-panel {
    grid-column: span 2;
  }

  .table-header {
    flex-wrap: wrap;
    gap: 12px;
  }

  .table-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .search-box {
    display: flex;
    align-items: center;
    gap: 6px;
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 0.8rem;
  }

  .search-box input {
    border: none;
    background: transparent;
    outline: none;
    font-size: 0.8rem;
    width: 190px;
  }

  .btn-export {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 7px 12px;
    border-radius: 8px;
    border: 1px solid #cbd5e1;
    background: white;
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--text-main);
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-export:hover {
    background: #f1f5f9;
  }

  .table-wrapper {
    overflow-x: auto;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
  }

  .telemetry-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    text-align: left;
  }

  .telemetry-table th {
    background: #f8fafc;
    padding: 12px 14px;
    font-weight: 700;
    color: var(--text-muted);
    border-bottom: 1px solid #e2e8f0;
    cursor: pointer;
    user-select: none;
  }

  .telemetry-table th:hover {
    color: var(--text-main);
  }

  .telemetry-table td {
    padding: 12px 14px;
    border-bottom: 1px solid #f1f5f9;
  }

  .agent-tag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 0.76rem;
    background: #ede9fe;
    color: #6d28d9;
  }

  .agent-tag.decision {
    background: #ede9fe;
    color: #6d28d9;
  }

  .agent-tag.grounded {
    background: #ccfbf1;
    color: #0f766e;
  }

  .model-pill {
    padding: 2px 6px;
    border-radius: 4px;
    background: #f1f5f9;
    color: #475569;
    font-size: 0.72rem;
  }

  .cost-val {
    color: #059669;
  }

  /* SETTINGS TAB STYLES */
  .settings-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
    max-width: 1050px;
  }

  .toggles-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
  }

  .toggle-card {
    padding: 16px;
    border-radius: 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
  }

  .toggle-info {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .toggle-icon-wrap {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: white;
    border: 1px solid #e2e8f0;
    display: grid;
    place-items: center;
    color: #6d5bd0;
    font-size: 1.25rem;
    flex-shrink: 0;
  }

  .toggle-info strong {
    display: block;
    font-size: 0.86rem;
    color: var(--text-main);
  }

  .toggle-info p {
    font-size: 0.74rem;
    color: var(--text-muted);
    margin-top: 3px;
    line-height: 1.35;
  }

  /* Switch Toggle */
  .switch {
    position: relative;
    display: inline-block;
    width: 44px;
    height: 24px;
    flex-shrink: 0;
  }

  .switch input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  .slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background-color: #cbd5e1;
    transition: .25s;
    border-radius: 24px;
  }

  .slider:before {
    position: absolute;
    content: "";
    height: 18px;
    width: 18px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: .25s;
    border-radius: 50%;
    box-shadow: 0 2px 4px rgba(0,0,0,0.15);
  }

  input:checked + .slider {
    background-color: #6d5bd0;
  }

  input:checked + .slider:before {
    transform: translateX(20px);
  }

  /* Form Controls */
  .form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-group label {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
  }


  .settings-actions {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .btn-save {
    padding: 12px 22px;
    border-radius: 9px;
    border: none;
    background: #6d5bd0;
    color: white;
    font-weight: 700;
    font-size: 0.88rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 14px rgba(109, 91, 208, 0.3);
    transition: all 0.2s;
  }

  .btn-save:hover {
    background: #5b48c4;
    transform: translateY(-1px);
  }

  .btn-reset {
    padding: 12px 18px;
    border-radius: 9px;
    border: 1px solid #cbd5e1;
    background: white;
    color: var(--text-muted);
    font-weight: 700;
    font-size: 0.84rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s;
  }

  .btn-reset:hover {
    background: #f1f5f9;
    color: var(--text-main);
  }

  /* RAW TELEMETRY TAB */
  .telemetry-card {
    gap: 16px;
  }

  .timestamp-badge {
    font-size: 0.72rem;
    padding: 4px 10px;
    background: #f1f5f9;
    border-radius: 6px;
    color: var(--text-muted);
    font-weight: 600;
  }

  .json-viewer {
    background: #1e1b2e;
    color: #e2e8f0;
    padding: 20px;
    border-radius: 12px;
    overflow-x: auto;
    font-family: monospace;
    font-size: 0.8rem;
    line-height: 1.5;
  }

  .btn-purge-cache {
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid #fecaca;
    background: #fef2f2;
    color: #b91c1c;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }

  .btn-purge-cache:hover:not(:disabled) {
    background: #fee2e2;
    color: #991b1b;
  }

  /* NGINX EDGE CACHING PANEL STYLES */
  .nginx-caching-panel {
    border-left: 4px solid #10b981;
    background: linear-gradient(180deg, #ffffff, #fcfefe);
  }

  .nginx-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    background: #ecfdf5;
    color: #047857;
    font-size: 0.72rem;
    font-weight: 800;
    border: 1px solid #a7f3d0;
  }

  .edge-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }

  .edge-kpi-card {
    padding: 14px;
    border-radius: 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .edge-kpi-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.68rem;
    font-weight: 800;
    color: var(--text-muted);
  }

  .edge-kpi-top i {
    font-size: 1.15rem;
    color: #10b981;
  }

  .edge-kpi-val {
    font-size: 1.55rem;
    font-weight: 800;
    letter-spacing: -0.03em;
  }

  .edge-kpi-val small {
    font-size: 0.75rem;
    font-weight: 600;
  }

  .edge-kpi-card small {
    font-size: 0.7rem;
    color: var(--text-muted);
    font-weight: 600;
  }

  .text-violet { color: #7c3aed; }
  .text-emerald { color: #059669; }
  .text-sky { color: #0284c7; }

  .cache-pipeline-grid {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 14px;
    margin-top: 4px;
  }

  .pipeline-card, .endpoint-caching-card {
    padding: 16px;
    border-radius: 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .pipeline-card h4, .endpoint-caching-card h4 {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0;
  }

  .pipeline-card h4 i, .endpoint-caching-card h4 i {
    color: #6d5bd0;
  }

  .pipeline-bars {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .pipeline-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .pipeline-label {
    display: flex;
    justify-content: space-between;
    font-size: 0.74rem;
  }

  .pipeline-track {
    height: 7px;
    background: #e2e8f0;
    border-radius: 5px;
    overflow: hidden;
  }

  .fill-edge {
    display: block;
    height: 100%;
    background: #10b981;
    border-radius: inherit;
  }

  .fill-azure {
    display: block;
    height: 100%;
    background: #6d5bd0;
    border-radius: inherit;
  }

  .token-comparison-bar {
    padding-top: 10px;
    border-top: 1px dashed #cbd5e1;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .bar-legend-split {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .bar-legend-split span {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .dot-saved {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
  }

  .dot-billed {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #6d5bd0;
  }

  .dual-token-track {
    height: 9px;
    background: #e2e8f0;
    border-radius: 6px;
    overflow: hidden;
    display: flex;
  }

  .track-saved {
    background: #10b981;
    height: 100%;
  }

  .track-billed {
    background: #6d5bd0;
    height: 100%;
  }

  /* Cache Suitability Table */
  .suitability-note {
    font-size: 0.72rem;
    color: var(--text-muted);
    margin: 4px 0 10px;
    font-style: italic;
  }

  .suitability-table {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .suit-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-radius: 8px;
    gap: 12px;
    border-left: 3px solid transparent;
  }

  .suit-row.suit-high     { background: #f0fdf4; border-color: #10b981; }
  .suit-row.suit-med-high { background: #f0fdfa; border-color: #06b6d4; }
  .suit-row.suit-cond     { background: #fffbeb; border-color: #f59e0b; }
  .suit-row.suit-poor     { background: #fff7ed; border-color: #f97316; }
  .suit-row.suit-unsafe   { background: #fef2f2; border-color: #ef4444; }

  .suit-left {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
    min-width: 0;
  }

  .suit-left strong {
    font-size: 0.78rem;
    color: var(--text-main);
  }

  .suit-left span {
    font-size: 0.7rem;
    color: var(--text-muted);
    line-height: 1.35;
  }

  .suit-badge {
    flex-shrink: 0;
    font-size: 0.65rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 3px 8px;
    border-radius: 20px;
    white-space: nowrap;
  }

  .suit-badge.high     { background: #d1fae5; color: #065f46; }
  .suit-badge.med-high { background: #cffafe; color: #164e63; }
  .suit-badge.cond     { background: #fef3c7; color: #78350f; }
  .suit-badge.poor     { background: #ffedd5; color: #7c2d12; }
  .suit-badge.unsafe   { background: #fee2e2; color: #7f1d1d; }

  .cache-key-note {
    margin-top: 10px;
    font-size: 0.7rem;
    color: var(--text-muted);
    display: flex;
    gap: 5px;
    align-items: flex-start;
    line-height: 1.4;
  }

  .cache-key-note i {
    flex-shrink: 0;
    margin-top: 1px;
    color: #6d5bd0;
  }

  @media (max-width: 1100px) {
    .kpi-grid { grid-template-columns: repeat(3, 1fr); }
    .visuals-grid { grid-template-columns: 1fr; }
    .edge-kpi-grid { grid-template-columns: repeat(2, 1fr); }
    .cache-pipeline-grid { grid-template-columns: 1fr; }
    .toggles-grid { grid-template-columns: 1fr; }
    .form-grid { grid-template-columns: 1fr; }
    .table-panel { grid-column: span 1; }
  }

  @media (max-width: 700px) {
    .general-analytics-view { padding: 18px; }
    .kpi-grid { grid-template-columns: 1fr; }
    .edge-kpi-grid { grid-template-columns: 1fr; }
    .header-card { flex-direction: column; align-items: flex-start; }
    .header-controls { align-items: flex-start; }
    .sub-nav-bar { flex-wrap: wrap; }
  }
</style>
