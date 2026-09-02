<script>
  import { onMount } from 'svelte';
  import AccessDenied from '../components/AccessDenied.svelte';
  import { userStore } from '../lib/stores/auth.js';
  import { apiListKnowledgeDocuments, apiUploadKnowledgeDocument } from '../lib/api.js';

  let title = '';
  let category = 'General';
  let selectedFile;
  let fileInput;
  let documents = [];
  let loading = true;
  let uploading = false;
  let dragging = false;
  let message = '';
  let error = '';
  let search = '';
  let scopeFilter = 'All';

  $: normalizedRole = ($userStore?.role || '').trim().toLowerCase();
  $: canManage = ['admin', 'super admin', 'ticketer'].includes(normalizedRole);
  $: managedCount = documents.filter((doc) => doc.status !== 'legacy').length;
  $: legacyCount = documents.filter((doc) => doc.status === 'legacy').length;
  $: filteredDocuments = documents.filter((doc) => {
    const query = search.trim().toLowerCase();
    const matchesSearch = !query || `${doc.title} ${doc.filename}`.toLowerCase().includes(query);
    const matchesScope = scopeFilter === 'All' || (doc.category || 'Unclassified') === scopeFilter;
    return matchesSearch && matchesScope;
  });

  async function loadDocuments() {
    if (!canManage) { loading = false; return; }
    loading = true;
    error = '';
    try { documents = (await apiListKnowledgeDocuments()).documents || []; }
    catch (err) { error = err.message; }
    finally { loading = false; }
  }

  function chooseFile(file) {
    if (!file) return;
    const extension = `.${file.name.split('.').pop().toLowerCase()}`;
    if (!['.pdf', '.docx', '.txt', '.md'].includes(extension)) {
      error = 'Choose a PDF, DOCX, TXT, or Markdown document.';
      return;
    }
    selectedFile = file;
    error = '';
    if (!title.trim()) title = file.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ');
  }

  function handleDrop(event) {
    dragging = false;
    chooseFile(event.dataTransfer.files?.[0]);
  }

  function clearFile() {
    selectedFile = undefined;
    if (fileInput) fileInput.value = '';
  }

  async function upload() {
    if (!title.trim() || !selectedFile) return;
    uploading = true;
    message = '';
    error = '';
    try {
      const result = await apiUploadKnowledgeDocument({ title: title.trim(), category, file: selectedFile });
      message = result.status === 'already_indexed'
        ? `${result.title} is already indexed. No duplicate was created.`
        : `${result.title} was uploaded and is now available to Genie.`;
      title = '';
      category = 'General';
      clearFile();
      await loadDocuments();
    } catch (err) { error = err.message; }
    finally { uploading = false; }
  }

  function formatBytes(value = 0) {
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(value) {
    if (!value) return 'Date unavailable';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 'Date unavailable' : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  onMount(loadDocuments);
</script>

{#if !canManage}
  <AccessDenied requiredRole="Admin or Ticketer" />
{:else}
  <div class="knowledge-view animate-fade">
    <div class="view-header">
      <div>
        <h1 class="view-title"><i class="ph-bold ph-books"></i> Corporate Knowledge Base</h1>
        <p class="view-subtitle">Manage the approved policies and procedures Genie uses to answer employee questions.</p>
      </div>
      <div class="security-badge"><i class="ph-fill ph-lock-key"></i><span><strong>Restricted library</strong><small>Admin &amp; Ticketer only</small></span></div>
    </div>

    <div class="stats-grid">
      <div class="stat-card"><span class="stat-icon purple"><i class="ph-duotone ph-files"></i></span><div><strong>{documents.length}</strong><span>Total documents</span></div></div>
      <div class="stat-card"><span class="stat-icon green"><i class="ph-duotone ph-check-circle"></i></span><div><strong>{managedCount}</strong><span>Managed uploads</span></div></div>
      <div class="stat-card"><span class="stat-icon amber"><i class="ph-duotone ph-archive"></i></span><div><strong>{legacyCount}</strong><span>Existing sources</span></div></div>
    </div>

    <div class="workspace-grid">
      <section class="panel upload-panel">
        <div class="panel-heading">
          <div class="heading-icon"><i class="ph-duotone ph-cloud-arrow-up"></i></div>
          <div><h2>Add a source document</h2><p>Approved content is securely stored, chunked, and indexed for Genie.</p></div>
        </div>

        <form on:submit|preventDefault={upload}>
          <div class="form-group">
            <label for="knowledge-title">Document title <span>Required</span></label>
            <input id="knowledge-title" bind:value={title} maxlength="255" placeholder="e.g. 2026 Employee Benefits Guide" disabled={uploading} />
          </div>
          <div class="form-group">
            <label for="knowledge-category">Who can receive answers from this document?</label>
            <div class="select-wrap"><i class="ph-bold ph-users-three"></i><select id="knowledge-category" bind:value={category} disabled={uploading}><option value="General">All employees — company-wide policy</option><option value="HR">HR team only</option><option value="IT">IT team only</option><option value="Accounting">Accounting team only</option><option value="WorkplaceOperations">Workplace Operations only</option></select><i class="ph-bold ph-caret-down caret"></i></div>
            <small class="field-help"><i class="ph-bold ph-info"></i> Employees never browse files directly. This scope controls which answers Genie may retrieve.</small>
          </div>

          <input bind:this={fileInput} id="knowledge-file" class="hidden-file" type="file" accept=".pdf,.docx,.txt,.md" on:change={(event) => chooseFile(event.currentTarget.files?.[0])} />
          <button type="button" class:dragging class="drop-zone" on:click={() => fileInput?.click()} on:dragover|preventDefault={() => dragging = true} on:dragleave={() => dragging = false} on:drop|preventDefault={handleDrop} disabled={uploading}>
            {#if selectedFile}
              <span class="file-icon"><i class="ph-duotone ph-file-text"></i></span>
              <span class="drop-copy"><strong>{selectedFile.name}</strong><small>{formatBytes(selectedFile.size)} · Ready to upload</small></span>
              <span class="replace-file">Replace</span>
            {:else}
              <span class="upload-icon"><i class="ph-duotone ph-upload-simple"></i></span>
              <span class="drop-copy"><strong>Drop a document here or click to browse</strong><small>PDF, DOCX, TXT, or Markdown · Maximum 15 MB</small></span>
            {/if}
          </button>

          {#if message}<div class="notice success" role="status"><i class="ph-fill ph-check-circle"></i><span>{message}</span></div>{/if}
          {#if error}<div class="notice error" role="alert"><i class="ph-fill ph-warning-circle"></i><span>{error}</span></div>{/if}

          <div class="form-actions">
            {#if selectedFile}<button type="button" class="clear-button" on:click={clearFile} disabled={uploading}>Clear</button>{/if}
            <button type="submit" class="upload-button" disabled={uploading || !title.trim() || !selectedFile}>
              {#if uploading}<i class="ph-bold ph-spinner animate-spin"></i> Processing document...{:else}<i class="ph-bold ph-sparkle"></i> Upload &amp; index for Genie{/if}
            </button>
          </div>
        </form>
      </section>

      <aside class="process-card">
        <span class="process-eyebrow">HOW IT WORKS</span>
        <h2>From document to trusted answer</h2>
        <div class="process-step"><span>1</span><div><strong>Private storage</strong><p>The original file is secured in Azure Blob Storage.</p></div></div>
        <div class="step-line"></div>
        <div class="process-step"><span>2</span><div><strong>Search indexing</strong><p>Text is split into focused passages and embedded.</p></div></div>
        <div class="step-line"></div>
        <div class="process-step"><span>3</span><div><strong>Grounded answers</strong><p>Genie answers from authorized passages and reports when it cannot verify information.</p></div></div>
        <div class="privacy-note"><i class="ph-fill ph-shield-check"></i><p><strong>Employee-safe by design</strong>Raw documents and this management screen remain inaccessible to employees.</p></div>
      </aside>
    </div>

    <section class="panel library-panel">
      <div class="library-header">
        <div><h2>Document library</h2><p>Review every source currently connected to Genie.</p></div>
        <button class="refresh-button" on:click={loadDocuments} disabled={loading}><i class="ph-bold ph-arrows-clockwise" class:animate-spin={loading}></i> Refresh</button>
      </div>
      <div class="library-tools">
        <div class="search-box"><i class="ph-bold ph-magnifying-glass"></i><input bind:value={search} type="search" placeholder="Search by document name..." /></div>
        <div class="filter-wrap"><i class="ph-bold ph-funnel"></i><select bind:value={scopeFilter}><option>All</option><option>General</option><option>HR</option><option>IT</option><option>Accounting</option><option>WorkplaceOperations</option><option>Unclassified</option></select></div>
        <span class="result-count">{filteredDocuments.length} result{filteredDocuments.length === 1 ? '' : 's'}</span>
      </div>

      {#if loading}
        <div class="state"><i class="ph-bold ph-spinner animate-spin"></i><strong>Loading knowledge sources...</strong></div>
      {:else if !filteredDocuments.length}
        <div class="state"><i class="ph-duotone ph-file-magnifying-glass"></i><strong>No matching documents</strong><p>Try another title or access scope.</p></div>
      {:else}
        <div class="table-wrap"><table><thead><tr><th>Document</th><th>Access scope</th><th>File size</th><th>Added</th><th>Index status</th></tr></thead><tbody>{#each filteredDocuments as doc (doc.id)}<tr><td><div class="document-cell"><span class="document-icon"><i class="ph-duotone ph-file-text"></i></span><div><strong>{doc.title}</strong><small>{doc.filename}</small></div></div></td><td><span class="scope scope-{(doc.category || 'unknown').toLowerCase()}">{doc.category || 'Unclassified'}</span></td><td class="muted-cell">{formatBytes(doc.size_bytes)}</td><td class="muted-cell">{formatDate(doc.uploaded_at)}</td><td><span class:existing={doc.status === 'legacy'} class="status"><i class="ph-fill ph-check-circle"></i>{doc.status === 'legacy' ? 'Existing source' : 'Indexed'}</span></td></tr>{/each}</tbody></table></div>
      {/if}
    </section>
  </div>
{/if}

<style>
  .knowledge-view{height:100%;overflow-y:auto;padding:28px;display:flex;flex-direction:column;gap:22px;color:var(--text-main)}
  .view-header{display:flex;align-items:center;justify-content:space-between;gap:24px}.view-title{display:flex;align-items:center;gap:10px;font-size:1.5rem;font-weight:700}.view-title i{color:var(--primary)}.view-subtitle{margin-top:4px;color:var(--text-muted);font-size:.86rem}
  .security-badge{display:flex;align-items:center;gap:10px;padding:10px 14px;border:1px solid #ddd6fe;border-radius:11px;background:#f5f3ff;color:#5b21b6}.security-badge>i{font-size:1.25rem}.security-badge span{display:flex;flex-direction:column}.security-badge strong{font-size:.78rem}.security-badge small{margin-top:1px;font-size:.68rem;color:#7c3aed}
  .stats-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.stat-card{display:flex;align-items:center;gap:13px;padding:16px 18px;border:1px solid var(--border-color);border-radius:12px;background:#fff;box-shadow:var(--shadow-sm)}.stat-icon{width:39px;height:39px;display:grid;place-items:center;border-radius:10px;font-size:1.2rem}.stat-icon.purple{background:#eef2ff;color:#4f46e5}.stat-icon.green{background:#ecfdf5;color:#059669}.stat-icon.amber{background:#fffbeb;color:#d97706}.stat-card div{display:flex;flex-direction:column}.stat-card strong{font-size:1.2rem;line-height:1.1}.stat-card span:last-child{margin-top:3px;color:var(--text-muted);font-size:.75rem}
  .workspace-grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(270px,.85fr);gap:20px;align-items:stretch}.panel,.process-card{border:1px solid var(--border-color);border-radius:14px;background:#fff;box-shadow:var(--shadow-sm)}.upload-panel{padding:24px}.panel-heading{display:flex;align-items:center;gap:13px;padding-bottom:20px;margin-bottom:20px;border-bottom:1px solid #edf0f3}.heading-icon{width:42px;height:42px;display:grid;place-items:center;border-radius:11px;background:var(--primary-light);color:var(--primary);font-size:1.35rem}.panel-heading h2,.library-header h2{font-size:1.04rem}.panel-heading p,.library-header p{margin-top:3px;color:var(--text-muted);font-size:.78rem}
  form{display:flex;flex-direction:column;gap:17px}.form-group{display:flex;flex-direction:column;gap:7px}.form-group label{font-size:.8rem;font-weight:700}.form-group label span{margin-left:5px;color:#9f1239;font-size:.64rem;text-transform:uppercase;letter-spacing:.04em}.form-group input,.select-wrap select{width:100%;height:43px;border:1px solid #d7dee7;border-radius:9px;background:#fff;padding:0 12px;color:var(--text-main);font:inherit;font-size:.85rem;outline:none}.form-group input:focus,.select-wrap select:focus{border-color:var(--primary);box-shadow:0 0 0 3px var(--primary-light)}.select-wrap{position:relative}.select-wrap>i:first-child{position:absolute;left:12px;top:50%;transform:translateY(-50%);z-index:1;color:#64748b}.select-wrap select{padding-left:36px;padding-right:35px;appearance:none}.select-wrap .caret{position:absolute;right:12px;top:50%;transform:translateY(-50%);pointer-events:none;color:#94a3b8}.field-help{display:flex;align-items:flex-start;gap:5px;color:#64748b;font-size:.7rem;line-height:1.45}.field-help i{margin-top:2px;color:#818cf8}
  .hidden-file{display:none}.drop-zone{width:100%;min-height:118px;display:flex;align-items:center;justify-content:center;gap:13px;padding:20px;border:1.5px dashed #b9c4d2;border-radius:11px;background:#f8fafc;color:var(--text-main);cursor:pointer;transition:.18s}.drop-zone:hover,.drop-zone.dragging{border-color:var(--primary);background:#f5f3ff}.upload-icon,.file-icon{width:43px;height:43px;display:grid;place-items:center;flex-shrink:0;border-radius:11px;background:#ede9fe;color:#6d28d9;font-size:1.35rem}.file-icon{background:#eef2ff;color:#4f46e5}.drop-copy{display:flex;flex-direction:column;text-align:left}.drop-copy strong{font-size:.82rem}.drop-copy small{margin-top:4px;color:var(--text-muted);font-size:.72rem}.replace-file{margin-left:auto;color:var(--primary);font-size:.75rem;font-weight:700}
  .form-actions{display:flex;align-items:center;justify-content:flex-end;gap:10px;padding-top:2px}.upload-button,.clear-button,.refresh-button{height:40px;display:inline-flex;align-items:center;justify-content:center;gap:7px;border-radius:9px;padding:0 15px;font-weight:700;font-size:.78rem;cursor:pointer}.upload-button{min-width:175px;border:0;background:var(--primary);color:#fff}.upload-button:hover{background:var(--primary-hover)}.clear-button,.refresh-button{border:1px solid var(--border-color);background:#fff;color:#475569}.clear-button:hover,.refresh-button:hover{background:#f8fafc}.upload-button:disabled,.clear-button:disabled,.refresh-button:disabled,.drop-zone:disabled{opacity:.58;cursor:not-allowed}
  .notice{display:flex;align-items:flex-start;gap:8px;padding:11px 13px;border-radius:9px;font-size:.78rem;font-weight:600;line-height:1.4}.notice i{font-size:1rem}.notice.success{border:1px solid #a7f3d0;background:#ecfdf5;color:#047857}.notice.error{border:1px solid #fecaca;background:#fef2f2;color:#b91c1c}
  .process-card{padding:24px;background:linear-gradient(155deg,#2b1b38 0%,#31213e 100%);color:#fff;border-color:#2b1b38}.process-eyebrow{color:#c4b5fd;font-size:.66rem;font-weight:800;letter-spacing:.12em}.process-card>h2{margin:7px 0 23px;font-size:1.05rem}.process-step{display:flex;gap:12px;align-items:flex-start}.process-step>span{width:27px;height:27px;display:grid;place-items:center;flex-shrink:0;border-radius:50%;background:#6f4b82;color:#fff;font-size:.72rem;font-weight:800}.process-step strong{display:block;font-size:.79rem}.process-step p{margin-top:3px;color:#cbd5e1;font-size:.71rem;line-height:1.45}.step-line{height:20px;margin-left:13px;border-left:1px dashed #765e82}.privacy-note{display:flex;gap:10px;margin-top:24px;padding:13px;border:1px solid #584364;border-radius:10px;background:#ffffff0d}.privacy-note i{color:#86efac;font-size:1.1rem}.privacy-note p{color:#d8d0dc;font-size:.7rem;line-height:1.45}.privacy-note strong{display:block;margin-bottom:2px;color:#fff;font-size:.74rem}
  .library-panel{overflow:hidden}.library-header{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:20px 22px;border-bottom:1px solid #edf0f3}.library-tools{display:flex;align-items:center;gap:10px;padding:13px 22px;background:#fafbfc;border-bottom:1px solid #edf0f3}.search-box{position:relative;width:min(360px,100%)}.search-box i,.filter-wrap i{position:absolute;left:11px;top:50%;transform:translateY(-50%);color:#94a3b8}.search-box input,.filter-wrap select{width:100%;height:36px;border:1px solid #dbe2ea;border-radius:8px;background:#fff;padding:0 11px 0 34px;font:inherit;font-size:.76rem;outline:none}.search-box input:focus,.filter-wrap select:focus{border-color:var(--primary)}.filter-wrap{position:relative;width:180px}.filter-wrap select{appearance:none}.result-count{margin-left:auto;color:#64748b;font-size:.72rem;font-weight:600}
  .table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse}th{text-align:left;padding:11px 18px;background:#fafbfc;color:#64748b;font-size:.65rem;font-weight:800;letter-spacing:.045em;text-transform:uppercase}td{padding:14px 18px;border-top:1px solid #edf0f3;font-size:.77rem;vertical-align:middle}tbody tr:hover{background:#fafbff}.document-cell{display:flex;align-items:center;gap:11px;min-width:230px}.document-icon{width:34px;height:34px;display:grid;place-items:center;flex-shrink:0;border-radius:8px;background:#f1f5f9;color:#64748b;font-size:1rem}.document-cell strong{display:block;max-width:340px;color:#1e293b;font-size:.79rem}.document-cell small{display:block;max-width:300px;margin-top:3px;overflow:hidden;color:#94a3b8;font-size:.68rem;text-overflow:ellipsis;white-space:nowrap}.muted-cell{color:#64748b;white-space:nowrap}.scope,.status{display:inline-flex;align-items:center;gap:5px;padding:4px 8px;border-radius:999px;background:#eef2ff;color:#4338ca;font-size:.66rem;font-weight:700;white-space:nowrap}.scope-hr{background:#fdf2f8;color:#be185d}.scope-it{background:#eff6ff;color:#1d4ed8}.scope-accounting{background:#fffbeb;color:#b45309}.scope-workplaceoperations{background:#f0fdf4;color:#15803d}.scope-unclassified,.scope-unknown{background:#f1f5f9;color:#64748b}.status{background:#ecfdf5;color:#047857}.status.existing{background:#f1f5f9;color:#64748b}.state{display:flex;min-height:180px;align-items:center;justify-content:center;flex-direction:column;gap:7px;color:#64748b}.state>i{font-size:1.7rem;color:#818cf8}.state strong{font-size:.82rem}.state p{font-size:.73rem}
  @media(max-width:1000px){.workspace-grid{grid-template-columns:1fr}.process-card{display:none}}
  @media(max-width:700px){.knowledge-view{padding:18px}.view-header{align-items:flex-start;flex-direction:column}.security-badge{width:100%}.stats-grid{grid-template-columns:1fr}.library-tools{align-items:stretch;flex-direction:column}.search-box,.filter-wrap{width:100%}.result-count{margin-left:0}.library-header{align-items:flex-start}.upload-panel{padding:18px}.form-actions{align-items:stretch;flex-direction:column-reverse}.form-actions button{width:100%}}
</style>
