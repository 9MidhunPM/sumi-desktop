/* Offline reference controller. All state lives in memory; no desktop APIs are called. */
(() => {
'use strict';
const $=id=>document.getElementById(id), I=UI.icon, E=UI.esc;
const s={route:'controls',mode:'panel',activity:'media',shape:'notch',reduced:false,wallpaper:'alpine',accent:'#8ab4ff',wifi:true,bluetooth:true,dnd:false,night:false,volume:68,brightness:74,playing:true,muted:false,position:81,trackIndex:0,voicePhase:'idle',transcript:'',reply:'',fields:{},widgetClock:true,widgetSpotify:true,widgetPriorities:true,widgetDeadline:false,priority1:'Review the Sumi reference',priority2:'Finish the little things',priority3:'Make time for a walk',priorityDone1:false,priorityDone2:false,priorityDone3:false,deadlineTitle:'Design review',deadlineDate:'2026-11-12',notifications:[{id:1,app:'Calendar',title:'Design review',body:'Your next session starts in 15 minutes.',time:'2m',read:false},{id:2,app:'Files',title:'Export complete',body:'Sumi reference has been saved to Downloads.',time:'8m',read:false}]};
const tracks=[{title:'Weightless',artist:'Marconi Union',album:'Ambient Transmissions Vol. 2',duration:489},{title:'A Walk',artist:'Tycho',album:'Dive',duration:317},{title:'Open Eye Signal',artist:'Jon Hopkins',album:'Immunity',duration:472}];
let history=[],hoverTimer,leaveTimer,toastTimer,replayTimer,voiceGeneration=0,previewHeld=false,lastRoute='',focusOrigin=null,resizeFrame=0;
const track=()=>tracks[s.trackIndex%tracks.length];
const time=seconds=>`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;
const iconButton=(name,label,action,value='',extra='')=>`<button class="icon-button ${extra}" data-action="${action}" data-value="${E(value)}" aria-label="${E(label)}" title="${E(label)}">${I(name)}</button>`;
const routeButton=(name,label,route)=>`<button class="icon-button" data-route="${route}" aria-label="${E(label)}" title="${E(label)}">${I(name,18)}</button>`;
function transport(cls=''){return `<div class="transport ${cls}">${iconButton('previous','Previous track','previous')}${iconButton(s.playing?'pause':'play',s.playing?'Pause music':'Play music','play','','main-play')}${iconButton('next','Next track','next')}</div>`;}
function progress(){return `<input class="progress-track" type="range" aria-label="Playback position" min="0" max="${track().duration}" value="${s.position}" data-range="position" style="background:linear-gradient(to right,#dcdce2 ${s.position/track().duration*100}%,#35353b ${s.position/track().duration*100}%)"><div class="progress-labels"><span data-playtime>${time(s.position)}</span><span data-remaining>−${time(track().duration-s.position)}</span></div>`;}
function connection(ic,key,title,detail,route){return `<div class="connect-line"><button class="connect-icon ${s[key]?'on':''}" data-toggle="${key}" aria-label="${s[key]?'Turn off':'Turn on'} ${title}" aria-pressed="${s[key]}">${I(ic,19)}</button><button class="connect-copy" data-route="${route}"><strong>${title}</strong><small>${E(s[key]?detail:'Off')}</small></button><button class="connection-nav" data-route="${route}" aria-label="${title} settings">${I('chevron-right',13)}</button></div>`;}
function controls(){
 const tools=[['launcher','search','Search'],['clipboard','clipboard','Clipboard'],['appearance','palette','Appearance'],['capture','camera','Capture'],['pomodoro','timer','Focus'],['widgets','layout','Widgets'],['system','cpu','System'],['audio','volume','Sound'],['calendar','calendar','Calendar'],['files','folder','Files'],['codex','code','Codex'],['power','power','Power']];
 return `<div class="controls-top"><div class="module controls-connect">${connection('wifi','wifi','Wi-Fi',s.network||'Studio Wi-Fi','wifi')}${connection('bluetooth','bluetooth','Bluetooth','Studio headphones','bluetooth')}<button class="text-link" data-route="audio" style="margin:3px 3px 5px;display:flex;gap:7px;align-items:center">${I('headphones',13)} Connected devices ${I('chevron-right',11)}</button></div><div class="controls-right"><button class="small-control ${s.dnd?'on':''}" data-toggle="dnd" aria-pressed="${s.dnd}">${I('moon',22)}<strong>Do Not Disturb</strong><span>${s.dnd?'On · a little quiet':'Off'}</span></button><button class="small-control ${s.night?'on':''}" data-toggle="night" aria-pressed="${s.night}">${I('sun',22)}<strong>Night light</strong><span>${s.night?'On · warm display':'Off'}</span></button><button class="battery-strip" data-route="power" aria-label="Battery and power profiles">${I('battery',22)}<strong>82%</strong><small>${s.powerProfile==='performance'?'Performance':s.powerProfile==='power-saver'?'Power saver':'Balanced'}</small>${I('chevron-right',12)}</button></div></div>
 <div class="controls-mid"><div class="module mini-player"><div class="mini-track"><button data-route="media" aria-label="Open full music player" style="padding:0;border-radius:10px">${UI.art(42)}</button><button class="track-copy" data-route="media"><div class="track-title">${E(track().title)}</div><div class="track-artist">${E(track().artist)}</div></button>${UI.wave()}</div>${transport()}</div><div class="module controls-sliders">${UI.range('brightness','Brightness',s.brightness,'sun')}${UI.range('volume','Volume',s.volume,s.muted?'volume-off':'volume')}</div></div>
 <nav class="tool-grid" aria-label="Desktop tools">${tools.map(([route,ic,label])=>`<button class="tool" data-route="${route}">${I(ic)}<span>${label}</span></button>`).join('')}</nav>
 <button class="thursday-entry" data-route="thursday"><span class="voice-orb"></span><span><strong>Ask Thursday</strong><small>${s.transcript?'Heard: '+E(s.transcript):'A thought away. Right here when you need it.'}</small></span>${I('chevron-right',15)}</button>
 <div class="notification-heading"><span>${s.notifications.length?'Recent notifications':'All caught up'}</span><button class="text-link" data-route="inbox">Inbox ${I('chevron-right',11).replace('class="icon"','class="icon" style="display:inline;vertical-align:middle"')}</button></div>${s.notifications.slice(0,1).map(n=>`<button class="notification-inline" data-action="convo-open-notification" data-value="${n.id}"><span class="row-icon">${I(n.app==='Calendar'?'calendar':'folder',17)}</span><span class="row-copy"><strong>${E(n.title)}</strong><small>${E(n.body)}</small></span><time>${E(n.time)}</time></button>`).join('')}`;
}
function media(){return `<div class="full-media"><div class="full-media-track">${UI.art(104)}<div class="track-copy"><div class="track-title">${E(s.longTitle?'A very long song title that still belongs beautifully beside its artwork':track().title)}</div><div class="track-artist">${E(track().artist)}</div><div class="source-line">${I('music',12)} ${E(track().album)}</div></div>${UI.wave()}</div>${progress()}${transport()}<div class="media-utilities">${iconButton('shuffle','Shuffle','shuffle','',''+(s.shuffle?'active':''))}<span class="source-line">${I('headphones',13)} ${E(s.audioOutput||'Studio speakers')}</span>${routeButton('airplay','Choose sound output','audio')}</div>${UI.range('volume','Volume',s.volume,'volume')}<div class="divider"></div><div class="media-footer"><button class="btn quiet" data-toggle="liked">${I('heart',16)} ${s.liked?'Saved to favorites':'Add to favorites'}</button><button class="btn quiet" data-toggle="longTitle">${s.longTitle?'Short title':'Try a long title'}</button></div></div>`;}
window.SumiPages=Object.assign(window.SumiPages||{},{controls:{title:'Controls',width:640,render:controls},media:{title:'Now playing',width:560,render:media}});
const pages=window.SumiPages;
function preserveInput(){const a=document.activeElement;if(!a||!$('island').contains(a))return null;return{selector:a.id?'#'+CSS.escape(a.id):a.dataset.bind?'[data-bind="'+CSS.escape(a.dataset.bind)+'"]':a.dataset.action?'[data-action="'+CSS.escape(a.dataset.action)+'"][data-value="'+CSS.escape(a.dataset.value||'')+'"]':a.dataset.toggle?'[data-toggle="'+CSS.escape(a.dataset.toggle)+'"]':null,start:a.selectionStart,end:a.selectionEnd};}
function restoreInput(saved){if(!saved?.selector)return;const a=$('island').querySelector(saved.selector);if(a){a.focus({preventScroll:true});if(typeof saved.start==='number'&&a.setSelectionRange)try{a.setSelectionRange(saved.start,saved.end)}catch{}}}
function applyPreferences(){
 $('desktop').dataset.wallpaper=['dusk','alpine','graphite'].includes(s.wallpaper)?s.wallpaper:'alpine';$('island').dataset.shape=s.shape==='floating'?'floating':'notch';
 document.body.classList.toggle('reduced',s.reduced);document.body.classList.toggle('night-light',s.night);
 document.documentElement.style.setProperty('--blue',s.accent||'#8ab4ff');
 document.querySelectorAll('.notification-dot').forEach(el=>el.hidden=!s.notifications.some(n=>!n.read));
}
function widgets(){
 $('desktop-widgets').dataset.layout=s.widgetLayout||'curated';
 $('desktop-widgets').innerHTML=`${s.widgetClock?`<button class="desktop-widget widget-time" data-route="calendar"><p class="weekday">Tuesday, 10 November</p><p class="date">09:41<span class="widget-period">AM</span></p><p class="year">A little time for what matters.</p></button>`:''}${s.widgetPriorities?`<div class="desktop-widget widget-priorities"><div class="widget-topline"><span>Make room for</span><button data-route="widgets" aria-label="Edit priorities">${I('more',16)}</button></div>${[1,2,3].map(i=>`<button class="priority-line ${s['priorityDone'+i]?'checked':''}" data-toggle="priorityDone${i}" aria-pressed="${s['priorityDone'+i]}"><span class="priority-check"></span><span>${E(s['priority'+i]||'A little breathing room')}</span></button>`).join('')}</div>`:''}${s.widgetSpotify?`<div class="desktop-widget widget-music"><button data-route="media" aria-label="Open music" style="padding:0">${UI.art(44)}</button><button class="track-copy" data-route="media"><div class="track-title">${E(track().title)}</div><div class="track-artist">${E(track().artist)}</div></button>${iconButton(s.playing?'pause':'play',s.playing?'Pause music':'Play music','play')}</div>`:''}${s.widgetDeadline?`<button class="desktop-widget widget-deadline" data-route="widgets"><div class="widget-topline">Coming up ${I('calendar',15)}</div><h3>${E(s.deadlineTitle||'Design review')}</h3><p class="hint">${E(s.deadlineDate||'2026-11-12')}</p></button>`:''}`;
}
function lanes(){
 let left='',right='';
 if(s.mode==='panel'){
 left=`${s.route==='controls'?routeButton('search','Search apps and tools','launcher'):iconButton('arrow-left','Back','back')}<span class="lane-label">${E(pages[s.route]?.title||'Controls')}</span>`;
 right=`<div class="lane-tools">${s.route!=='controls'?routeButton('layout','Open Controls','controls'):routeButton('settings','Open Settings','settings')}${iconButton('x','Close island','close')}</div>`;
 } else if(s.mode==='voice'){
 const label={listening:'Listening',transcribing:'Transcribing',heard:'Heard',reply:'Thursday',error:'Try again',idle:'Thursday'}[s.voicePhase];
 left=`<span class="voice-orb ${s.voicePhase==='listening'?'active':''}"></span><span class="voice-label">${label}</span>`;
 right=`${s.voicePhase==='listening'||s.voicePhase==='reply'?UI.wave('mic'):I(s.voicePhase==='error'?'alert':'check',18)}${iconButton('x','Dismiss speech preview','close')}`;
 } else if(s.mode==='event'){
 left=`${I(s.event==='battery'?'battery':s.event==='brightness'?'sun':'bell',20)}<span class="lane-label">${s.event==='battery'?'Low battery':s.event==='brightness'?'Brightness':'Notification'}</span>`;
 right=`<span class="lane-label">${s.event==='battery'?'20%':s.event==='brightness'?s.brightness+'%':'Now'}</span>${iconButton('x','Dismiss preview','close')}`;
 } else if(s.activity==='media'){
 left=s.mode==='hover'?`<div class="hover-track">${UI.art(54)}<div class="track-copy"><div class="track-title">${E(track().title)}</div><div class="track-artist">${E(track().artist)}</div></div></div>`:`${UI.art(26)}<span class="track-copy"><span class="track-title" style="font-size:11px">${E(track().title)}</span></span>`;
 right=s.mode==='hover'?`${UI.wave()}<div class="hover-transport">${iconButton('previous','Previous track','previous')}${iconButton(s.playing?'pause':'play',s.playing?'Pause music':'Play music','play')}${iconButton('next','Next track','next')}</div>`:UI.wave();
 } else {
 left=`<button class="lane-label" data-route="calendar" aria-label="Open calendar">Tue 10</button>`;
 right=`<button class="lane-label" data-route="inbox" aria-label="Open Inbox" style="display:flex;align-items:center;gap:6px">${I('bell',14)} ${s.notifications.length}</button>`;
 }
 $('left-lane').innerHTML=left;$('right-lane').innerHTML=right;
}
function voiceContent(){
 const phase=s.voicePhase;
 const text=phase==='listening'?(s.transcript?E(s.transcript)+'<span class="typing-caret"></span>':'I’m listening…'):phase==='transcribing'?E(s.transcript||'Getting every word.'):phase==='heard'?E(s.transcript):phase==='reply'?E(s.reply||'Your twenty-five-minute focus timer is ready.'):phase==='error'?'I didn’t catch that. Try once more.':'Say what’s on your mind.';
 return `${phase==='reply'?`<p class="heard-line">Heard: “${E(s.transcript)}”</p>`:''}<p class="voice-summary ${phase==='listening'&&!s.transcript?'provisional':''}">${text}</p><div class="voice-foot"><span>${phase==='listening'?'Live draft · sample speech':phase==='transcribing'?'Finishing transcription':phase==='heard'?'Final transcript · thinking…':phase==='reply'?'Sample response':phase==='error'?'No words were recognized':'Ready when you are'}</span><button data-action="${phase==='error'?'voice-retry':'open-thursday'}">${phase==='error'?'Try again':'Open Thursday'} ↗</button></div>`;
}
function render(){
 const saved=preserveInput();const content=$('island-content'),scroll=content.scrollTop;
 applyPreferences();$('island').dataset.mode=s.mode;$('island').dataset.currentRoute=s.route;lanes();widgets();
 let html='';
 if(s.mode==='panel') html=(pages[s.route]||pages.controls).render(s);
 else if(s.mode==='hover')html=s.activity==='media'?`${progress()}<div class="source-line">${I('headphones',12)} ${E(s.audioOutput||'Studio speakers')}<button data-route="media" style="margin-left:auto;color:#c8c8d3;font-size:10px;padding:0">Full player ↗</button></div>`:`<div class="idle-glance"><div><h2>Good morning.</h2><p>Tuesday, 10 November</p></div><button class="btn" data-route="calendar">${I('calendar',17)} Calendar</button></div>`;
 else if(s.mode==='voice')html=voiceContent();
 else if(s.mode==='event')html=s.event==='battery'?`<p class="voice-summary">A little power would help.</p><p class="hint">20% remaining. Switch to Power Saver or connect your charger.</p><button class="btn" data-action="battery-saver">${I('battery',16)} Use Power Saver</button>`:s.event==='brightness'?UI.range('brightness','Display brightness',s.brightness,'sun'):`<p class="voice-summary">Design review</p><p class="hint">Your next session starts in 15 minutes.</p><div style="display:flex;gap:8px"><button class="btn" data-route="calendar">Open calendar</button><button class="btn quiet" data-action="close">Dismiss</button></div>`;
 content.innerHTML=html;
 if(lastRoute!==s.mode+':'+s.route){content.scrollTop=0;content.classList.remove('swapping');void content.offsetWidth;content.classList.add('swapping');lastRoute=s.mode+':'+s.route}else content.scrollTop=scroll;
 $('clock-button').setAttribute('aria-label',s.mode==='panel'?'Close Controls and return to desktop':'Open full Controls');
 $('clock-button').setAttribute('aria-expanded',String(s.mode==='panel'));
 const names={panel:pages[s.route]?.title||'Controls',rest:s.activity==='media'?'Music, at a glance':'At rest',hover:s.activity==='media'?'A closer listen':'A quiet glance',voice:'Thursday, understood',event:'Just enough attention'};
 const captions={panel:s.route==='controls'?'Your full setup, together again.':'Every detail, part of the same desktop.',rest:'Hover for a glance. Click for everything.',hover:'Artwork left. Live activity right. Time stays.',voice:'See your words. Know what was heard.',event:'A short update, right where you expect it.'};
 $('view-name').textContent=names[s.mode];$('view-caption').textContent=captions[s.mode];
 document.querySelectorAll('[data-scene]').forEach(b=>{const on=b.dataset.scene==='controls'?s.mode==='panel':b.dataset.scene==='voice'?s.mode==='voice':b.dataset.scene==='music'?s.activity==='media'&&['rest','hover'].includes(s.mode):s.activity==='idle'&&['rest','hover'].includes(s.mode);b.classList.toggle('selected',on);b.setAttribute('aria-pressed',String(on));});
 if(s.mode==='panel')$('route-picker').value=s.route;else $('route-picker').value='';
 restoreInput(saved);requestAnimationFrame(sizeIsland);
}
function sizeIsland(){
 const island=$('island'),desktop=$('desktop'),content=$('island-content');
 const width=s.mode==='panel'?(pages[s.route]?.width||640):s.mode==='rest'?(s.activity==='media'?420:280):s.mode==='hover'?(s.activity==='media'?520:440):s.mode==='voice'?520:480;
 island.style.setProperty('--island-width',Math.min(width,desktop.clientWidth-(innerWidth<=520?12:24))+'px');
 let height=s.mode==='rest'?46:s.mode==='hover'?(s.activity==='media'?156:152):s.mode==='voice'?(s.voicePhase==='reply'?204:170):s.mode==='event'?(s.event==='brightness'?138:224):0;
 if(!height){const children=[...content.children];const last=children.at(-1);const natural=last?last.offsetTop+last.offsetHeight+4:300;height=Math.max(230,natural+74);}
 height=Math.min(height,desktop.clientHeight-(s.shape==='floating'?34:24));
 island.style.setProperty('--island-height',height+'px');
 updateContour();
}
function roundedPoint(cx,cy,r,angle){const power=2/3.5;return[cx+r*Math.sign(Math.cos(angle))*Math.abs(Math.cos(angle))**power,cy+r*Math.sign(Math.sin(angle))*Math.abs(Math.sin(angle))**power];}
function updateContour(){
 const el=$('island'),w=el.getBoundingClientRect().width,h=el.getBoundingClientRect().height,x=12,r=Math.min(s.mode==='rest'?23:30,h/2,w/2),notch=s.shape!=='floating';
 let d='';
 const move=(px,py)=>{d+=`M${px.toFixed(3)} ${py.toFixed(3)} `},line=(px,py)=>{d+=`L${px.toFixed(3)} ${py.toFixed(3)} `};
 const corner=(cx,cy,rad,start)=>{for(let i=1;i<=20;i++){const p=roundedPoint(cx,cy,rad,start+i*Math.PI/40);line(p[0],p[1]);}};
 if(notch){move(0,0);line(w+24,0);d+=`C${w+17} 0 ${w+12} 4 ${w+12} 12 `;line(w+12,h-r);corner(w+12-r,h-r,r,0);line(x+r,h);corner(x+r,h-r,r,Math.PI/2);line(x,12);d+=`C${x} 4 7 0 0 0 Z`;}
 else{move(x+r,0);line(x+w-r,0);corner(x+w-r,r,r,-Math.PI/2);line(x+w,h-r);corner(x+w-r,h-r,r,0);line(x+r,h);corner(x+r,h-r,r,Math.PI/2);line(x,r);corner(x+r,r,r,Math.PI);d+='Z';}
 $('silhouette').setAttribute('viewBox',`0 0 ${w+24} ${h}`);$('silhouette-path').setAttribute('d',d);
}
new ResizeObserver(()=>{updateContour();cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{if(s.mode==='panel')sizeIsland();});}).observe($('island'));
new ResizeObserver(()=>sizeIsland()).observe($('desktop'));
function cancelReplay(){clearTimeout(replayTimer);replayTimer=undefined;}
function go(route){if(!pages[route])return;cancelReplay();if(route!=='thursday')voiceGeneration++;if(s.mode==='panel'&&s.route!==route)history.push(s.route);else if(s.mode!=='panel'){history=[];focusOrigin=document.activeElement;}s.route=route;s.mode='panel';previewHeld=false;clearTimeout(hoverTimer);clearTimeout(leaveTimer);render();requestAnimationFrame(()=>{const target=$('island-content').querySelector('input:not([type=range]),textarea')||$('left-lane').querySelector('button');target?.focus({preventScroll:true});});}
function back(){cancelReplay();if(s.filePreview&&['files','launcher'].includes(s.route)){s.filePreview='';render();return;}if(s.wifiSelected&&s.route==='wifi'){s.wifiSelected='';render();return;}if(history.length){s.route=history.pop();s.mode='panel';render();}else if(s.route!=='controls')go('controls');else close();}
function close(){cancelReplay();clearTimeout(hoverTimer);clearTimeout(leaveTimer);voiceGeneration++;s.mode='rest';s.voicePhase='idle';previewHeld=false;history=[];render();if(focusOrigin?.isConnected)focusOrigin.focus({preventScroll:true});else $('clock-button').focus({preventScroll:true});focusOrigin=null;}
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3300);}
function setActivity(name){if(name==='thursday'||name==='voice'){scene('voice');return;}s.activity=name==='idle'?'idle':'media';if(s.mode!=='panel')s.mode='rest';render();}
function cancelVoice(){voiceGeneration++;s.voicePhase="idle";}
function voiceDemo(){
 const generation=++voiceGeneration;s.voicePhase='listening';s.transcript='';s.reply='';if(s.mode!=='panel')s.mode='voice';render();
 const step=(ms,fn)=>setTimeout(()=>{if(generation!==voiceGeneration)return;fn();render();},ms);
 step(1200,()=>s.transcript='Set a focus timer');step(2500,()=>s.transcript='Set a focus timer for twenty-five minutes.');step(3500,()=>s.voicePhase='transcribing');step(4500,()=>s.voicePhase='heard');step(6500,()=>{s.voicePhase='reply';s.reply='Your twenty-five-minute focus timer is ready. A little room to think.';});
}
function scene(name){cancelReplay();voiceGeneration++;history=[];clearTimeout(hoverTimer);clearTimeout(leaveTimer);previewHeld=true;
 if(name==='controls'){s.mode='panel';s.route='controls';render();}
 else if(name==='rest'){s.activity='idle';s.mode='rest';render();}
 else if(name==='music'){s.activity='media';s.mode='hover';render();}
 else if(name==='voice'){s.mode='voice';voiceDemo();}
 else if(name==='notification'||name==='battery'||name==='brightness'){s.mode='event';s.event=name;render();}
}
function action(name,value){
 cancelReplay();if(['convo-save-correction','convo-new-chat','convo-send'].includes(name)){voiceGeneration++;s.voicePhase='idle';}
 if(window.SumiActions?.[name]){window.SumiActions[name](s,value);return;}
 const actions={back,close,play(){s.playing=!s.playing;render();},next(){s.trackIndex=(s.trackIndex+1)%tracks.length;s.position=0;render();},previous(){s.trackIndex=(s.trackIndex+tracks.length-1)%tracks.length;s.position=0;render();},shuffle(){s.shuffle=!s.shuffle;render();toast(s.shuffle?'Shuffle is on':'Shuffle is off');},'guide'(){$('guide').showModal();},'guide-close'(){$('guide').close();},'open-thursday'(){go('thursday');},'voice-retry'(){voiceDemo();},'battery-saver'(){s.powerProfile='power-saver';toast('Power Saver enabled in the preview');close();},workspace(){document.querySelectorAll('.workspace').forEach(b=>b.classList.toggle('active',b.dataset.value===value));toast(`Workspace ${value} · preview`);},replay(){const target={mode:s.mode,route:s.route,activity:s.activity};voiceGeneration++;s.mode='rest';render();replayTimer=setTimeout(()=>{Object.assign(s,target);render();},450);},'voice-error'(){voiceGeneration++;s.mode='voice';s.voicePhase='error';s.transcript='';render();}};
 if(actions[name])actions[name]();else toast('Preview action: '+name);
}
window.Sumi={state:s,go,back,render,close,toast,applyPreferences,setActivity,voiceDemo,cancelVoice,scene,action,track};
document.addEventListener('click',e=>{
 const b=e.target.closest('[data-route],[data-action],[data-toggle],[data-scene]');
 if(b){if(b.disabled)return;cancelReplay();if(b.dataset.route){go(b.dataset.route);return;}if(b.dataset.scene){scene(b.dataset.scene);return;}if(b.dataset.toggle){s[b.dataset.toggle]=!s[b.dataset.toggle];render();return;}action(b.dataset.action,b.dataset.value||'');return;}
 if(e.target.closest('#clock-button')){s.mode==='panel'?close():go('controls');return;}
 if(e.target.closest('#island')){if(s.mode==='rest'||e.clientY-$('island').getBoundingClientRect().top<43)go('controls');return;}
 if(e.target.closest('#desktop')&&!e.target.closest('.desktop-widget'))close();
});
document.addEventListener('input',e=>{
 const el=e.target;
 if(el.dataset.range){s[el.dataset.range]=Number(el.value);el.style.setProperty('--range-value',el.value+'%');document.querySelectorAll(`[data-value-for="${CSS.escape(el.dataset.range)}"]`).forEach(x=>x.textContent=el.value+'%');if(el.dataset.range==='position')updatePlayback();return;}
 if(el.dataset.bind){s[el.dataset.bind]=el.value;pages[s.route]?.onInput?.(s,el.dataset.bind,el.value);if(/^(priority|deadline)/.test(el.dataset.bind))widgets();}
});
$('route-picker').addEventListener('change',e=>{const v=e.target.value;if(v.startsWith('scenario:'))scene(v.slice(9));else if(v==='voice-error')action(v);else if(v==='unavailable'){s.deviceUnavailable='wifi';go('wifi');}else if(v)go(v);});
$('island').addEventListener('pointerenter',()=>{previewHeld=false;clearTimeout(leaveTimer);if(s.mode==='rest')hoverTimer=setTimeout(()=>{if(s.mode==='rest'){s.mode='hover';render();}},180);});
$('island').addEventListener('pointerleave',()=>{clearTimeout(hoverTimer);if(s.mode==='hover'&&!previewHeld)leaveTimer=setTimeout(()=>{if(s.mode==='hover'){s.mode='rest';render();}},250);});
document.addEventListener('keydown',e=>{if($('guide').open)return;if(e.key==='Escape'){e.preventDefault();close();}else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();go('launcher');requestAnimationFrame(()=>document.querySelector('[data-bind="searchQuery"]')?.focus());}else if(e.altKey&&e.key==='ArrowLeft'){e.preventDefault();back();}});
function updatePlayback(){document.querySelectorAll('[data-playtime]').forEach(el=>el.textContent=time(s.position));document.querySelectorAll('[data-remaining]').forEach(el=>el.textContent='−'+time(track().duration-s.position));document.querySelectorAll('[data-range=position]').forEach(el=>{el.value=s.position;el.style.background=`linear-gradient(to right,#dcdce2 ${s.position/track().duration*100}%,#35353b ${s.position/track().duration*100}%)`;});}
setInterval(()=>{if(s.playing){s.position=Math.min(track().duration,s.position+1);updatePlayback();}},1000);
document.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=I(el.dataset.icon,16));
const groups=[['Island & activity',[['controls','Controls'],['media','Full music player'],['scenario:rest','Resting island'],['scenario:music','Music hover'],['scenario:voice','Speech demonstration'],['voice-error','Speech not recognized'],['scenario:notification','Notification preview'],['scenario:battery','Low battery'],['scenario:brightness','Brightness feedback']]],['Your devices',['wifi','bluetooth','audio','capture','system','power','pomodoro']],['Desktop tools',['launcher','files','clipboard','calendar','inbox','notification','thursday','codex']],['Make it yours',['appearance','widgets','settings','help']]];
$('route-picker').innerHTML='<option value="">All views</option>'+groups.map(([label,items])=>`<optgroup label="${label}">${items.map(item=>{const[v,t]=Array.isArray(item)?item:[item,pages[item]?.title||item];return `<option value="${v}">${E(t)}</option>`;}).join('')}</optgroup>`).join('')+'<optgroup label="Edge cases"><option value="unavailable">Unavailable device</option></optgroup>';
const params=new URLSearchParams(location.search);if(params.get('view')&&pages[params.get('view')])s.route=params.get('view');if(params.get('shape')==='floating')s.shape='floating';
if(params.get('scene'))scene(params.get('scene'));else render();
})();
