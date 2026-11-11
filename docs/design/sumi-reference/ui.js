/* Shared primitives for the offline Sumi design reference. */
(() => {
'use strict';
const paths={
search:'<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/>',
wifi:'<path d="M2 8.5a16 16 0 0 1 20 0M5.5 12a10.5 10.5 0 0 1 13 0M9 15.5a5.1 5.1 0 0 1 6 0"/><circle cx="12" cy="19" r=".8" fill="currentColor" stroke="none"/>',
bluetooth:'<path d="m7 7 11 10-6 5V2l6 5L7 17"/>',
volume:'<path d="M11 4 6 8H3v8h3l5 4V4ZM15 8a6 6 0 0 1 0 8M18 4a11 11 0 0 1 0 16"/>',
'volume-off':'<path d="M11 4 6 8H3v8h3l5 4V4ZM16 9l6 6m0-6-6 6"/>',
sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/>',
moon:'<path d="M20.7 13.4A9 9 0 0 1 10.6 3.3 9 9 0 1 0 20.7 13.4Z"/>',
battery:'<rect x="2" y="6" width="18" height="12" rx="3"/><path d="M22 10v4"/><rect x="5" y="9" width="11" height="6" rx="1" fill="currentColor" stroke="none"/>',
bell:'<path d="M18 8a6 6 0 0 0-12 0c0 6-3 6-3 9h18c0-3-3-3-3-9M10 21h4"/>',
settings:'<path d="m9 3 1-1h4l1 3 3 1 3 2-1 3v2l1 3-3 2-3 1-1 3h-4l-1-3-3-1-3-2 1-3v-2L3 8l3-2 3-1Z"/><circle cx="12" cy="12" r="3"/>',
play:'<path d="m8 4 12 8-12 8Z" fill="currentColor" stroke="none"/>',
pause:'<path d="M6 4h4v16H6zM14 4h4v16h-4z" fill="currentColor" stroke="none"/>',
next:'<path d="m3 5 9 7-9 7V5Zm9 0 9 7-9 7V5Z" fill="currentColor" stroke="none"/>',
previous:'<path d="m21 5-9 7 9 7V5Zm-9 0-9 7 9 7V5Z" fill="currentColor" stroke="none"/>',
x:'<path d="m6 6 12 12M6 18 18 6"/>',
'arrow-left':'<path d="m12 5-7 7 7 7M5 12h16"/>',
'arrow-right':'<path d="m12 5 7 7-7 7M19 12H3"/>',
'arrow-up':'<path d="m5 12 7-7 7 7M12 5v16"/>',
'chevron-right':'<path d="m9 5 7 7-7 7"/>',
'chevron-left':'<path d="m15 5-7 7 7 7"/>',
'chevron-down':'<path d="m5 9 7 7 7-7"/>',
folder:'<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
clipboard:'<rect x="5" y="4" width="14" height="18" rx="3"/><rect x="8" y="2" width="8" height="5" rx="2" fill="currentColor" stroke="none"/><path d="M9 12h6m-6 4h4"/>',
palette:'<path d="M12 3a9 9 0 1 0 0 18h2a2 2 0 0 0 0-4h-1a2 2 0 0 1 0-4h4a4 4 0 0 0 4-4c0-3-4-6-9-6Z"/><circle cx="7.5" cy="9" r=".8"/><circle cx="11" cy="6.5" r=".8"/><circle cx="16" cy="7" r=".8"/><circle cx="6.5" cy="14" r=".8"/>',
camera:'<path d="M9 5 11 3h4l2 3h3a2 2 0 0 1 2 2v11H2V8a2 2 0 0 1 2-2h4Z"/><circle cx="12" cy="12" r="4"/>',
video:'<rect x="2" y="6" width="14" height="13" rx="3"/><path d="m16 10 6-4v13l-6-4"/>',
timer:'<circle cx="12" cy="14" r="8"/><path d="M12 10v4l3 2M9 2h6m-3 0v4m6 1 2-2"/>',
clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
calendar:'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 2v6m10-6v6M3 10h18m-14 4h2m3 0h2m3 0h1m-11 3h2m3 0h2"/>',
layout:'<rect x="3" y="3" width="8" height="8" rx="2"/><rect x="15" y="3" width="6" height="12" rx="2"/><rect x="3" y="15" width="8" height="6" rx="2"/><path d="M15 20h6"/>',
cpu:'<rect x="5" y="5" width="14" height="14" rx="3"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v3m6-3v3m-6 14v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/>',
power:'<path d="M12 2v10M6.3 5.3a9 9 0 1 0 11.4 0"/>',
sparkles:'<path d="m12 3 2.8 6.2L21 12l-6.2 2.8L12 21l-2.8-6.2L3 12l6.2-2.8L12 3ZM20 2v4m-2-2h4"/>',
mic:'<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/>',
headphones:'<path d="M4 13v-2a8 8 0 0 1 16 0v2"/><rect x="3" y="12" width="4" height="9" rx="2"/><rect x="17" y="12" width="4" height="9" rx="2"/>',
keyboard:'<rect x="2" y="5" width="20" height="14" rx="3"/><path d="M6 9h1m4 0h1m4 0h1m-11 4h1m4 0h1m4 0h1M7 16h10"/>',
speaker:'<rect x="5" y="2" width="14" height="20" rx="3"/><circle cx="12" cy="15" r="3"/><circle cx="12" cy="7" r="1"/>',
monitor:'<rect x="2" y="3" width="20" height="14" rx="3"/><path d="M12 17v4m-5 0h10"/>',
window:'<rect x="2" y="4" width="20" height="17" rx="3"/><path d="M2 9h20M6 6.5h.1m3 0h.1"/>',
check:'<path d="m5 12 4 4L20 5"/>',
lock:'<rect x="4" y="10" width="16" height="12" rx="3"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v3"/>',
replay:'<path d="M3 9a9 9 0 1 1 1 9M3 3v6h6"/>',
help:'<circle cx="12" cy="12" r="9"/><path d="M9 8a3 3 0 0 1 6 1c0 2-3 2-3 5m0 3h.01"/>',
music:'<path d="M9 18V5l12-3v13M9 9l12-3"/><ellipse cx="6" cy="18" rx="3" ry="2.5"/><ellipse cx="18" cy="15" rx="3" ry="2.5"/>',
globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
terminal:'<rect x="2" y="4" width="20" height="16" rx="3"/><path d="m6 9 3 3-3 3m6 0h5"/>',
code:'<path d="m7 6-5 6 5 6m10-12 5 6-5 6m-4-15-2 18"/>',
file:'<path d="M13 2H5v20h14V8l-6-6Zm0 0v6h6M8 13h8m-8 4h6"/>',
link:'<path d="m9 15 6-6m-8 4-2 2a4 4 0 0 0 6 6l3-3m3-5 2-2a4 4 0 0 0-6-6l-3 3"/>',
trash:'<path d="M3 6h18M6 6l1 15h10l1-15M9 6V3h6v3m-5 4v7m4-7v7"/>',
home:'<path d="m2 11 10-9 10 9M5 9v13h5v-8h4v8h5V9"/>',
edit:'<path d="m16 3 5 5M4 16 17 3a2 2 0 0 1 4 4L8 20l-6 2 2-6Z"/>',
plus:'<path d="M12 4v16M4 12h16"/>',
'message-circle':'<path d="M21 11.5a9 9 0 0 1-9.5 9 10 10 0 0 1-4-.8L2 22l1.8-5.5a10 10 0 0 1-.8-4A9 9 0 1 1 21 11.5Z"/>',
shield:'<path d="m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6l9-4Z"/><path d="m8 12 3 3 5-6"/>',
loader:'<path d="M12 3a9 9 0 1 1-9 9"/>',
alert:'<path d="m12 3 10 18H2L12 3Zm0 6v5m0 3h.01"/>',
crop:'<path d="M6 2v16h16M2 6h16v16"/>',
cursor:'<path d="m4 2 16 12-8 1-4 7-4-20Z"/>',
memory:'<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 9v5m4-5v5m4-5v5m4-5v5M6 18v3m4-3v3m4-3v3m4-3v3"/>',
drive:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="12" cy="10" r="4"/><path d="m12 10 4 5M6 18h.01m3 0h.01"/>',
logout:'<path d="M9 3H3v18h6m6-14 5 5-5 5M8 12h12"/>',
stop:'<rect x="5" y="5" width="14" height="14" rx="2" fill="currentColor" stroke="none"/>',
heart:'<path d="M20.8 4.6c-2.2-2.2-5.6-1.8-8.8 1.4C8.8 2.8 5.4 2.4 3.2 4.6.8 7 .8 10.1 3.2 13L12 22l8.8-9c2.4-2.9 2.4-6 0-8.4Z"/>',
shuffle:'<path d="M3 5h3l12 14h3M3 19h3L18 5h3m-4-3 4 3-4 3m0 8 4 3-4 3"/>',
repeat:'<path d="M20 8V5H5a3 3 0 0 0-3 3v3m18 5v3H5a3 3 0 0 1-3-3v-2m15-9 3 3 3-3M5 16l-3-3-2 3"/>',
airplay:'<path d="M3 17V4h18v13M12 14l7 8H5l7-8Z"/>',
more:'<circle cx="5" cy="12" r="1" fill="currentColor"/><circle cx="12" cy="12" r="1" fill="currentColor"/><circle cx="19" cy="12" r="1" fill="currentColor"/>'
};
paths.refresh=paths.replay;paths.desktop=paths.monitor;paths.sound=paths.volume;paths.close=paths.x;paths.chevron=paths['chevron-right'];
const esc=t=>String(t??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon=(name,size=20)=>`<svg class="icon" width="${Number(size)||20}" height="${Number(size)||20}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.layout}</svg>`;
const row=({icon:ic,title,sub='',route='',action='',value='',end='',danger=false})=>{const tag=route||action?'button':'div';return `<${tag} class="settings-row ${danger?'danger':''}" ${route?`data-route="${esc(route)}"`:''} ${action?`data-action="${esc(action)}" data-value="${esc(value)}"`:''}>${ic?`<span class="row-icon">${icon(ic)}</span>`:''}<span class="row-copy"><span class="row-title">${esc(title)}</span>${sub?`<span class="row-sub" style="display:block">${esc(sub)}</span>`:''}</span><span class="row-end">${end||(route?icon('chevron-right',16):'')}</span></${tag}>`};
const toggle=(key,label,on,ic,sub='')=>`<button class="settings-row toggle-row" data-toggle="${esc(key)}" role="switch" aria-checked="${!!on}" aria-label="${esc(label)}">${ic?`<span class="row-icon">${icon(ic)}</span>`:''}<span class="row-copy"><span class="row-title">${esc(label)}</span>${sub?`<span class="row-sub" style="display:block">${esc(sub)}</span>`:''}</span><span class="switch ${on?'on':''}" aria-hidden="true"></span></button>`;
const range=(key,label,value,ic='volume')=>`<div class="range-control"><label class="range-label" for="range-${esc(key)}"><span>${icon(ic,16)}${esc(label)}</span><output data-value-for="${esc(key)}">${value}%</output></label><input type="range" id="range-${esc(key)}" min="0" max="100" value="${value}" data-range="${esc(key)}" style="--range-value:${value}%"></div>`;
const section=(title,body)=>`<section><h3 class="section-title">${esc(title)}</h3>${body}</section>`;
const empty=(ic,title,detail)=>`<div class="empty-state">${icon(ic,32)}<h3>${esc(title)}</h3><p>${esc(detail)}</p></div>`;
const art=(size=48)=>`<span class="artwork" role="img" aria-label="Sample album artwork" style="--art-size:${Number(size)}px"></span>`;
const wave=(cls='')=>`<span class="wave ${esc(cls)} ${window.Sumi?.state?.playing===false&&!String(cls).includes('mic')?'paused':''}" role="img" aria-label="Simulated ${String(cls).includes('mic')?'speech':'audio'} waveform">${[6,12,21,15,27,18,23,10,5].map((h,i)=>`<i style="--bar-height:${h}px;--bar-delay:${i*-.13}s"></i>`).join('')}</span>`;
window.UI={esc,icon,row,toggle,range,section,empty,art,wave};
})();
