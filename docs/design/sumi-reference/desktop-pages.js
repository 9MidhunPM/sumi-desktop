/* Sumi reference: desktop tools. Local sample state only; no system integrations. */
(() => {
  const E = text => UI.esc(String(text ?? ''));
  const I = (name, size) => UI.icon(name, size);
  const A = (name, value, label, cls = 'btn quiet') => `<button class="${cls}" data-action="desk-${name}" data-value="${E(value)}">${label}</button>`;
  const intro = (title, detail) => `<div class="page-intro"><h2>${title}</h2><p>${detail}</p></div>`;
  const apps = [
    {name:'Browser', detail:'Your tabs, close at hand', icon:'globe', tint:'blue'},
    {name:'Files', detail:'Folders and recent documents', icon:'folder', tint:'blue', route:'files'},
    {name:'Spotify', detail:'Music for this moment', icon:'music', tint:'green', route:'media'},
    {name:'Terminal', detail:'A fresh command line', icon:'terminal', tint:'gray'},
    {name:'Code', detail:'Pick up where you left off', icon:'code', tint:'blue'},
    {name:'Thursday', detail:'Your desktop companion', icon:'sparkles', tint:'purple', route:'thursday'},
    {name:'Notes', detail:'A place for your thoughts', icon:'file', tint:'amber'},
    {name:'Settings', detail:'Make Sumi yours', icon:'settings', tint:'gray', route:'settings'}
  ];
  const files = [
    {name:'Documents', detail:'Folder · 12 items', kind:'folder'},
    {name:'Pictures', detail:'Folder · 24 items', kind:'folder'},
    {name:'Downloads', detail:'Folder · 6 items', kind:'folder'},
    {name:'Project notes.md', detail:'Documents · Modified today', kind:'file', text:'Sumi design notes\n\nKeep the clock stationary.\nLet useful things gather around it.\nKeep every desktop tool within reach.'},
    {name:'Weekend playlist.txt', detail:'Documents · Yesterday', kind:'file', text:'A few things worth listening to\n\n1. Weightless — Marconi Union\n2. A Walk — Tycho\n3. Open Eye Signal — Jon Hopkins'},
    {name:'Design review.pdf', detail:'Downloads · 1.4 MB', kind:'file', text:'Design review\n\nA calm surface, clear feedback, and familiar controls.\n\nThis is a sample document preview.'}
  ];
  const clipSamples = [
    {id:'c1',text:'Keep the time still. Let everything else find its place.',kind:'Text',time:'Just now'},
    {id:'c2',text:'https://example.com/design-notes',kind:'Link',time:'8 min ago'},
    {id:'c3',text:'Meeting notes: share the reference, review the interactions, then polish the native shell.',kind:'Text',time:'22 min ago'}
  ];
  const actions = [
    ['appearance','palette','Appearance','Wallpaper, colors and desktop style'],
    ['widgets','layout','Desktop widgets','Priorities, deadlines and placement'],
    ['capture','camera','Capture screen','Screenshot or record an area'],
    ['pomodoro','timer','Start a focus session','Make a little room for deep work'],
    ['inbox','bell','Notification Inbox','Read, act on, and dismiss notifications'],
    ['power','power','Session controls','Lock, suspend and power options']
  ];
  function init(s) {
    s.searchQuery ??= ''; s.searchTab ??= 'Apps'; s.filePath ??= 'Home';
    s.clipItems ??= clipSamples.map(x => ({...x})); s.clipPaused ??= false;
    s.widgetClock ??= true; s.widgetSpotify ??= true; s.widgetPriorities ??= true; s.widgetDeadline ??= true;
    s.priority1 ??= 'Review the Sumi reference'; s.priority2 ??= 'Make something worth keeping'; s.priority3 ??= 'Take a walk';
    s.priorityDone1 ??= false; s.priorityDone2 ??= false; s.priorityDone3 ??= false;
    s.deadlineTitle ??= 'Design review'; s.deadlineDate ??= '2026-11-12';
    s.widgetLayout ??= 'curated'; s.codexView ??= 'available'; s.accent ??= '#8ab4ff';
  }
  function searchHeader(s, tab) {
    const tabs = ['Apps','Files','Windows','Actions','Clipboard'];
    return `<label class="desk-search">${I('search',21)}<input class="field" aria-label="Search ${tab.toLowerCase()}" autocomplete="off" spellcheck="false" data-bind="searchQuery" placeholder="${tab === 'Apps' ? 'Search apps, or find a tool…' : 'Search ' + tab.toLowerCase() + '…'}" value="${E(s.searchQuery)}"><kbd>Ctrl K</kbd></label><div class="desk-tabs" role="tablist" aria-label="Search categories">${tabs.map(t => A('tab',t,t,`desk-tab ${tab === t ? 'selected' : ''}`)).join('')}</div>`;
  }
  function matches(s, text) { return text.toLowerCase().includes(s.searchQuery.toLowerCase().trim()); }
  function appResults(s) {
    const filtered = apps.filter(a => matches(s,a.name+' '+a.detail));
    if (!filtered.length) return UI.empty('search','No matching apps','Try a different name, or switch to another category.');
    if (s.searchQuery) return `<div class="list desk-results">${filtered.map(a => UI.row({icon:a.icon,title:a.name,sub:a.detail,action:'desk-launch',value:a.name,end:'↵'})).join('')}</div>`;
    return `<div class="section-title">Within reach</div><div class="desk-apps">${apps.slice(0,6).map(a => A('launch',a.name,`<span class="desk-appicon ${a.tint}">${I(a.icon,25)}</span><span>${a.name}</span>`,'desk-app')).join('')}</div><div class="section-title">Pick up where you left off</div><div class="list">${UI.row({icon:'code',title:'Code',sub:'Sumi · desktop workspace',action:'desk-launch',value:'Code',end:'↵'})}${UI.row({icon:'file',title:'Project notes.md',sub:'Documents · opened today',action:'desk-file',value:'Project notes.md'})}</div>`;
  }
  function fileResults(s) {
    if (s.filePreview) {
      const file = files.find(f => f.name === s.filePreview);
      return `<div class="desk-file-head">${A('file-close','',`${I('arrow-left',16)} Files`)}<span class="hint">Local sample preview</span></div><div class="desk-document"><div class="desk-document-title">${I('file',24)}<strong>${E(file.name)}</strong></div><pre>${E(file.text)}</pre></div>`;
    }
    const pool = s.filePath === 'Home' ? files : files.filter(f => f.kind === 'file');
    const found = pool.filter(f => matches(s,f.name+' '+f.detail));
    return `<div class="desk-breadcrumb">${A('folder','Home',`${I('home',15)} Home`)}${s.filePath !== 'Home' ? `<span>/</span><span>${E(s.filePath)}</span>` : ''}<span class="desk-result-count">${found.length} items</span></div>${found.length ? `<div class="list">${found.map(f => UI.row({icon:f.kind,title:f.name,sub:f.detail,action:f.kind === 'folder' ? 'desk-folder' : 'desk-file',value:f.name,end:f.kind === 'folder' ? I('chevron-right',16) : ''})).join('')}</div>` : UI.empty('folder','No files found','Try another name or return to Home.')}`;
  }
  function clipboardResults(s) {
    const found = s.clipItems.filter(c => matches(s,c.text));
    return `<div class="desk-toolbar"><span class="hint">${s.clipPaused ? 'History paused' : 'History is on'} · ${s.clipItems.length} items</span><div>${A('clip-pause','',s.clipPaused ? 'Resume' : 'Pause')}${A('clip-clear','', 'Clear history')}</div></div>${s.clipConfirm ? `<div class="desk-confirm"><strong>Clear clipboard history?</strong><p>Remove the sample items from this preview.</p><div class="desk-actions">${A('clip-cancel','','Cancel')}${A('clip-clear-confirm','','Clear history','btn danger')}</div></div>` : ''}${found.length ? `<div class="desk-clips">${found.map(c => `<article class="desk-clip"><button data-action="desk-clip-copy" data-value="${c.id}" class="desk-clip-copy"><span class="desk-clip-meta">${I(c.kind==='Link'?'link':'clipboard',14)} ${c.kind}<span>${c.time}</span></span><span class="desk-clip-text">${E(c.text)}</span></button><button class="icon-button" data-action="desk-clip-delete" data-value="${c.id}" aria-label="Delete clipboard item">${I('trash',16)}</button></article>`).join('')}</div>` : UI.empty('clipboard',s.clipItems.length ? 'No matching items' : 'Your clipboard is clear',s.clipItems.length ? 'Try another search.' : 'Copied text will appear here. This preview uses sample items.')}${s.clipCopied ? `<div class="desk-paste"><span class="hint">Selected sample text</span><p>${E(s.clipCopied)}</p></div>` : ''}${!s.clipItems.length ? A('clip-reset','','Restore sample items') : ''}`;
  }
  function renderSearch(s, forcedTab) {
    init(s); const tab = forcedTab || s.searchTab;
    let body = '';
    if (tab === 'Apps') body = appResults(s);
    if (tab === 'Files') body = fileResults(s);
    if (tab === 'Clipboard') body = clipboardResults(s);
    if (tab === 'Actions') {
      const found = actions.filter(a => matches(s,a[2]+' '+a[3]));
      body = found.length ? `<div class="list">${found.map(a => UI.row({icon:a[1],title:a[2],sub:a[3],route:a[0]})).join('')}</div>` : UI.empty('search','No matching actions','Try “capture”, “focus” or “appearance”.');
    }
    if (tab === 'Windows') {
      const windows = [{name:'Sumi reference',app:'Browser',icon:'globe'}, {name:'Project notes',app:'Code',icon:'code'}, {name:'Your music',app:'Spotify',icon:'music'}].filter(w=>matches(s,w.name+' '+w.app));
      body = windows.length ? `<div class="list">${windows.map(w=>UI.row({icon:w.icon,title:w.name,sub:w.app+' · Workspace 1',action:'desk-window',value:w.name})).join('')}</div>` : UI.empty('layout','No matching windows','Try an app or window name.');
    }
    return `<div class="desk-search-page">${searchHeader(s,tab)}${body}<div class="desk-key-hint"><span><kbd>Tab</kbd> move between controls</span><span><kbd>Enter</kbd> select <kbd>Esc</kbd> close</span></div></div>`;
  }
  function searchInput(s,key) { if (key === 'searchQuery') Sumi.render(); }
  const pages = {
    launcher:{title:'Search',width:600,render:s=>renderSearch(s),onInput:searchInput},
    files:{title:'Files',width:600,render:s=>renderSearch(s,'Files'),onInput:searchInput},
    clipboard:{title:'Clipboard',width:600,render:s=>renderSearch(s,'Clipboard'),onInput:searchInput},
    appearance:{title:'Appearance',width:640,render(s) {
      init(s);
      return `${intro('Make yourself at home.','A different atmosphere. The same familiar desktop.')}<div class="desk-wallpapers">${[['dusk','Dusk','Warm light, soft edges'],['alpine','Alpine','A little room to breathe'],['graphite','Graphite','Quiet, after hours']].map(([id,name,detail])=>`<button class="desk-wallpaper ${s.wallpaper===id?'selected':''}" data-action="desk-wallpaper" data-value="${id}" aria-pressed="${s.wallpaper===id}"><span class="desk-wallpaper-art ${id}"><span class="desk-mini-island"></span>${s.wallpaper===id?`<span class="desk-wallpaper-check">${I('check',14)}</span>`:''}</span><span class="desk-wallpaper-name">${name}</span><small>${detail}</small></button>`).join('')}</div><div class="desk-settings-line"><div><strong>Accent color</strong><p class="hint">A small detail, across the desktop.</p></div><div class="desk-swatches">${['#8ab4ff','#a6d5b4','#dcb48d','#c6b2ee','#eeeeef'].map(c=>`<button class="desk-swatch ${s.accent===c?'selected':''}" style="--swatch:${c}" data-action="desk-accent" data-value="${c}" aria-label="${({'#8ab4ff':'Blue','#a6d5b4':'Sage','#dcb48d':'Warm sand','#c6b2ee':'Lilac','#eeeeef':'Silver'})[c]} accent" aria-pressed="${s.accent===c}">${s.accent===c?I('check',14):''}</button>`).join('')}</div></div><div class="list">${UI.row({icon:'layout',title:'Island shape',sub:'Attached to the edge, or floating just below it',end:`<div class="segmented">${A('shape','notch','Notch',s.shape==='notch'?'selected':'')}${A('shape','floating','Floating',s.shape==='floating'?'selected':'')}</div>`})}${UI.toggle('reduced','Reduce motion',s.reduced,'sparkles','Quieter transitions throughout the preview')}${UI.row({icon:'layout',title:'Desktop widgets',sub:'Choose what stays in sight',route:'widgets'})}</div><p class="hint desk-footnote">Changes apply to this reference only. Your live wallpaper and preferences stay untouched.</p>`;
    }},
    widgets:{title:'Desktop widgets',width:580,render(s) {
      init(s);
      return `${intro('A few things worth keeping in sight.','Shape your desktop around the things that matter today.')}<div class="section-title">Daily priorities</div><div class="desk-priorities">${[1,2,3].map(i=>`<div class="desk-priority"><button class="desk-check ${s['priorityDone'+i]?'done':''}" data-toggle="priorityDone${i}" aria-label="${s['priorityDone'+i]?'Mark incomplete':'Complete'} priority ${i}" aria-pressed="${s['priorityDone'+i]}">${s['priorityDone'+i]?I('check',13):''}</button><input class="field ${s['priorityDone'+i]?'done':''}" data-bind="priority${i}" aria-label="Priority ${i}" placeholder="Something worth doing" value="${E(s['priority'+i])}"></div>`).join('')}</div><div class="desk-inline-end">${A('clear-done','','Clear completed')}</div><div class="section-title">Next deadline</div><div class="desk-deadline-fields"><input class="field" data-bind="deadlineTitle" aria-label="Deadline title" placeholder="Give it a name" value="${E(s.deadlineTitle)}"><input class="field" type="date" data-bind="deadlineDate" aria-label="Deadline date" value="${E(s.deadlineDate)}"></div><div class="section-title">Visible widgets</div><div class="list">${UI.toggle('widgetClock','Clock',s.widgetClock,'clock','Time and date, at a glance')}${UI.toggle('widgetSpotify','Now playing',s.widgetSpotify,'music','Artwork and a little room for music')}${UI.toggle('widgetPriorities','Priorities',s.widgetPriorities,'check','Your three things for today')}${UI.toggle('widgetDeadline','Deadline',s.widgetDeadline,'calendar','The next thing on the horizon')}</div><div class="desk-settings-line"><span>Placement</span><div class="segmented">${A('layout','curated','Curated',s.widgetLayout==='curated'?'selected':'')}${A('layout','minimal','Minimal',s.widgetLayout==='minimal'?'selected':'')}</div></div><div class="desk-save"><span class="hint">${s.widgetsSaved?'Saved in this preview':'Edits are kept while you explore.'}</span>${A('widgets-save','','Save changes','btn primary')}</div>`;
    }},
    help:{title:'Keyboard shortcuts',width:560,render(s) {
      init(s);
      const shortcuts = [
        ['Find an app','Super','Space'],['Notification Inbox','Super','N'],['Search within the island','Ctrl','K'],['Close the island','Esc'],['Move between controls','Tab'],['Activate a control','Enter'],['Switch search category','Alt','1–5']
      ];
      return `${intro('A little less reaching.','Your everyday tools, right under your fingertips.')}<div class="list desk-shortcuts">${shortcuts.map(([label,...keys])=>`<div class="desk-shortcut"><span>${label}</span><span>${keys.map(k=>`<kbd>${k}</kbd>`).join('')}</span></div>`).join('')}</div><p class="hint desk-footnote">Desktop shortcuts are shown for the native shell. In this browser preview, use Tab, Enter, Escape, and Ctrl/⌘ K.</p><div class="section-title">Explore Sumi</div><div class="list">${UI.row({icon:'settings',title:'Controls',sub:'Connections, sound, brightness, and more',route:'controls'})}${UI.row({icon:'sparkles',title:'Thursday',sub:'Speak, see what was heard, and continue',route:'thursday'})}${UI.row({icon:'code',title:'Codex status',sub:'A read-only view of your local agent',route:'codex'})}</div>`;
    }},
    codex:{title:'Codex',width:580,render(s) {
      init(s);
      const mode = s.codexView;
      const picker = `<div class="desk-state-picker"><span class="hint">Preview state</span><div class="segmented">${['available','stale','unavailable'].map(v=>A('codex-state',v,v[0].toUpperCase()+v.slice(1),mode===v?'selected':'')).join('')}</div></div>`;
      if (mode === 'unavailable') return `${picker}${UI.empty('code','Codex is unavailable','Start the local status service to see your agent here. This reference is not connected to a live service.')}<div class="desk-centered">${A('codex-state','available','Preview connected state','btn primary')}</div>`;
      return `${picker}<div class="desk-codex-heading"><span class="desk-appicon gray">${I('code',25)}</span><div><h2>${mode==='stale'?'Connection paused':'Your workspace, in view.'}</h2><p class="hint">${mode==='stale'?'Last received 12 minutes ago. Activity may be outdated.':'Connected · Sample local status'}</p></div><span class="desk-status ${mode==='stale'?'stale':''}"></span></div><div class="desk-codex-task"><div class="desk-eyeline">Sumi desktop <span>${mode==='stale'?'Last known state':'Working'}</span></div><h3>Build the interactive reference</h3><p>${mode==='stale'?'Waiting for a fresh update before showing live progress.':'Bringing the full control hub, music, and Thursday into one coherent design.'}</p><div class="desk-task-progress"><span style="width:68%"></span></div><div class="desk-task-meta"><span>Design & implementation</span><span>4 of 6 steps</span></div></div><div class="section-title">Recent activity</div><div class="desk-timeline"><div><span class="desk-timeline-dot"></span><strong>Fixed clock layout defined</strong><small>Sample event · 2 min ago</small></div><div><span class="desk-timeline-dot"></span><strong>Full Controls routes preserved</strong><small>Sample event · 5 min ago</small></div><div><span class="desk-timeline-dot"></span><strong>Reference workspace opened</strong><small>Sample event · 9 min ago</small></div></div><p class="hint desk-footnote">Read-only status. Sample activity is never presented as your real agent’s progress.</p>`;
    }}
  };
  window.SumiPages = Object.assign(window.SumiPages || {}, pages);
  const refresh = () => { Sumi.applyPreferences?.(); Sumi.render(); };
  window.SumiActions = Object.assign(window.SumiActions || {}, {
    'desk-tab'(s,value) { s.searchQuery=''; s.filePreview=''; s.searchTab=value; Sumi.go(value==='Files'?'files':value==='Clipboard'?'clipboard':'launcher'); },
    'desk-launch'(s,value) { const app=apps.find(a=>a.name===value); if(app?.route) Sumi.go(app.route); else Sumi.toast(`${value} opened · preview only`); },
    'desk-window'(s,value) { Sumi.toast(`Switched to ${value} · preview only`); },
    'desk-folder'(s,value) { s.filePath=value; s.searchQuery=''; Sumi.go('files'); },
    'desk-file'(s,value) { s.filePreview=value; s.searchQuery=''; Sumi.go('files'); },
    'desk-file-close'(s) { s.filePreview=''; Sumi.render(); },
    'desk-clip-copy'(s,value) { s.clipCopied=s.clipItems.find(c=>c.id===value)?.text || ''; Sumi.render(); Sumi.toast('Sample text selected. Your system clipboard was not changed.'); },
    'desk-clip-delete'(s,value) { s.clipItems=s.clipItems.filter(c=>c.id!==value); Sumi.render(); },
    'desk-clip-pause'(s) { s.clipPaused=!s.clipPaused; Sumi.render(); },
    'desk-clip-clear'(s) { s.clipConfirm=true; Sumi.render(); },
    'desk-clip-cancel'(s) { s.clipConfirm=false; Sumi.render(); },
    'desk-clip-clear-confirm'(s) { s.clipItems=[]; s.clipConfirm=false; s.clipCopied=''; Sumi.render(); },
    'desk-clip-reset'(s) { s.clipItems=clipSamples.map(c=>({...c})); Sumi.render(); },
    'desk-wallpaper'(s,value) { s.wallpaper=value; refresh(); },
    'desk-accent'(s,value) { s.accent=value; document.documentElement.style.setProperty('--accent',value); refresh(); },
    'desk-shape'(s,value) { s.shape=value; refresh(); },
    'desk-layout'(s,value) { s.widgetLayout=value; refresh(); },
    'desk-clear-done'(s) { [1,2,3].forEach(i=>{if(s['priorityDone'+i]){s['priority'+i]='';s['priorityDone'+i]=false;}}); refresh(); },
    'desk-widgets-save'(s) { s.widgetsSaved=true; refresh(); Sumi.toast('Widget changes saved in this preview.'); },
    'desk-codex-state'(s,value) { s.codexView=value; Sumi.render(); }
  });
  const styles = document.createElement('style');
  styles.textContent = `
    .desk-search{display:flex;align-items:center;gap:12px;padding:3px 0 17px;color:#a9a9b1}.desk-search .field{flex:1;min-width:0;border:0!important;background:transparent!important;padding:10px 0;font-size:17px}.desk-search kbd{flex:none}.desk-tabs{display:flex;gap:4px;border-bottom:1px solid #ffffff13;padding-bottom:12px;margin-bottom:18px}.desk-tab{flex:1;padding:8px 5px;border:0;border-radius:9px;background:transparent;color:#aaaab3;font-size:12px;cursor:pointer}.desk-tab.selected{background:#ffffff19;color:white}.desk-tab:hover{color:white;background:#ffffff10}.desk-apps{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;padding:6px 0 22px}.desk-app{display:flex;flex-direction:column;gap:10px;align-items:center;min-width:0;background:none;border:0;color:#e9e9ed;font-size:11px;cursor:pointer;padding:8px 0;border-radius:12px}.desk-app:hover{background:#ffffff0b}.desk-appicon{width:46px;height:46px;border-radius:13px;display:inline-flex;align-items:center;justify-content:center;flex:none;background:#24252b;color:#e3e3e8}.desk-appicon.blue{background:#254974;color:#b8d9ff}.desk-appicon.green{background:#245439;color:#a1edba}.desk-appicon.purple{background:#494062;color:#e0cbff}.desk-appicon.amber{background:#625037;color:#ffe0ad}.desk-appicon.gray{background:#323238;color:#eeeeef}.desk-key-hint{display:flex;justify-content:space-between;gap:10px;padding-top:20px;color:#888892;font-size:10px}.desk-key-hint kbd{font-size:9px}.desk-breadcrumb{display:flex;gap:10px;align-items:center;color:#a4a4ad;margin-bottom:10px;font-size:12px}.desk-breadcrumb .btn{padding:6px 9px;min-height:30px}.desk-result-count{margin-left:auto;color:#888892}.desk-file-head,.desk-toolbar,.desk-actions,.desk-inline-end,.desk-save{display:flex;align-items:center;justify-content:space-between;gap:12px}.desk-file-head{margin-bottom:14px}.desk-toolbar{margin:0 0 14px}.desk-toolbar>div{display:flex;gap:4px}.desk-toolbar .btn{font-size:11px;padding:7px 10px;min-height:30px}.desk-document{background:#1b1c20;border-radius:16px;padding:22px}.desk-document-title{display:flex;align-items:center;gap:12px;font-size:15px}.desk-document pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;font-size:13px;line-height:1.85;color:#bcbcc5;margin-top:22px}.desk-clips{display:flex;flex-direction:column;gap:8px}.desk-clip{display:flex;align-items:center;gap:8px;background:#191a1e;border-radius:14px;padding-right:8px}.desk-clip-copy{border:0;background:transparent;text-align:left;color:inherit;cursor:pointer;padding:15px 16px;flex:1;min-width:0;border-radius:14px}.desk-clip-copy:hover{background:#ffffff07}.desk-clip-meta{display:flex;align-items:center;gap:6px;color:#9898a3;font-size:10px}.desk-clip-meta>span{margin-left:auto}.desk-clip-text{display:block;overflow-wrap:anywhere;font-size:13px;line-height:1.5;color:#e4e4e9;margin-top:9px}.desk-confirm{background:#232327;padding:18px;border-radius:14px;margin-bottom:12px;font-size:14px}.desk-confirm p{font-size:12px;color:#b0b0bb;margin:8px 0 16px}.desk-actions{justify-content:flex-end}.desk-paste{padding:14px 0 0}.desk-paste p{font-size:12px;line-height:1.5;overflow-wrap:anywhere;color:#c7c7d0}.desk-wallpapers{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:24px 0 22px}.desk-wallpaper{padding:0;border:0;background:none;text-align:left;color:inherit;cursor:pointer;min-width:0;border-radius:14px}.desk-wallpaper-art{height:100px;position:relative;display:block;overflow:hidden;border-radius:13px;box-shadow:inset 0 0 0 1px #ffffff16;transition:box-shadow .15s}.desk-wallpaper.selected .desk-wallpaper-art{box-shadow:inset 0 0 0 2px #ededf1}.desk-wallpaper-art.dusk{background:radial-gradient(ellipse at 78% 90%,#c48764,transparent 60%),linear-gradient(145deg,#65747a,#9a8d83 55%,#bf987c)}.desk-wallpaper-art.alpine{background:radial-gradient(ellipse at 45% 110%,#879eab,transparent 65%),linear-gradient(145deg,#d0dadd,#8dabb0 55%,#527777)}.desk-wallpaper-art.graphite{background:radial-gradient(ellipse at 55% 120%,#72757e,transparent 60%),linear-gradient(140deg,#282a33,#474b56)}.desk-mini-island{position:absolute;top:0;left:33%;width:34%;height:12px;background:#080809;border-radius:0 0 7px 7px}.desk-wallpaper-check{position:absolute;right:8px;bottom:8px;background:#f0f0f3;color:#171719;display:grid;place-items:center;width:21px;height:21px;border-radius:50%}.desk-wallpaper-name{display:block;font-size:13px;font-weight:600;margin:11px 0 3px}.desk-wallpaper small{font-size:10px;color:#9898a3}.desk-settings-line{display:flex;gap:16px;align-items:center;justify-content:space-between;margin:18px 0;font-size:13px}.desk-settings-line strong{font-size:13px}.desk-settings-line p{margin:5px 0 0}.desk-swatches{display:flex;gap:9px}.desk-swatch{display:grid;place-items:center;width:23px;height:23px;border-radius:50%;border:0;background:var(--swatch);cursor:pointer;color:#111}.desk-swatch.selected{outline:1px solid #e9e9ef;outline-offset:3px}.desk-footnote{margin:17px 0 0;line-height:1.65;font-size:11px}.desk-priorities{display:flex;flex-direction:column;gap:8px}.desk-priority{display:flex;align-items:center;gap:11px}.desk-priority .field{flex:1;min-width:0}.desk-priority .field.done{text-decoration:line-through;color:#90909a}.desk-check{display:grid;place-items:center;flex:none;width:22px;height:22px;border:1px solid #5a5b64;background:transparent;border-radius:7px;color:#16171a;cursor:pointer}.desk-check.done{background:#b2c7a7;border-color:#b2c7a7}.desk-inline-end{justify-content:flex-end;margin-top:8px}.desk-inline-end .btn{font-size:11px}.desk-deadline-fields{display:grid;grid-template-columns:1fr 150px;gap:10px}.desk-deadline-fields input{min-width:0;color-scheme:dark}.desk-save{margin-top:20px;padding-top:17px;border-top:1px solid #ffffff12}.desk-shortcut{display:flex;align-items:center;justify-content:space-between;gap:15px;padding:15px 4px;border-bottom:1px solid #ffffff0b;font-size:13px}.desk-shortcut:last-child{border:0}.desk-shortcut>span:last-child{display:flex;gap:5px}.desk-shortcut kbd{font-size:11px;padding:5px 8px;min-width:27px;text-align:center;background:#2a2a30;color:#c3c3cc;border:1px solid #ffffff13;border-radius:6px;font-family:inherit}.desk-state-picker{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:24px}.desk-state-picker .segmented button{font-size:11px;padding:7px 9px}.desk-centered{text-align:center;margin:16px 0}.desk-codex-heading{display:flex;align-items:center;gap:14px;margin-bottom:24px}.desk-codex-heading h2{font-size:17px;letter-spacing:-.02em;margin:0 0 5px}.desk-codex-heading p{margin:0;font-size:11px}.desk-status{width:7px;height:7px;border-radius:50%;background:#9bd5a8;margin-left:auto}.desk-status.stale{background:#d7b57f}.desk-codex-task{background:#1d1e23;border-radius:17px;padding:21px}.desk-eyeline{display:flex;justify-content:space-between;color:#a6a6b2;font-size:11px}.desk-eyeline>span{color:#b5c7aa}.desk-codex-task h3{font-size:17px;letter-spacing:-.01em;margin:17px 0 7px}.desk-codex-task p{font-size:12px;line-height:1.65;color:#aaaab6;margin:0 0 20px}.desk-task-progress{height:3px;background:#3a3b43;border-radius:3px;overflow:hidden}.desk-task-progress>span{display:block;height:100%;background:#d9dce3}.desk-task-meta{display:flex;justify-content:space-between;font-size:10px;color:#95959f;margin-top:9px}.desk-timeline{padding:0 4px}.desk-timeline>div{position:relative;padding:8px 0 15px 24px}.desk-timeline strong{font-size:12px;font-weight:500;display:block}.desk-timeline small{display:block;font-size:10px;color:#888894;margin-top:5px}.desk-timeline-dot{position:absolute;left:0;top:11px;width:6px;height:6px;border-radius:50%;background:#626571}.desk-timeline>div:not(:last-child):before{position:absolute;content:'';left:2px;top:22px;width:1px;height:28px;background:#303138}
    @media(max-width:600px){.desk-apps{grid-template-columns:repeat(3,1fr);gap:8px}.desk-wallpapers{gap:9px}.desk-wallpaper-art{height:76px}.desk-wallpaper small{display:none}.desk-settings-line{flex-wrap:wrap}.desk-key-hint{flex-wrap:wrap}.desk-deadline-fields{grid-template-columns:1fr}.desk-state-picker{flex-wrap:wrap}.desk-search kbd{display:none}.desk-toolbar{flex-wrap:wrap}.desk-tab{font-size:11px}.desk-appicon{width:42px;height:42px}}
  `;
  document.head.append(styles);
})();
