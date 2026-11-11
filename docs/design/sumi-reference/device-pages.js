/* Local sample-data device pages. No system settings or hardware are accessed. */
(() => {
  'use strict';
  const e = value => UI.esc(String(value ?? ''));
  const icon = (name, size = 20) => UI.icon(name, size);
  const intro = (title, detail) => `<div class="page-intro"><h2>${e(title)}</h2><p>${e(detail)}</p></div>`;
  const button = (text, action, value = '', kind = '') => `<button class="btn ${kind}" data-action="${action}" data-value="${e(value)}">${e(text)}</button>`;
  const choices = (name, selected, options) => `<div class="segmented" aria-label="${e(name)}">${options.map(([value, label, action]) => `<button class="${selected === value ? 'selected' : ''}" aria-pressed="${selected === value}" data-action="${action}" data-value="${e(value)}">${e(label)}</button>`).join('')}</div>`;
  const panel = html => `<div class="module dev-module">${html}</div>`;
  const callout = (text, error = false) => `<p class="dev-callout ${error ? 'dev-error' : ''}" role="status">${icon(error ? 'alert' : 'check', 16)}<span>${e(text)}</span></p>`;
  const rows = html => `<div class="list">${html}</div>`;
  const suffix = text => `<span class="row-end">${e(text)}</span>`;
  const defaults = s => {
    s.network ??= 'Studio Wi-Fi';
    s.audioOutput ??= 'Studio speakers';
    s.audioInput ??= 'Built-in microphone';
    s.inputLevel ??= 64;
    s.micMuted ??= false;
    s.btConnected ??= ['Studio headphones'];
    s.powerProfile ??= 'balanced';
    s.focusMinutes ??= 25;
    s.focusRemainingMs ??= s.focusMinutes * 60000;
    s.focusRunning ??= false;
    s.captureMode ??= 'region';
    s.captureDelay ??= '0';
    s.captureCursor ??= true;
    s.captureAnnotate ??= false;
    s.captureRecording ??= false;
    currentState = s;
    return s;
  };
  let currentState;
  const unavailable = (title, detail) => `<div class="dev-unavailable">${UI.empty('monitor', title, detail)}${button('Try again', 'dev-retry', '', 'primary')}</div>`;
  const focusLeft = s => s.focusRunning ? Math.max(0, s.focusDeadline - Date.now()) : s.focusRemainingMs;
  const formatTime = ms => `${Math.floor(Math.ceil(ms / 1000) / 60).toString().padStart(2, '0')}:${(Math.ceil(ms / 1000) % 60).toString().padStart(2, '0')}`;

  const pages = {
    wifi: {
      title: 'Wi-Fi', width: 500,
      render(state) {
        const s = defaults(state);
        if (s.deviceUnavailable === 'wifi') return unavailable('Wi-Fi is unavailable', 'The adapter could not be reached. Your saved networks are still here.');
        if (s.wifiSelected) return `${intro(s.wifiSelected, 'Join this network in the local preview.')}${panel(`<div class="dev-network-mark">${icon('wifi', 32)}</div><label class="dev-field-label" for="dev-wifi-password">Password</label><input id="dev-wifi-password" class="field" type="password" autocomplete="off" placeholder="Enter a sample password" data-bind="wifiPassword" value="${e(s.wifiPassword)}" aria-describedby="dev-password-hint"><p class="hint" id="dev-password-hint">Use any 8 characters. Nothing is sent or saved outside this preview.</p>${s.wifiError ? callout(s.wifiError, true) : ''}<div class="dev-actions">${button('Cancel', 'dev-wifi-cancel')}${button('Join network', 'dev-wifi-connect', '', 'primary')}</div>`)}`;
        return `${intro('Stay connected', s.wifi && s.network ? `${s.network} · Connected` : 'Choose a network to get connected.')}${UI.toggle('wifi', 'Wi-Fi', s.wifi, 'wifi', s.wifi ? 'On' : 'Off')}${s.wifi ? `${s.network ? UI.section('Connected network', rows(UI.row({icon: 'wifi', title: s.network, sub: 'Private address · WPA3 Personal', action: 'dev-wifi-disconnect', end: 'Disconnect'}))) : ''}${UI.section('Other networks', rows(['Studio Wi-Fi', 'Guest network', 'Phone hotspot'].filter(n => n !== s.network).map((name, i) => UI.row({icon: 'wifi', title: name, sub: i === 1 ? 'Personal hotspot' : 'Secured network', action: 'dev-wifi-select', value: name, end: icon('lock', 14)})).join('')))}<div class="dev-footer"><span class="hint">${s.wifiScanned ? 'Networks updated just now' : 'Nearby networks'}</span>${button('Refresh', 'dev-wifi-scan', '', 'quiet')}</div>` : UI.empty('wifi', 'Wi-Fi is off', 'Turn it on to see nearby networks.')}`;
      }
    },
    bluetooth: {
      title: 'Bluetooth', width: 500,
      render(state) {
        const s = defaults(state);
        if (s.deviceUnavailable === 'bluetooth') return unavailable('Bluetooth is unavailable', 'The adapter could not be reached. Try connecting again.');
        const connected = s.btConnected;
        const known = ['Studio headphones', 'Wireless keyboard'];
        return `${intro('Your devices, together', s.bluetooth ? 'Discoverable as Sumi desktop' : 'Bluetooth is turned off.')}${UI.toggle('bluetooth', 'Bluetooth', s.bluetooth, 'bluetooth', s.bluetooth ? 'On' : 'Off')}${s.bluetooth ? `${s.btPairing ? panel(`<div class="dev-network-mark">${icon('bluetooth', 28)}</div><h3 class="dev-center">Pair ${e(s.btPairing)}?</h3><p class="hint dev-center">Confirm that this code matches the one on your device.</p><div class="dev-pair-code tabular">482 019</div><div class="dev-actions">${button('Cancel', 'dev-bt-cancel')}${button('Pair device', 'dev-bt-confirm', '', 'primary')}</div>`) : ''}${UI.section('My devices', rows(known.map(name => UI.row({icon: name.includes('headphones') ? 'headphones' : 'keyboard', title: name, sub: connected.includes(name) ? (name.includes('headphones') ? 'Connected · 82% battery' : 'Connected · 94% battery') : 'Not connected', action: 'dev-bt-toggle', value: name, end: connected.includes(name) ? 'Disconnect' : 'Connect'})).join('')))}${UI.section('Nearby devices', rows(UI.row({icon: 'speaker', title: 'Living room speaker', sub: s.btSpeakerPaired ? 'Paired' : 'Ready to pair', action: s.btSpeakerPaired ? 'dev-bt-toggle' : 'dev-bt-pair', value: 'Living room speaker', end: s.btSpeakerPaired ? (connected.includes('Living room speaker') ? 'Disconnect' : 'Connect') : 'Pair'})))}<div class="dev-footer"><span class="hint">${s.btScanned ? 'Discovery complete' : 'Searching for nearby devices'}</span>${button('Refresh', 'dev-bt-scan', '', 'quiet')}</div>` : UI.empty('bluetooth', 'Bluetooth is off', 'Your paired devices will appear when Bluetooth is on.')}`;
      }
    },
    audio: {
      title: 'Sound', width: 520,
      render(state) {
        const s = defaults(state);
        if (s.deviceUnavailable === 'audio') return unavailable('No sound devices found', 'Connect an audio device, then try again.');
        return `${intro('Sound, your way', 'Choose where you listen and how you are heard.')}${UI.section('Output', rows(['Studio speakers', 'Studio headphones', 'Display audio'].map((name, i) => UI.row({icon: i === 1 ? 'headphones' : 'volume', title: name, sub: i === 0 ? 'Built-in audio' : i === 1 ? 'Bluetooth · 82% battery' : 'HDMI / DisplayPort', action: 'dev-output', value: name, end: s.audioOutput === name ? icon('check', 18) : ''})).join('')))}${panel(`${UI.range('volume', 'Output volume', s.volume, s.muted ? 'volume-off' : 'volume')}${UI.toggle('muted', 'Mute output', !!s.muted, 'volume-off', s.muted ? 'Sound is muted' : 'Sound is on')}`)}${UI.section('Input', rows(['Built-in microphone', 'Headset microphone'].map(name => UI.row({icon: 'mic', title: name, sub: name === 'Built-in microphone' ? 'Internal array' : 'Studio headphones', action: 'dev-input', value: name, end: s.audioInput === name ? icon('check', 18) : ''})).join('')))}${panel(`${UI.range('inputLevel', 'Input level', s.inputLevel, 'mic')}${UI.toggle('micMuted', 'Mute microphone', s.micMuted, 'mic', s.micMuted ? 'Microphone is muted' : 'Microphone is available')}`)}`;
      }
    },
    capture: {
      title: 'Capture & record', width: 520,
      render(state) {
        const s = defaults(state);
        const pending = s.capturePending;
        if (pending) return `${intro(pending === 'record' ? 'Choose what to record' : 'Choose what to capture', 'The island steps out of the way during selection.')}${panel(`<div class="dev-capture-preview" role="img" aria-label="Sample screen selection"><div class="dev-capture-window"><i></i><i></i><i></i><div class="dev-capture-selection">${icon(s.captureMode === 'window' ? 'window' : 'crop', 28)}<span>${s.captureMode === 'screen' ? 'Entire display' : s.captureMode === 'window' ? 'Selected window' : 'Selected region'}</span></div></div></div><p class="hint dev-center">This selection is contained entirely inside the reference.</p><div class="dev-actions">${button('Cancel', 'dev-capture-cancel')}${button(pending === 'record' ? 'Start recording' : 'Capture selection', 'dev-capture-confirm', '', 'primary')}</div>`)}`;
        return `${intro('Save a moment', 'Capture a region, a window, or your entire display.')}${choices('Capture area', s.captureMode, [['region', 'Region', 'dev-capture-mode'], ['window', 'Window', 'dev-capture-mode'], ['screen', 'Display', 'dev-capture-mode']])}<div class="dev-capture-hero">${icon(s.captureRecording ? 'video' : 'crop', 44)}<strong>${s.captureRecording ? 'Recording your selection' : (s.captureMode === 'region' ? 'Just the part you need' : s.captureMode === 'window' ? 'A single window' : 'Everything on your display')}</strong><span class="hint">${s.captureRecording ? '<span id="dev-record-time" class="tabular">' + formatTime(Date.now() - s.captureStarted) + '</span> · Demo recording' : 'A clean capture, ready to share.'}</span></div>${s.captureResult ? callout(s.captureResult) : ''}${panel(`${UI.toggle('captureAnnotate', 'Annotate screenshots', s.captureAnnotate, 'edit', 'Open your capture for markup')}${UI.toggle('captureCursor', 'Include pointer', s.captureCursor, 'cursor', 'Show the pointer in recordings')}<div class="dev-delay"><span class="row-title">Delay</span>${choices('Capture delay', s.captureDelay, [['0', 'None', 'dev-capture-delay'], ['3', '3 sec', 'dev-capture-delay'], ['5', '5 sec', 'dev-capture-delay']])}</div>`)}<div class="dev-actions dev-actions-fill">${button('Take screenshot', 'dev-capture-start', 'shot', 'primary')}${button(s.captureRecording ? 'Stop recording' : 'Record screen', s.captureRecording ? 'dev-record-stop' : 'dev-capture-start', 'record', s.captureRecording ? 'danger' : '')}</div>`;
      }
    },
    system: {
      title: 'System', width: 520,
      render(state) {
        const s = defaults(state);
        return `${intro('A little room to breathe', 'Your desktop at a glance.')}${[['cpu', 'Processor', s.statsSample ? '18%' : '12%', s.statsSample ? 18 : 12, s.statsSample ? '8 cores · 2.8 GHz' : '8 cores · 2.4 GHz'], ['memory', 'Memory', s.statsSample ? '6.4 GB' : '6.2 GB', s.statsSample ? 40 : 39, s.statsSample ? '9.6 GB available of 16 GB' : '9.8 GB available of 16 GB'], ['drive', 'Storage', '186 GB', 37, '314 GB available of 500 GB']].map(([glyph, label, number, pct, detail]) => panel(`<div class="dev-stat-head"><span>${icon(glyph, 20)}${label}</span><strong class="tabular">${number}</strong></div><div class="dev-meter" role="meter" aria-label="${label} usage" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div><p class="hint">${detail}</p>`)).join('')}${UI.section('This session', rows(UI.row({icon: 'monitor', title: 'Display', sub: '2560 × 1600 · 120 Hz', route: 'settings', end: 'Settings'}) + UI.row({icon: 'battery', title: 'Battery', sub: '82% · About 5 hours remaining', route: 'power', end: 'Power'})))}<div class="dev-footer"><span class="hint">${s.statsRefreshed ? 'Updated just now · Sample readings' : 'Sample readings · Local preview'}</span>${button('Refresh', 'dev-stats-refresh', '', 'quiet')}</div>`;
      }
    },
    power: {
      title: 'Power & session', width: 500,
      render(state) {
        const s = defaults(state);
        if (s.powerPending) return `${intro(`${s.powerPending}?`, s.powerPending === 'Log out' || s.powerPending === 'Restart' || s.powerPending === 'Shut down' ? 'Save your work before ending this session.' : 'Your current work will remain available.')}${panel(`<div class="dev-network-mark">${icon(s.powerPending === 'Lock' ? 'lock' : s.powerPending === 'Sleep' ? 'moon' : 'power', 38)}</div><p class="hint dev-center">This is a local preview. Your computer will stay exactly as it is.</p><div class="dev-actions">${button('Cancel', 'dev-power-cancel')}${button(s.powerPending, 'dev-power-confirm', '', s.powerPending === 'Shut down' ? 'danger' : 'primary')}</div>`)}`;
        return `${intro('Ready for what’s next', 'A balanced desktop, with energy to spare.')}<div class="dev-battery"><div class="dev-battery-icon"><span></span></div><div><strong class="tabular">82<span>%</span></strong><p class="hint">About 5 hours remaining</p></div></div>${UI.section('Power profile', choices('Power profile', s.powerProfile, [['saver', 'Low power', 'dev-power-profile'], ['balanced', 'Balanced', 'dev-power-profile'], ['performance', 'Performance', 'dev-power-profile']]))}<p class="hint dev-profile-copy">${{saver: 'Uses less energy to keep you going longer.', balanced: 'A comfortable balance of performance and battery life.', performance: 'More performance when your work needs it.'}[s.powerProfile]}</p>${s.powerResult ? callout(s.powerResult) : ''}${UI.section('Session', rows([['lock', 'Lock', 'Keep your session private'], ['moon', 'Sleep', 'Pick up where you left off'], ['logout', 'Log out', 'End your current session'], ['refresh', 'Restart', 'Start fresh'], ['power', 'Shut down', 'Turn off your computer']].map(([glyph, title, sub]) => UI.row({icon: glyph, title, sub, action: 'dev-power-ask', value: title, danger: title === 'Shut down'})).join('')))}`;
      }
    },
    pomodoro: {
      title: 'Focus', width: 460,
      render(state) {
        const s = defaults(state);
        const left = focusLeft(s);
        return `${intro('One thing at a time', s.focusRunning ? 'You have a little space to do your best work.' : 'Choose a quiet stretch. Make something good.')}<div class="dev-focus"><div class="dev-focus-icon">${icon('timer', 28)}</div><div id="dev-focus-time" class="dev-focus-time tabular">${formatTime(left)}</div><p class="hint" id="dev-focus-status">${s.focusRunning ? 'Focus session in progress' : left === 0 ? 'Session complete. Take a breath.' : 'Ready when you are'}</p></div>${choices('Focus duration', String(s.focusMinutes), [['15', '15 min', 'dev-focus-duration'], ['25', '25 min', 'dev-focus-duration'], ['45', '45 min', 'dev-focus-duration']])}<div class="dev-actions dev-actions-fill">${button(s.focusRunning ? 'Pause session' : left === 0 ? 'Start again' : left < s.focusMinutes * 60000 ? 'Resume session' : 'Start focusing', 'dev-focus-toggle', '', 'primary')}${button('Reset', 'dev-focus-reset')}</div>${UI.toggle('focusQuiet', 'Quiet notifications', !!s.focusQuiet, 'moon', 'Keep distractions out of your focus session')}${s.focusComplete ? callout('Session complete. A fresh start is ready when you are.') : ''}`;
      }
    },
    settings: {
      title: 'Preferences', width: 520,
      render(state) {
        const s = defaults(state);
        return `${intro('Make yourself at home', 'The little details that make Sumi yours.')}${UI.section('Island', panel(`<div class="dev-delay"><span class="row-title">Shape</span>${choices('Island shape', s.shape, [['notch', 'Screen edge', 'dev-shape'], ['floating', 'Floating', 'dev-shape']])}</div>${UI.toggle('reduced', 'Reduce motion', !!s.reduced, 'sparkles', 'Quieter transitions, the same clear feedback')}${UI.toggle('dnd', 'Do Not Disturb', !!s.dnd, 'moon', s.dnd ? 'Notifications are silenced' : 'Notifications can appear')}`))}${UI.section('Personalize', rows(UI.row({icon: 'palette', title: 'Appearance', sub: 'Wallpaper, color, and your desktop’s character', route: 'appearance'}) + UI.row({icon: 'grid', title: 'Desktop widgets', sub: 'Keep the things you care about in view', route: 'widgets'})))}${UI.section('Get around', rows(UI.row({icon: 'keyboard', title: 'Keyboard shortcuts', sub: 'A faster way through your day', route: 'help'}) + UI.row({icon: 'volume', title: 'Sound devices', sub: 'Speakers, headphones, and microphone', route: 'audio'})))}<p class="hint dev-settings-note">Preferences here affect this reference only.</p>`;
      }
    }
  };

  const actions = {
    'dev-retry': s => { s.deviceUnavailable = ''; Sumi.render(); Sumi.toast('Sample device connected'); },
    'dev-wifi-select': (s, name) => { s.wifiSelected = name; s.wifiPassword = ''; s.wifiError = ''; Sumi.render(); setTimeout(() => document.getElementById('dev-wifi-password')?.focus(), 60); },
    'dev-wifi-cancel': s => { s.wifiSelected = ''; s.wifiPassword = ''; s.wifiError = ''; Sumi.render(); },
    'dev-wifi-connect': s => {
      if ((s.wifiPassword || '').length < 8) { s.wifiError = 'Use at least 8 characters for the sample password.'; Sumi.render(); return; }
      s.network = s.wifiSelected; s.wifiSelected = ''; s.wifiPassword = ''; s.wifiError = ''; Sumi.render(); Sumi.toast(`Connected to ${s.network}`);
    },
    'dev-wifi-disconnect': s => { const name = s.network; s.network = ''; Sumi.render(); Sumi.toast(`Disconnected from ${name}`); },
    'dev-wifi-scan': s => { s.wifiScanned = true; Sumi.render(); Sumi.toast('Nearby networks updated'); },
    'dev-bt-toggle': (s, name) => { s.btConnected = s.btConnected.includes(name) ? s.btConnected.filter(n => n !== name) : [...s.btConnected, name]; Sumi.render(); Sumi.toast(`${name} ${s.btConnected.includes(name) ? 'connected' : 'disconnected'}`); },
    'dev-bt-pair': (s, name) => { s.btPairing = name; Sumi.render(); },
    'dev-bt-cancel': s => { s.btPairing = ''; Sumi.render(); },
    'dev-bt-confirm': s => { s.btConnected = [...new Set([...s.btConnected, s.btPairing])]; s.btSpeakerPaired = true; const name = s.btPairing; s.btPairing = ''; Sumi.render(); Sumi.toast(`${name} paired and connected`); },
    'dev-bt-scan': s => { s.btScanned = true; Sumi.render(); Sumi.toast('Nearby devices updated'); },
    'dev-output': (s, name) => { s.audioOutput = name; Sumi.render(); Sumi.toast(`Playing through ${name.toLowerCase()}`); },
    'dev-input': (s, name) => { s.audioInput = name; Sumi.render(); },
    'dev-capture-mode': (s, mode) => { s.captureMode = mode; Sumi.render(); },
    'dev-capture-delay': (s, delay) => { s.captureDelay = delay; Sumi.render(); },
    'dev-capture-start': (s, kind) => { s.capturePending = kind; s.captureResult = ''; Sumi.render(); },
    'dev-capture-cancel': s => { s.capturePending = ''; Sumi.render(); },
    'dev-capture-confirm': s => {
      if (s.capturePending === 'record') { s.captureRecording = true; s.captureStarted = Date.now(); Sumi.toast('Demo recording started'); }
      else { s.captureResult = s.captureAnnotate ? 'Sample screenshot captured and ready for markup.' : 'Sample screenshot saved to Pictures / Screenshots.'; Sumi.toast('Screenshot captured in preview'); }
      s.capturePending = ''; Sumi.render();
    },
    'dev-record-stop': s => { s.captureRecording = false; s.captureResult = `Sample recording saved · ${formatTime(Date.now() - s.captureStarted)}`; Sumi.render(); Sumi.toast('Demo recording saved'); },
    'dev-stats-refresh': s => { s.statsRefreshed = true; s.statsSample = !s.statsSample; Sumi.render(); Sumi.toast('Sample readings refreshed'); },
    'dev-power-profile': (s, profile) => { s.powerProfile = profile; Sumi.render(); },
    'dev-power-ask': (s, kind) => { s.powerPending = kind; Sumi.render(); },
    'dev-power-cancel': s => { s.powerPending = ''; Sumi.render(); },
    'dev-power-confirm': s => { s.powerResult = `${s.powerPending} confirmed in preview. Your desktop is unchanged.`; s.powerPending = ''; Sumi.render(); Sumi.toast('Demo action confirmed'); },
    'dev-focus-duration': (s, value) => { s.focusMinutes = Number(value); s.focusRemainingMs = s.focusMinutes * 60000; s.focusRunning = false; s.focusComplete = false; Sumi.render(); },
    'dev-focus-toggle': s => {
      if (s.focusRunning) { s.focusRemainingMs = focusLeft(s); s.focusRunning = false; }
      else { if (s.focusRemainingMs <= 0) s.focusRemainingMs = s.focusMinutes * 60000; s.focusDeadline = Date.now() + s.focusRemainingMs; s.focusRunning = true; s.focusComplete = false; }
      Sumi.render();
    },
    'dev-focus-reset': s => { s.focusRunning = false; s.focusRemainingMs = s.focusMinutes * 60000; s.focusComplete = false; Sumi.render(); },
    'dev-shape': (s, shape) => { s.shape = shape; Sumi.render(); }
  };

  window.SumiPages = Object.assign(window.SumiPages || {}, pages);
  window.SumiActions = Object.assign(window.SumiActions || {}, actions);
  setInterval(() => {
    const s = currentState;
    if (!s) return;
    if (s.focusRunning) {
      const left = focusLeft(s);
      const timer = document.getElementById('dev-focus-time');
      if (timer) timer.textContent = formatTime(left);
      if (left <= 0) { s.focusRunning = false; s.focusRemainingMs = 0; s.focusComplete = true; Sumi.render(); Sumi.toast('Focus session complete. Take a breath.'); }
    }
    const recordTime = document.getElementById('dev-record-time');
    if (recordTime && s.captureRecording) recordTime.textContent = formatTime(Date.now() - s.captureStarted);
  }, 1000);

  const style = document.createElement('style');
  style.textContent = `
    .dev-module{padding:16px;margin-bottom:12px}.dev-module .settings-row{padding-left:0;padding-right:0}.dev-module .settings-row:last-child{border-bottom:0}.dev-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:18px;flex-wrap:wrap}.dev-actions-fill{margin:20px 0}.dev-actions-fill>.btn{flex:1}.dev-footer{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px}.dev-footer .hint{margin:0}.dev-callout{display:flex;gap:9px;align-items:flex-start;padding:12px 14px;border-radius:12px;background:#163023;color:#a7e5bd;font-size:12px;line-height:1.45;margin:12px 0}.dev-callout svg{flex-shrink:0;margin-top:1px}.dev-error{background:#341e1e;color:#ffb0a8}.dev-network-mark{display:flex;justify-content:center;color:#f5f5f7;margin:12px 0 26px}.dev-field-label{display:block;font-size:12px;color:#b6b6c0;margin-bottom:8px}.dev-center{text-align:center}.dev-pair-code{text-align:center;font-size:36px;font-weight:500;letter-spacing:.12em;margin:20px 0}.dev-unavailable{text-align:center;padding-bottom:16px}.dev-delay{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:58px}.dev-delay .segmented{flex:0 1 260px}.dev-capture-hero{display:flex;flex-direction:column;align-items:center;gap:12px;padding:28px 12px;color:#e6e6ed}.dev-capture-hero>svg{color:#acaeb9}.dev-capture-hero strong{font-size:17px;font-weight:550}.dev-capture-preview{padding:12px;border-radius:14px;background:#34333e;min-height:170px;display:flex;align-items:center;justify-content:center}.dev-capture-window{width:90%;height:145px;background:#17171d;border-radius:10px;padding:10px;position:relative}.dev-capture-window>i{display:inline-block;width:6px;height:6px;background:#71717c;border-radius:50%;margin-right:4px}.dev-capture-selection{position:absolute;inset:36px 27px 17px;border:1.5px dashed #c9cad5;background:#ffffff09;border-radius:4px;display:flex;align-items:center;justify-content:center;gap:12px;color:#d8d8e0;font-size:12px}.dev-stat-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}.dev-stat-head>span{display:flex;align-items:center;gap:10px;font-size:14px}.dev-stat-head strong{font-size:24px;letter-spacing:-.025em;font-weight:550}.dev-meter{height:6px;background:#3a3a42;border-radius:6px;overflow:hidden}.dev-meter i{height:100%;display:block;border-radius:inherit;background:#b8bac8}.dev-module>.hint:last-child{margin-bottom:0}.dev-battery{display:flex;justify-content:center;align-items:center;gap:24px;padding:18px 0 24px}.dev-battery-icon{height:43px;width:78px;border:3px solid #8c9194;border-radius:12px;padding:4px;position:relative}.dev-battery-icon:after{content:'';position:absolute;right:-8px;top:12px;width:4px;height:14px;background:#8c9194;border-radius:0 3px 3px 0}.dev-battery-icon span{display:block;width:82%;height:100%;background:#9fdeb4;border-radius:5px}.dev-battery strong{font-size:40px;font-weight:500;letter-spacing:-.03em}.dev-battery strong span{font-size:24px;color:#a8a8b2}.dev-battery .hint{margin:2px 0}.dev-profile-copy{min-height:32px}.dev-focus{text-align:center;padding:20px 0 28px}.dev-focus-icon{color:#dadce6;margin-bottom:16px}.dev-focus-time{font-size:66px;line-height:1.1;font-weight:400;letter-spacing:-.035em}.dev-focus .hint{margin:10px 0 0}.dev-settings-note{margin-top:20px;text-align:center}@media(max-width:520px){.dev-delay{align-items:flex-start;flex-direction:column;gap:10px;padding:12px 0}.dev-delay .segmented{flex:auto;width:100%}.dev-focus-time{font-size:58px}}
  `;
  document.head.appendChild(style);
})();
