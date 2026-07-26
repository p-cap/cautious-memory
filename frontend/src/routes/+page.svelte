<script>
  let page = 'Home';
  let request = '';
  let sending = false;
  let importing = false;
  let importedSite = null;
  let previewWidth = 560;
  let applying = null;
  let previewing = null;
  let previewLoading = false;
  let previewLoadingTitle = 'Loading preview';
  let stagedPreview = null;
  let drafts = [];
  let postTitle = '';
  let postSlug = '';
  let postExcerpt = '';
  let postBody = '';
  let postPublishedAt = new Date().toISOString().slice(0, 16);
  let postNotice = '';
  let messages = [{ role: 'assistant', text: 'Describe a Svelte change and I’ll prepare a local draft. Nothing is applied or published in this prototype.' }];
  const pages = ['Home', 'About'];

  function selectPosts() {
    if (!importedSite?.post_route) return;
    page = importedSite.post_route;
    messages = [...messages, { role: 'assistant', text: `Posts are managed on the detected ${importedSite.post_route} page. Describe a post or a change to the post list.` }];
  }

  function slugify(title) {
    return title.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  }

  function updatePostTitle(event) {
    postTitle = event.currentTarget.value;
    if (!postSlug) postSlug = slugify(postTitle);
  }

  async function createPostDraft() {
    if (!postTitle.trim() || !postSlug.trim() || !postBody.trim()) return;
    postNotice = '';
    let draft = null;
    try {
      const response = await fetch('/api/posts/draft', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ import_id: importedSite?.import_id, title: postTitle, slug: postSlug, published_at: postPublishedAt, excerpt: postExcerpt, body: postBody }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || 'The local post draft could not be created.');
      draft = { label: 'New post', page, proposal: body.proposal, changes: body.changes ?? [] };
      drafts = [draft];
      stagedPreview = null;
      messages = [...messages, { role: 'assistant', text: body.proposal }];
    } catch (error) {
      postNotice = error instanceof Error ? error.message : 'The local post draft could not be created.';
      return;
    }
    if (draft.changes?.length) {
      const previewReady = await previewDraft(draft, importedSite?.post_route);
      postNotice = previewReady ? 'A disposable preview of this post is open on the right. Use Open staged post preview to inspect its temporary URL.' : 'The post draft was created, but its disposable preview could not be built.';
    } else {
      postNotice = 'A post draft was created, but it did not include a previewable local source change.';
    }
  }

  function renderMarkdown(value) {
    const escaped = String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
    return escaped
      .replace(/```([\w-]+)?\n([\s\S]*?)```/g, (_match, language, code) => `<pre class="code-${language || 'plain'}"><code>${code}</code></pre>`)
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/~~(.+?)~~/g, '<del>$1</del>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  function shortDescription(value) {
    const plain = String(value)
      .replace(/```[\s\S]*?```/g, '')
      .replace(/[*_`#]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
    const summary = plain.split(/\b(?:here is|here are|proposed changes|status:)\b/i)[0].trim();
    if (!summary) return 'A local Svelte update is ready to review.';
    return summary.length > 280 ? `${summary.slice(0, 277).trimEnd()}…` : summary;
  }

  function resizePreview(event) {
    const update = (pointerEvent) => {
      previewWidth = Math.min(Math.max(window.innerWidth - pointerEvent.clientX, 430), Math.max(430, window.innerWidth - 555));
    };
    const stop = () => {
      window.removeEventListener('pointermove', update);
      window.removeEventListener('pointerup', stop);
      document.body.style.cursor = '';
    };
    document.body.style.cursor = 'col-resize';
    update(event);
    window.addEventListener('pointermove', update);
    window.addEventListener('pointerup', stop, { once: true });
  }

  const labelFor = (text) => {
    const value = text.toLowerCase();
    if (value.includes('hero') || value.includes('headline')) return 'Hero direction';
    if (value.includes('testimonial') || value.includes('review')) return 'Social proof section';
    if (value.includes('nav')) return 'Navigation copy';
    return 'Svelte page draft';
  };

  async function send(text = request) {
    const prompt = text.trim();
    if (!prompt || sending || !importedSite) return;
    messages = [...messages, { role: 'user', text: prompt }];
    request = '';
    const applyMatch = prompt.match(/^apply(?:\s+local(?:ly)?)?(?:\s+(?:change|draft))?\s*(\d+)?$/i);
    if (applyMatch) {
      const pending = drafts.filter((draft) => draft.changes?.length && !draft.applied).slice().reverse();
      const requestedIndex = Number(applyMatch[1] || 1) - 1;
      const draft = pending[requestedIndex];
      if (!draft) {
        messages = [...messages, { role: 'assistant', text: 'There is no pending local change with that number. Use an Apply locally button on a proposal card.' }];
      } else {
        await applyDraft(draft);
      }
      return;
    }
    sending = true;
    try {
      const response = await fetch('/api/drafts', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ request: prompt, page, site_name: importedSite?.name, import_id: importedSite?.import_id }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || 'The local draft service did not respond.');
      const proposal = body.proposal?.trim() || (body.changes?.length
        ? `A proposed local update is ready to preview in: ${body.changes.map((change) => change.path).join(', ')}.`
        : 'A local draft was created, but no readable proposal summary was returned.');
      const draft = { label: labelFor(prompt), page, proposal, changes: body.changes ?? [] };
      drafts = [draft];
      stagedPreview = null;
      messages = [...messages, { role: 'assistant', text: proposal }];
      return draft;
    } catch (error) {
      messages = [...messages, { role: 'assistant', text: error instanceof Error ? error.message : 'Could not create a local draft.' }];
      return null;
    } finally { sending = false; }
  }

  async function applyDraft(draft) {
    if (!importedSite?.import_id || !draft.changes?.length || draft.applied || stagedPreview?.draft !== draft || applying) return;
    applying = draft;
    previewLoadingTitle = 'Loading local change';
    previewLoading = true;
    try {
      const response = await fetch('/api/changes/apply', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ import_id: importedSite.import_id, changes: draft.changes }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || 'The local change could not be applied.');
      importedSite = { ...importedSite, preview_url: `${body.preview_url}?updated=${Date.now()}` };
      stagedPreview = null;
      previewLoading = true;
      drafts = drafts.map((item) => item === draft ? { ...item, applied: true } : item);
      messages = [...messages, { role: 'assistant', text: 'Applied the change to the local imported source and rebuilt its preview. Nothing was committed or published.' }];
    } catch (error) {
      previewLoading = false;
      messages = [...messages, { role: 'assistant', text: error instanceof Error ? error.message : 'The local change could not be applied.' }];
    } finally { applying = null; }
  }

  async function previewDraft(draft, previewPath = '') {
    if (!importedSite?.import_id || !draft.changes?.length || previewing) return;
    previewing = draft;
    previewLoadingTitle = 'Loading preview change';
    previewLoading = true;
    try {
      const response = await fetch('/api/changes/preview', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ import_id: importedSite.import_id, changes: draft.changes }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || 'The change preview could not be built.');
      const baseUrl = body.preview_url.replace(/\/$/, '');
      const route = previewPath ? `/${previewPath.replace(/^\/+|\/+$/g, '')}` : '';
      stagedPreview = { draft, url: `${baseUrl}${route}/?previewed=${Date.now()}` };
      previewLoading = true;
      messages = [...messages, { role: 'assistant', text: 'Built a disposable local preview of this proposal. Review it on the right before applying anything.' }];
      return true;
    } catch (error) {
      previewLoading = false;
      messages = [...messages, { role: 'assistant', text: error instanceof Error ? error.message : 'The change preview could not be built.' }];
      return false;
    } finally { previewing = null; }
  }

  function discardPreview() {
    if (window.confirm('Discard this disposable change preview and return to the current local site? The imported source will not be changed.')) {
      stagedPreview = null;
      previewLoadingTitle = 'Loading current site';
      previewLoading = true;
    }
  }

  function cancelDraft(draft) {
    if (draft.applied) return;
    if (window.confirm('Cancel this local change? Its disposable preview will be discarded and the current local site will remain unchanged.')) {
      if (stagedPreview?.draft === draft) {
        stagedPreview = null;
        previewLoadingTitle = 'Loading current site';
        previewLoading = true;
      }
      drafts = drafts.filter((item) => item !== draft);
      messages = [...messages, { role: 'assistant', text: 'Cancelled the local change. The imported source was not modified.' }];
    }
  }

  async function importProject(event) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file || importing) return;
    importing = true;
    try {
      const response = await fetch('/api/imports', { method: 'POST', headers: { 'content-type': 'application/zip', 'x-project-filename': file.name }, body: file });
      const responseText = await response.text();
      let body = {};
      try { body = JSON.parse(responseText); } catch { /* A proxy may return plain text or HTML. */ }
      if (!response.ok) {
        const backendDetail = (body && typeof body === 'object' ? body.detail : '') || responseText.trim().replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').slice(0, 300);
        throw new Error(backendDetail || `Could not import this project archive (HTTP ${response.status}).`);
      }
      importedSite = body;
      stagedPreview = null;
      previewLoadingTitle = 'Loading local preview';
      previewLoading = true;
      page = body.routes.includes('/') ? 'Home' : body.routes[0];
      messages = [...messages, { role: 'assistant', text: `${body.name} is available as a local, read-only import. I detected ${body.framework}, ${body.routes.length} route${body.routes.length === 1 ? '' : 's'}${body.post_route ? `, including ${body.post_route} for posts` : ''}, and prepared its local preview.` }];
    } catch (error) {
      messages = [...messages, { role: 'assistant', text: error instanceof Error ? error.message : 'Could not import this project.' }];
    } finally { importing = false; input.value = ''; }
  }
</script>

<svelte:head><title>Studio — local prototype</title></svelte:head>

<main style:--preview-width={`${previewWidth}px`}>
  <aside>
    <a class="brand" href="/"><i class="happy-computer" aria-label="Computerized smiley face"><span>◉‿◉</span></i> SIGNAL STUDIO</a>
    <p class="caption">OPERATING SYSTEM FOR SITE CHANGES</p>
    <nav>{#each pages as item}<button class:active={page === item} on:click={() => page = item}><span>{item === 'Home' ? '⌂' : '□'}</span>{item}</button>{/each}<button class="posts-nav" class:active={page === importedSite?.post_route} disabled={!importedSite?.post_route} on:click={selectPosts}><span>▤</span><b>Posts</b>{#if importedSite?.post_route}<small>{importedSite.post_route}</small>{/if}</button></nav>
    <label class="import"><b>Import a project</b><span>{importedSite ? importedSite.name : 'Choose a Svelte/SvelteKit ZIP'}</span><input type="file" accept=".zip,application/zip" on:change={importProject} disabled={importing} />{#if importing}<em>Inspecting local archive…</em>{/if}</label>
  </aside>

  <section class="chat">
    <header><div><h1>{page === importedSite?.post_route ? 'Create a post' : importedSite ? 'What would you like to explore?' : 'Import a project to start chatting'}</h1></div></header>
    {#if page === importedSite?.post_route}<div class="cms"><div class="cms-intro"><b>Posts CMS</b><span>Target: {importedSite.post_route}</span></div><label>Title<input value={postTitle} on:input={updatePostTitle} placeholder="A clear post title" /></label><label>Slug<input bind:value={postSlug} placeholder="my-new-post" /></label><label>Published date &amp; time<input type="datetime-local" bind:value={postPublishedAt} /></label><label>Excerpt<textarea bind:value={postExcerpt} rows="2" placeholder="A short summary for the posts list"></textarea></label><label>Post body<textarea class="post-body" bind:value={postBody} rows="10" placeholder="Write the post content in Markdown…"></textarea></label><button class="create-post" disabled={sending || !postTitle.trim() || !postSlug.trim() || !postBody.trim()} on:click={createPostDraft}>{sending ? 'Creating local draft…' : 'Create local post draft'}</button>{#if postNotice}<p class="post-notice">{postNotice}</p>{/if}{#if stagedPreview}<a class="open-staged" href={stagedPreview.url} target="_blank" rel="noopener">Open staged post preview ↗</a>{/if}<p>Creates a reviewable local proposal. It will not publish or modify source automatically.</p></div>{:else}<div class="conversation">{#each messages as message}<article class:user={message.role === 'user'}><span class="avatar">{message.role === 'user' ? 'You' : 'S'}</span><div class="message-text">{@html renderMarkdown(message.text)}</div></article>{/each}{#if sending}<article><span class="avatar">S</span><div class="message-text thinking" role="status"><span class="thinking-label">Creating proposal</span><span class="thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="thinking-scan" aria-hidden="true"></span></div></article>{/if}</div>
    <div class="compose"><form on:submit|preventDefault={() => send()}><textarea bind:value={request} rows="2" disabled={!importedSite} placeholder={importedSite ? 'Describe a visual, content, or layout change…' : 'Import a Svelte project to enable chat'} on:keydown={(event) => event.key === 'Enter' && !event.shiftKey && (event.preventDefault(), send())}></textarea><button disabled={!importedSite || !request.trim() || sending}>Send</button></form></div>{/if}
  </section>

  <section class="preview"><div class="resizer" role="separator" aria-orientation="vertical" aria-label="Resize preview panel" on:pointerdown={resizePreview}></div>
    <header><span>{importedSite ? `${importedSite.name} · ${stagedPreview ? 'change preview' : importedSite.framework}` : 'No project imported'}</span><span class="no-deploy">No deploy target</span></header>
    <div class="canvas">{#if importedSite?.preview_url}<div class="preview-tools"><a href={stagedPreview?.url ?? importedSite.preview_url} target="_blank" rel="noopener">Open local preview ↗</a>{#if stagedPreview}<button class="discard-preview" on:click={discardPreview}>Discard preview · show current site</button>{/if}</div><div class="frame-wrap"><iframe class="site-frame" title={`${importedSite.name} local preview`} src={stagedPreview?.url ?? importedSite.preview_url} on:load={() => previewLoading = false}></iframe>{#if previewLoading}<div class="preview-loading" role="status"><span class="signal-loader" aria-hidden="true"><i></i><i></i><i></i></span><b>{previewLoadingTitle}</b><small>Preparing the local site…</small></div>{/if}</div>{:else}<div class="empty-preview"><span>⌁</span><h2>Import a Svelte project to start previewing</h2><p>Choose a Svelte or SvelteKit ZIP from the sidebar. Its local browser preview will be ready after import.</p></div>{/if}</div>
    <div class="drafts"><div class="draft-title"><div><p class="caption">{importedSite ? 'IMPORTED SITE' : 'PROPOSALS'}</p><h2>{importedSite ? 'Detected routes' : 'Local drafts'}</h2></div><span>{importedSite ? importedSite.routes.length : drafts.length}</span></div>{#if importedSite}<div class="routes" aria-label="Detected site routes">{#each importedSite.routes as route}<span>{route}</span>{/each}</div><p class="empty">Review the latest change, then preview or cancel it. Nothing touches the imported source until you apply it.</p>{:else if !drafts.length}<p class="empty">Your Gemini proposals will appear here. They are never applied automatically.</p>{/if}{#each drafts as draft}<article class="draft"><span>✓</span><div><b>{draft.label}</b><small>{draft.page} · {draft.applied ? 'applied locally' : 'local proposal'}</small><p class="change-summary">{shortDescription(draft.proposal)}</p><div class="draft-actions">{#if stagedPreview?.draft === draft && !draft.applied}<button class="apply-change" disabled={applying === draft} on:click={() => applyDraft(draft)}>{applying === draft ? 'Applying locally…' : 'Apply locally'}</button>{:else}<button class="preview-change" class:recommended={!draft.applied} disabled={previewing === draft || draft.applied || !draft.changes?.length} on:click={() => previewDraft(draft)}>{previewing === draft ? 'Building preview…' : draft.applied ? 'Applied locally' : 'Preview change'}</button>{/if}<button class="cancel-change" disabled={draft.applied} on:click={() => cancelDraft(draft)}>{draft.applied ? 'Change applied' : 'Cancel change'}</button></div></div></article>{/each}</div>
  </section>
</main>

<style>
  .preview-tools{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;color:#7e7f76;font-size:11px}
  .conversation article:not(.user){width:91%}.conversation article:not(.user) .message-text{width:calc(100% - 34px)}.message-text :global(pre),.message-text :global(pre code){min-width:0!important;max-width:100%!important;white-space:pre-wrap!important;overflow-wrap:anywhere!important;word-break:break-word!important}
  .thinking{position:relative;display:flex;align-items:center;gap:7px;min-width:190px;overflow:hidden}.thinking-label{position:relative;z-index:1}.thinking-dots{display:flex;gap:3px;position:relative;z-index:1}.thinking-dots i{display:block;width:5px;height:5px;background:#ff552f;animation:thinking-dot 1s ease-in-out infinite}.thinking-dots i:nth-child(2){animation-delay:.16s}.thinking-dots i:nth-child(3){animation-delay:.32s}.thinking-scan{position:absolute;inset:0 auto 0 -35%;width:30%;background:linear-gradient(90deg,transparent,#ffe86b99,transparent);animation:thinking-scan 1.5s linear infinite}@keyframes thinking-dot{50%{transform:translateY(-4px);background:#356cf4}}@keyframes thinking-scan{to{left:110%}}@media(prefers-reduced-motion:reduce){.thinking-dots i,.thinking-scan{animation:none}}
  .preview-tools a{height:32px;display:inline-flex;align-items:center;border-radius:7px;padding:0 10px;background:#1b1c19;color:#fff;text-decoration:none;font-size:11px;font-weight:650}
  .preview-tools a:hover{background:#373934}
  .apply-change{margin-top:9px;padding:7px 9px;border:0;border-radius:6px;background:#e4f4ea;color:#276b49;font-size:11px;font-weight:700}
  .apply-change:disabled{opacity:.6;cursor:wait}
  .cms{padding:27px 29px;overflow:auto;display:grid;gap:13px}.cms-intro{display:flex;justify-content:space-between;align-items:center}.cms-intro b{font-size:14px}.cms-intro span{font:10px ui-monospace,SFMono-Regular,Menlo,monospace;color:#74756d}.cms label{display:grid;gap:6px;color:#66675f;font-size:11px;font-weight:700}.cms input,.cms textarea{width:100%;padding:10px;border:1px solid #dedfd9;border-radius:8px;background:#fbfbf9;color:#191a17;font:13px Inter,ui-sans-serif,sans-serif;resize:vertical}.cms .post-body{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;line-height:1.5}.create-post{height:36px;border:0;border-radius:8px;background:#1b1c19;color:#fff;font-size:12px;font-weight:700}.create-post:disabled{background:#dadbd5;color:#989992;cursor:not-allowed}.cms>p{margin:0;color:#85867e;font-size:10px;line-height:1.5}.cms>.post-notice{padding:9px;border-radius:7px;background:#edf8f1;color:#286b46;font-size:11px}.open-staged{display:inline-flex;align-items:center;height:34px;border-radius:8px;padding:0 10px;background:#eaf4ed;color:#286b46;text-decoration:none;font-size:11px;font-weight:700}
  .draft-actions{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:9px}.preview-change,.discard-preview,.cancel-change{padding:7px 9px;border:1px solid #d9dad3;border-radius:6px;background:#fff;color:#52534d;font-size:11px;font-weight:700}.preview-change:disabled,.cancel-change:disabled{opacity:.6;cursor:wait}.preview-change.recommended{border-color:#5eaf7b;background:#f0fbf4;color:#286b46;animation:preview-pulse 1.7s ease-in-out infinite}@keyframes preview-pulse{50%{box-shadow:0 0 0 5px #78c6942b}}.discard-preview{height:32px;margin-left:auto;padding:0 9px;border-color:#e4c5bd;background:#fff6f3;color:#944335}.cancel-change{border-color:#d85a4b;background:#fff5f2;color:#8e3026}.draft-actions .apply-change,.draft-actions .preview-change,.draft-actions .cancel-change{width:100%;margin-top:0}
  :global(*){box-sizing:border-box}:global(body){margin:0;background:#f5f5f2;color:#191a17;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}button,textarea{font:inherit}button{cursor:pointer}main{height:100vh;min-height:670px;display:grid;grid-template-columns:205px minmax(350px,1fr) var(--preview-width)}aside{padding:27px 14px;background:#fbfbf9;border-right:1px solid #e5e5e0;display:flex;flex-direction:column}.brand{font-size:21px;font-weight:760;letter-spacing:-.05em;color:inherit;text-decoration:none;display:flex;gap:8px;align-items:center}.brand i,.avatar{font:normal 14px Georgia,serif;background:#1a1b18;color:white;border-radius:7px;width:25px;height:25px;display:grid;place-items:center}.caption{font-size:10px;letter-spacing:.12em;font-weight:750;color:#8f9088;margin:29px 10px 10px}nav{display:grid;gap:3px}nav button{padding:9px 10px;border:0;border-radius:7px;color:#67685f;background:transparent;text-align:left;font-size:13px}nav button span{width:23px;display:inline-block;color:#999a91}nav button small{float:right;font:9px ui-monospace,SFMono-Regular,Menlo,monospace;color:#8e8f87}.posts-nav{display:flex;align-items:center}.posts-nav b{font:inherit;font-weight:inherit}.posts-nav small{margin-left:auto;float:none}nav button:disabled{opacity:.4;cursor:not-allowed}nav button.active{background:#e9eae5;color:#171814;font-weight:650}.import{display:grid;gap:5px;margin:19px 9px 0;padding:11px;border:1px dashed #d3d4cc;border-radius:8px;cursor:pointer}.import b{font-size:11px}.import span,.import em{font-size:10px;line-height:1.35;color:#74756d}.import em{color:#9b6b18;font-style:normal}.import input{display:none}.safe{margin-top:auto;border-top:1px solid #e8e8e3;padding:17px 9px 4px;display:grid;gap:5px}.safe b{font-size:11px;color:#378157}.safe span{font-size:10px;line-height:1.45;color:#85867e}.chat{background:white;border-right:1px solid #e5e5e0;display:flex;flex-direction:column;min-width:0}.chat header,.preview header{height:88px;padding:25px 29px;display:flex;justify-content:space-between;align-items:start;border-bottom:1px solid #ededE8}.chat header .caption{margin:0}.chat h1{font-size:21px;margin:6px 0 0;letter-spacing:-.045em}.badge,.no-deploy{font-size:10px;border:1px solid #dfe0da;border-radius:999px;padding:6px 9px;color:#5c5d56}.conversation{padding:27px 29px;overflow:auto;flex:1;display:flex;flex-direction:column;gap:18px;min-width:0}.conversation article{display:flex;gap:9px;align-items:flex-start;max-width:91%;min-width:0}.conversation article.user{align-self:flex-end;flex-direction:row-reverse}.conversation .user .avatar{background:#dfc453;color:#2a291d;font:600 9px Inter, sans-serif}.message-text{margin:0;min-width:0;max-width:100%;overflow-wrap:anywhere;background:#f1f2ee;border-radius:4px 14px 14px 14px;padding:11px 13px;font-size:13px;line-height:1.5;white-space:normal}.conversation .user .message-text{background:#1b1c19;color:#fff;border-radius:14px 4px 14px 14px}.message-text :global(h1),.message-text :global(h2),.message-text :global(h3){margin:0 0 7px;font-size:14px;line-height:1.3}.message-text :global(strong),.proposal-text :global(strong){font-weight:750}.message-text :global(del){color:#a9554a;text-decoration-thickness:2px}.message-text :global(code){font:11px ui-monospace,SFMono-Regular,Menlo,monospace;background:#e1e2dc;border-radius:3px;padding:1px 4px;overflow-wrap:anywhere}.conversation .user .message-text :global(code){background:#ffffff20}.message-text :global(pre){max-width:100%;margin:8px 0;overflow-x:auto;background:#20211e;color:#f5f5f2;border-radius:6px;padding:9px;white-space:pre-wrap;overflow-wrap:anywhere}.message-text :global(pre.code-remove){background:#fff1ef;color:#98483c;text-decoration:line-through;text-decoration-thickness:2px}.message-text :global(pre.code-replace){background:#ecf7ef;color:#245b3b}.message-text :global(pre code){background:transparent;padding:0;color:inherit}.message-text :global(li){margin-left:16px}.thinking{color:#777871}.compose{padding:13px 18px 19px}.chips{display:flex;gap:7px;overflow:auto;margin-bottom:9px}.chips button{white-space:nowrap;border:1px solid #e1e2dc;border-radius:999px;background:#fff;padding:7px 10px;font-size:11px;color:#5f6059}.compose form{border:1px solid #dedfd9;border-radius:11px;padding:10px;display:flex;gap:8px;align-items:end;box-shadow:0 1px 2px #2221}.compose textarea{width:100%;resize:none;outline:0;border:0;background:transparent;font-size:13px;line-height:1.4}.compose form button{background:#1b1c19;color:white;border:0;border-radius:7px;min-width:62px;height:28px;padding:0 10px;font-size:12px;font-weight:700}.compose form button:disabled{background:#dadbd5;color:#989992}.preview{position:relative;overflow:auto}.resizer{position:absolute;z-index:2;top:0;bottom:0;left:-5px;width:10px;cursor:col-resize}.resizer:hover,.resizer:focus{background:#d8d9d2;outline:0}.preview header{height:58px;padding:0 22px;align-items:center;font-size:12px;color:#686960}.no-deploy{color:#9b6b18;border-color:#e3d2a5;background:#fff9e8}.canvas{padding:25px 25px 19px}.site-frame{display:block;width:100%;height:320px;border:0;background:#fff;box-shadow:0 9px 26px #17181420}.empty-preview{min-height:320px;border:1px dashed #d7d8d1;background:#fafaf7;display:grid;place-content:center;text-align:center;padding:35px;box-shadow:0 9px 26px #1718140c}.empty-preview>span{font-size:26px;color:#b0b19f}.empty-preview h2{font-size:17px;letter-spacing:-.04em;margin:10px 0 5px}.empty-preview p{max-width:270px;font-size:11px;line-height:1.5;color:#7e7f76;margin:0 auto}.drafts{margin:0 25px 25px;border:1px solid #e2e3dd;border-radius:10px;background:#fff;padding:17px}.draft-title{display:flex;justify-content:space-between;align-items:center}.draft-title .caption{margin:0}.draft-title h2{font-size:15px;margin:4px 0 0;letter-spacing:-.035em}.draft-title>span{font-size:11px;background:#f0f1ec;border-radius:10px;padding:3px 7px}.routes{display:flex;flex-wrap:wrap;gap:5px;margin:13px 0 4px}.routes span{border:1px solid #dfe0da;border-radius:999px;background:#f7f8f4;padding:4px 7px;color:#54554e;font:10px ui-monospace,SFMono-Regular,Menlo,monospace}.empty{font-size:11px;line-height:1.5;color:#898a82;margin:17px 0 3px}.draft{border-top:1px solid #eeeeea;margin-top:13px;padding-top:12px;display:flex;gap:9px}.draft>span{width:18px;height:18px;border-radius:50%;display:grid;place-items:center;background:#e4f4ea;color:#318056;font-size:11px}.draft b{display:block;font-size:12px}.draft small{font-size:10px;color:#8d8e85}.draft p,.proposal-text{font-size:11px;color:#5f6059;line-height:1.45;margin:6px 0 0}@media(max-width:850px){main{display:block;height:auto;min-height:100vh}aside{display:none}.preview{display:none}.chat{height:100vh}.chat header{padding:23px 19px}.conversation{padding:22px 19px}.compose{padding:13px 14px 16px}}
  /* Signal-deck inspired interface treatment */
  :global(body){background:#f5f2e8;font-family:Arial,Helvetica,sans-serif}
  main{gap:0;background:#f5f2e8;padding:10px;grid-template-columns:205px minmax(350px,1fr) var(--preview-width)}
  aside,.chat,.preview{background:#fdfcf7;border:3px solid #181818}
  aside{border-right:0;padding:20px 14px}.chat{border-right:0}.brand{font-size:16px;letter-spacing:-.04em;font-weight:900}.brand i,.avatar{border-radius:0;background:#191919;font-family:Arial,Helvetica,sans-serif;font-weight:900}.brand i.happy-computer{position:relative;width:34px;background:#ffe86b;color:#191919;border:2px solid #191919;overflow:hidden}.happy-computer span{display:grid;place-items:center;width:24px;height:15px;background:#191919;border:1px solid #191919;color:#baff74;font:900 8px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:-1.8px;box-shadow:0 2px 0 #191919}.caption{font-weight:900;letter-spacing:.08em;color:#242424;margin:24px 8px 10px}
  nav{gap:5px}nav button{border:2px solid transparent;border-radius:0;padding:9px 8px;font-weight:700;color:#1a1a1a}nav button span{color:#1a1a1a}nav button:hover{border-color:#1a1a1a;background:#ffe86b}nav button.active{border-color:#1a1a1a;background:#ffe86b;box-shadow:3px 3px 0 #191919}.posts-nav small{font-weight:700;color:#1a1a1a}.import{border:2px dashed #191919;border-radius:0;background:#fffef9;margin:22px 7px 0}.import b{font-weight:900}.import:hover{background:#ffe86b}
  .chat header,.preview header{height:88px;padding:18px 23px;border-bottom:3px solid #181818}.chat h1{font-size:25px;font-weight:900;line-height:1;letter-spacing:-.06em}.badge,.no-deploy{border:2px solid #181818;border-radius:0;background:#fffef9;color:#191919;font-weight:800}.no-deploy{background:#ffe86b}.conversation{padding:22px;gap:14px;background:#fdfcf7}.conversation article{max-width:95%}.message-text{border:2px solid #181818;border-radius:0;background:#fffef9;padding:11px 12px;box-shadow:3px 3px 0 #181818;font-weight:500}.conversation .user .message-text{background:#1a1a1a;border-color:#1a1a1a}.compose{padding:15px;border-top:3px solid #181818;background:#fdfcf7}.chips button{border:2px solid #181818;border-radius:0;background:#fffef9;color:#191919;font-weight:700}.chips button:hover{background:#ffe86b}.compose form{border:3px solid #181818;border-radius:0;box-shadow:3px 3px 0 #181818}.compose form button{border-radius:0;background:#ff552f;font-weight:900}.compose form button:disabled{background:#d6d2c4}
  .cms{padding:22px;background:#fdfcf7}.cms-intro{border:3px solid #181818;background:#ffe86b;padding:10px}.cms-intro b{font-weight:900}.cms input,.cms textarea{border:2px solid #181818;border-radius:0;background:#fffef9}.create-post{border:3px solid #181818;border-radius:0;background:#ff552f;box-shadow:3px 3px 0 #181818;font-weight:900}.open-staged{border:2px solid #181818;border-radius:0;background:#ffe86b;color:#191919}.cms>.post-notice{border:2px solid #181818;border-radius:0;background:#e8f4ff;color:#191919}.compose textarea{flex:1;min-width:0}.compose form button{margin-left:auto;flex:0 0 auto;align-self:flex-end}
  .preview{background:#f5f2e8}.preview header{background:#fffef9}.canvas{padding:18px}.preview-tools a{border:2px solid #181818;border-radius:0;background:#ff552f;box-shadow:3px 3px 0 #181818;font-weight:900}.discard-preview{border:2px solid #181818;border-radius:0;background:#fffef9;color:#191919;font-weight:800}.site-frame{border:3px solid #181818;box-shadow:5px 5px 0 #181818}.empty-preview{border:3px dashed #181818;border-radius:0;background:#fffef9;box-shadow:4px 4px 0 #181818}.drafts{margin:0 18px 18px;border:3px solid #181818;border-radius:0;background:#fffef9;padding:14px;box-shadow:4px 4px 0 #181818}.draft-title>span{border:2px solid #181818;border-radius:0;background:#ffe86b;font-weight:800}.routes span{border:2px solid #181818;border-radius:0;background:#fffef9;color:#191919;font-weight:700}.draft{border-top:2px solid #181818}.draft>span{border-radius:0;background:#ffe86b;color:#191919;font-weight:900}.preview-change,.apply-change,.cancel-change{border:2px solid #181818;border-radius:0;box-shadow:2px 2px 0 #181818;font-weight:900}.preview-change{background:#fffef9;color:#191919}.preview-change.recommended{border-color:#181818;background:#ffe86b;color:#191919;animation:none}.apply-change{background:#356cf4;color:#fff}.cancel-change{background:#ff552f;color:#fff;border-color:#181818}.draft-actions{gap:10px}
  .frame-wrap{position:relative;min-height:320px}.preview-loading{position:absolute;inset:0;z-index:1;display:grid;place-content:center;justify-items:center;gap:9px;background:#171814ee;color:#fffef9;text-align:center}.preview-loading:before{content:'LOCAL PREVIEW';border:2px solid #ffe86b;background:#171814;padding:4px 7px;color:#ffe86b;font:900 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em}.preview-loading b{font-size:15px;font-weight:900}.preview-loading small{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:#e5e1d1}.signal-loader{position:relative;width:50px;height:32px;border:3px solid #fffef9;background:#171814;box-shadow:4px 4px 0 #ff552f;overflow:hidden}.signal-loader:before{content:'···';position:absolute;inset:0;display:grid;place-items:center;color:#baff74;font:900 23px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:5px;animation:signal-blink .9s steps(2,end) infinite}.signal-loader i{display:none}@keyframes signal-blink{50%{opacity:.18}}
  @media(max-width:850px){main{padding:0}.chat{border:0}}
</style>
