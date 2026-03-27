/* ============================================================
   MarketAI Pro – Frontend JS
   Talks to FastAPI at localhost:8000
   ============================================================ */

const API = 'http://localhost:8000';

/* ── State ── */
let state = {
  sessionId: null,
  generatedCopy: null,
  sdxlImagePaths: null,
  imagePrompt: null,
};

/* ═══════════════════════════════════════
   UTILITY
═══════════════════════════════════════ */
function $(id) { return document.getElementById(id); }

function toast(msg, isError = false) {
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' error' : '');
  el.textContent = msg;
  $('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function show(id)  { const el = $(id); if (el) { el.classList.remove('hidden'); } }
function hide(id)  { const el = $(id); if (el) { el.classList.add('hidden'); } }
function toggle(id, show) { show ? show(id) : hide(id); }

function setHtml(id, html) { const el = $(id); if (el) el.innerHTML = html; }

/* ═══════════════════════════════════════
   TABS
═══════════════════════════════════════ */
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => { p.classList.remove('active'); p.classList.add('hidden'); });
    btn.classList.add('active');
    const panel = $('panel' + tab.charAt(0).toUpperCase() + tab.slice(1));
    if (panel) { panel.classList.remove('hidden'); panel.classList.add('active'); }
    if (tab === 'history') loadHistory();
    if (tab === 'visuals') refreshVisualsState();
  });
});

/* ═══════════════════════════════════════
   PLATFORM MULTI-CHIPS
═══════════════════════════════════════ */
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => chip.classList.toggle('active'));
});
function selectedPlatforms() {
  return [...document.querySelectorAll('.chip.active')].map(c => c.dataset.value);
}

/* ═══════════════════════════════════════
   PLATFORM OUTPUT TABS
═══════════════════════════════════════ */
document.querySelectorAll('.ptab').forEach(btn => {
  btn.addEventListener('click', () => {
    const key = btn.dataset.ptab;
    document.querySelectorAll('.ptab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.ptab-panel').forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
    btn.classList.add('active');
    const panel = $('ptab' + key.charAt(0).toUpperCase() + key.slice(1));
    if (panel) { panel.classList.add('active'); panel.style.display = 'block'; }
  });
});

/* ═══════════════════════════════════════
   CHARACTER COUNT
═══════════════════════════════════════ */
const descEl = $('description');
function updateDescCount() { $('descCount').textContent = `${descEl.value.length}/500`; }
descEl.addEventListener('input', updateDescCount);
updateDescCount();

/* ═══════════════════════════════════════
   BRAND DROPDOWN – load brands on start
═══════════════════════════════════════ */
async function loadBrands() {
  try {
    const res = await fetch(`${API}/list-brands`);
    const brands = await res.json();
    const sel = $('brandSelect');
    brands.forEach(b => {
      const opt = document.createElement('option');
      opt.value = b; opt.textContent = b;
      sel.appendChild(opt);
    });
  } catch { /* silent */ }
}

/* ═══════════════════════════════════════
   FILE UPLOAD & PARSE
═══════════════════════════════════════ */
const fileInput = $('fileInput');
const dropZone  = $('dropZone');
const parseBtn  = $('parseBtn');
let pendingFile = null;

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setPendingFile(fileInput.files[0]);
});

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('over');
  if (e.dataTransfer.files[0]) setPendingFile(e.dataTransfer.files[0]);
});

function setPendingFile(file) {
  pendingFile = file;
  $('dropZone').querySelector('.drop-text').textContent = file.name;
  parseBtn.disabled = false;
}

parseBtn.addEventListener('click', async () => {
  if (!pendingFile) return;
  parseBtn.disabled = true;
  parseBtn.textContent = 'Parsing…';
  hide('parseStatus');
  const fd = new FormData();
  fd.append('file', pendingFile);
  try {
    const res = await fetch(`${API}/onboard-brand`, { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Parse failed');
    // refresh brand list
    const opt = document.createElement('option');
    opt.value = data.brand_name; opt.textContent = data.brand_name; opt.selected = true;
    $('brandSelect').appendChild(opt);
    toast(`✅ Brand "${data.brand_name}" onboarded!`);
    const ps = $('parseStatus');
    ps.textContent = `✓ ${data.brand_name} — template stored`;
    ps.classList.remove('hidden');
    if (data.onboarding_summary) renderOnboardSummary(data.onboarding_summary);
  } catch (err) {
    const ps = $('parseStatus');
    ps.textContent = err.message;
    ps.classList.add('error-msg');
    ps.classList.remove('hidden');
    toast(err.message, true);
  } finally {
    parseBtn.textContent = 'Parse & Scrape';
    parseBtn.disabled = false;
  }
});

function renderOnboardSummary(summary) {
  const el = $('onboardSummary');
  el.innerHTML = `<strong>Parsed</strong>: ${summary.search_status || '—'} &nbsp;|&nbsp; ${Object.keys(summary.parsed_fields || {}).length} fields`;
  el.classList.remove('hidden');
}

/* ═══════════════════════════════════════
   MOCK EVENT
═══════════════════════════════════════ */
$('mockEventBtn').addEventListener('click', async () => {
  try {
    const res = await fetch(`${API}/mock-events`);
    const ev = await res.json();
    $('featureName').value = ev.feature_name || '';
    $('description').value = ev.description || '';
    $('audience').value = ev.target_audience || '';
    updateDescCount();
    toast('⚡ Mock event loaded');
  } catch { toast('Could not load event', true); }
});

/* ═══════════════════════════════════════
   GENERATE CAMPAIGN
═══════════════════════════════════════ */
$('generateBtn').addEventListener('click', generateCampaign);

async function generateCampaign() {
  const platforms = selectedPlatforms();
  if (!platforms.length) { toast('Select at least one platform', true); return; }

  const payload = {
    feature_name:   $('featureName').value.trim(),
    description:    $('description').value.trim(),
    target_audience:$('audience').value.trim(),
    tone:           $('tone').value,
    platforms,
    brand_name:     $('brandSelect').value,
  };
  if (!payload.feature_name) { toast('Enter a feature name', true); return; }

  $('generateBtn').disabled = true;
  hide('generateBtnText'); show('generateSpinner');
  hide('generateError'); hide('outputContent'); show('outputEmpty');

  try {
    const res = await fetch(`${API}/generate-sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data.detail || data));

    state.sessionId = data.session_id;
    state.generatedCopy = data.copy;
    state.imagePrompt = data.copy?.image_prompt || payload.feature_name;

    renderOutput(data);
    toast('✅ Campaign generated!');
    refreshVisualsState();
  } catch (err) {
    const el = $('generateError');
    el.textContent = 'Error: ' + err.message;
    el.classList.remove('hidden');
    toast('Generation failed', true);
  } finally {
    $('generateBtn').disabled = false;
    show('generateBtnText'); hide('generateSpinner');
  }
}

/* ── Render generated output ── */
function renderOutput(data) {
  hide('outputEmpty');
  show('outputContent');

  // Score ring
  const score = data.brand_score || 0;
  $('scoreNumber').textContent = score;
  const arc = $('scoreArc');
  const circumference = 251.2;
  arc.style.strokeDashoffset = circumference - (score / 100) * circumference;
  if (score >= 80) arc.style.stroke = 'var(--secondary)';
  else if (score >= 60) arc.style.stroke = '#FDCB6E';
  else arc.style.stroke = 'var(--error)';

  const desc = score >= 80 ? 'Elite brand resonance' : score >= 60 ? 'Good alignment' : 'Needs tuning';
  $('scoreDesc').textContent = desc;

  // Stat chips
  const ts = data.token_stats || {};
  $('statTokens').textContent = `${ts.total_tokens || '—'} tokens`;
  $('statLatency').textContent = ts.generation_time_ms ? `${(ts.generation_time_ms/1000).toFixed(1)}s` : '—';

  // Platform content
  populatePlatform('linkedin', data.copy?.linkedin);
  populatePlatform('twitter',  data.copy?.twitter);
  populatePlatform('instagram', data.copy?.instagram);

  // Stats / Validation
  $('genStats').textContent = JSON.stringify(data.token_stats, null, 2);
  $('genValidation').textContent = JSON.stringify(data.validation, null, 2);
}

function populatePlatform(key, item) {
  const ta = $('out' + key.charAt(0).toUpperCase() + key.slice(1));
  const hd = $('hash' + key.charAt(0).toUpperCase() + key.slice(1));
  if (!ta) return;
  ta.value = item?.caption || '';
  hd.innerHTML = (item?.hashtags || []).map(h => `<span class="hashtag">${h}</span>`).join('');
}

/* ═══════════════════════════════════════
   VISUALS TAB
═══════════════════════════════════════ */
function refreshVisualsState() {
  if (!state.sessionId) {
    show('visualsLocked'); hide('visualsReady'); return;
  }
  hide('visualsLocked'); show('visualsReady');
  if (state.sdxlImagePaths) {
    renderImages(state.sdxlImagePaths);
    activateStep(3);
  }
}

$('generateVisualsBtn').addEventListener('click', generateVisuals);

async function generateVisuals() {
  if (!state.sessionId) { toast('Generate a campaign first', true); return; }

  $('generateVisualsBtn').disabled = true;
  hide('visBtnText'); show('visSpinner');
  show('visStatus'); hide('imageResults');

  activateStep(2);

  try {
    const res = await fetch(`${API}/generate-image`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        prompt: state.imagePrompt,
        platforms: ['linkedin', 'instagram'],
        provider: 'local',
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data.detail || data));

    state.sdxlImagePaths = data.image_paths_by_platform;
    renderImages(state.sdxlImagePaths);
    activateStep(3);
    show('packageActions');
    toast('✅ Visuals generated!');
  } catch (err) {
    toast('Visual generation failed: ' + err.message, true);
  } finally {
    $('generateVisualsBtn').disabled = false;
    show('visBtnText'); hide('visSpinner');
    hide('visStatus');
  }
}

function renderImages(paths) {
  show('imageResults');
  const li = $('imgLiSrc');
  const ig = $('imgIgSrc');
  if (paths.linkedin)  li.src = pathToUrl(paths.linkedin);
  if (paths.instagram) ig.src = pathToUrl(paths.instagram);
}

function pathToUrl(p) {
  // Convert absolute Windows path → /static URL served by FastAPI
  const norm = p.replace(/\\/g, '/');
  const idx = norm.indexOf('/output/');
  if (idx === -1) return p;
  // Slice off everything before+including '/output' → keep '/<sessionId>/...'
  return `${API}/static${norm.slice(idx + '/output'.length)}`;
}

/* ── Step tracker ── */
function activateStep(n) {
  for (let i = 1; i <= 4; i++) {
    const el = document.querySelector(`#step${i}`);
    if (!el) continue;
    el.classList.remove('done', 'active');
    if (i < n) el.classList.add('done');
    else if (i === n) el.classList.add('active');
  }
}

/* ── Build Package ── */
$('buildPkgBtn').addEventListener('click', async () => {
  if (!state.sessionId) return;
  $('buildPkgBtn').textContent = 'Building…';
  $('buildPkgBtn').disabled = true;
  try {
    const res = await fetch(`${API}/package/${state.sessionId}`);
    if (!res.ok) throw new Error('Package build failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const dl = $('downloadLink');
    dl.href = url;
    dl.download = `marketai_${state.sessionId.slice(0,8)}.zip`;
    dl.style.display = 'inline-flex';
    activateStep(4);
    toast('📦 Package ready!');
  } catch (err) {
    toast(err.message, true);
  } finally {
    $('buildPkgBtn').textContent = '📦 Build Package';
    $('buildPkgBtn').disabled = false;
  }
});

/* ── Slack Notify ── */
$('slackBtn').addEventListener('click', async () => {
  if (!state.sessionId) return;
  try {
    const res = await fetch(`${API}/notify/${state.sessionId}`, { method: 'POST' });
    const data = await res.json();
    if (data.ok) { toast('🚀 Slack notification sent!'); }
    else { toast('Slack not configured or failed', true); }
  } catch { toast('Slack request failed', true); }
});

/* ═══════════════════════════════════════
   HISTORY
═══════════════════════════════════════ */
async function loadHistory() {
  setHtml('historyContent', '<p class="muted">Loading…</p>');
  try {
    const res = await fetch(`${API}/history`);
    const records = await res.json();
    if (!records.length) {
      setHtml('historyContent', '<p class="muted">No history yet.</p>');
      return;
    }
    const rows = records.map(r => {
      const sc = r.brand_score || 0;
      const cls = sc >= 80 ? 'high' : sc >= 60 ? 'med' : 'low';
      const date = new Date(r.timestamp || Date.now()).toLocaleString();
      return `<tr>
        <td>${r.feature_name || '—'}</td>
        <td><span class="score-badge ${cls}">${sc}/100</span></td>
        <td>${r.token_count || '—'}</td>
        <td>${r.generation_time_ms ? (r.generation_time_ms/1000).toFixed(1)+'s' : '—'}</td>
        <td>${(r.platforms||[]).join(', ')}</td>
        <td style="color:var(--on-surface);font-size:12px">${date}</td>
      </tr>`;
    }).join('');
    setHtml('historyContent', `
      <table class="history-table">
        <thead><tr><th>Feature</th><th>Score</th><th>Tokens</th><th>Time</th><th>Platforms</th><th>Date</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`);
  } catch {
    setHtml('historyContent', '<p class="muted">Could not load history — is the backend running?</p>');
  }
}

/* ═══════════════════════════════════════
   SERVE IMAGES — Static mount helper
   FastAPI serves output/ as /static
═══════════════════════════════════════ */
// Mount output dir as /static in FastAPI if not done already (handled in main.py)

/* ═══════════════════════════════════════
   INIT
═══════════════════════════════════════ */
loadBrands();

// Show ptab-panels correctly on init
document.querySelectorAll('.ptab-panel').forEach(p => {
  if (!p.classList.contains('active')) p.style.display = 'none';
  else p.style.display = 'block';
});
