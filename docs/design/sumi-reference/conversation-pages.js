/* Sumi reference: local, illustrative conversation and information surfaces. */
(() => {
  const style = document.createElement('style');
  style.textContent = `
    .convo-topline,.convo-actions,.inbox-toolbar,.calendar-topline{display:flex;align-items:center;justify-content:space-between;gap:12px}
    .convo-topline{margin-bottom:20px}.convo-topline .segmented{display:flex;gap:3px}.convo-topline .segmented button{font-size:12px}
    .convo-presence{display:flex;align-items:center;gap:7px;color:#b3b5bd;font-size:12px}.convo-presence i{width:6px;height:6px;background:#5bd795;border-radius:50%}
    .conversation-log{display:flex;flex-direction:column;gap:19px;margin:0 0 20px;min-height:104px}
    .chat-message{max-width:91%;font-size:14px;line-height:1.55;overflow-wrap:anywhere}.chat-message.user{align-self:flex-end;background:#25262b;border-radius:18px 18px 5px 18px;padding:12px 16px}.chat-message.assistant{align-self:flex-start;padding:0 2px}
    .chat-byline{display:flex;align-items:center;gap:7px;font-size:11px;color:#b4b4bf;margin-bottom:6px}.chat-byline svg{color:#c2b7f5}.chat-message p{margin:0;white-space:pre-wrap}.chat-message.assistant p{color:#e2e2e7}
    .heard-strip{display:flex;align-items:flex-start;gap:10px;padding:14px 0;border-top:1px solid #ffffff13;border-bottom:1px solid #ffffff13;margin:2px 0 18px;font-size:12px;color:#c3c3cc}.heard-strip>svg{flex:none;color:#b7a9ed}.heard-strip p{margin:2px 0 0;line-height:1.5;color:#f0f0f4;white-space:pre-wrap}.heard-strip .icon-button{margin-left:auto;flex:none}
    .convo-task{background:#1d1e23;border-radius:16px;padding:16px;margin-bottom:16px}.convo-task-head{display:flex;align-items:center;gap:10px;font-size:13px;font-weight:600}.convo-task p{font-size:12px;line-height:1.5;color:#bdbdc7;margin:8px 0 12px}.convo-task .convo-actions{justify-content:flex-start;gap:8px}.convo-task .btn{min-height:34px;font-size:12px}.task-filenames{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 14px}.task-filenames span{padding:5px 8px;background:#2d2e35;border-radius:6px;font-size:11px;color:#d5d5dc}
    .convo-compose{display:flex;align-items:flex-end;gap:8px;background:#202126;border-radius:18px;padding:10px}.convo-compose textarea{resize:vertical;max-height:110px;min-height:40px;flex:1;min-width:0;background:none;border:0;padding:10px 4px;color:#f5f5f7;font:inherit;font-size:13px;outline:none;line-height:1.4}.convo-compose textarea::placeholder{color:#a4a4af}.convo-compose .icon-button{flex:none;width:38px;height:38px}.convo-compose .send-button{background:#f1f1f5;color:#151519;border-radius:12px}.convo-compose .send-button:disabled{opacity:.35;cursor:default}
    .convo-footnote{display:flex;justify-content:space-between;gap:12px;font-size:10px;color:#9b9ca8;margin-top:9px}.convo-footnote button{background:none;border:0;color:#b4accd;padding:0;font:inherit;cursor:pointer}
    .correction-editor{margin-bottom:18px;padding:15px;background:#22212a;border-radius:16px}.correction-editor label{display:block;font-size:12px;color:#c4bbdf;margin-bottom:8px}.correction-editor textarea{width:100%;box-sizing:border-box;min-height:70px;resize:vertical;margin-bottom:10px}.correction-editor .convo-actions{justify-content:flex-end}
    .calendar-topline{margin-bottom:20px}.calendar-topline h2{font-size:19px;letter-spacing:-.025em;margin:0}.calendar-navigation{display:flex;gap:4px;align-items:center}.calendar-navigation .icon-button{width:34px;height:34px}.calendar-navigation .btn{min-height:32px;font-size:12px}
    .calendar-weekdays,.calendar-days{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;text-align:center}.calendar-weekdays{margin-bottom:10px;color:#a7a7b3;font-size:11px}.calendar-day{height:42px;width:100%;padding:0;background:transparent;color:#e4e4e9;border:0;border-radius:13px;font-family:inherit;font-size:13px;cursor:pointer;position:relative}.calendar-day:hover{background:#24252a}.calendar-day.adjacent{color:#73747e}.calendar-day.today{color:#b9acf9}.calendar-day.today:after{position:absolute;content:'';width:4px;height:4px;background:#b7a5ff;border-radius:50%;bottom:5px;left:calc(50% - 2px)}.calendar-day.selected{background:#eceaf3;color:#1a1920;font-weight:600}.calendar-day.selected:after{background:#5e458d}.calendar-selection{border-top:1px solid #ffffff15;margin-top:20px;padding-top:16px;display:flex;gap:12px;align-items:center}.calendar-selection .date-number{font-size:28px;line-height:1;letter-spacing:-.025em;color:#e2d9ff}.calendar-selection p{margin:3px 0;font-size:12px;color:#aeadbb}.calendar-selection strong{font-size:13px;font-weight:500}
    .inbox-toolbar{margin-bottom:16px}.inbox-toolbar .btn{min-height:32px;padding:0 10px;font-size:11px}.inbox-count{font-size:12px;color:#aaaab6}.inbox-toolbar-actions{display:flex;gap:4px}.notice-list{display:flex;flex-direction:column;gap:10px}.notice-card{position:relative;display:flex;background:#202126;border-radius:18px;padding:14px;gap:12px}.notice-open{display:flex;gap:12px;flex:1;text-align:left;background:none;border:0;color:inherit;padding:0;min-width:0;cursor:pointer;font:inherit}.notice-app-icon{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:#303039;flex:none;color:#ded9f3}.notice-copy{min-width:0;flex:1}.notice-byline{display:flex;align-items:center;gap:6px;color:#b8b8c3;font-size:10px;margin-bottom:5px}.notice-byline .notice-time{margin-left:auto}.notice-unread{width:5px;height:5px;border-radius:50%;background:#afa0ee}.notice-copy h3{font-size:13px;font-weight:600;margin:0 0 4px;line-height:1.4}.notice-copy p{font-size:12px;color:#b9bac4;line-height:1.45;margin:0}.notice-card .icon-button{width:26px;height:26px;flex:none;color:#aaaab7}
    .notice-detail{padding:4px 2px 10px}.notice-detail .notice-app-icon{width:46px;height:46px;border-radius:14px;margin-bottom:18px}.notice-detail h2{font-size:23px;line-height:1.25;letter-spacing:-.03em;margin:8px 0 12px}.notice-detail p{font-size:14px;line-height:1.65;color:#c6c6d0;margin:0 0 22px}.notice-detail .convo-actions{justify-content:flex-start;flex-wrap:wrap}.undo-notice{display:flex;justify-content:space-between;align-items:center;gap:10px;background:#25242d;border-radius:12px;padding:10px 12px;font-size:12px;color:#c7c2d8;margin-top:12px}
    @media(max-width:520px){.calendar-days,.calendar-weekdays{gap:3px}.calendar-day{height:36px}.convo-topline{gap:6px}.convo-presence{font-size:10px}.convo-footnote{font-size:9px}.chat-message{max-width:96%}.notice-card{padding:12px}.inbox-toolbar-actions{gap:0}.inbox-toolbar .btn{padding:0 7px}.convo-topline .segmented button{padding:7px 9px}}
  `;
  document.head.appendChild(style);

  const E = value => window.UI.esc(value ?? '');
  const I = (name, size = 18) => window.UI.icon(name, size);
  const action = (name, label, value = '', cls = 'btn') => `<button type="button" class="${cls}" data-action="convo-${name}" data-value="${E(value)}">${label}</button>`;
  const iconAction = (name, icon, label, value = '') => `<button type="button" class="icon-button" data-action="convo-${name}" data-value="${E(value)}" aria-label="${E(label)}" title="${E(label)}">${I(icon)}</button>`;
  const TODAY = new Date(2026, 10, 10);
  const dateKey = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
  const parseDate = key => { const a = key.split('-').map(Number); return new Date(a[0],a[1]-1,a[2]); };
  const init = s => {
    s.chatView ??= 'conversation';
    s.chatDraft ??= '';
    s.chatMessages ??= [
      {role:'user',text:'Help me make room for some focused work.'},
      {role:'assistant',text:'A quiet workspace, a little music, and one thing at a time. Want to start a 25-minute focus session?'}
    ];
    s.chatTask ??= null;
    s.chatCorrection ??= false;
    s.chatCorrectedText ??= '';
    s.calendarOffset ??= 0;
    s.calendarSelected ??= dateKey(TODAY);
    s.notifications ??= [];
  };
  const messageHTML = msg => `<article class="chat-message ${msg.role === 'user' ? 'user' : 'assistant'}">${msg.role === 'assistant' ? `<div class="chat-byline">${I('sparkles',13)} Thursday</div>` : ''}<p>${E(msg.text)}</p></article>`;
  function taskHTML(s) {
    const t = s.chatTask;
    if (!t) return '';
    const waiting = t.status === 'approval';
    const running = t.status === 'running';
    const status = {approval:'Your approval is needed',running:'Working on your request',done:'Task complete',cancelled:'Task cancelled'}[t.status];
    return `<section class="convo-task" aria-label="Thursday task"><div class="convo-task-head">${I(waiting?'shield':running?'loader':t.status==='done'?'check':'x',18)} ${E(status)}</div><p>${E(t.detail)}</p>${waiting?'<div class="task-filenames"><span>reference.png</span><span>notes.md</span><span>layout.svg</span></div>':''}<div class="convo-actions">${waiting ? action('approve','Approve move','','btn primary') + action('decline','Decline','','btn quiet') : running ? action('cancel-task','Cancel task','','btn quiet') : action('clear-task','Dismiss','','btn quiet')}</div></section>`;
  }
  function thursday(s) {
    init(s);
    const history = s.chatView === 'history';
    const listening = ['listening','transcribing'].includes(s.voicePhase);
    const phaseText = {listening:'Listening',transcribing:'Transcribing',heard:'Heard',reply:'Reply',error:'Could not hear you'}[s.voicePhase] || 'Heard';
    const transcript = s.transcript || s.lastHeard;
    return `<div class="convo-topline"><div class="segmented" role="group" aria-label="Thursday view">${action('view','Conversation','conversation',`btn ${history?'quiet':'selected'}`)}${action('view','History','history',`btn ${history?'selected':'quiet'}`)}</div><span class="convo-presence"><i></i> Local demo</span></div>${history ? historyHTML(s) : `
      <div class="conversation-log" aria-live="polite">${s.chatMessages.map(messageHTML).join('')}</div>
      ${listening || transcript ? `<div class="heard-strip">${I('mic')}<div><span>${E(phaseText)}${listening?' · live draft':''}</span><p>${E(transcript || 'Say something. Your words will appear here.')}</p></div>${!listening && transcript ? iconAction('edit-heard','edit','Correct what Thursday heard') : ''}</div>` : ''}
      ${s.chatCorrection ? `<div class="correction-editor"><label for="heard-correction">Correct what Thursday heard</label><textarea id="heard-correction" class="field" data-bind="chatCorrectedText">${E(s.chatCorrectedText)}</textarea><div class="convo-actions">${action('cancel-correction','Cancel','','btn quiet')}${action('save-correction','Use correction','','btn primary')}</div></div>`:''}
      ${taskHTML(s)}
      <div class="convo-compose">${iconAction('voice','mic','Try a sample voice conversation')}<textarea id="conversation-draft" data-bind="chatDraft" rows="1" placeholder="Ask Thursday anything…" aria-label="Message Thursday">${E(s.chatDraft)}</textarea><button type="button" class="icon-button send-button" data-action="convo-send" aria-label="Send sample message" ${s.chatDraft.trim()?'':'disabled'}>${I('arrow-up',19)}</button></div>
      <div class="convo-footnote"><span>Sample conversation · no messages leave this preview</span>${action('approval-demo','Try an approval','','')}</div>
    `}`;
  }
  function historyHTML(s) {
    const history = [
      ['focus','A little space to focus','Today · 9:34 AM','Help me make room for some focused work.'],
      ['workspace','A quieter workspace','Yesterday · 6:12 PM','Keep notifications quiet while I work.'],
      ['files','Make room for new ideas','Monday · 4:28 PM','Help me organize my reference files.']
    ];
    return `<p class="hint" style="margin-bottom:16px">Pick up where you left off.</p><div class="list">${history.map(([id,title,sub])=>UI.row({icon:'message-circle',title,sub,action:'convo-open-history',value:id})).join('')}</div><div style="margin-top:18px">${action('new-chat',`${I('plus',16)} New conversation`,'','btn quiet')}</div>`;
  }
  function calendar(s) {
    init(s);
    const month = new Date(TODAY.getFullYear(),TODAY.getMonth()+s.calendarOffset,1);
    const start = new Date(month.getFullYear(),month.getMonth(),1-((month.getDay()+6)%7));
    const selected = parseDate(s.calendarSelected);
    const days = Array.from({length:42},(_,i)=>{
      const d = new Date(start.getFullYear(),start.getMonth(),start.getDate()+i), key=dateKey(d);
      const classes=['calendar-day',d.getMonth()!==month.getMonth()?'adjacent':'',key===dateKey(TODAY)?'today':'',key===s.calendarSelected?'selected':''].filter(Boolean).join(' ');
      return `<button type="button" class="${classes}" data-action="convo-select-date" data-value="${key}" aria-label="${E(d.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'}))}" aria-pressed="${key===s.calendarSelected}" ${key===dateKey(TODAY)?'aria-current="date"':''}>${d.getDate()}</button>`;
    }).join('');
    return `<div class="calendar-topline"><h2>${E(month.toLocaleDateString('en-US',{month:'long',year:'numeric'}))}</h2><div class="calendar-navigation">${iconAction('calendar-month','chevron-left','Previous month','-1')}${action('calendar-today','Today','','btn quiet')}${iconAction('calendar-month','chevron-right','Next month','1')}</div></div><div class="calendar-weekdays" aria-hidden="true">${['M','T','W','T','F','S','S'].map(v=>`<span>${v}</span>`).join('')}</div><div class="calendar-days" role="group" aria-label="Calendar dates">${days}</div><div class="calendar-selection"><span class="date-number tabular">${selected.getDate()}</span><div><strong>${E(selected.toLocaleDateString('en-US',{weekday:'long',month:'long'}))}</strong><p>Local calendar · no account connected</p></div></div>`;
  }
  function inbox(s) {
    init(s);
    const count = s.notifications.length;
    const unread = s.notifications.filter(n=>!n.read).length;
    return `<div class="inbox-toolbar"><span class="inbox-count">${count ? `${unread} unread · ${count} total` : 'All caught up'}</span><div class="inbox-toolbar-actions">${count? action('read-all','Mark all read','','btn quiet')+action('clear-inbox','Clear all','','btn quiet'):''}</div></div>${count?`<div class="notice-list">${s.notifications.map(n=>`<article class="notice-card"><button type="button" class="notice-open" data-action="convo-open-notification" data-value="${n.id}" aria-label="Open ${E(n.title)}"><span class="notice-app-icon">${I(n.app==='Calendar'?'calendar':'folder')}</span><span class="notice-copy"><span class="notice-byline">${!n.read?'<i class="notice-unread"></i>':''}${E(n.app)}<span class="notice-time">${E(n.time)}</span></span><h3>${E(n.title)}</h3><p>${E(n.body)}</p></span></button>${iconAction('dismiss-notification','x',`Dismiss ${n.title}`,n.id)}</article>`).join('')}</div>`:UI.empty('bell','A moment of quiet','Your notifications will be here when something needs your attention.')}${s.lastDismissed?.length?`<div class="undo-notice"><span>${s.lastDismissed.length===1?'Notification dismissed':'Notifications cleared'}</span>${action('undo-dismiss','Undo','','btn quiet')}</div>`:''}<div style="margin-top:18px">${action('sample-notification',`${I('plus',14)} Add sample notification`,'','btn quiet')}</div>`;
  }
  function notification(s) {
    init(s);
    const n = s.notifications.find(n=>String(n.id)===String(s.notificationId)) || s.notifications[0];
    if (!n) return UI.empty('bell','This notification was dismissed','Your Inbox is up to date.')+`<div style="margin-top:16px"><button type="button" class="btn quiet" data-route="inbox">Back to Inbox</button></div>`;
    return `<article class="notice-detail"><div class="notice-app-icon">${I(n.app==='Calendar'?'calendar':'folder',24)}</div><span class="hint">${E(n.app)} · ${E(n.time)} ago</span><h2>${E(n.title)}</h2><p>${E(n.body)}</p><div class="convo-actions">${action('notification-primary',n.app==='Calendar'?'Open calendar':'Show in Files',n.id,'btn primary')}${action('toggle-read',n.read?'Mark unread':'Mark read',n.id,'btn quiet')}${action('dismiss-detail','Dismiss',n.id,'btn quiet')}</div></article>`;
  }

  window.SumiPages = Object.assign(window.SumiPages || {}, {
    thursday:{title:'Thursday',width:600,render:thursday,onInput(s,key,value){if(key==='chatDraft'){const send=document.querySelector('[data-action="convo-send"]');if(send)send.disabled=!value.trim();}}},
    calendar:{title:'Calendar',width:460,render:calendar},
    inbox:{title:'Inbox',width:540,render:inbox},
    notification:{title:'Notification',width:500,render:notification}
  });
  window.SumiActions = Object.assign(window.SumiActions || {}, {
    'convo-view'(s,value){s.chatView=value;Sumi.render();},
    'convo-open-history'(s,value){init(s);s.chatView='conversation';const content={focus:['Help me make room for some focused work.','A quiet workspace, a little music, and one thing at a time. Want to start a 25-minute focus session?'],workspace:['Keep notifications quiet while I work.','Do Not Disturb keeps the distractions out of your way. You can change it anytime in Controls.'],files:['Help me organize my reference files.','I can help group the reference files. You get to review the move before anything changes.']}[value];s.chatMessages=[{role:'user',text:content[0]},{role:'assistant',text:content[1]}];s.chatTask=null;Sumi.render();},
    'convo-new-chat'(s){Sumi.cancelVoice();init(s);s.chatView='conversation';s.chatMessages=[{role:'assistant',text:'What would you like a hand with?'}];s.chatTask=null;s.transcript='';s.lastHeard='';s.chatDraft='';Sumi.render();},
    'convo-send'(s){init(s);const text=s.chatDraft.trim();if(!text)return;Sumi.cancelVoice();s.transcript='';s.lastHeard='';s.chatDraft='';s.chatMessages.push({role:'user',text});const timer=/focus|timer|minute/i.test(text);const files=/file|move|archive/i.test(text);s.chatMessages.push({role:'assistant',text:timer?'Here is a 25-minute focus session to try. Open Focus to start it in this preview.':files?'I’ve prepared a sample file move. Review the files below before approving it.':'This is a sample reply so you can review how the conversation feels. Your message stays in this local preview.'});if(files)s.chatTask={status:'approval',detail:'Move these 3 sample reference files into the Archive folder?'};else if(timer)s.chatTask={status:'running',detail:'Preparing your 25-minute focus session. You can cancel this sample task.'};Sumi.render();},
    'convo-voice'(s){s.chatView='conversation';Sumi.voiceDemo();},
    'convo-edit-heard'(s){Sumi.cancelVoice();s.chatCorrection=true;s.chatCorrectedText=s.transcript||s.lastHeard||'';Sumi.render();setTimeout(()=>document.querySelector('#heard-correction')?.focus(),0);},
    'convo-cancel-correction'(s){s.chatCorrection=false;Sumi.render();},
    'convo-save-correction'(s){const text=(s.chatCorrectedText||'').trim();if(!text){Sumi.toast('Enter the words Thursday should have heard.');return;}s.transcript=text;s.lastHeard=text;s.chatCorrection=false;s.voicePhase='heard';Sumi.render();Sumi.toast('Corrected transcript saved in this preview.');},
    'convo-approval-demo'(s){init(s);s.chatTask={status:'approval',detail:'Move these 3 sample reference files into the Archive folder?'};Sumi.render();},
    'convo-approve'(s){s.chatTask={status:'done',detail:'The 3 sample files were moved to Archive. No files on your desktop were changed.'};Sumi.render();},
    'convo-decline'(s){s.chatTask={status:'cancelled',detail:'The file move was declined. All sample files stayed where they were.'};Sumi.render();},
    'convo-cancel-task'(s){s.chatTask={status:'cancelled',detail:'The sample task was cancelled. You can start again whenever you’re ready.'};Sumi.render();},
    'convo-clear-task'(s){s.chatTask=null;Sumi.render();},
    'convo-calendar-month'(s,value){s.calendarOffset+=Number(value);Sumi.render();},
    'convo-calendar-today'(s){s.calendarOffset=0;s.calendarSelected=dateKey(TODAY);Sumi.render();},
    'convo-select-date'(s,value){s.calendarSelected=value;Sumi.render();},
    'convo-open-notification'(s,value){s.notificationId=value;const n=s.notifications.find(n=>String(n.id)===String(value));if(n)n.read=true;Sumi.go('notification');},
    'convo-read-all'(s){s.notifications.forEach(n=>n.read=true);Sumi.render();},
    'convo-clear-inbox'(s){s.lastDismissed=[...s.notifications];s.notifications=[];Sumi.render();},
    'convo-dismiss-notification'(s,value){s.lastDismissed=s.notifications.filter(n=>String(n.id)===String(value));s.notifications=s.notifications.filter(n=>String(n.id)!==String(value));Sumi.render();},
    'convo-dismiss-detail'(s,value){s.lastDismissed=s.notifications.filter(n=>String(n.id)===String(value));s.notifications=s.notifications.filter(n=>String(n.id)!==String(value));Sumi.go('inbox');},
    'convo-undo-dismiss'(s){const existing=new Set(s.notifications.map(n=>n.id));s.notifications=[...(s.lastDismissed||[]).filter(n=>!existing.has(n.id)),...s.notifications];s.lastDismissed=[];Sumi.render();},
    'convo-toggle-read'(s,value){const n=s.notifications.find(n=>String(n.id)===String(value));if(n)n.read=!n.read;Sumi.render();},
    'convo-notification-primary'(s,value){const n=s.notifications.find(n=>String(n.id)===String(value));if(n){n.read=true;Sumi.go(n.app==='Calendar'?'calendar':'files');}},
    'convo-sample-notification'(s){s.notifications.unshift({id:Date.now(),app:'Files',title:'Reference ready',body:'Your latest Sumi design reference is ready to review.',time:'Now',read:false});Sumi.render();}
  });
  document.addEventListener('keydown',event=>{
    if(event.target.id==='conversation-draft' && event.key==='Enter' && !event.shiftKey){event.preventDefault();const state=window.Sumi.state; if(state)window.SumiActions['convo-send'](state);}
  });
})();
