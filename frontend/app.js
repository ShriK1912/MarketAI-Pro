/* ============================================================
   MarketAI Pro – Frontend JS  (Fixed: tab switching, image URLs, carousel/GIF/MP4)
   ============================================================ */

const API = 'http://localhost:8000';

let state = {
  sessionId: null,
  generatedCopy: null,
  imagePrompt: null,
  hasVisuals: false,
};

/* ── Helpers ─────────────────────────────────── */
const $  = id => document.getElementById(id);
const el = q => document.querySelector(q);

function show(id) { const e = $(id); if (e) e.style.display = ''; }   // restore default
function showFlex(id) { const e = $(id); if (e) e.style.display = 'flex'; }
function showBlock(id) { const e = $(id); if (e) e.style.display = 'block'; }
function hide(id) { const e = $(id); if (e) e.style.display = 'none'; }
function setHtml(id, html) { const e = $(id); if (e) e.innerHTML = html; }

function toast(msg, isError = false) {
  const el = document.createElement('div');
  el.className = 'toast' + (isError ? ' error' : '');
  el.textContent = msg;
  $('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

/* ── Convert backend file path → API /static URL ──
   Handles both:
     absolute: C:\Users\...\output\SESSION\images\file.png
     relative: output\SESSION\images\file.png
*/
function pathToUrl(p) {
  if (!p) return '';
  const norm = p.replace(/\\/g, '/');
  // Match "output/" anywhere in the normalised path
  const match = norm.match(/(?:^|.*\/)output\/(.*)/);
  if (!match) return `${API}/static/${norm}`;
  return `${API}/static/${match[1]}`;
}

/* ═══════════════════════════════════════
   TABS
═══════════════════════════════════════ */
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    ['panelGenerate','panelVisuals','panelHistory'].forEach(id => hide(id));
    const panelId = 'panel' + tab.charAt(0).toUpperCase() + tab.slice(1);
    showBlock(panelId);

    if (tab === 'history') loadHistory();
    if (tab === 'visuals') refreshVisualsState();
  });
});

/* ═══════════════════════════════════════
   PLATFORM CHIPS  (multi-select)
═══════════════════════════════════════ */
document.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => c.classList.toggle('active')));
const selectedPlatforms = () => [...document.querySelectorAll('.chip.active')].map(c => c.dataset.value);

/* ═══════════════════════════════════════
   PLATFORM OUTPUT TABS  (fixed: use style, not class)
═══════════════════════════════════════ */
document.querySelectorAll('.ptab').forEach(btn => {
  btn.addEventListener('click', () => {
    const key = btn.dataset.ptab;
    // deactivate all
    document.querySelectorAll('.ptab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.ptab-panel').forEach(p => { p.style.display = 'none'; });
    // activate chosen
    btn.classList.add('active');
    const panel = $('ptab' + key.charAt(0).toUpperCase() + key.slice(1));
    if (panel) panel.style.display = 'block';
  });
});

/* ═══════════════════════════════════════
   CHAR COUNT
═══════════════════════════════════════ */
const descEl = $('description');
const updateDescCount = () => { $('descCount').textContent = `${descEl.value.length}/500`; };
descEl.addEventListener('input', updateDescCount);
updateDescCount();

/* ═══════════════════════════════════════
   BRAND LIST
═══════════════════════════════════════ */
async function loadBrands() {
  try {
    const brands = await fetch(`${API}/list-brands`).then(r => r.json());
    brands.forEach(b => {
      const o = document.createElement('option');
      o.value = b; o.textContent = b;
      $('brandSelect').appendChild(o);
    });
  } catch {/*silent*/}
}

/* ═══════════════════════════════════════
   FILE UPLOAD / PARSE
═══════════════════════════════════════ */
let pendingFile = null;
const dropZone = $('dropZone');
const fileInput = $('fileInput');
const parseBtn  = $('parseBtn');

fileInput.addEventListener('change', () => { if (fileInput.files[0]) setPendingFile(fileInput.files[0]); });
dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('over');
  if (e.dataTransfer.files[0]) setPendingFile(e.dataTransfer.files[0]);
});
function setPendingFile(f) {
  pendingFile = f;
  dropZone.querySelector('.drop-text').textContent = f.name;
  parseBtn.disabled = false;
}

parseBtn.addEventListener('click', async () => {
  if (!pendingFile) return;
  parseBtn.disabled = true; parseBtn.textContent = 'Parsing…';
  hide('parseStatus');
  const fd = new FormData();
  fd.append('file', pendingFile);
  try {
    const res  = await fetch(`${API}/onboard-brand`, { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Parse failed');
    const opt  = document.createElement('option');
    opt.value  = data.brand_name; opt.textContent = data.brand_name; opt.selected = true;
    $('brandSelect').appendChild(opt);
    toast(`✅ "${data.brand_name}" onboarded!`);
    const ps = $('parseStatus');
    ps.textContent = `✓ ${data.brand_name} stored`;
    ps.className = 'status-msg'; ps.style.display = 'block';
  } catch (err) {
    const ps = $('parseStatus');
    ps.textContent = err.message;
    ps.className = 'error-msg'; ps.style.display = 'block';
    toast(err.message, true);
  } finally {
    parseBtn.textContent = 'Parse & Scrape'; parseBtn.disabled = false;
  }
});

/* ═══════════════════════════════════════
   MOCK EVENT
═══════════════════════════════════════ */
$('mockEventBtn').addEventListener('click', async () => {
  try {
    const ev = await fetch(`${API}/mock-events`).then(r => r.json());
    $('featureName').value  = ev.feature_name    || '';
    $('description').value  = ev.description     || '';
    $('audience').value     = ev.target_audience || '';
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
  const featureName = $('featureName').value.trim();
  if (!featureName)      { toast('Enter a feature name', true); return; }
  if (!platforms.length) { toast('Select at least one platform', true); return; }

  $('generateBtn').disabled = true;
  hide('generateBtnText'); showBlock('generateSpinner');
  hide('generateError');
  hide('outputContent'); showBlock('outputEmpty');

  try {
    const res = await fetch(`${API}/generate-sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        feature_name:    featureName,
        description:     $('description').value.trim(),
        target_audience: $('audience').value.trim(),
        tone:            $('tone').value,
        platforms,
        brand_name:      $('brandSelect').value,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data.detail || data));

    state.sessionId     = data.session_id;
    state.generatedCopy = data.copy;
    state.imagePrompt   = data.copy?.image_prompt || featureName;
    state.hasVisuals    = false;

    renderOutput(data);
    toast('✅ Campaign generated!');
    refreshVisualsState();
  } catch (err) {
    const e = $('generateError');
    e.textContent = 'Error: ' + err.message;
    e.style.display = 'block';
    toast('Generation failed', true);
  } finally {
    $('generateBtn').disabled = false;
    showBlock('generateBtnText'); hide('generateSpinner');
  }
}

/* ── Render output ── */
function renderOutput(data) {
  hide('outputEmpty');
  showBlock('outputContent');

  // Score ring animation
  const score = data.brand_score || 0;
  $('scoreNumber').textContent = score;
  const arc = $('scoreArc');
  const C = 251.2;
  arc.style.strokeDashoffset = C - (score / 100) * C;
  arc.style.stroke = score >= 80 ? 'var(--secondary)' : score >= 60 ? '#FDCB6E' : 'var(--error)';

  $('scoreDesc').textContent = score >= 80 ? 'Elite brand resonance' : score >= 60 ? 'Good alignment' : 'Needs tuning';

  const ts = data.token_stats || {};
  $('statTokens').textContent  = `${ts.total_tokens  || '—'} tokens`;
  $('statLatency').textContent = ts.generation_time_ms ? `${(ts.generation_time_ms/1000).toFixed(1)}s` : '—';

  // Populate all 3 platform panels
  populatePlatform('linkedin',  data.copy?.linkedin);
  populatePlatform('twitter',   data.copy?.twitter);
  populatePlatform('instagram', data.copy?.instagram);

  $('genStats').textContent      = JSON.stringify(data.token_stats, null, 2);
  $('genValidation').textContent = JSON.stringify(data.validation,  null, 2);
}

function populatePlatform(key, item) {
  const K   = key.charAt(0).toUpperCase() + key.slice(1);
  const ta  = $('out' + K);
  const hd  = $('hash' + K);
  if (!ta) return;
  ta.value   = item?.caption || '(not generated for this platform)';
  hd.innerHTML = (item?.hashtags || []).map(h => `<span class="hashtag">${h}</span>`).join('');
}

/* ═══════════════════════════════════════
   VISUALS TAB
═══════════════════════════════════════ */
function refreshVisualsState() {
  if (!state.sessionId) {
    showBlock('visualsLocked'); hide('visualsReady'); return;
  }
  hide('visualsLocked'); showBlock('visualsReady');
}

$('generateVisualsBtn').addEventListener('click', generateVisuals);

// Fake progress bar that ticks up while waiting
let progressInterval = null;
function startProgress() {
  let pct = 0;
  const bar = $('visProgressBar');
  if (bar) bar.style.width = '0%';
  progressInterval = setInterval(() => {
    pct = Math.min(pct + (Math.random() * 1.2), 90); // never hits 100 until done
    if (bar) bar.style.width = pct + '%';
  }, 3000);
}
function finishProgress() {
  clearInterval(progressInterval);
  const bar = $('visProgressBar');
  if (bar) { bar.style.width = '100%'; setTimeout(() => bar.style.width = '0%', 800); }
}

async function generateVisuals() {
  if (!state.sessionId) { toast('Generate a campaign first', true); return; }

  $('generateVisualsBtn').disabled = true;
  hide('visBtnText'); showBlock('visSpinner');

  // Reset previous results
  hide('imageResults'); hide('carouselResults'); hide('gifResults'); hide('videoResults'); hide('packageActions');

  // Show loading
  showFlex('visStatus');
  startProgress();
  activateStep(2);

  try {
    const res = await fetch(`${API}/generate-image`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        prompt:     state.imagePrompt,
        platforms:  ['linkedin', 'instagram'],
        provider:   'local',
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data.detail || data));

    finishProgress();
    hide('visStatus');
    state.hasVisuals = true;

    // ── Hero images ──
    const paths = data.image_paths_by_platform || {};
    if (paths.linkedin || paths.instagram) {
      if (paths.linkedin)  { $('imgLiSrc').src = pathToUrl(paths.linkedin); }
      if (paths.instagram) { $('imgIgSrc').src = pathToUrl(paths.instagram); }
      showBlock('imageResults');
    }

    // ── Carousel ──
    const slides = data.carousel_paths || [];
    if (slides.length) {
      const grid = $('carouselGrid');
      grid.innerHTML = slides.map((p, i) =>
        `<div class="carousel-slide"><img src="${pathToUrl(p)}" alt="Slide ${i+1}" /><p class="slide-label">Slide ${i+1}</p></div>`
      ).join('');
      showBlock('carouselResults');
    }

    // ── GIF ──
    if (data.gif_path) {
      $('gifSrc').src = pathToUrl(data.gif_path);
      showBlock('gifResults');
    }

    // ── Video ──
    if (data.mp4_path) {
      const vid = $('videoSrc');
      vid.src = pathToUrl(data.mp4_path);
      vid.load();
      showBlock('videoResults');
    }

    showBlock('packageActions');
    activateStep(3);
    toast('✅ Visuals generated!');
  } catch (err) {
    finishProgress();
    hide('visStatus');
    toast('Visual generation failed: ' + err.message, true);
  } finally {
    $('generateVisualsBtn').disabled = false;
    showBlock('visBtnText'); hide('visSpinner');
  }
}

/* ── Step tracker ── */
function activateStep(n) {
  for (let i = 1; i <= 4; i++) {
    const e = $('step' + i);
    if (!e) continue;
    e.classList.remove('done','active');
    if (i < n) e.classList.add('done');
    else if (i === n) e.classList.add('active');
  }
}

/* ── Build Package ── */
$('buildPkgBtn').addEventListener('click', async () => {
  if (!state.sessionId) return;
  $('buildPkgBtn').textContent = 'Building…'; $('buildPkgBtn').disabled = true;
  try {
    const res = await fetch(`${API}/package/${state.sessionId}`);
    if (!res.ok) throw new Error('Package build failed');
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const dl   = $('downloadLink');
    dl.href = url; dl.download = `marketai_${state.sessionId.slice(0,8)}.zip`;
    dl.style.display = 'inline-flex';
    activateStep(4);
    toast('📦 Package ready!');
  } catch (err) { toast(err.message, true); }
  finally { $('buildPkgBtn').textContent = '📦 Build Package'; $('buildPkgBtn').disabled = false; }
});

/* ── Slack Notify ── */
$('slackBtn').addEventListener('click', async () => {
  if (!state.sessionId) return;
  try {
    const data = await fetch(`${API}/notify/${state.sessionId}`, { method: 'POST' }).then(r => r.json());
    toast(data.ok ? '🚀 Slack notification sent!' : 'Slack not configured', !data.ok);
  } catch { toast('Slack request failed', true); }
});

/* ═══════════════════════════════════════
   HISTORY
═══════════════════════════════════════ */
async function loadHistory() {
  setHtml('historyContent', '<p class="muted">Loading…</p>');
  try {
    const records = await fetch(`${API}/history`).then(r => r.json());
    if (!records.length) { setHtml('historyContent', '<p class="muted">No history yet.</p>'); return; }
    const rows = records.map(r => {
      const sc  = r.brand_score || 0;
      const cls = sc >= 80 ? 'high' : sc >= 60 ? 'med' : 'low';
      const dt  = r.timestamp ? new Date(r.timestamp).toLocaleString() : '—';
      return `<tr>
        <td>${r.feature_name || '—'}</td>
        <td><span class="score-badge ${cls}">${sc}/100</span></td>
        <td>${r.token_count || '—'}</td>
        <td>${r.generation_time_ms ? (r.generation_time_ms/1000).toFixed(1)+'s' : '—'}</td>
        <td>${(r.platforms||[]).join(', ')}</td>
        <td style="color:var(--on-surface);font-size:12px">${dt}</td>
      </tr>`;
    }).join('');
    setHtml('historyContent', `
      <table class="history-table">
        <thead><tr><th>Feature</th><th>Score</th><th>Tokens</th><th>Time</th><th>Platforms</th><th>Date</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`);
  } catch { setHtml('historyContent', '<p class="muted">Could not load history — is the backend running?</p>'); }
}

/* ═══════════════════════════════════════
   INIT
═══════════════════════════════════════ */
loadBrands();
