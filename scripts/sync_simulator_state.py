from pathlib import Path

path = Path('/Users/vince/sTIMulation/templates/index.html')
text = path.read_text()

old_block = """socket.on('connect',       ()=>{ setConnBadge('connected'); addLog({msg:'Connected to simulation server',cls:'green',sim_time:0}); });
socket.on('disconnect',    ()=>setConnBadge('disconnected'));
socket.on('connect_error', ()=>setConnBadge('reconnecting'));

socket.on('stats', data=>{
  STATE.stats=data;
  updateStatsUI(data);
  anHandleStats(data);
});
"""
new_block = """async function refreshSimulatorContext() {
  try {
    const [statusRes, configRes] = await Promise.all([fetch('/api/status'), fetch('/api/config')]);
    if (!statusRes.ok || !configRes.ok) return;
    const [status, config] = await Promise.all([statusRes.json(), configRes.json()]);
    applyConfigToUI(config);
    syncRuntimeState(status);
  } catch (error) {
    console.warn('Failed to refresh simulator context', error);
  }
}

socket.on('connect',       ()=>{ setConnBadge('connected'); addLog({msg:'Connected to simulation server',cls:'green',sim_time:0}); refreshSimulatorContext(); });
socket.on('disconnect',    ()=>setConnBadge('disconnected'));
socket.on('connect_error', ()=>setConnBadge('reconnecting'));

socket.on('stats', data=>{
  STATE.stats={...STATE.stats,...data};
  syncRuntimeState(data);
  anHandleStats(data);
});
"""
if old_block not in text:
    raise SystemExit('socket block not found')
text = text.replace(old_block, new_block)

old_helper = """function updateButtonStates() {
  const s=document.getElementById('btn-start'),p=document.getElementById('btn-pause');
  if(STATE.simRunning){s.style.display='none';p.style.display='block';p.classList.remove('active-yellow');}
  else{s.style.display='block';s.classList.remove('active-green');p.style.display='none';p.classList.remove('active-yellow');}
}

function getConfig(){ return{ green:+document.getElementById('sl-green').value, yellow:+document.getElementById('sl-yellow').value, red:+document.getElementById('sl-red').value, scenario:document.getElementById('sel-scenario').value, road_type:+document.getElementById('sel-road').value, right_turn:document.getElementById('ck-rturn').checked, speed:+document.getElementById('sl-speed').value, seed:+document.getElementById('sl-seed').value }; }
"""
new_helper = """function applyConfigToUI(cfg) {
  if (!cfg) return;
  if (cfg.green_duration != null) document.getElementById('sl-green').value = cfg.green_duration;
  if (cfg.yellow_duration != null) document.getElementById('sl-yellow').value = cfg.yellow_duration;
  if (cfg.red_duration != null) document.getElementById('sl-red').value = cfg.red_duration;
  if (cfg.scenario) document.getElementById('sel-scenario').value = cfg.scenario;
  if (cfg.road_type != null) document.getElementById('sel-road').value = String(cfg.road_type);
  if (cfg.right_turn_free != null) document.getElementById('ck-rturn').checked = !!cfg.right_turn_free;
  if (cfg.speed_factor != null) document.getElementById('sl-speed').value = cfg.speed_factor;
  if (cfg.seed != null) document.getElementById('sl-seed').value = cfg.seed;
  document.getElementById('v-speed').textContent = document.getElementById('sl-speed').value + '×';
  document.getElementById('v-green').textContent = document.getElementById('sl-green').value;
  document.getElementById('v-yellow').textContent = document.getElementById('sl-yellow').value;
  document.getElementById('v-red').textContent = document.getElementById('sl-red').value;
  document.getElementById('rt-label').textContent = document.getElementById('ck-rturn').checked ? 'Allowed' : 'Signal only';
  document.getElementById('hdr-scenario').textContent = document.getElementById('sel-scenario').options[document.getElementById('sel-scenario').selectedIndex].text;
}

function syncRuntimeState(data) {
  if (!data) return;
  STATE.simRunning = !!data.running;
  STATE.simPaused  = !!data.paused;
  STATE.stats      = {...STATE.stats, ...data};
  updateStatsUI(STATE.stats);
  updatePhaseHeaders(STATE.stats);
  updateButtonStates();
}

function updateButtonStates() {
  const s=document.getElementById('btn-start'),p=document.getElementById('btn-pause');
  if(STATE.simRunning){
    s.style.display='none';
    p.style.display='block';
    p.classList.toggle('active-yellow', STATE.simPaused);
    p.innerHTML = STATE.simPaused
      ? '<svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" style="margin-right:4px;vertical-align:middle"><polygon points="2,1 9,5 2,9"/></svg>Resume'
      : '<svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" style="margin-right:4px;vertical-align:middle"><rect x="2" y="1" width="2.5" height="8"/><rect x="5.5" y="1" width="2.5" height="8"/></svg>Pause';
  } else {
    s.style.display='block';
    s.classList.remove('active-green');
    p.style.display='none';
    p.classList.remove('active-yellow');
    p.innerHTML = '<svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" style="margin-right:4px;vertical-align:middle"><rect x="2" y="1" width="2.5" height="8"/><rect x="5.5" y="1" width="2.5" height="8"/></svg>Pause';
  }
}

function getConfig(){ return{ green:+document.getElementById('sl-green').value, yellow:+document.getElementById('sl-yellow').value, red:+document.getElementById('sl-red').value, scenario:document.getElementById('sel-scenario').value, road_type:+document.getElementById('sel-road').value, right_turn:document.getElementById('ck-rturn').checked, speed:+document.getElementById('sl-speed').value, seed:+document.getElementById('sl-seed').value }; }
"""
if old_helper not in text:
    raise SystemExit('button/helper block not found')
text = text.replace(old_helper, new_helper)

# make config changes persist locally as a fallback
old_oncfg = """function onCfgChange(){
  socket.emit('cmd_update_config',{ green_duration:+document.getElementById('sl-green').value, yellow_duration:+document.getElementById('sl-yellow').value, red_duration:+document.getElementById('sl-red').value, scenario:document.getElementById('sel-scenario').value, road_type:+document.getElementById('sel-road').value, right_turn_free:document.getElementById('ck-rturn').checked, speed_factor:+document.getElementById('sl-speed').value, seed:+document.getElementById('sl-seed').value });
  document.getElementById('rt-label').textContent=document.getElementById('ck-rturn').checked?'Allowed':'Signal only';
  document.getElementById('hdr-scenario').textContent=document.getElementById('sel-scenario').options[document.getElementById('sel-scenario').selectedIndex].text;
}
"""
new_oncfg = """function onCfgChange(){
  const cfg = { green_duration:+document.getElementById('sl-green').value, yellow_duration:+document.getElementById('sl-yellow').value, red_duration:+document.getElementById('sl-red').value, scenario:document.getElementById('sel-scenario').value, road_type:+document.getElementById('sel-road').value, right_turn_free:document.getElementById('ck-rturn').checked, speed_factor:+document.getElementById('sl-speed').value, seed:+document.getElementById('sl-seed').value };
  localStorage.setItem('stimulation:lastConfig', JSON.stringify(cfg));
  socket.emit('cmd_update_config', cfg);
  applyConfigToUI(cfg);
}
"""
if old_oncfg not in text:
    raise SystemExit('onCfgChange block not found')
text = text.replace(old_oncfg, new_oncfg)

# restore cached UI state before websocket refresh as a fallback
anchor = """window.addEventListener('resize', resize);
function zoomAt(factor, focusX=canvas.width/2, focusY=canvas.height/2) {
"""
replacement = """window.addEventListener('resize', resize);
const __cachedConfig = (() => { try { return JSON.parse(localStorage.getItem('stimulation:lastConfig') || 'null'); } catch { return null; } })();
if (__cachedConfig) applyConfigToUI(__cachedConfig);
function zoomAt(factor, focusX=canvas.width/2, focusY=canvas.height/2) {
"""
if anchor in text:
    text = text.replace(anchor, replacement)

path.write_text(text)
print('synced simulator state UI')
