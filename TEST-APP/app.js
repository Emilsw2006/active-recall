// Trusted Types Policy for browser compatibility (fix white screen)
if (window.trustedTypes && window.trustedTypes.createPolicy) {
  window.trustedTypes.createPolicy('default', {
    createHTML: (s) => s,
    createScriptURL: (s) => s,
    createScript: (s) => s,
  });
}

// Si el frontend viene del propio backend...
// Si viene del servidor estático (8080), apuntamos al backend manualmente
const API = (location.port === '8080')
  ? `http://${location.hostname}:8000`
  : location.origin;
const COLORS = ['#e8a030','#4f7eff','#4dd68a','#ff5c5c','#a78bfa','#f472b6','#38bdf8','#fb923c','#facc15','#34d399'];

// Stop audio when tab goes hidden (phone locks screen, switches app, etc.)
document.addEventListener('visibilitychange', () => {
  if (document.hidden) stopCurrentAudio();
});

// ─ State ─
let token  = localStorage.getItem('ar_t') || '';
let uid    = localStorage.getItem('ar_u') || '';
let uname  = localStorage.getItem('ar_n') || '';
let umundo = localStorage.getItem('ar_mundo') || '';
let curSubjectId    = localStorage.getItem('ar_subj_id')    || '';
let curSubjectName  = localStorage.getItem('ar_subj_name')  || '';
let curSubjectColor = localStorage.getItem('ar_subj_color') || '';
let curDocId        = '';
let pollingTimer    = null;
let pickedColor     = COLORS[0];

// ─ Helpers ─
const $  = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;');

function cleanDocTitle(filename) {
  return (filename || '')
    .replace(/\.(pdf|docx?|txt|pptx?|xlsx?)$/i, '')
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .trim() || filename;
}

function toggleDocCard(id) {
  const card = document.getElementById('doc-card-' + id);
  if (!card) return;
  const wasOpen = card.classList.contains('open');
  document.querySelectorAll('.doc-card.open').forEach(c => c.classList.remove('open'));
  if (!wasOpen) {
    card.classList.add('open');
    loadDocTemas(id);
  }
}

function toggleSessCard(id) {
  const card = document.getElementById('sess-acc-' + id);
  if (!card) return;
  const wasOpen = card.classList.contains('open');
  document.querySelectorAll('.sess-acc-item.open').forEach(c => c.classList.remove('open'));
  if (!wasOpen) card.classList.add('open');
}

function toast(msg, type='info') {
  const container = $('toasts');
  if (!container) return console.warn("Toasts container missing");
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${{ok:'✓',err:'✕',info:'ℹ'}[type]}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

async function api(path, opts={}) {
  const r = await fetch(API + path, {
    headers: { 'Content-Type':'application/json', ...(token ? {Authorization:`Bearer ${token}`} : {}) },
    ...opts,
  });
  const d = await r.json().catch(() => ({}));
  if (r.status === 401 || r.status === 403) {
    // Token inválido o expirado — cerrar sesión automáticamente
    logout();
    throw new Error(T('toast_session_expired'));
  }
  if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
  return d;
}
// ─ Helper: show/hide btn by ID (null-safe) ─
function _showBtn(id, show) { const el = $(id); if (el) el.style.display = show ? '' : 'none'; }

// ─ Navigation Arch (7 Vistas) ─
function switchView(viewName) {
  const views = ['historial', 'hub', 'materiales', 'lobby', 'duelo', 'resumen', 'test'];
  const slidePos = { 
    'historial': -100, 
    'hub': 0, 
    'materiales': 100, 
    'lobby': 200, 
    'duelo': 300, 
    'resumen': 400, 
    'test': 500 
  };

  views.forEach(v => {
    const btn = $(`nav-btn-${v}`);
    const view = $(`v-${v}`);
    if (btn) btn.classList.toggle('active', v === viewName);
    if (view) {
      view.classList.toggle('active', v === viewName);
      view.style.transform = `translateX(${slidePos[v] - slidePos[viewName]}%)`;
    }
  });

  // Session/Lobby mode — hide header + nav
  const appEl = $('screen-app');
  const wasInDuelo = appEl && appEl.classList.contains('session-mode');
  if (appEl) {
    appEl.classList.toggle('session-mode', viewName === 'duelo' || viewName === 'test');
    appEl.classList.toggle('lobby-mode', viewName === 'lobby');
  }
  // Stop any playing audio when leaving the session view
  if (wasInDuelo && viewName !== 'duelo') {
    stopCurrentAudio();
  }

  // Unlock AudioContext on any user-initiated navigation
  _ensureAudioCtx();

  // FAB upload + nav shift — solo en materiales
  const matFab = $('mat-fab');
  const navEl = document.querySelector('.floating-nav');
  const showFab = viewName === 'materiales' && curSubjectId;
  if (matFab) {
    matFab.style.display = showFab ? 'flex' : 'none';
    // Position FAB right of the nav bar
    if (showFab && navEl) {
      requestAnimationFrame(() => {
        const navRect = navEl.getBoundingClientRect();
        matFab.style.left = (navRect.right + 10) + 'px';
      });
    }
  }
  if (navEl) {
    navEl.classList.toggle('nav-with-fab', showFab);
  }

  // Load data
  if (viewName === 'hub' || viewName === 'materiales') {
    if (curSubjectId) loadDocs();
    else loadSubjectsHome();
    if (viewName === 'hub') refreshNotifications();
  } else if (viewName === 'historial') {
    loadSessions();
    loadPlanes();
  } else if (viewName === 'lobby') {
    if (!curSubjectId) { switchView('hub'); return; }
    loadTopicsLobby();
  }
}

// ─ Notificaciones dinámicas ─
let _notifIdx = 0;
let _notifInterval = null;

async function refreshNotifications() {
  const uid = localStorage.getItem('ar_u');
  if (!uid) return;
  const track = $('notif-track');
  const dots = $('notif-dots');
  if (!track) return;

  let notifs = [];
  try {
    notifs = await api(`/notificaciones/${uid}`);
  } catch(e) { /* silently fail */ }

  if (!notifs.length) {
    track.innerHTML = `<div class="notif-item"><div class="notif-item-title">${T('hub_notif_title')}</div><div class="notif-item-sub">${T('hub_notif_sub')}</div></div>`;
    dots.innerHTML = '';
    if (_notifInterval) { clearInterval(_notifInterval); _notifInterval = null; }
    return;
  }

  track.innerHTML = notifs.map(n => {
    const ac = JSON.stringify(n.accion || {}).replace(/'/g, '&#39;');
    return `<div class="notif-item notif-${n.color}" data-action='${ac}' onclick="handleNotifClick(this)">
      <div class="notif-item-title">${n.titulo}</div>
      <div class="notif-item-sub">${n.mensaje}</div>
    </div>`;
  }).join('');

  dots.innerHTML = notifs.map((_, i) =>
    `<span class="notif-dot${i === 0 ? ' active' : ''}" onclick="goNotif(${i})"></span>`
  ).join('');

  _notifIdx = 0;
  track.scrollLeft = 0;

  if (_notifInterval) { clearInterval(_notifInterval); _notifInterval = null; }
}

function goNotif(i) {
  const track = $('notif-track');
  if (!track) return;
  _notifIdx = i;
  track.scrollTo({ left: track.offsetWidth * i, behavior: 'smooth' });
}

function _onNotifScroll(el) {
  if (!el) return;
  const i = Math.round(el.scrollLeft / el.offsetWidth) || 0;
  _notifIdx = i;
  const dots = $('notif-dots');
  if (dots) {
    dots.querySelectorAll('.notif-dot').forEach((d, j) => d.classList.toggle('active', j === i));
  }
}

function handleNotifClick(el) {
  const action = JSON.parse((el.dataset.action || '{}').replace(/&#39;/g, "'"));
  if (!action.tipo) return;
  switch (action.tipo) {
    case 'reanudar_sesion':
      resumeSessionFromHistory(action.sesion_id, action.asignatura_id, action.asignatura_nombre || '');
      break;
    case 'continuar_plan':
      switchView('historial');
      break;
    case 'ver_errores':
      switchView('historial');
      break;
    case 'iniciar_sesion':
      switchView('lobby');
      break;
  }
}

function openAjustesModal() {
  const name  = uname || 'Explorador';
  const email = localStorage.getItem('ar_email') || '';
  const nameEl  = $('ajustes-name');   if (nameEl)  nameEl.textContent  = name;
  const emailEl = $('ajustes-email-lbl'); if (emailEl) emailEl.textContent = email;
  const avatarEl = $('ajustes-avatar'); if (avatarEl) avatarEl.textContent = name.charAt(0).toUpperCase();
  // Hide edit forms
  const editDiv = $('ajustes-name-edit'); if (editDiv) editDiv.style.display = 'none';
  const mundoEdit = $('ajustes-mundo-edit'); if (mundoEdit) mundoEdit.style.display = 'none';
  // Populate mundo label
  const mundoLbl = $('lbl-mundo-actual');
  if (mundoLbl) mundoLbl.textContent = umundo || 'Sin definir';
  // Highlight current language button
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.lang === currentLang);
  });
  $('modal-ajustes').classList.add('open');
}

function changeLang(lang) {
  applyLang(lang);
  // Re-translate buttons that have text content set dynamically
  const mundoLbl = $('lbl-mundo-actual');
  if (mundoLbl && !umundo) mundoLbl.textContent = 'Sin definir';
  // Re-render tipo-label if in test
  const tipoEl = $('test-tipo-label');
  if (tipoEl && _testPreguntas[_testIndex]) {
    const tipoLabels = {
      una_correcta: T('test_select_one'),
      dos_correctas: T('test_select_two'),
      una_incorrecta: T('test_which_wrong'),
    };
    tipoEl.textContent = tipoLabels[_testPreguntas[_testIndex].tipo] || T('test_select_one');
  }
  // Update next/confirm buttons if visible
  const confirmBtn = $('btn-test-confirm'), nextBtn = $('btn-test-next');
  if (confirmBtn && confirmBtn.style.display !== 'none') confirmBtn.textContent = T('test_confirm');
  if (nextBtn && nextBtn.style.display !== 'none') {
    nextBtn.textContent = _testIndex + 1 < _testPreguntas.length ? T('test_next') : T('test_see_result');
  }
}

function openMundoEdit() {
  const editDiv = $('ajustes-mundo-edit');
  const inp = $('ajustes-mundo-inp');
  if (!editDiv || !inp) return;
  inp.value = umundo || '';
  editDiv.style.display = 'block';
  setTimeout(() => inp.focus(), 50);
}

function cancelMundoEdit() {
  const editDiv = $('ajustes-mundo-edit');
  if (editDiv) editDiv.style.display = 'none';
}

async function saveMundoEdit() {
  const inp = $('ajustes-mundo-inp');
  if (!inp) return;
  const newMundo = inp.value.trim();
  if (!newMundo) return toast(T('validation_write_topic'), 'err');
  try {
    await api(`/auth/update-mundo-analogias?usuario_id=${uid}&mundo=${encodeURIComponent(newMundo)}`);
    umundo = newMundo;
    localStorage.setItem('ar_mundo', umundo);
    const lbl = $('lbl-mundo-actual'); if (lbl) lbl.textContent = umundo;
    cancelMundoEdit();
    toast(T('toast_analogies_updated'), 'ok');
  } catch(e) { toast(e.message, 'err'); }
}

function startEditName() {
  const editDiv = $('ajustes-name-edit');
  const inp = $('ajustes-name-inp');
  if (!editDiv || !inp) return;
  inp.value = uname || '';
  editDiv.style.display = 'block';
  setTimeout(() => inp.focus(), 50);
}

function cancelEditName() {
  const editDiv = $('ajustes-name-edit');
  if (editDiv) editDiv.style.display = 'none';
}

async function saveEditName() {
  const inp = $('ajustes-name-inp');
  if (!inp) return;
  const newName = inp.value.trim();
  if (!newName) return toast(T('validation_write_name'), 'err');
  try {
    await api(`/auth/update-nombre?usuario_id=${uid}&nombre=${encodeURIComponent(newName)}`);
    uname = newName;
    localStorage.setItem('ar_n', uname);
    const nameEl = $('ajustes-name'); if (nameEl) nameEl.textContent = uname;
    const avatarEl = $('ajustes-avatar'); if (avatarEl) avatarEl.textContent = uname.charAt(0).toUpperCase();
    const greetEl = $('greet-name'); if (greetEl) greetEl.textContent = uname;
    cancelEditName();
    toast(T('toast_name_updated'), 'ok');
  } catch(e) { toast(e.message, 'err'); }
}
function closeAjustesModal() { $('modal-ajustes').classList.remove('open'); }
function closeAjustesBg(e) { if(e.target === $('modal-ajustes')) closeAjustesModal(); }

function switchHistTab(tab) {
  const sesEl = $('hist-panel-sesiones');
  const plEl  = $('hist-panel-planes');
  const tabS  = $('hist-tab-sesiones');
  const tabP  = $('hist-tab-planes');
  if (!sesEl || !plEl) return;
  if (tab === 'sesiones') {
    sesEl.style.display = ''; plEl.style.display = 'none';
    tabS.classList.add('on'); tabP.classList.remove('on');
  } else {
    sesEl.style.display = 'none'; plEl.style.display = '';
    tabS.classList.remove('on'); tabP.classList.add('on');
  }
}

function goHome() {
  switchView('hub');
  // Restore header from memory/localStorage immediately (no async delay)
  if (curSubjectId && curSubjectName) {
    _applySubjectHeader(curSubjectName, curSubjectColor);
  }
  const nameEl = $('greet-name');
  if (nameEl) nameEl.textContent = uname || 'Estudiante';
  if (curSubjectId) loadDocs();
  else loadSubjectsHome();
}

// ─ UI Selectors ─
let modeSelector = 'voz';

function setStudyMode(mode) {
  modeSelector = mode;
  // New tab style
  ['ltab-voz','ltab-test'].forEach(id => $(id) && $(id).classList.remove('active'));
  const tabEl = mode === 'voz' ? $('ltab-voz') : $('ltab-test');
  if (tabEl) tabEl.classList.add('active');
  // Slide indicator
  const ind = $('lm-indicator');
  if (ind) ind.classList.toggle('right', mode === 'test');
  checkMicPermission();
}

function pickDuration(dur) {
  sessDurationType = dur; // also update session variable
  ['dur-corta','dur-larga'].forEach(id => $(id) && $(id).classList.remove('on'));
  const active = dur === 'corta' ? 'dur-corta' : 'dur-larga';
  if ($(active)) $(active).classList.add('on');
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('ar_theme', theme);
  $('tog-light').classList.toggle('on', theme === 'light');
  $('tog-dark').classList.toggle('on', theme === 'dark');
}

function openSettings() {
  if (confirm(T('confirm_logout'))) {
    logout();
  }
}

// ─ Auth ─
function switchTab(tab) {
  $('tab-login').classList.toggle('on', tab==='login');
  $('tab-register').classList.toggle('on', tab==='register');
  $('form-login').style.display    = tab==='login'    ? 'block' : 'none';
  $('form-register').style.display = tab==='register' ? 'block' : 'none';
  $('auth-err').style.display = 'none';
}

function showAuthErr(msg) {
  const el = $('auth-err');
  el.textContent = msg;
  el.style.display = 'block';
}

async function doLogin() {
  const email = $('l-email').value.trim();
  const pass  = $('l-pass').value;
  if (!email || !pass) return showAuthErr('Rellena todos los campos');
  const btn = $('btn-login');
  btn.disabled = true; btn.textContent = T('auth_btn_login_loading');
  try {
    const d = await api('/auth/login', { method:'POST', body: JSON.stringify({email, password:pass}) });
    saveSession(d); enterApp();
  } catch(e) { showAuthErr(e.message); }
  finally { btn.disabled=false; btn.textContent=T('auth_btn_login'); }
}

async function doRegister() {
  const nombre = $('r-name').value.trim();
  const email  = $('r-email').value.trim();
  const pass   = $('r-pass').value;
  const mundo  = $('r-mundo').value.trim();
  if (!nombre || !email || !pass) return showAuthErr('Rellena nombre, email y contraseña');
  const btn = $('btn-register');
  btn.disabled=true; btn.textContent=T('auth_btn_register_loading');
  try {
    const d = await api('/auth/register', { method:'POST', body: JSON.stringify({nombre,email,password:pass,mundo_analogias:mundo||null}) });
    saveSession(d); enterApp();
    // New user: open subject creation wizard for onboarding
    setTimeout(() => openSubjectWizard(), 600);
  } catch(e) { showAuthErr(e.message); }
  finally { btn.disabled=false; btn.textContent=T('auth_btn_register'); }
}

function saveSession(d) {
  token=d.token; uid=d.usuario_id; uname=d.nombre;
  localStorage.setItem('ar_t', token);
  localStorage.setItem('ar_u', uid);
  localStorage.setItem('ar_n', uname);
  if (d.email) localStorage.setItem('ar_email', d.email);
  if (d.mundo_analogias != null) { umundo = d.mundo_analogias; localStorage.setItem('ar_mundo', umundo); }
}

function logout() {
  token=uid=uname='';
  ['ar_t','ar_u','ar_n'].forEach(k => localStorage.removeItem(k));
  $('screen-auth').classList.add('active');
  $('screen-app').classList.remove('active');
}

function enterApp() {
  $('screen-auth').classList.remove('active');
  $('screen-app').classList.add('active');
  const nameEl = $('greet-name');
  if (nameEl) nameEl.textContent = uname || 'Estudiante';
  goHome();
}

async function loadSubjectsHome() {
  try {
    const data = await api(`/asignaturas/${uid}`);
    _subjData  = data;
    
    // Bottom Sheet list with search support & active subject highlight
    const subjectList = $('sb-subjects');
    if (subjectList) {
      if (!data.length) {
        subjectList.innerHTML = `<div class="empty-state" style="margin-top:16px;font-size:.85rem">${T('empty_no_subjects')}</div>`;
      } else {
        const PENCIL = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`;
        const TRASH  = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>`;
        const CHECK  = `<svg class="sheet-item-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>`;
        subjectList.innerHTML = data.map(s => `
          <div class="sheet-item ${s.id === curSubjectId ? 'active-subject' : ''}"
            data-name="${esc(s.nombre)}"
            onclick="goSubject('${s.id}', '${esc(s.nombre)}', '${s.color||COLORS[0]}')">
            <div class="sheet-item-dot" style="background:${s.color||COLORS[0]}"></div>
            <div class="sheet-item-name">${esc(s.nombre)}</div>
            <div style="font-size:.73rem; color:var(--txt3); white-space:nowrap; flex-shrink:0">${s.recuento_documentos || 0} docs</div>
            ${CHECK}
            <button class="sheet-action-btn" title="Renombrar" onclick="editSubject('${s.id}','${esc(s.nombre)}');event.stopPropagation()">${PENCIL}</button>
            <button class="sheet-action-btn danger" title="Eliminar" onclick="deleteSubject('${s.id}','${esc(s.nombre)}');event.stopPropagation()">${TRASH}</button>
          </div>`).join('');
      }
    }

    if (!curSubjectId && data.length > 0) {
      goSubject(data[0].id, data[0].nombre, data[0].color);
    } else if (!curSubjectId && data.length === 0) {
      $('bc-subject').textContent = T('subj_empty');
      $('header-dot').style.background = 'var(--txt3)';
    }
  } catch(e) { console.error(e); }
}


// ─ Subject edit / delete ─
async function editSubject(id, currentName) {
  const newName = prompt('Nuevo nombre:', currentName);
  if (!newName || newName.trim() === currentName) return;
  try {
    await api(`/asignaturas/${id}`, { method: 'PUT', body: JSON.stringify({ nombre: newName.trim() }) });
    if (id === curSubjectId) {
      curSubjectName = newName.trim();
      localStorage.setItem('ar_subj_name', curSubjectName);
      _applySubjectHeader(curSubjectName, curSubjectColor);
    }
    toast(T('toast_subject_renamed'), 'ok');
    loadSubjectsHome();
  } catch(e) { toast(e.message, 'err'); }
}

async function deleteSubject(id, name) {
  if (!confirm(TF('confirm_delete_subject', {name}))) return;
  try {
    await api(`/asignaturas/${id}`, { method: 'DELETE' });
    toast(T('toast_subject_deleted'), 'ok');
    if (id === curSubjectId) {
      curSubjectId = ''; curSubjectName = ''; curSubjectColor = '';
      localStorage.removeItem('ar_subj_id');
      localStorage.removeItem('ar_subj_name');
      localStorage.removeItem('ar_subj_color');
    }
    await loadSubjectsHome();
    if (!curSubjectId) { $('bc-subject').textContent = T('subj_empty'); }
  } catch(e) { toast(e.message, 'err'); }
}

// ─ Subject ─
async function goSubject(id, name, color=null) {
  closeModal();
  curSubjectId   = id;
  curSubjectName = name;
  clearInterval(pollingTimer);
  resetProgress();
  
  // Persist to localStorage so header survives page reload
  localStorage.setItem('ar_subj_id',    id);
  localStorage.setItem('ar_subj_name',  name);
  
  // Determine color
  let c = color;
  if (!c && _subjData.length) {
    const s = _subjData.find(x => x.id === id);
    if (s) c = s.color || COLORS[0];
  }
  if (c) {
    curSubjectColor = c;
    localStorage.setItem('ar_subj_color', c);
  }
  
  // Update header immediately
  _applySubjectHeader(name, c);
  
  switchView('hub');
  loadDocs();
}

function _applySubjectHeader(name, color) {
  const textEl = $('bc-subject');
  const dotEl  = $('header-dot');
  if (textEl) textEl.textContent = name || T('subj_empty');
  if (dotEl && color) dotEl.style.background = color;
}

async function loadDocs() {
  if (!curSubjectId) return;
  const list = $('doc-list');
  list.innerHTML = `<div class="empty-state">${T('empty_loading')}</div>`;
  try {
    const docs = await api(`/documentos/asignatura/${curSubjectId}`);
    if (!docs.length) {
      list.innerHTML = `<div class="empty-state">${T('empty_no_notes')}</div>`;
      return;
    }
    list.className = 'doc-list';
    // Separate: ready/processing docs vs error docs
    const okDocs    = docs.filter(d => d.estado !== 'error');
    const errorDocs = docs.filter(d => d.estado === 'error');

    const PDF_ICON = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="opacity:.7"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
    const SPIN_ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="animation:spin .9s linear infinite;flex-shrink:0"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`;

    const renderOk = okDocs.map(d => {
      const title = cleanDocTitle(d.titulo || d.nombre_archivo);
      const fecha = d.fecha_subida ? new Date(d.fecha_subida).toLocaleDateString('es',{day:'numeric',month:'short'}) : '—';
      const isProc = d.estado === 'procesando';
      const bodyHtml = isProc
        ? `<div style="display:flex;align-items:center;gap:8px;padding:8px 0;font-size:.82rem;color:var(--txt2)">${SPIN_ICON} Extrayendo conceptos con IA...</div>`
        : `<div class="doc-temas-list" id="doc-temas-${d.id}"><div class="atom-loading">Abriendo...</div></div>
           <div class="doc-card-actions" style="margin-top:10px">
             <button class="doc-btn danger" onclick="deleteDocument('${d.id}');event.stopPropagation()">Eliminar doc</button>
           </div>`;
      return `
      <div class="doc-card${isProc ? ' doc-processing' : ''}" id="doc-card-${d.id}" onclick="${isProc ? '' : `toggleDocCard('${d.id}')`}">
        <div class="doc-card-header" style="${isProc ? 'cursor:default' : ''}">
          <span class="doc-card-icon">${isProc ? SPIN_ICON : PDF_ICON}</span>
          <div class="doc-card-info">
            <div class="doc-card-title">${esc(title)}</div>
            <div class="doc-card-date">${isProc ? T('mat_processing') : fecha}</div>
          </div>
          ${isProc ? '' : `<svg class="doc-card-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>`}
        </div>
        <div class="doc-card-body">${bodyHtml}</div>
      </div>`;
    }).join('');

    // Error docs: shown separately at the bottom, muted, delete only
    const renderErrors = errorDocs.length ? `
      <div style="font-size:.72rem;color:var(--red);margin:12px 0 6px;padding:0 2px;display:flex;align-items:center;gap:5px;opacity:.8">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        ${errorDocs.length} documento${errorDocs.length > 1 ? 's' : ''} con error de procesamiento
      </div>
      ${errorDocs.map(d => {
        const title = cleanDocTitle(d.titulo || d.nombre_archivo);
        return `<div class="doc-card" style="opacity:.55" id="doc-card-${d.id}">
          <div class="doc-card-header" style="cursor:default">
            <span class="doc-card-icon">${PDF_ICON}</span>
            <div class="doc-card-info">
              <div class="doc-card-title" style="text-decoration:line-through">${esc(title)}</div>
              <div class="doc-card-date" style="color:var(--red)">Error al procesar</div>
            </div>
            <button class="doc-btn danger" style="flex-shrink:0" onclick="deleteDocument('${d.id}');event.stopPropagation()">Borrar</button>
          </div>
        </div>`;
      }).join('')}` : '';

    list.innerHTML = renderOk + renderErrors;
    if (!okDocs.length && !errorDocs.length) {
      list.innerHTML = `<div class="empty-state">${T('empty_no_notes')}</div>`;
    }

    const inProg = docs.some(d => d.estado === 'procesando');
    if (inProg && !pollingTimer) {
      pollingTimer = setInterval(loadDocs, 4000);
    } else if (!inProg && pollingTimer) {
      clearInterval(pollingTimer);
      pollingTimer = null;
    }
  } catch(e) {
    list.innerHTML = `<div class="empty-state" style="color:var(--red)">${e.message}</div>`;
  }
}

async function deleteDocument(docId) {
  if(!confirm(T('confirm_delete_doc'))) return;
  try {
    await api(`/documento/${docId}`, { method: 'DELETE' });
    toast(T('toast_doc_deleted'), "ok");
    loadDocs();
  } catch(e) {
    toast(e.message, "err");
  }
}

async function loadDocTemas(docId) {
  const container = document.getElementById(`doc-temas-${docId}`);
  if (!container) return;
  container.innerHTML = `<div class="atom-loading">${T('lobby_loading_topics')}</div>`;
  try {
    const data = await api(`/documento/${docId}/temas`);
    const temas = data.temas || [];
    if (!temas.length) {
      // Fallback: show atoms directly if no temas
      const atoms = await api(`/atomos/documento/${docId}`);
      if (!atoms.length) {
        container.innerHTML = `<div class="atom-loading">${T('empty_no_content')}</div>`;
        return;
      }
      container.innerHTML = atoms.map(a => `
        <div class="doc-tema-item">
          <span class="doc-tema-title">${esc(a.titulo || 'Concepto')}</span>
        </div>`).join('');
      return;
    }
    container.innerHTML = temas.map(t => `
      <div class="doc-tema-item" onclick="toggleTemaBody('tema-body-${t.id}');event.stopPropagation()">
        <div class="doc-tema-row">
          <svg class="doc-tema-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>
          <span class="doc-tema-title">${esc(t.titulo)}</span>
          <span class="doc-tema-count">${t.n_atomos} átomos</span>
        </div>
        <div class="doc-tema-body" id="tema-body-${t.id}" style="display:none">
          ${(t.subtemas || []).length
            ? (t.subtemas || []).map(st => `
                <div class="doc-subtema-item">
                  <span class="doc-subtema-title">${esc(st.titulo)}</span>
                  <span class="doc-tema-count">${st.n_atomos}</span>
                </div>`).join('')
            : `<div class="atom-loading" style="padding:8px 0">Sin subtemas</div>`
          }
        </div>
      </div>`).join('');
  } catch(e) {
    container.innerHTML = `<div class="atom-loading" style="color:var(--red)">${e.message}</div>`;
  }
}

function toggleTemaBody(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const isOpen = el.style.display !== 'none';
  el.style.display = isOpen ? 'none' : 'block';
  // Rotate chevron
  const row = el.previousElementSibling;
  if (row) {
    const chev = row.querySelector('.doc-tema-chevron');
    if (chev) chev.style.transform = isOpen ? '' : 'rotate(180deg)';
  }
}

async function deleteAtom(atomId, docId) {
  try {
    await api(`/atomos/${atomId}`, { method: 'DELETE' });
    const el = $('atom-item-' + atomId);
    if (el) el.remove();
    const countEl = document.querySelector(`#doc-card-${docId} .doc-card-atoms-count`);
    if (countEl) {
      const remaining = document.querySelectorAll(`#doc-card-${docId} .atom-item`).length;
      countEl.textContent = `${remaining} conceptos`;
    }
    toast(T('toast_atoms_deleted'), 'ok');
  } catch(e) {
    toast(e.message, 'err');
  }
}

async function deleteAllAtoms(docId) {
  if (!confirm(T('confirm_delete_atoms'))) return;
  try {
    const atoms = await api(`/atomos/documento/${docId}`);
    if (!atoms.length) return toast(T('toast_no_atoms_delete'), 'info');
    await Promise.all(atoms.map(a => api(`/atomos/${a.id}`, { method: 'DELETE' })));
    toast(T('toast_atoms_deleted'), 'ok');
    const container = document.querySelector(`#doc-card-${docId} .doc-card-atoms-list`);
    if (container) container.innerHTML = '<div class="atom-loading">Sin conceptos extraídos.</div>';
    const countEl = document.querySelector(`#doc-card-${docId} .doc-card-atoms-count`);
    if (countEl) countEl.textContent = '0 conceptos';
  } catch(e) {
    toast(e.message, 'err');
  }
}

// ─ Upload ─
function dragOver(e)  { e.preventDefault(); $('upload-zone').classList.add('drag'); }
function dragLeave(e) { $('upload-zone').classList.remove('drag'); }
function onDrop(e)    { e.preventDefault(); $('upload-zone').classList.remove('drag'); if(e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]); }
function fileSelected(e) { if(e.target.files[0]) uploadFile(e.target.files[0]); }

function resetProgress() {
  // Progress card elements may not exist in current UI — guard all accesses
  const pc = $('prog-card'); if (pc) pc.classList.remove('show');
  const pf = $('prog-fill'); if (pf) pf.style.width = '0';
  const pp = $('prog-pct');  if (pp) pp.textContent = '0%';
  ['ps-upload','ps-gemini','ps-embed','ps-done'].forEach(id => {
    const el = $(id); if (el) el.classList.remove('active','done');
  });
}

function setStep(stepId) {
  const order = ['ps-upload','ps-gemini','ps-embed','ps-done'];
  const idx   = order.indexOf(stepId);
  const pcts  = [18,50,80,100];
  order.forEach((id,i) => {
    const el = $(id); if (!el) return;
    el.classList.remove('active','done');
    if      (i < idx)  el.classList.add('done');
    else if (i === idx) el.classList.add('active');
  });
  const pct = pcts[idx] || 0;
  const pf = $('prog-fill'); if (pf) pf.style.width = pct + '%';
  const pp = $('prog-pct');  if (pp) pp.textContent = pct + '%';
}

async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) return toast(T('toast_pdf_only'),'err');
  $('file-inp').value = '';
  const displayName = cleanDocTitle(file.name);
  toast(T('toast_uploading'), 'info');

  const form = new FormData();
  form.append('pdf_file', file);
  form.append('usuario_id', uid);
  form.append('asignatura_id', curSubjectId);

  try {
    const res = await fetch(`${API}/documento/upload`, {
      method:'POST', headers:{Authorization:`Bearer ${token}`}, body:form,
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail);
    curDocId = d.documento_id;

    toast(T('toast_uploaded_processing'), 'info');
    await loadDocs();

    clearInterval(pollingTimer);
    pollingTimer = setInterval(async () => {
      try {
        const estado = await api(`/documento/${curDocId}/estado`);
        if (estado.estado === 'listo') {
          clearInterval(pollingTimer); pollingTimer = null;
          toast(T('toast_doc_ready'), 'ok');
          await loadDocs();
        } else if (estado.estado === 'error') {
          clearInterval(pollingTimer); pollingTimer = null;
          toast(T('toast_processing_error'), 'err');
          await loadDocs();
        }
      } catch {}
    }, 3500);
  } catch(e) {
    toast(e.message, 'err');
  }
}

// Document viewer atom list removed to keep experience minimal y clean.

// ─ Modal ─
function openModal() {
  buildColorPicker();
  // Reset panels
  const searchWrap = $('search-subj-wrap');
  const createForm = $('create-subj-form');
  const searchInput = $('search-subj-input');
  if (searchWrap) searchWrap.style.display = 'none';
  if (createForm) createForm.style.display = 'none';
  if (searchInput) searchInput.value = '';
  $('modal-bg').classList.add('open');
  loadSubjectsHome();
}
function closeModal() { $('modal-bg').classList.remove('open'); }
function closeModalBg(e) { if(e.target === $('modal-bg')) closeModal(); }

// Toggle buscador de asignaturas
function toggleSubjectSearch() {
  const wrap = $('search-subj-wrap');
  if (!wrap) return;
  const visible = wrap.style.display !== 'none';
  wrap.style.display = visible ? 'none' : 'block';
  if (!visible) {
    const inp = $('search-subj-input');
    if (inp) { inp.value = ''; inp.focus(); filterSubjects(''); }
  }
}

// Filtrar lista de asignaturas por texto
function filterSubjects(query) {
  const q = (query || '').toLowerCase();
  document.querySelectorAll('#sb-subjects .sheet-item').forEach(item => {
    const name = (item.dataset.name || '').toLowerCase();
    item.style.display = name.includes(q) ? '' : 'none';
  });
}

// Mostrar formulario de crear asignatura
function showCreateSubject() {
  const form = $('create-subj-form');
  if (!form) return;
  form.style.display = 'block';
  buildColorPicker();
  const inp = $('m-name');
  if (inp) { inp.value = ''; setTimeout(() => inp.focus(), 150); }
}

// Ocultar formulario de crear asignatura
function hideCreateSubject() {
  const form = $('create-subj-form');
  if (form) form.style.display = 'none';
}

function buildColorPicker() {
  const container = $('color-picker');
  if(!container) return;
  container.innerHTML = COLORS.map(c => `
    <div class="c-opt ${c === pickedColor ? 'on' : ''}" 
         style="background:${c}" 
         onclick="selectColor('${c}', this)"></div>
  `).join('');
}

function selectColor(color, el) {
  pickedColor = color;
  document.querySelectorAll('.c-opt').forEach(opt => opt.classList.remove('on'));
  el.classList.add('on');
}

async function createSubject() {
  const name = $('m-name').value.trim();
  if(!name) return toast(T('validation_write_name'),'err');
  try {
    const s = await api('/asignaturas/', {
      method:'POST',
      body: JSON.stringify({usuario_id:uid, nombre:name, color:pickedColor})
    });
    closeModal();
    toast(T('toast_subject_created'),'ok');
    loadSubjectsHome();
    if (s && s.id) goSubject(s.id, s.nombre, s.color);
  } catch(e) { toast(e.message,'err'); }
}

// ─ Subject Wizard ─
let _wizSubjectId = null;
let _wizPickedColor = COLORS[0];
let _wizPendingUploads = 0;

function openSubjectWizard() {
  _wizSubjectId = null;
  _wizPickedColor = pickedColor;
  _wizPendingUploads = 0;
  closeModal();

  // Reset wizard
  const nameInp = $('wiz-name');
  if (nameInp) nameInp.value = '';
  $('wiz-file-list').innerHTML = '';
  $('wiz-file-inp').value = '';

  // Step 1 active
  document.getElementById('wizard-step1').classList.add('active');
  document.getElementById('wizard-step2').classList.remove('active');

  buildWizardColorPicker();
  $('subject-wizard').style.display = 'flex';
  setTimeout(() => nameInp && nameInp.focus(), 200);
}

function closeSubjectWizard() {
  $('subject-wizard').style.display = 'none';
  _wizSubjectId = null;
}

function buildWizardColorPicker() {
  const container = $('wiz-color-picker');
  if (!container) return;
  container.innerHTML = COLORS.map(c => `
    <div class="c-opt ${c === _wizPickedColor ? 'on' : ''}"
         style="background:${c}"
         onclick="selectWizardColor('${c}', this)"></div>
  `).join('');
}

function selectWizardColor(color, el) {
  _wizPickedColor = color;
  document.querySelectorAll('#wiz-color-picker .c-opt').forEach(o => o.classList.remove('on'));
  el.classList.add('on');
}

async function wizardStep1Next() {
  const name = ($('wiz-name') || {}).value?.trim();
  if (!name) return toast(T('validation_write_name'), 'err');

  const btn = $('wiz-btn-next');
  if (btn) { btn.disabled = true; btn.textContent = T('subj_creating'); }

  try {
    const s = await api('/asignaturas/', {
      method: 'POST',
      body: JSON.stringify({ usuario_id: uid, nombre: name, color: _wizPickedColor }),
    });
    _wizSubjectId = s.id;
    curSubjectId   = s.id;
    curSubjectName = s.nombre;
    curSubjectColor = s.color || _wizPickedColor;
    localStorage.setItem('ar_subj_id',    curSubjectId);
    localStorage.setItem('ar_subj_name',  curSubjectName);
    localStorage.setItem('ar_subj_color', curSubjectColor);
    _applySubjectHeader(curSubjectName, curSubjectColor);
    toast(T('toast_subject_created'), 'ok');

    // Go to step 2
    $('wiz-subject-name').textContent = name;
    document.getElementById('wizard-step1').classList.remove('active');
    document.getElementById('wizard-step2').classList.add('active');
  } catch(e) {
    toast(e.message, 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = T('wiz_next'); }
  }
}

function wizardBack() {
  document.getElementById('wizard-step2').classList.remove('active');
  document.getElementById('wizard-step1').classList.add('active');
}

function wizardFileSelected(event) {
  const files = Array.from(event.target.files || []);
  event.target.value = '';
  files.forEach(file => {
    if (!file.name.toLowerCase().endsWith('.pdf')) return toast(T('toast_pdf_only'), 'err');
    _uploadWizardFile(file);
  });
}

function _wizUpdateEmpezarBtn() {
  const btn = document.querySelector('#wizard-step2 .wizard-btn-primary');
  if (!btn) return;
  if (_wizPendingUploads > 0) {
    btn.disabled = true;
    btn.textContent = `${T('mat_uploading')} (${_wizPendingUploads})`;
  } else {
    btn.disabled = false;
    btn.textContent = T('wiz_start');
  }
}

async function _uploadWizardFile(file) {
  if (!_wizSubjectId) return toast(T('validation_create_subject_first'), 'err');
  const list = $('wiz-file-list');
  const itemId = 'wiz-file-' + Date.now();
  const item = document.createElement('div');
  item.className = 'wiz-file-item';
  item.id = itemId;
  item.innerHTML = `<span class="wiz-file-name">${esc(file.name)}</span><span class="wiz-file-status">${T('mat_uploading')}</span>`;
  list.appendChild(item);

  _wizPendingUploads++;
  _wizUpdateEmpezarBtn();

  const form = new FormData();
  form.append('pdf_file', file);
  form.append('usuario_id', uid);
  form.append('asignatura_id', _wizSubjectId);

  try {
    const res = await fetch(`${API}/documento/upload`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form,
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail);
    const st = item.querySelector('.wiz-file-status');
    if (st) st.textContent = T('mat_processing');
    item.classList.add('done');
  } catch(e) {
    const st = item.querySelector('.wiz-file-status');
    if (st) st.textContent = T('mat_error_upload');
    item.classList.add('error');
    toast(e.message, 'err');
  } finally {
    _wizPendingUploads = Math.max(0, _wizPendingUploads - 1);
    _wizUpdateEmpezarBtn();
  }
}

async function wizardFinish() {
  if (_wizPendingUploads > 0) {
    return toast(T('validation_wait_upload'), 'info');
  }
  closeSubjectWizard();
  await loadSubjectsHome();
  // Re-apply header in case loadSubjectsHome reset anything
  if (curSubjectId && curSubjectName) {
    _applySubjectHeader(curSubjectName, curSubjectColor || COLORS[0]);
  }
  switchView('hub');
  if (curSubjectId) loadDocs();
}

// ─ Session state ─
let sessSubjectId = '';
let sessDurationType = 'corta';
let sessModoVoz = true;
let sessSubjectName = '';
let sessDocTopics = []; // [{id, titulo, n_atomos}]
let sessId = '';
let sessPlanId = ''; // plan_id if this session belongs to a plan
let sessWs = null;
let sessMediaRecorder = null;
let sessStream = null;
let sessState = 'IDLE';
let sessGreenCount = 0, sessYellowCount = 0, sessRedCount = 0;
let _sessAnswered = [];       // [{pregunta, respuesta_usuario, ruta, texto_completo, flashcard}]
let _currentQPregunta = '';  // text of active question (set on pregunta msg)
let vadAudioCtx = null;
let vadAnimId = null;
let vadSilenceTimer = null;
let vadNoAudioTimer = null;
let vadHasSentAudio = false;
let _wsReconnectAttempts = 0;

const CHECK_SVG = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>`;

function renderTopicList() {
  const container = $('topic-list');
  if (!container) return;
  if (!sessDocTopics.length) {
    container.innerHTML = `<div style="padding:20px;text-align:center;color:rgba(255,255,255,0.50);font-size:.85rem">${T('empty_no_notes')}</div>`;
    return;
  }
  container.innerHTML = sessDocTopics.map((t, i) => `
    <div class="lobby-topic-item checked" id="topic-${i}" onclick="toggleTopic(${i})">
      <div class="lobby-topic-cb">${CHECK_SVG}</div>
      <span class="lobby-topic-name">${esc(t.titulo)}</span>
      <span class="lobby-topic-n">${t.n_atomos} átomos</span>
    </div>
  `).join('');
}

function toggleTopic(i) {
  const el = $(`topic-${i}`);
  if (!el) return;
  el.classList.toggle('checked');
}

function loadTopicsLobby() {
  const list = $('topic-list');
  if (!list) return;
  // Reset lobby state to defaults
  setStudyMode(modeSelector || 'voz');
  pickDuration(sessDurationType || 'corta');
  const subId = curSubjectId || sessSubjectId;
  if (!subId) {
    list.innerHTML = `<div style="padding:20px;text-align:center;color:rgba(255,255,255,0.50);font-size:.85rem">${T('validation_select_subject')}</div>`;
    return;
  }
  list.innerHTML = `<div style="padding:20px;text-align:center;color:rgba(255,255,255,0.50);font-size:.85rem">${T('lobby_loading_topics')}</div>`;

  checkMicPermission();

  api(`/documentos/asignatura/${subId}/temas`)
    .then(data => {
      sessDocTopics = data;
      if (!data.length) {
        list.innerHTML = `<div class="empty-state">${T('empty_no_notes')}</div>`;
        return;
      }
      renderTopicList();
    })
    .catch(e => {
      list.innerHTML = `<div class="empty-state" style="color:var(--red)">${e.message}</div>`;
    });
}

function startSessionFlow() {
  const selected = (sessDocTopics || []).filter((t, i) => {
    const el = $(`topic-${i}`);
    return el && el.classList.contains('checked');
  });

  if (!selected.length) return toast(T('validation_select_topic'), 'err');

  toast(T('sess_starting'), 'info');
  api('/sesion/crear', {
    method: 'POST',
    body: JSON.stringify({
      usuario_id: uid,
      asignatura_id: curSubjectId,
      temas_elegidos: selected.map(t => t.id),
      duration_type: sessDurationType || 'corta',
    }),
  }).then(res => {
    sessId = res.sesion_id;
    sessPlanId = ''; // not a plan session
    sessGreenCount = 0; sessYellowCount = 0; sessRedCount = 0;
    if (modeSelector === 'test') {
      switchView('test');
      loadTestQuestions();
    } else {
      switchView('duelo');
      connectSessionWS(res.n_atomos);
    }
  }).catch(e => toast(e.message, 'err'));
}

async function loadTopicsForSession() {
  loadTopicsLobby();
}

function _updateDurationLabels() {
  // Simplificado para la nueva arquitectura
  console.log("Actualizando etiquetas de duración...");
}

function connectSessionWS(totalAtomos) {
  _sessAnswered = [];
  _currentQPregunta = '';
  _updateHistBtn();
  const wsProto = API.startsWith('https') ? 'wss' : 'ws';
  const wsHost = API.replace(/^https?:\/\//, '');
  const wsUrl = `${wsProto}://${wsHost}/ws/sesion/${sessId}?voice=${encodeURIComponent(sessKokoroVoice)}&lang=${encodeURIComponent(currentLang)}`;
  sessWs = new WebSocket(wsUrl);
  sessWs.binaryType = 'arraybuffer';
  setVoiceState('connecting');

  sessWs.onopen = () => {
    _wsReconnectAttempts = 0;
    setVoiceState('waiting');
    // Enviar voz Kokoro seleccionada
    sessWs.send(JSON.stringify({ type: 'set_voice', voice: sessKokoroVoice }));
  };

  sessWs.onmessage = async (event) => {
    const msg = JSON.parse(event.data);

    // ── Helper: hide all action buttons ──
    const _hideAllBtns = () => {
      ['btn-pista','btn-saltar','btn-enviar','btn-reanudar-escucha','btn-siguiente'].forEach(id => _showBtn(id, false));
    };

    // ── Estado messages (prefetch system) ──
    if (msg.type === 'estado') {
      if (msg.estado === 'generating_question') {
        setVoiceState('waiting');
        const trEl = $('duel-transcript');
        if (trEl) trEl.textContent = T('sess_next_q');
      } else if (msg.estado === 'processing_answer') {
        setVoiceState('processing');
        const trEl = $('duel-transcript');
        if (trEl) trEl.textContent = '';
      } else if (msg.estado === 'servidor_ocupado') {
        setVoiceState('processing');
        const trEl = $('duel-transcript');
        if (trEl) trEl.textContent = T('sess_busy');
      }
      return;
    }

    if (msg.type === 'pregunta') {
      _closeAllPanels();
      _currentQPregunta = msg.pregunta || '';
      const qEl = $('duel-question');
      updateProgress(msg.progreso.actual, msg.progreso.total);

      // While AI speaks: only Saltar
      _hideAllBtns();
      _showBtn('btn-saltar', true);
      setVoiceState('speaking_ai');

      // Typewriter + audio simultáneamente
      const duration = estimateAudioDuration(msg.audio_base64, msg.audio_format);
      const typePromise = typewriterText(qEl, msg.pregunta, duration);
      const audioPromise = playAudio(msg.audio_base64, msg.pregunta, msg.audio_format);
      await Promise.all([typePromise, audioPromise]);
      await new Promise(r => setTimeout(r, 300));

      // Now ready to answer: Pista + Enviar + Saltar
      setVoiceState('listening');
      _showBtn('btn-pista', true);
      _showBtn('btn-enviar', true);
      _showBtn('btn-saltar', true);
      startMicrophone();
    }

    else if (msg.type === 'feynman') {
      stopMicrophone();
      _hideAllBtns();
      _showBtn('btn-saltar', true);
      const qEl = $('duel-question');
      if (qEl) { qEl.innerHTML = `<em style="color:var(--yellow);font-size:.88em">${T('feedback_feynman')}</em><br>`; }
      setVoiceState('speaking_ai');
      const duration = estimateAudioDuration(msg.audio_base64, msg.audio_format);
      // Append typewriter text after the Feynman label
      const typeTarget = qEl;
      const typePromise = (async () => {
        if (!typeTarget) return;
        const words = msg.texto.split(/\s+/);
        const msPerWord = Math.max(80, duration / words.length);
        for (let i = 0; i < words.length; i++) {
          typeTarget.innerHTML += (i > 0 ? ' ' : '') + esc(words[i]);
          await new Promise(r => setTimeout(r, msPerWord));
        }
      })();
      await Promise.all([typePromise, playAudio(msg.audio_base64, msg.texto, msg.audio_format)]);
      await new Promise(r => setTimeout(r, 300));
      setVoiceState('listening');
      _showBtn('btn-enviar', true);
      _showBtn('btn-saltar', true);
      startMicrophone();
    }

    else if (msg.type === 'resultado') {
      stopMicrophone();
      _hideAllBtns();
      if (msg.ruta === 'verde') sessGreenCount++;
      else if (msg.ruta === 'amarillo') sessYellowCount++;
      else sessRedCount++;

      // Track answered question for back navigation
      _sessAnswered.push({
        pregunta: _currentQPregunta,
        respuesta_usuario: msg.respuesta_usuario || '',
        ruta: msg.ruta,
        texto_completo: msg.texto_completo || '',
        flashcard: msg.flashcard ? {
          paso_1_concepto_base: msg.flashcard.paso_1_concepto_base || '',
          paso_2_error_cometido: msg.flashcard.paso_2_error_cometido || '',
          paso_3_analogia: msg.flashcard.paso_3_analogia || '',
        } : null,
      });
      _updateHistBtn();

      updateProgress(msg.progreso.actual, msg.progreso.total);
      setVoiceState('evaluated_' + msg.ruta);

      // Show result state in transcript
      const trEl = $('duel-transcript');
      if (trEl) {
        if (msg.ruta === 'rojo') {
          // Show first sentence of LLM feedback (explains what was wrong)
          trEl.textContent = _primeraOracion(msg.respuesta_voz || '') || T('feedback_incorrect');
        } else {
          trEl.textContent = msg.ruta === 'verde' ? T('feedback_correct') : T('feedback_almost');
        }
      }

      await playAudio(msg.audio_base64, _primeraOracion(msg.respuesta_voz), msg.audio_format);

      if (msg.ruta === 'rojo') {
        showErrorPanel(
          msg.respuesta_usuario || '',
          msg.flashcard?.paso_1_concepto_base || '',
          msg.texto_completo || msg.flashcard?.paso_2_error_cometido || '',
          msg.flashcard?.paso_3_analogia || ''
        );
      } else {
        showAnswerPanel(msg.ruta, msg.texto_completo, msg.es_ultima, msg.respuesta_usuario, msg.flashcard);
      }
    }

    else if (msg.type === 'pista') {
      stopMicrophone();
      setVoiceState('speaking_ai');
      const hintBox = $('hint-box');
      const hintText = $('hint-box-text');
      if (hintBox && hintText) { hintText.textContent = msg.texto; hintBox.style.display = ''; }
      const trEl = $('duel-transcript'); if (trEl) trEl.textContent = '';
      _hideAllBtns();
      await playAudio(msg.audio_base64, msg.texto, msg.audio_format);
      setVoiceState('listening');
      _showBtn('btn-enviar', true);
      _showBtn('btn-saltar', true);
      startMicrophone();
    }

    else if (msg.type === 'skip_ok') {
      updateProgress(msg.progreso.actual, msg.progreso.total);
      toast(T('feedback_skipped'), 'info');
    }

    else if (msg.type === 'pausa_ok') {
      const pausedData = {
        sesionId: sessId, asignaturaId: sessSubjectId,
        asignaturaNombre: sessSubjectName, pausedAt: Date.now(),
        questionIndex: msg.current_question_index || 0,
      };
      localStorage.setItem('ar_paused_' + sessSubjectId, JSON.stringify(pausedData));
      toast(msg.mensaje, 'ok');
      setTimeout(() => closeSession(), 800);
    }

    else if (msg.type === 'modo_cambiado') {
      sessModoVoz = msg.modo === 'voice';
    }

    else if (msg.type === 'sesion_completa') {
      stopMicrophone();
      closeErrorPanel();
      showComplete();
    }

    else if (msg.type === 'stt_error') {
      // Transcription failed — ask user to repeat, restart mic
      const trEl = $('duel-transcript');
      if (trEl) trEl.textContent = '';
      setVoiceState('listening');
      _showBtn('btn-enviar', true);
      _showBtn('btn-saltar', true);
      startMicrophone();
    }

    else if (msg.type === 'error') {
      toast(msg.mensaje, 'err');
    }
  };

  sessWs.onclose = () => {
    stopMicrophone();
    if (sessState === 'complete') return;
    // Try reconnecting up to 2 times
    if (_wsReconnectAttempts < 2 && sessId) {
      _wsReconnectAttempts++;
      setVoiceState('connecting');
      const trEl = $('duel-transcript');
      if (trEl) trEl.textContent = '';
      setTimeout(() => { if (sessId) connectSessionWS(); }, 2000);
    } else {
      toast(T('toast_connection_lost'), 'err');
      closeSession();
    }
  };

  sessWs.onerror = () => {}; // onclose handles recovery
}

// ─ Controles de sesión ─
function setSessControls(enabled) {
  document.querySelectorAll('.sess-ctrl-btn').forEach(b => b.disabled = !enabled);
}

function pedirPista() {
  if (sessWs && sessWs.readyState === WebSocket.OPEN) {
    sessWs.send(JSON.stringify({ type: 'pista' }));
  }
}

function skipPregunta() {
  if (sessWs && sessWs.readyState === WebSocket.OPEN) {
    stopMicrophone();
    sessWs.send(JSON.stringify({ type: 'skip' }));
  }
}

async function pausarSesion() {
  stopCurrentAudio();
  stopMicrophone();
  if (sessWs && sessWs.readyState === WebSocket.OPEN) {
    setSessControls(false);
    sessWs.send(JSON.stringify({ type: 'pausar' }));
  } else {
    // WS no disponible — volver a home (progreso ya guardado en servidor)
    closeSession();
  }
}

function toggleModo() {
  if (sessWs && sessWs.readyState === WebSocket.OPEN) {
    sessModoVoz = !sessModoVoz;
    sessWs.send(JSON.stringify({ type: 'switch_mode', mode: sessModoVoz ? 'voice' : 'chat' }));
  }
}

function updateProgress(actual, total) {
  const pct = Math.round((actual / total) * 100);
  const el = $('duel-counter');
  if (el) el.textContent = TF('label_question_counter', {n: actual, total: total});
}

function setVoiceState(state) {
  sessState = state;
  const orb = $('orb-visual');
  const statusEl = $('duel-transcript');
  if (!orb) return;
  orb.className = 'voice-orb';

  const MIC  = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>`;
  const SPK  = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`;
  const CHK  = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>`;
  const HALF = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 1 0 20" fill="currentColor" opacity=".4"/></svg>`;
  const X    = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
  const SPIN = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="animation:spin .9s linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`;
  const DOTS = `<svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor"><circle cx="4" cy="12" r="2.2"/><circle cx="12" cy="12" r="2.2"/><circle cx="20" cy="12" r="2.2"/></svg>`;
  const STAR = `<svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`;
  const PULSE_DOTS = `<div class="typing-dots"><span></span><span></span><span></span></div>`;

  const states = {
    connecting:         { svg: PULSE_DOTS, txt: '', cls: 'processing' },
    waiting:            { svg: PULSE_DOTS, txt: '', cls: 'processing' },
    speaking_ai:        { svg: SPK,  txt: '', cls: 'speaking' },
    listening:          { svg: MIC,  txt: '', cls: 'listening' },
    finishing:          { svg: PULSE_DOTS, txt: '', cls: 'finishing' },
    processing:         { svg: PULSE_DOTS, txt: '', cls: 'processing' },
    evaluated_verde:    { svg: CHK,  txt: T('feedback_correct'), cls: 'evaluated-verde' },
    evaluated_amarillo: { svg: HALF, txt: T('feedback_almost'), cls: 'evaluated-amarillo' },
    evaluated_rojo:     { svg: X,    txt: T('feedback_incorrect'), cls: 'evaluated-rojo' },
    disconnected:       { svg: X,    txt: T('toast_connection_lost'), cls: '' },
    complete:           { svg: STAR, txt: T('toast_plan_completed'), cls: '' },
  };
  const s = states[state] || states.waiting;
  orb.innerHTML = s.svg;
  if (s.cls) orb.classList.add(s.cls);
  if (statusEl) statusEl.textContent = s.txt;
}

function orbClick() {
  if (sessState === 'speaking_ai' && sessWs && sessWs.readyState === WebSocket.OPEN) {
    sessWs.send(JSON.stringify({ type: 'barge_in' }));
    setVoiceState('listening');
    startMicrophone();
  }
  else if (sessState === 'finishing') {
    if (vadSilenceTimer) { clearTimeout(vadSilenceTimer); vadSilenceTimer = null; }
    setVoiceState('listening');
    const orb = $('orb-visual');
    if(orb) orb.className = 'voice-orb listening';
  }
}

async function startMicrophone() {
  if (sessMediaRecorder && sessMediaRecorder.state === 'recording') return;
  vadHasSentAudio = false;
  try {
    sessStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });

    // VAD via AudioContext
    vadAudioCtx = new AudioContext();
    const source = vadAudioCtx.createMediaStreamSource(sessStream);
    const analyser = vadAudioCtx.createAnalyser();
    analyser.fftSize = 512;
    analyser.smoothingTimeConstant = 0.7;
    source.connect(analyser);
    const buf = new Uint8Array(analyser.fftSize);
    const orb = $('orb-visual');
    const THRESHOLD = 0.016;
    let isSpeaking = false;

    function vadLoop() {
      if (sessState !== 'listening') return;
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
      const rms = Math.sqrt(sum / buf.length);

      if (rms > THRESHOLD) {
        if (!isSpeaking) {
          isSpeaking = true;
          orb.classList.add('vad-active');
          // Suspend CSS animation so JS can drive transform directly
          if (orb) orb.style.animationPlayState = 'paused';
        }
        vadHasSentAudio = true;
        // Audio-reactive: scale + red glow based on voice amplitude
        const scale = 1 + Math.min(rms * 5, 0.55);
        const glowPx = Math.round(rms * 220);
        orb.style.transform = `scale(${scale})`;
        orb.style.boxShadow = `0 0 ${glowPx}px rgba(248,113,113,0.75), 0 0 ${glowPx*2}px rgba(248,113,113,0.28), inset 0 1px 0 rgba(255,255,255,0.40)`;
        if (vadSilenceTimer) {
          clearTimeout(vadSilenceTimer);
          vadSilenceTimer = null;
          if ($('duel-transcript')) $('duel-transcript').textContent = '';
        }
      } else {
        if (isSpeaking) {
          isSpeaking = false;
          // Restore CSS animation
          if (orb) orb.style.animationPlayState = '';
          orb.style.transform = '';
          orb.style.boxShadow = '';
          // No auto-timeout — el usuario pulsa Enviar cuando esté listo
        }
        if (!isSpeaking) {
          orb.style.transform = '';
          orb.style.boxShadow = '';
        }
        if (!vadHasSentAudio) orb.classList.remove('vad-active');
      }
      vadAnimId = requestAnimationFrame(vadLoop);
    }
    vadLoop();

    // Timer de seguridad: si en 45s no habla nada, envía lo que haya
    vadNoAudioTimer = setTimeout(() => {
      if (sessState === 'listening') stopMicrophone();
    }, 45000);

    sessMediaRecorder = new MediaRecorder(sessStream, { mimeType: 'audio/webm;codecs=opus' });
    sessMediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0 && sessWs && sessWs.readyState === WebSocket.OPEN) {
        sessWs.send(e.data);
      }
    };
    sessMediaRecorder.start(100);
  } catch(e) {
    toast(T('toast_mic_failed') + ': ' + e.message, 'err');
  }
}

function stopMicrophone() {
  if (vadAnimId) { cancelAnimationFrame(vadAnimId); vadAnimId = null; }
  if (vadSilenceTimer) { clearTimeout(vadSilenceTimer); vadSilenceTimer = null; }
  if (vadNoAudioTimer) { clearTimeout(vadNoAudioTimer); vadNoAudioTimer = null; }
  if (vadAudioCtx) { vadAudioCtx.close().catch(()=>{}); vadAudioCtx = null; }
  const orb = $('orb-visual');
  if (orb) { orb.style.transform = ''; orb.style.boxShadow = ''; orb.classList.remove('vad-active'); }
  // Si teníamos audio → mostrar "evaluando" inmediatamente (antes de recibir respuesta del backend)
  if (vadHasSentAudio && (sessState === 'listening' || sessState === 'finishing')) {
    setVoiceState('processing');
  }
  if (sessMediaRecorder && sessMediaRecorder.state !== 'inactive') {
    sessMediaRecorder.stop();
  }
  if (sessStream) {
    sessStream.getTracks().forEach(t => t.stop());
    sessStream = null;
  }
  sessMediaRecorder = null;
}

// ─ AudioContext unlock (mobile autoplay policy) ─
let _audioCtx = null;
let _currentAudio = null;   // Track active Audio element to stop on overlap
let _currentAudioSrc = null; // Track active AudioBufferSourceNode

function _ensureAudioCtx() {
  if (!_audioCtx) {
    try { _audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {}
  }
  if (_audioCtx && _audioCtx.state === 'suspended') {
    _audioCtx.resume().catch(() => {});
  }
}

// ─ Mic permission helpers ─
async function checkMicPermission() {
  if (modeSelector !== 'voz') { _showBtn('lobby-mic-check', false); return; }
  try {
    const perm = await navigator.permissions.query({ name: 'microphone' });
    _showBtn('lobby-mic-check', perm.state !== 'granted');
  } catch(e) { _showBtn('lobby-mic-check', false); }
}

async function requestLobbyMic() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach(t => t.stop());
    _showBtn('lobby-mic-check', false);
    toast(T('toast_mic_enabled'), 'ok');
  } catch(e) {
    toast(T('toast_mic_failed') + ': ' + e.message, 'err');
  }
}

// ─ Text-to-Speech (Kokoro via backend) ─

let _typewriterTimer = null;

async function typewriterText(el, texto, durationMs) {
  // Cancel any ongoing typewriter
  if (_typewriterTimer) { clearInterval(_typewriterTimer); _typewriterTimer = null; }
  if (!el || !texto) return;

  const words = texto.split(/\s+/);
  if (words.length === 0) return;

  el.textContent = '';
  el.classList.add('typewriting');
  el.classList.remove('expanded');

  const msPerWord = Math.max(80, (durationMs || 2000) / words.length);
  let i = 0;

  return new Promise(resolve => {
    _typewriterTimer = setInterval(() => {
      if (i < words.length) {
        el.textContent += (i > 0 ? ' ' : '') + words[i];
        i++;
      } else {
        clearInterval(_typewriterTimer);
        _typewriterTimer = null;
        el.classList.remove('typewriting');
        resolve();
      }
    }, msPerWord);
  });
}

function estimateAudioDuration(base64, fmt) {
  if (!base64) return 2000;
  const bytes = base64.length * 0.75;
  // WAV 24kHz 16bit mono: ~48000 bytes/sec; MP3 128kbps: ~16000 bytes/sec
  const bytesPerSec = fmt === 'wav' ? 48000 : 16000;
  return Math.max(1000, (bytes / bytesPerSec) * 1000);
}

function stopCurrentAudio() {
  if (_currentAudio) {
    try { _currentAudio.pause(); _currentAudio.src = ''; } catch(e) {}
    _currentAudio = null;
  }
  if (_currentAudioSrc) {
    try { _currentAudioSrc.stop(); } catch(e) {}
    _currentAudioSrc = null;
  }
}

async function playAudio(base64, _fallbackText, fmt) {
  if (!base64) return;
  stopCurrentAudio();
  _ensureAudioCtx();
  const mime = (fmt === 'wav') ? 'audio/wav' : 'audio/mpeg';
  return new Promise((resolve) => {
    const audio = new Audio(`data:${mime};base64,${base64}`);
    _currentAudio = audio;
    audio.onended = () => { _currentAudio = null; resolve(); };
    audio.onerror = () => { _currentAudio = null; resolve(); };
    const p = audio.play();
    if (p && typeof p.catch === 'function') {
      p.catch(() => {
        // Mobile blocked — decode via AudioContext
        _currentAudio = null;
        if (!_audioCtx) { resolve(); return; }
        try {
          const raw = atob(base64);
          const bytes = new Uint8Array(raw.length);
          for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
          _audioCtx.decodeAudioData(bytes.buffer, (decoded) => {
            const src = _audioCtx.createBufferSource();
            _currentAudioSrc = src;
            src.buffer = decoded;
            src.connect(_audioCtx.destination);
            src.onended = () => { _currentAudioSrc = null; resolve(); };
            src.start(0);
          }, resolve);
        } catch(e) { resolve(); }
      });
    }
  });
}

async function showComplete() {
  sessState = 'complete';
  setVoiceState('complete');
  const total = sessGreenCount + sessYellowCount + sessRedCount;
  const pct = total > 0 ? Math.round((sessGreenCount / total) * 100) : 0;

  const scoreEl = $('res-score');
  if (scoreEl) scoreEl.textContent = pct + '%';
  const aciertosEl = $('res-aciertos');
  if (aciertosEl) aciertosEl.textContent = sessGreenCount;
  const amarillosEl = $('res-amarillos');
  if (amarillosEl) amarillosEl.textContent = sessYellowCount;
  const fallosEl = $('res-fallos');
  if (fallosEl) fallosEl.textContent = sessRedCount;

  // Show/hide test buttons
  const btnTestSesion = $('btn-test-sesion');
  const btnTestPlan   = $('btn-test-plan');
  if (btnTestSesion) btnTestSesion.style.display = 'none';
  if (btnTestPlan)   btnTestPlan.style.display   = 'none';

  if (sessId) {
    if (btnTestSesion) btnTestSesion.style.display = '';
  }

  // If this session belongs to a plan, check if plan is fully done
  if (sessPlanId) {
    try {
      const planSessions = await api(`/plan/${sessPlanId}/sesiones`);
      const allDone = planSessions.length > 0 && planSessions.every(s => s.status === 'completada');
      if (allDone) {
        if (btnTestSesion) btnTestSesion.style.display = 'none'; // plan test supersedes
        if (btnTestPlan)   btnTestPlan.style.display   = '';
      }
    } catch(e) {
      // silently ignore — test sesion button already shown
    }
  }

  switchView('resumen');
}

function siguientePregunta() {
  _showBtn('btn-siguiente', false);
  stopMicrophone();
  if (sessWs && sessWs.readyState === WebSocket.OPEN) {
    sessWs.send(JSON.stringify({ type: 'next' }));
  }
}

// ══ TEST (TIPO TEST — Gemini MCQ) ═══════════════════════════════════════════

let _testPreguntas   = [];   // [{id, pregunta, tipo, opciones, correctas, explicacion, explicaciones_opciones}]
let _testIndex       = 0;
let _testMode        = '';   // 'sesion' | 'plan'
let _testSesionId    = '';
let _testPlanId      = '';
let _testSeleccionadas = new Set();
let _testRespuestas  = [];   // [{pregunta_id, seleccionadas, correcta}]
let _testSavedId     = null;
let _testSavedPregs  = [];   // saved for revision overlay

function iniciarTestSesion() {
  if (!sessId) return toast(T('toast_no_session'), 'err');
  _testMode = 'sesion'; _testSesionId = sessId; _testPlanId = '';
  _resetTestState();
  switchView('test');
  const lims = { corta: 5, larga: 10, plan: 8, asignatura: 8 };
  const n = lims[sessDurationType] || 6;
  _generarTest({ sesion_id: sessId, usuario_id: uid, asignatura_id: curSubjectId, n_preguntas: n, lang: currentLang });
}

function iniciarTestPlan() {
  if (!sessPlanId) return toast(T('toast_no_plan'), 'err');
  _testMode = 'plan'; _testPlanId = sessPlanId; _testSesionId = '';
  _resetTestState();
  switchView('test');
  _generarTest({ plan_id: sessPlanId, usuario_id: uid, asignatura_id: curSubjectId, n_preguntas: 10, lang: currentLang });
}

function _resetTestState() {
  _testPreguntas = []; _testIndex = 0;
  _testSeleccionadas = new Set(); _testRespuestas = [];
  _testSavedId = null; _testSavedPregs = [];
}

async function _generarTest(body) {
  const loading = $('test-loading'), content = $('test-content'), results = $('test-results');
  if (loading) loading.style.display = '';
  if (content) content.style.display = 'none';
  if (results) results.style.display = 'none';
  try {
    const preguntas = await api('/test/generar', { method: 'POST', body: JSON.stringify(body) });
    if (!preguntas || !preguntas.length) { toast(T('test_no_questions'), 'err'); switchView('hub'); return; }
    _testPreguntas = preguntas;
    _testIndex = 0;
    if (loading) loading.style.display = 'none';
    if (content) content.style.display = '';
    _renderTestQuestion();
  } catch(e) {
    toast(T('test_error') + ': ' + e.message, 'err');
    switchView('hub');
  }
}

function _renderTestQuestion() {
  if (_testIndex >= _testPreguntas.length) { _mostrarResultados(); return; }
  const p = _testPreguntas[_testIndex];
  const total = _testPreguntas.length;

  // Progress
  const fill = $('test-prog-fill'), label = $('test-progreso');
  if (fill) fill.style.width = `${(_testIndex / total) * 100}%`;
  if (label) label.textContent = `${_testIndex + 1} / ${total}`;

  // Type label
  const tipoLabels = {
    una_correcta: T('test_select_one'),
    dos_correctas: T('test_select_two'),
    una_incorrecta: T('test_which_wrong'),
  };
  const tipoEl = $('test-tipo-label');
  if (tipoEl) tipoEl.textContent = tipoLabels[p.tipo] || T('test_select_one');

  const pregEl = $('test-pregunta');
  if (pregEl) pregEl.textContent = p.pregunta;

  const fbEl = $('test-feedback');
  if (fbEl) fbEl.style.display = 'none';

  _testSeleccionadas = new Set();
  const confirmBtn = $('btn-test-confirm'), nextBtn = $('btn-test-next');
  if (confirmBtn) { confirmBtn.style.display = 'none'; confirmBtn.disabled = false; }
  if (nextBtn) nextBtn.style.display = 'none';

  // Scroll to top
  const scrollable = document.querySelector('.test-scrollable');
  if (scrollable) scrollable.scrollTop = 0;

  // Options
  const opcsEl = $('test-opciones');
  if (!opcsEl) return;
  opcsEl.innerHTML = '';
  p.opciones.forEach((opt, i) => {
    const div = document.createElement('div');
    div.className = 'test-option';
    div.dataset.idx = String(i);
    div.innerHTML = `<div class="test-option-check"></div><div class="test-option-content"><span class="test-option-text">${esc(opt)}</span><span class="test-option-explain" id="test-opt-ex-${i}"></span></div>`;
    div.onclick = () => _toggleTestOption(div, i, p);
    opcsEl.appendChild(div);
  });
}

function _toggleTestOption(el, idx, pregunta) {
  if (el.classList.contains('answered')) return;
  const maxSel = pregunta.tipo === 'dos_correctas' ? 2 : 1;
  if (_testSeleccionadas.has(idx)) {
    _testSeleccionadas.delete(idx);
    el.classList.remove('selected');
  } else {
    if (_testSeleccionadas.size >= maxSel) {
      if (maxSel === 1) {
        _testSeleccionadas.clear();
        $('test-opciones').querySelectorAll('.test-option').forEach(o => o.classList.remove('selected'));
      } else return;
    }
    _testSeleccionadas.add(idx);
    el.classList.add('selected');
  }
  const confirmBtn = $('btn-test-confirm');
  if (confirmBtn) confirmBtn.style.display = _testSeleccionadas.size === maxSel ? '' : 'none';
}

function confirmarRespuesta() {
  if (_testSeleccionadas.size === 0) return;
  const p = _testPreguntas[_testIndex];
  const selected = Array.from(_testSeleccionadas).sort((a,b) => a-b);
  const correct = [...p.correctas].sort((a,b) => a-b);
  const isCorrect = JSON.stringify(selected) === JSON.stringify(correct);

  _testRespuestas.push({ pregunta_id: p.id ?? _testIndex, seleccionadas: selected, correcta: isCorrect });

  // Reveal each option
  const opcsEl = $('test-opciones');
  opcsEl.querySelectorAll('.test-option').forEach(opt => {
    const i = parseInt(opt.dataset.idx);
    const wasSelected = selected.includes(i);
    const isCorrectOpt = correct.includes(i);
    opt.classList.remove('selected');
    opt.classList.add('answered');
    opt.onclick = null;
    if (isCorrectOpt && wasSelected) opt.classList.add('a-correct');
    else if (!isCorrectOpt && wasSelected) opt.classList.add('a-wrong');
    else if (isCorrectOpt && !wasSelected) opt.classList.add('a-reveal');
    else opt.classList.add('a-neutral');
    // Show per-option explanation
    const exEl = document.getElementById(`test-opt-ex-${i}`);
    if (exEl && p.explicaciones_opciones?.[i]) exEl.textContent = p.explicaciones_opciones[i];
  });

  // Overall feedback
  const fbEl = $('test-feedback'), fbText = $('test-feedback-text');
  if (fbEl && fbText) {
    fbText.textContent = (isCorrect ? '✓ ' : '✗ ') + (p.explicacion || (isCorrect ? T('feedback_correct') : T('feedback_incorrect')));
    fbEl.className = 'test-feedback ' + (isCorrect ? 'correct' : 'wrong');
    fbEl.style.display = '';
  }

  const confirmBtn = $('btn-test-confirm'), nextBtn = $('btn-test-next');
  if (confirmBtn) confirmBtn.style.display = 'none';
  if (nextBtn) {
    nextBtn.style.display = '';
    nextBtn.textContent = _testIndex + 1 < _testPreguntas.length ? T('test_next') : T('test_see_result');
  }
}

function nextTestQuestion() {
  _testIndex++;
  _renderTestQuestion();
}

async function _mostrarResultados() {
  const content = $('test-content'), results = $('test-results');
  if (content) content.style.display = 'none';
  if (results) results.style.display = '';

  const correctas = _testRespuestas.filter(r => r.correcta).length;
  const total = _testRespuestas.length;
  const pct = total > 0 ? Math.round((correctas / total) * 100) : 0;

  // Animate progress bar to 100%
  const fill = $('test-prog-fill'), label = $('test-progreso');
  if (fill) fill.style.width = '100%';
  if (label) label.textContent = `${total} / ${total}`;

  const pctEl = $('test-res-pct'), titleEl = $('test-res-title'), subEl = $('test-res-sub');
  if (pctEl) pctEl.textContent = pct + '%';
  if (titleEl) titleEl.textContent = pct >= 80 ? T('test_excellent') : pct >= 60 ? T('test_good') : T('test_practice');
  if (subEl) subEl.textContent = `${correctas} ${T('test_correct_of')} ${total} ${T('test_correct_suffix')}`;

  // Save to DB
  try {
    const saved = await api('/test/guardar', {
      method: 'POST',
      body: JSON.stringify({
        usuario_id: uid, asignatura_id: curSubjectId || null,
        sesion_id: _testSesionId || null, plan_id: _testPlanId || null,
        preguntas: _testPreguntas, respuestas: _testRespuestas,
        puntuacion: correctas, total, tipo: _testMode,
      })
    });
    _testSavedId = saved.id;
    _testSavedPregs = _testPreguntas;
  } catch(e) {
    console.warn('No se pudo guardar el test:', e);
  }
}

function openTestRevision() {
  const overlay = $('fallos-overlay');
  const track = $('fallos-q-track'), dotsEl = $('fallos-q-dots');
  const titleEl = $('fallos-overlay-title');
  if (!overlay || !track) return;

  const pregs = _testSavedPregs.length ? _testSavedPregs : _testPreguntas;
  const total = pregs.length;
  const correctas = _testRespuestas.filter(r => r.correcta).length;

  if (titleEl) titleEl.textContent = TF('label_test_score', {correct: correctas, total});
  if (dotsEl) dotsEl.innerHTML = `<span class="fallos-q-counter">1 / ${total}</span>`;

  track.innerHTML = pregs.map((p, i) => {
    const resp = _testRespuestas[i] || { seleccionadas: [], correcta: false };
    const correct = [...p.correctas].sort((a,b) => a-b);
    const tipoLabels = { una_correcta: T('test_select_one'), dos_correctas: T('test_select_two'), una_incorrecta: T('test_which_wrong') };
    const optsHtml = p.opciones.map((opt, oi) => {
      const wasSelected = resp.seleccionadas.includes(oi);
      const isCorrectOpt = correct.includes(oi);
      let cls = '';
      if (isCorrectOpt && wasSelected) cls = 'a-correct';
      else if (!isCorrectOpt && wasSelected) cls = 'a-wrong';
      else if (isCorrectOpt && !wasSelected) cls = 'a-reveal';
      else cls = 'a-neutral';
      const explain = p.explicaciones_opciones?.[oi]
        ? `<div class="test-option-explain" style="display:block;margin-top:4px">${esc(p.explicaciones_opciones[oi])}</div>` : '';
      return `<div class="test-option answered ${cls}" style="margin-bottom:8px;cursor:default"><div class="test-option-check"></div><div class="test-option-content"><span class="test-option-text">${esc(opt)}</span>${explain}</div></div>`;
    }).join('');
    const badge = resp.correcta
      ? `<span style="color:#34d399;font-size:.78rem;font-weight:700">${esc(T('panel_correct_badge'))}</span>`
      : `<span style="color:#f87171;font-size:.78rem;font-weight:700">${esc(T('feedback_incorrect'))}</span>`;
    return `<div class="fallos-q-slide" style="overflow-y:auto">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        ${badge}
        <span style="font-size:.72rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--accent)">${tipoLabels[p.tipo]||''}</span>
      </div>
      <div style="font-size:1rem;font-weight:500;color:var(--txt);line-height:1.55;margin-bottom:14px">${esc(p.pregunta)}</div>
      ${optsHtml}
      <div class="test-feedback ${resp.correcta ? 'correct' : 'wrong'}" style="margin-top:10px;display:block">
        <div class="test-feedback-text">${esc(p.explicacion||'')}</div>
      </div>
    </div>`;
  }).join('');

  // Update counter on scroll
  track.onscroll = () => {
    if (!track.offsetWidth) return;
    const idx = Math.round(track.scrollLeft / track.offsetWidth);
    if (dotsEl) dotsEl.innerHTML = `<span class="fallos-q-counter">${idx + 1} / ${total}</span>`;
  };

  track.scrollTo({ left: 0, behavior: 'instant' });
  overlay.classList.add('open');
}

function exitTest() {
  switchView('hub');
}

function loadTestQuestions() {
  connectSessionWS(20);
}

function closeSession() {
  stopCurrentAudio();
  stopMicrophone();
  if (sessWs) { sessWs.close(); sessWs = null; }
  sessId = '';
  _updateHistBtn();
  switchView('hub');
}

// ─ Helpers de audio/texto ─
function _primeraOracion(texto) {
  if (!texto) return '';
  // Extrae hasta el primer punto, signo de exclamación o interrogación
  const match = texto.match(/^.{0,200}?[.!?](?:\s|$)/s);
  return match ? match[0].trim() : texto.slice(0, 160);
}

// ─ Enviar respuesta manualmente ─
function enviarRespuesta() {
  if (sessState !== 'listening') return;
  _showBtn('btn-enviar', false);
  stopMicrophone();
}

// ─ Error flashcard panel ─
function showErrorPanel(respuestaUsuario, errorExplicacion, respuestaCorrecta, analogia) {
  const el = $('error-panel'); if (!el) return;
  const fru = $('fc-respuesta-usuario');  if (fru) fru.textContent = respuestaUsuario || T('empty_no_answer');
  const fpq = $('fc-por-que-mal');        if (fpq) fpq.textContent = errorExplicacion || '';
  const frc = $('fc-respuesta-correcta'); if (frc) frc.textContent = respuestaCorrecta || '';
  const fan = $('fc-analogia');           if (fan) fan.textContent = analogia || '';
  // Reset swipe to first card
  const track = $('fc-track'); if (track) track.scrollLeft = 0;
  if (typeof _onFcScroll === 'function') _onFcScroll(track);
  // Clear transcript
  const trEl = $('duel-transcript'); if (trEl) trEl.textContent = '';
  el.classList.add('open');
}

function _onFcScroll(track) {
  if (!track) return;
  const idx = Math.round(track.scrollLeft / track.offsetWidth) || 0;
  const dots = document.querySelectorAll('#fc-dots .fc-dot');
  dots.forEach((d, i) => d.classList.toggle('active', i === idx));
}

function closeErrorPanel() {
  const el = $('error-panel'); if (el) el.classList.remove('open');
}

function showAnswerPanel(ruta, textoCompleto, esUltima, respuestaUsuario, flashcard) {
  const el = $('answer-panel'); if (!el) return;
  const badge = $('answer-panel-badge');
  const text  = $('answer-panel-text');
  const next  = $('answer-panel-next');
  if (badge) {
    badge.textContent = ruta === 'verde' ? T('panel_correct_badge') : T('panel_almost_badge');
    badge.className = 'answer-panel-badge' + (ruta === 'amarillo' ? ' amarillo' : '');
  }
  if (text) text.textContent = textoCompleto || '';

  // Show user answer section for amarillo
  const userSec = $('answer-panel-user-section');
  const userTxt = $('answer-panel-user-text');
  if (userSec && userTxt) {
    if (ruta === 'amarillo' && respuestaUsuario) {
      userTxt.textContent = respuestaUsuario;
      userSec.style.display = '';
    } else {
      userSec.style.display = 'none';
    }
  }

  // Show analogy section for amarillo (if flashcard available)
  const analSec = $('answer-panel-analogy-section');
  const analTxt = $('answer-panel-analogy');
  if (analSec && analTxt) {
    const analogia = flashcard?.paso_3_analogia || '';
    if (ruta === 'amarillo' && analogia) {
      analTxt.textContent = analogia;
      analSec.style.display = '';
    } else {
      analSec.style.display = 'none';
    }
  }

  if (next) {
    next.textContent = esUltima ? T('test_see_result') : T('panel_next');
    next.onclick = () => {
      closeAnswerPanel();
      if (esUltima) showComplete(); else siguientePregunta();
    };
  }
  el.classList.add('open');
}

function closeAnswerPanel() {
  const el = $('answer-panel'); if (el) el.classList.remove('open');
}

function _closeAllPanels() {
  closeErrorPanel();
  closeAnswerPanel();
  const hintBox = $('hint-box'); if (hintBox) hintBox.style.display = 'none';
}

function repetirPregunta() {
  closeErrorPanel();
  // Hide all action buttons while waiting for server to re-send the question
  ['btn-pista','btn-saltar','btn-enviar','btn-reanudar-escucha','btn-siguiente'].forEach(id => _showBtn(id, false));
  setVoiceState('waiting');
  if (sessWs && sessWs.readyState === WebSocket.OPEN) {
    sessWs.send(JSON.stringify({ type: 'repetir' }));
    // Backend will respond with a 'pregunta' message which auto-starts the mic
  }
}

function _onFcScroll(el) {
  if (!el) return;
  const idx = Math.round(el.scrollLeft / el.offsetWidth);
  document.querySelectorAll('#fc-dots .fc-dot').forEach((d, i) => d.classList.toggle('active', i === idx));
}

// ─ Expandir pregunta larga ─
function expandQuestion(el) { if (el) el.classList.toggle('expanded'); }

// ─ Reanudar escucha después de pista ─
function reanudarEscucha() {
  _showBtn('btn-reanudar-escucha', false);
  _showBtn('btn-pista', true);
  _showBtn('btn-enviar', true);
  const tr = $('duel-transcript'); if (tr) tr.textContent = '';
  setVoiceState('listening');
  startMicrophone();
}

// ─ Selector de voz Kokoro ─
const KOKORO_VOICES = [
  { id: 'ef_dora',  label: 'Dora',  genero: 'Mujer' },
  { id: 'em_alex',  label: 'Alex',  genero: 'Hombre' },
  { id: 'em_santa', label: 'Santa', genero: 'Hombre' },
];

let sessKokoroVoice = localStorage.getItem('ar_kokoro_voice') || 'ef_dora';

function _updateVozBtn() {
  const v = KOKORO_VOICES.find(v => v.id === sessKokoroVoice) || KOKORO_VOICES[0];
  const el = $('lbl-voz-actual');
  if (el) el.textContent = `${v.label} · ${T('lang_es')}`;
}
_updateVozBtn();

function openVoicePicker() {
  _renderKokoroVoiceList();
  $('voice-picker-modal').classList.add('open');
}

function closeVoicePicker() {
  if (_voicePreviewAudio) { _voicePreviewAudio.pause(); _voicePreviewAudio = null; }
  $('voice-picker-modal').classList.remove('open');
}

let _voicePreviewAudio = null;

function _renderKokoroVoiceList() {
  const CHECK = `<svg class="voice-item-check" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>`;
  const PLAY_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
  $('kokoro-voice-list').innerHTML = KOKORO_VOICES.map(v => {
    const sel = v.id === sessKokoroVoice;
    return `<div class="voice-item ${sel ? 'selected' : ''}" id="voice-item-${v.id}">
      <button class="voice-preview-btn" id="vpreview-${v.id}"
        onclick="previewVoice('${v.id}');event.stopPropagation()" title="Probar voz">
        ${PLAY_ICON}
      </button>
      <div class="voice-item-info" onclick="selectKokoroVoice('${v.id}')">
        <div class="voice-item-name">${v.label}</div>
        <div class="voice-item-lang">${v.genero === 'Mujer' ? T('voice_gender_female') : T('voice_gender_male')} · ${T('lang_es')}</div>
      </div>
      ${sel ? CHECK : '<div style="width:15px"></div>'}
    </div>`;
  }).join('');
}

async function previewVoice(voiceId) {
  const btn = $(`vpreview-${voiceId}`);
  if (btn) btn.classList.add('playing');
  // Stop any playing preview
  if (_voicePreviewAudio) { _voicePreviewAudio.pause(); _voicePreviewAudio = null; }
  document.querySelectorAll('.voice-preview-btn.playing').forEach(b => { if (b.id !== `vpreview-${voiceId}`) b.classList.remove('playing'); });
  try {
    const res = await api(`/tts/preview?voice=${voiceId}`);
    if (!res.audio_b64) { toast(T('toast_preview_unavailable'), 'info'); return; }
    const mime = res.format === 'wav' ? 'audio/wav' : 'audio/mpeg';
    const src = `data:${mime};base64,${res.audio_b64}`;
    _voicePreviewAudio = new Audio(src);
    _voicePreviewAudio.onended = () => { if (btn) btn.classList.remove('playing'); };
    _voicePreviewAudio.onerror = () => { if (btn) btn.classList.remove('playing'); };
    await _voicePreviewAudio.play();
  } catch(e) {
    if (btn) btn.classList.remove('playing');
    toast(T('toast_preview_failed'), 'info');
  }
}

function selectKokoroVoice(voiceId) {
  // Stop preview if playing
  if (_voicePreviewAudio) { _voicePreviewAudio.pause(); _voicePreviewAudio = null; }
  sessKokoroVoice = voiceId;
  localStorage.setItem('ar_kokoro_voice', voiceId);
  _updateVozBtn();
  _renderKokoroVoiceList();
  if (sessWs && sessWs.readyState === WebSocket.OPEN) {
    sessWs.send(JSON.stringify({ type: 'set_voice', voice: voiceId }));
  }
  const v = KOKORO_VOICES.find(v => v.id === voiceId);
  toast(TF('toast_voice_selected', {name: v.label}), 'ok');
  closeVoicePicker();
}

// voice-picker-modal backdrop close handled via onclick in HTML

// ─ Plans panel ─
let _planWizTopics = [];
let _planAtomosPorSesion = 10;

const CHECK_SVG_PLAN = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>`;

function openPlanWizard() {
  if (!curSubjectId) { toast(T('validation_select_subject'), 'err'); return; }
  const wiz = $('plan-wizard');
  if (!wiz) return;
  wiz.style.display = 'flex';

  showPlanWizStep(1);
  _planAtomosPorSesion = 10;
  const slider = $('plan-atoms-slider');
  if (slider) slider.value = 10;
  const sliderLabel = $('plan-atoms-val');
  if (sliderLabel) sliderLabel.textContent = TF('plan_n_questions', {n: 10});

  const subjEl = $('plan-wiz-subject');
  if (subjEl) subjEl.textContent = curSubjectName || T('subj_modal_title');

  const topicsEl = $('plan-wiz-topics');
  if (topicsEl) topicsEl.innerHTML = `<div class="atom-loading">${T('lobby_loading_topics')}</div>`;

  api(`/documentos/asignatura/${curSubjectId}/temas`)
    .then(data => {
      _planWizTopics = data;
      renderPlanWizTopics();
    })
    .catch(e => {
      if (topicsEl) topicsEl.innerHTML = `<div class="atom-loading" style="color:var(--red)">${e.message}</div>`;
    });
}

function closePlanWizard() {
  const wiz = $('plan-wizard');
  if (wiz) wiz.style.display = 'none';
}

function showPlanWizStep(n) {
  const s1 = $('plan-wiz-step1');
  const s2 = $('plan-wiz-step2');
  if (s1) s1.style.display = n === 1 ? 'flex' : 'none';
  if (s2) s2.style.display = n === 2 ? 'flex' : 'none';
}

function renderPlanWizTopics() {
  const container = $('plan-wiz-topics');
  if (!container) return;
  if (!_planWizTopics.length) {
    container.innerHTML = `<div style="padding:16px;text-align:center;color:rgba(255,255,255,0.50);font-size:.85rem">${T('empty_no_notes')}</div>`;
    return;
  }
  container.innerHTML = _planWizTopics.map((t, i) => `
    <div class="lobby-topic-item checked" id="plan-topic-${i}" onclick="togglePlanTopic(${i})">
      <div class="lobby-topic-cb">${CHECK_SVG_PLAN}</div>
      <span class="lobby-topic-name">${esc(t.titulo)}</span>
      <span class="lobby-topic-n">${TF('lobby_n_atoms', {n: t.n_atomos})}</span>
    </div>`).join('');
}

function togglePlanTopic(i) {
  const el = $(`plan-topic-${i}`);
  if (el) el.classList.toggle('checked');
}

function setPlanAtomsSlider(val) {
  _planAtomosPorSesion = parseInt(val, 10);
  const label = $('plan-atoms-val');
  if (label) label.textContent = TF('plan_n_questions', {n: _planAtomosPorSesion});
}

function planWizStep1Next() {
  const selected = _planWizTopics.filter((t, i) => {
    const el = $(`plan-topic-${i}`);
    return el && el.classList.contains('checked');
  });
  if (!selected.length) { toast(T('validation_select_topic'), 'err'); return; }
  showPlanWizStep(2);
  const dateInp = $('plan-exam-date');
  if (dateInp) {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    dateInp.min = tomorrow.toISOString().split('T')[0];
    if (!dateInp.value) {
      const suggest = new Date();
      suggest.setDate(suggest.getDate() + 30);
      dateInp.value = suggest.toISOString().split('T')[0];
    }
  }
}

async function submitPlanWizard() {
  const dateInp = $('plan-exam-date');
  if (!dateInp || !dateInp.value) { toast(T('validation_select_date'), 'err'); return; }

  const selected = _planWizTopics.filter((t, i) => {
    const el = $(`plan-topic-${i}`);
    return el && el.classList.contains('checked');
  });
  if (!selected.length) { toast(T('validation_select_topic'), 'err'); showPlanWizStep(1); return; }

  const btn = $('plan-wiz-submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = T('empty_loading'); }

  try {
    const res = await api('/plan/crear', {
      method: 'POST',
      body: JSON.stringify({
        usuario_id:        uid,
        asignatura_id:     curSubjectId,
        temas_elegidos:    selected.map(t => t.id),
        fecha_examen:      dateInp.value,
        atomos_por_sesion: _planAtomosPorSesion,
      }),
    });
    toast(TF('toast_plan_created', {n: res.total_sesiones}), 'ok');
    closePlanWizard();
    switchHistTab('planes');
    loadPlanes();
  } catch(e) {
    toast(e.message, 'err');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = T('plan_create'); }
  }
}

async function loadPlanes() {
  if (!curSubjectId) return;
  const listEl = $('planes-list');
  if (!listEl) return;
  listEl.innerHTML = `<div class="empty-state">${T('hist_loading_plans')}</div>`;
  try {
    const planes = await api(`/planes/usuario/${uid}?asignatura_id=${curSubjectId}`);
    if (!planes.length) {
      listEl.innerHTML = `<div class="empty-state">${T('hist_empty_plans')}<br>${T('hist_empty_plans_hint')}</div>`;
      return;
    }
    listEl.innerHTML = planes.map(p => {
      _planCache[p.id] = p;
      const completed = p.sesiones_completadas || 0;
      const total     = p.sesiones_totales || p.total_sesiones || 0;
      const pct       = total > 0 ? Math.round((completed / total) * 100) : 0;
      const pending   = total - completed;
      const fechaExamen = p.fecha_examen
        ? new Date(p.fecha_examen + 'T12:00:00').toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })
        : '—';
      const daysLeft = p.fecha_examen
        ? Math.ceil((new Date(p.fecha_examen + 'T12:00:00') - new Date()) / 86400000)
        : null;
      const daysLabel = daysLeft !== null
        ? (daysLeft > 0 ? TF('plan_days_left', {n: daysLeft}) : daysLeft === 0 ? T('plan_today') : T('plan_exam_passed'))
        : '';
      const urgent = daysLeft !== null && daysLeft <= 7 && daysLeft >= 0;

      return `
        <div class="plan-card" id="plan-card-${p.id}" onclick="openPlanDetail('${p.id}')">
          <div class="plan-card-header">
            <div class="plan-card-name">${esc(p.nombre)}</div>
            <button class="plan-card-del" onclick="event.stopPropagation();deletePlan('${p.id}')" title="Eliminar">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div class="plan-card-meta">
            <span>${T('plan_exam')} ${fechaExamen}</span>
            ${daysLabel ? `<span class="plan-days${urgent ? ' urgent' : ''}">${daysLabel}</span>` : ''}
          </div>
          <div class="plan-progress-wrap">
            <div class="plan-progress-bar"><div class="plan-progress-fill" style="width:${pct}%"></div></div>
            <span class="plan-progress-label">${completed}/${total} ${T('plan_sessions')}</span>
          </div>
          ${pending > 0
            ? `<div class="plan-done-badge" style="color:rgba(255,255,255,0.45)">${T('plan_tap_detail')}</div>`
            : `<div class="plan-done-badge">${T('plan_completed')}</div>`
          }
        </div>`;
    }).join('');
  } catch(e) {
    listEl.innerHTML = `<div class="empty-state" style="color:var(--red)">${e.message}</div>`;
  }
}

async function deletePlan(planId) {
  if (!confirm(T('plan_delete_confirm'))) return;
  try {
    await api(`/plan/${planId}`, { method: 'DELETE' });
    toast(T('toast_plan_deleted'), 'ok');
    loadPlanes();
  } catch(e) {
    toast(e.message, 'err');
  }
}

async function startNextPlanSession(planId) {
  try {
    const next = await api(`/plan/${planId}/proxima`);
    // Reusar el flujo de reanudación — el WS handler carga la sesión desde DB automáticamente
    await resumeSessionFromHistory(next.id, next.asignatura_id, curSubjectName);
  } catch(e) {
    toast(e.message === 'No hay sesiones pendientes en este plan' ? T('toast_plan_completed') : e.message, 'info');
  }
}

// ─ Sessions panel ─
const _sessHistData = {};
const _planCache = {};

async function loadSessions() {
  if (!curSubjectId) return;
  const list = $('sessions-list');
  list.innerHTML = `<div class="empty-state">${T('hist_loading')}</div>`;
  try {
    // Fetch oral sessions + tests in parallel
    const [sessions, tests] = await Promise.all([
      api(`/sesiones/usuario/${uid}`),
      api(`/tests/usuario/${uid}`).catch(() => []),
    ]);

    // Oral sessions for this subject (no plan)
    const filteredSess = sessions.filter(s => s.asignatura_id === curSubjectId && !s.plan_id);
    // Tests for this subject
    const filteredTests = tests.filter(t => t.asignatura_id === curSubjectId);

    if (!filteredSess.length && !filteredTests.length) {
      list.innerHTML = `<div class="empty-state">${T('hist_empty_sessions')}</div>`;
      return;
    }

    // Build mixed items sorted by date desc
    const items = [];
    filteredSess.forEach(s => items.push({ _type: 'session', _date: s.fecha_inicio || '', ...s }));
    filteredTests.forEach(t => items.push({ _type: 'test', _date: t.fecha || '', ...t }));
    items.sort((a, b) => new Date(b._date) - new Date(a._date));

    list.className = 'sess-acc-list';
    list.innerHTML = items.map(item => {
      if (item._type === 'test') {
        // ── Test card ──
        const t = item;
        const fecha = t.fecha ? new Date(t.fecha).toLocaleDateString('es',{day:'numeric',month:'short'}) : '—';
        const hora  = t.fecha ? new Date(t.fecha).toLocaleTimeString('es',{hour:'2-digit',minute:'2-digit'}) : '';
        const pct   = t.total > 0 ? Math.round((t.puntuacion / t.total) * 100) : 0;
        const pctColor = pct >= 80 ? '#34d399' : pct >= 60 ? '#e8a030' : '#f87171';
        return `
          <div class="sess-acc-item" id="sess-acc-test-${t.test_id}" onclick="toggleSessCard('test-${t.test_id}')">
            <div class="sess-acc-header">
              <div class="sess-acc-info">
                <div class="sess-acc-title" style="display:flex;align-items:center;gap:7px">
                  <span class="sess-acc-test-badge">TEST</span>
                  ${t.tipo === 'plan' ? T('hist_test_plan') : T('hist_test_session')}
                </div>
                <div class="sess-acc-meta">${fecha}${hora ? ' · ' + hora : ''} · <span style="color:${pctColor};font-weight:700">${TF('hist_n_correct', {n: t.puntuacion, total: t.total})} (${pct}%)</span></div>
              </div>
              <span class="sess-acc-badge">✓</span>
              <svg class="sess-acc-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <div class="sess-acc-body">
              <div class="sess-acc-actions">
                <button class="sess-acc-btn" onclick="openTestRevisionFromHistory('${t.test_id}');event.stopPropagation()">${T('hist_review')} (${t.total})</button>
              </div>
            </div>
          </div>`;
      } else {
        // ── Oral session card ──
        const s = item;
        _sessHistData[s.sesion_id] = s;
        const fecha = s.fecha_inicio ? new Date(s.fecha_inicio).toLocaleDateString('es',{day:'numeric',month:'short'}) : '—';
        const hora  = s.fecha_inicio ? new Date(s.fecha_inicio).toLocaleTimeString('es',{hour:'2-digit',minute:'2-digit'}) : '';
        const c = s.conteo || {};
        const temas = s.temas_nombres || [];
        const sesNombre = temas.length ? temas.slice(0,2).join(' · ') + (temas.length > 2 ? ` +${temas.length-2}` : '') : (s.duration_type === 'larga' ? T('hist_session_long') : T('hist_session_short'));
        const done = s.status === 'completada';
        const answered = c.total || 0;
        const fraccion = done
          ? (answered > 0 ? TF('label_answered', {n: answered}) : T('hist_completed'))
          : (answered > 0 ? TF('label_answered', {n: answered}) : T('label_unanswered'));
        const badgeTxt = done ? '✓' : '';
        const scoresHtml = (c.total > 0) ? `<div class="sess-acc-scores">
          <span class="sess-score-pill g">✓ ${c.verde||0}</span>
          <span class="sess-score-pill y">◐ ${c.amarillo||0}</span>
          <span class="sess-score-pill r">✕ ${c.rojo||0}</span>
        </div>` : '';
        const resumeBtn = !done ? `<button class="sess-acc-btn" onclick="resumeSessionFromHistory('${s.sesion_id}','${s.asignatura_id}','${esc(s.asignatura_nombre)}','${s.duration_type||'corta'}');event.stopPropagation()">${T('hist_resume')}</button>` : '';
        const repetirBtn = done ? `<button class="sess-acc-btn" onclick="repetirSesion('${s.sesion_id}');event.stopPropagation()">${T('hist_repeat')}</button>` : '';
        const revisarBtn = (c.total > 0) ? `<button class="sess-acc-btn" onclick="openRevision('${s.sesion_id}');event.stopPropagation()">${T('hist_review')} (${c.total})</button>` : '';
        const deleteBtn = `<button class="sess-acc-btn danger" onclick="confirmDeleteSession('${s.sesion_id}');event.stopPropagation()">${T('hist_delete')}</button>`;
        return `
          <div class="sess-acc-item" id="sess-acc-${s.sesion_id}" onclick="toggleSessCard('${s.sesion_id}')">
            <div class="sess-acc-header">
              <div class="sess-acc-info">
                <div class="sess-acc-title">${esc(sesNombre)}</div>
                <div class="sess-acc-meta">${fecha}${hora ? ' · ' + hora : ''} · <span style="font-variant-numeric:tabular-nums;color:rgba(255,255,255,0.60)">${fraccion}</span></div>
              </div>
              <span class="sess-acc-badge">${badgeTxt}</span>
              <svg class="sess-acc-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <div class="sess-acc-body">
              ${scoresHtml}
              <div class="sess-acc-actions">${resumeBtn}${repetirBtn}${revisarBtn}${deleteBtn}</div>
            </div>
          </div>`;
      }
    }).join('');
  } catch(e) {
    list.innerHTML = `<div class="empty-state" style="color:var(--red)">${e.message}</div>`;
  }
}

async function openTestRevisionFromHistory(testId) {
  try {
    const data = await api(`/test/${testId}/revision`);
    // Temporarily set globals so openTestRevision can use them
    _testPreguntas = data.preguntas || [];
    _testRespuestas = data.respuestas || [];
    _testSavedPregs = _testPreguntas;
    openTestRevision();
  } catch(e) {
    toast(T('toast_error_review'), 'err');
  }
}

async function resumeSessionFromHistory(sesionId, asignaturaId, asignaturaNombre, durationType) {
  sessSubjectId = asignaturaId;
  sessSubjectName = asignaturaNombre;
  sessId = sesionId;
  if (durationType) sessDurationType = durationType;
  if (!sessPlanId) sessPlanId = ''; // keep if set by startPlanSession, clear otherwise
  sessGreenCount = 0; sessYellowCount = 0; sessRedCount = 0;
  sessModoVoz = true;

  // Ensure subject context is set
  if (asignaturaId !== curSubjectId) {
    curSubjectId = asignaturaId;
    curSubjectName = asignaturaNombre;
    localStorage.setItem('ar_subj_id', asignaturaId);
    localStorage.setItem('ar_subj_name', asignaturaNombre);
    _applySubjectHeader(asignaturaNombre, curSubjectColor);
  }

  const counter = $('duel-counter');
  if (counter) counter.textContent = T('sess_resuming');
  const question = $('duel-question');
  if (question) question.textContent = T('sess_connecting');

  switchView('duelo');
  connectSessionWS(null);
}

// ─ Fallos panel ─

async function openFallos(sesionId) {
  const overlay  = $('fallos-overlay');
  const qTrack   = $('fallos-q-track');
  const qDotsEl  = $('fallos-q-dots');
  const titleEl  = $('fallos-overlay-title');
  if (!overlay || !qTrack || !qDotsEl) return;

  if (titleEl) titleEl.textContent = T('rev_errors');
  qTrack.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;width:100%;color:rgba(255,255,255,0.45);font-size:.84rem">${T('rev_loading')}</div>`;
  qDotsEl.innerHTML = '';
  overlay.classList.add('open');

  try {
    const fallos = await api(`/sesion/${sesionId}/fallos`);
    if (!fallos.length) {
      qTrack.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;width:100%;padding:40px 20px"><span style="font-family:Cormorant Garamond,serif;font-size:1.4rem;color:#fff">${T('rev_no_errors')}</span><span style="color:rgba(255,255,255,0.45);font-size:.83rem;text-align:center">${T('rev_all_correct')}</span></div>`;
      return;
    }

    // Question counter "1 / N"
    qDotsEl.innerHTML = `<span class="fallos-q-counter">1 / ${fallos.length}</span>`;

    // Build outer slides
    qTrack.innerHTML = fallos.map((f, idx) => {
      const preguntaText = (f.pregunta && f.pregunta !== f.titulo) ? f.pregunta : f.titulo;
      const esSaltada = f.respuesta_usuario === '[saltado]';
      const innerTrackId = `fallos-inner-${idx}`;
      const innerDotsId  = `fallos-idots-${idx}`;

      let innerCards;
      const nCards = f.flashcard ? 4 : 2;
      if (f.flashcard) {
        innerCards = `
          <div class="fallos-inner-card fallos-inner-user">
            <div class="fallos-inner-label">${T('panel_your_answer')}</div>
            <div class="fallos-inner-text">${esSaltada ? `<em style="color:rgba(255,255,255,0.40)">${T('feedback_skipped')}</em>` : esc(f.respuesta_usuario || T('empty_no_answer'))}</div>
          </div>
          <div class="fallos-inner-card fallos-inner-error">
            <div class="fallos-inner-label">${T('panel_why_wrong')}</div>
            <div class="fallos-inner-text">${esc(f.flashcard.concepto || '')}</div>
          </div>
          <div class="fallos-inner-card fallos-inner-answer">
            <div class="fallos-inner-label">${T('panel_the_answer')}</div>
            <div class="fallos-inner-text">${esc(f.texto_completo || f.flashcard.error_cometido || '')}</div>
          </div>
          <div class="fallos-inner-card fallos-inner-analogy">
            <div class="fallos-inner-label">${T('panel_analogy')}</div>
            <div class="fallos-inner-text">${esc(f.flashcard.analogia_generada || T('empty_no_content'))}</div>
          </div>`;
      } else {
        innerCards = `
          <div class="fallos-inner-card fallos-inner-user">
            <div class="fallos-inner-label">${T('panel_your_answer')}</div>
            <div class="fallos-inner-text" style="color:rgba(255,255,255,0.55);font-style:italic">${esSaltada ? T('feedback_skipped') : esc(f.respuesta_usuario || T('empty_no_answer'))}</div>
          </div>
          <div class="fallos-inner-card fallos-inner-answer">
            <div class="fallos-inner-label">${T('panel_the_answer')}</div>
            <div class="fallos-inner-text">${esc(f.texto_completo || '')}</div>
          </div>`;
      }

      const innerDots = Array.from({length: nCards}, (_, i) =>
        `<span class="fallos-inner-dot${i===0?' active':''}" onclick="scrollFalloInner('${innerTrackId}','${innerDotsId}',${i})"></span>`
      ).join('');

      return `
        <div class="fallos-q-slide">
          <div class="fallos-q-question">${esc(preguntaText)}</div>
          <div class="fallos-inner-track" id="${innerTrackId}" onscroll="_falloInnerScroll(this,'${innerDotsId}')">
            ${innerCards}
          </div>
          <div class="fallos-inner-dots" id="${innerDotsId}">${innerDots}</div>
        </div>`;
    }).join('');

    // Outer scroll → update counter
    qTrack.addEventListener('scroll', () => {
      const idx = Math.round(qTrack.scrollLeft / qTrack.offsetWidth);
      const counter = qDotsEl.querySelector('.fallos-q-counter');
      if (counter) counter.textContent = `${idx + 1} / ${fallos.length}`;
    }, { passive: true });

  } catch(e) {
    qTrack.innerHTML = `<div style="padding:20px;color:var(--red);font-size:.82rem">${e.message}</div>`;
  }
}

function _falloInnerScroll(el, dotsId) {
  if (!el) return;
  const idx = Math.round(el.scrollLeft / el.offsetWidth);
  const dots = document.getElementById(dotsId);
  if (dots) dots.querySelectorAll('.fallos-inner-dot').forEach((d, i) => d.classList.toggle('active', i === idx));
}

function scrollFalloQ(idx) {
  const track = $('fallos-q-track');
  if (track) track.scrollTo({ left: idx * track.offsetWidth, behavior: 'smooth' });
}

function scrollFalloInner(trackId, dotsId, idx) {
  const track = document.getElementById(trackId);
  if (track) track.scrollTo({ left: idx * track.offsetWidth, behavior: 'smooth' });
}

function closeFallos() {
  $('fallos-overlay').classList.remove('open');
}

// Shared renderer for both revision (API) and session history (client-side)
function _renderRevisionSlides(items, overlay, qTrack, qDotsEl) {
  const stateBadge = { verde: '✓', amarillo: '◐', rojo: '✕' };
  const stateColor = { verde: '#4caf81', amarillo: '#e8a030', rojo: '#e05050' };

  qDotsEl.innerHTML = `<span class="fallos-q-counter">1 / ${items.length}</span>`;

  qTrack.innerHTML = items.map((f, idx) => {
    const preguntaText = (f.pregunta && f.pregunta !== f.titulo) ? f.pregunta : f.titulo;
    const esSaltada = f.respuesta_usuario === '[saltado]';
    const estado = f.estado || 'rojo';
    const innerTrackId = `fallos-inner-${idx}`;
    const innerDotsId  = `fallos-idots-${idx}`;
    const badgeLabel = estado === 'verde' ? T('panel_correct_badge') : estado === 'amarillo' ? T('panel_almost_badge') : T('panel_wrong_badge');
    const badge = `<span style="display:inline-block;margin-bottom:6px;padding:2px 10px;border-radius:20px;font-size:.72rem;font-weight:600;background:${stateColor[estado]}22;color:${stateColor[estado]}">${esc(badgeLabel)}</span>`;

    let innerCards;
    const nCards = f.flashcard ? 4 : 2;
    if (f.flashcard) {
      innerCards = `
        <div class="fallos-inner-card fallos-inner-user">
          <div class="fallos-inner-label">${T('panel_your_answer')}</div>
          <div class="fallos-inner-text">${esSaltada ? `<em style="color:rgba(255,255,255,0.40)">${T('feedback_skipped')}</em>` : esc(f.respuesta_usuario || T('empty_no_answer'))}</div>
        </div>
        <div class="fallos-inner-card fallos-inner-error">
          <div class="fallos-inner-label">${T('panel_why_wrong')}</div>
          <div class="fallos-inner-text">${esc(f.flashcard.concepto || '')}</div>
        </div>
        <div class="fallos-inner-card fallos-inner-answer">
          <div class="fallos-inner-label">${T('panel_the_answer')}</div>
          <div class="fallos-inner-text">${esc(f.texto_completo || f.flashcard.error_cometido || '')}</div>
        </div>
        <div class="fallos-inner-card fallos-inner-analogy">
          <div class="fallos-inner-label">${T('panel_analogy')}</div>
          <div class="fallos-inner-text">${esc(f.flashcard.analogia_generada || T('empty_no_content'))}</div>
        </div>`;
    } else {
      innerCards = `
        <div class="fallos-inner-card fallos-inner-user">
          <div class="fallos-inner-label">${T('panel_your_answer')}</div>
          <div class="fallos-inner-text" style="color:rgba(255,255,255,0.55);font-style:italic">${esSaltada ? T('feedback_skipped') : esc(f.respuesta_usuario || T('empty_no_answer'))}</div>
        </div>
        <div class="fallos-inner-card fallos-inner-answer">
          <div class="fallos-inner-label">${T('panel_the_answer')}</div>
          <div class="fallos-inner-text">${esc(f.texto_completo || '')}</div>
        </div>`;
    }

    const innerDots = Array.from({length: nCards}, (_, i) =>
      `<span class="fallos-inner-dot${i===0?' active':''}" onclick="scrollFalloInner('${innerTrackId}','${innerDotsId}',${i})"></span>`
    ).join('');

    return `
      <div class="fallos-q-slide">
        ${badge}
        <div class="fallos-q-question">${esc(preguntaText)}</div>
        <div class="fallos-inner-track" id="${innerTrackId}" onscroll="_falloInnerScroll(this,'${innerDotsId}')">
          ${innerCards}
        </div>
        <div class="fallos-inner-dots" id="${innerDotsId}">${innerDots}</div>
      </div>`;
  }).join('');

  qTrack.addEventListener('scroll', () => {
    const idx = Math.round(qTrack.scrollLeft / qTrack.offsetWidth);
    const counter = qDotsEl.querySelector('.fallos-q-counter');
    if (counter) counter.textContent = `${idx + 1} / ${items.length}`;
  }, { passive: true });
}

function _updateHistBtn() {
  const btn = $('btn-sess-hist');
  const cnt = $('sess-hist-count');
  if (!btn) return;
  // Show once session is active (even 0 answered — user can open to see empty state)
  if (sessId) {
    btn.style.display = '';
    if (cnt) cnt.textContent = _sessAnswered.length > 0 ? _sessAnswered.length : '';
  } else {
    btn.style.display = 'none';
  }
}

async function openSessHistory() {
  const overlay  = $('fallos-overlay');
  const qTrack   = $('fallos-q-track');
  const qDotsEl  = $('fallos-q-dots');
  const titleEl  = $('fallos-overlay-title');
  if (!overlay || !qTrack || !qDotsEl) return;

  if (titleEl) titleEl.textContent = T('rev_history');
  qTrack.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;width:100%;color:rgba(255,255,255,0.45);font-size:.84rem;padding:40px">${T('rev_loading')}</div>`;
  qDotsEl.innerHTML = '';
  overlay.classList.add('open');

  if (!sessId) {
    qTrack.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;width:100%;color:rgba(255,255,255,0.45);font-size:.84rem;padding:40px">${T('rev_no_session')}</div>`;
    return;
  }

  try {
    // Load full session history from API (all days, all attempts)
    const items = await api(`/sesion/${sessId}/revision`);
    if (!items.length) {
      qTrack.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;width:100%;padding:40px 20px"><span style="font-family:Cormorant Garamond,serif;font-size:1.4rem;color:#fff">${T('rev_empty')}</span><span style="color:rgba(255,255,255,0.45);font-size:.83rem;text-align:center">${T('rev_empty_hint')}</span></div>`;
      return;
    }
    _renderRevisionSlides(items, overlay, qTrack, qDotsEl);
  } catch(e) {
    qTrack.innerHTML = `<div style="padding:20px;color:var(--red);font-size:.82rem">${e.message}</div>`;
  }
}

async function openRevision(sesionId) {
  const overlay  = $('fallos-overlay');
  const qTrack   = $('fallos-q-track');
  const qDotsEl  = $('fallos-q-dots');
  const titleEl  = $('fallos-overlay-title');
  if (!overlay || !qTrack || !qDotsEl) return;

  if (titleEl) titleEl.textContent = T('rev_session');
  qTrack.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;width:100%;color:rgba(255,255,255,0.45);font-size:.84rem">${T('rev_loading')}</div>`;
  qDotsEl.innerHTML = '';
  overlay.classList.add('open');

  try {
    const items = await api(`/sesion/${sesionId}/revision`);
    if (!items.length) {
      qTrack.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;width:100%;padding:40px 20px"><span style="font-family:Cormorant Garamond,serif;font-size:1.4rem;color:#fff">${T('rev_no_answers')}</span><span style="color:rgba(255,255,255,0.45);font-size:.83rem;text-align:center">${T('rev_no_data')}</span></div>`;
      return;
    }
    _renderRevisionSlides(items, overlay, qTrack, qDotsEl);
  } catch(e) {
    qTrack.innerHTML = `<div style="padding:20px;color:var(--red);font-size:.82rem">${e.message}</div>`;
  }
}

// ─ Plan detail overlay ─

let _currentPlanDetailId = '';

async function openPlanDetail(planId) {
  _currentPlanDetailId = planId;
  const overlay = $('plan-detail-overlay');
  if (!overlay) return;

  const p = _planCache[planId] || {};
  const planName   = p.nombre || '';
  const fechaExamen = p.fecha_examen || '';
  const completadas = p.sesiones_completadas || 0;
  const totales     = p.sesiones_totales || p.total_sesiones || 0;

  const titleEl = $('plan-detail-title');
  const metaEl  = $('plan-detail-meta');
  const bodyEl  = $('plan-detail-body');
  if (titleEl) titleEl.textContent = planName;
  if (metaEl) {
    const fechaFmt = fechaExamen
      ? new Date(fechaExamen + 'T12:00:00').toLocaleDateString('es', { day: 'numeric', month: 'long', year: 'numeric' })
      : '—';
    metaEl.textContent = `${T('plan_exam')} ${fechaFmt} · ${completadas}/${totales} ${T('plan_sessions')}`;
  }
  if (bodyEl) bodyEl.innerHTML = `<div style="color:rgba(255,255,255,0.45);font-size:.82rem;padding:12px 0">${T('rev_loading')}</div>`;
  overlay.classList.add('open');

  try {
    const sessions = await api(`/plan/${planId}/sesiones`);
    if (!sessions.length) {
      bodyEl.innerHTML = `<div style="color:rgba(255,255,255,0.45);font-size:.83rem;text-align:center;padding:24px">${T('hist_empty_sessions')}</div>`;
      return;
    }
    const atomosPorSesion = p.atomos_por_sesion || 10;
    bodyEl.innerHTML = sessions.map(s => {
      const isDone   = s.status === 'completada';
      const isActive = s.status === 'empezada';
      const prog     = s.current_question_index || 0;
      const label    = isDone
        ? TF('plan_n_questions', {n: `${atomosPorSesion}/${atomosPorSesion}`})
        : isActive
          ? TF('plan_n_questions', {n: `${prog}/${atomosPorSesion}`})
          : TF('plan_n_questions', {n: `0/${atomosPorSesion}`});
      return `
        <div class="plan-detail-sess${isDone ? ' done' : ''}">
          <div class="plan-detail-sess-num">${isDone ? '✓' : s.numero}</div>
          <div class="plan-detail-sess-info">
            <div class="plan-detail-sess-label">${TF('plan_session_n', {n: s.numero})}</div>
            <div class="plan-detail-sess-status">${label}</div>
          </div>
          ${!isDone ? `<button class="plan-detail-sess-btn" onclick="startPlanSession('${s.id}')">${T('plan_start_session')}</button>` : ''}
        </div>`;
    }).join('');
  } catch(e) {
    if (bodyEl) bodyEl.innerHTML = `<div style="color:var(--red);font-size:.82rem;padding:8px">${e.message}</div>`;
  }
}

function closePlanDetail() {
  const overlay = $('plan-detail-overlay');
  if (overlay) overlay.classList.remove('open');
}

async function startPlanSession(sesionId) {
  const planId = _currentPlanDetailId;
  closePlanDetail();
  try {
    sessPlanId = planId; // remember which plan this session belongs to
    sessDurationType = 'plan';
    await resumeSessionFromHistory(sesionId, curSubjectId, curSubjectName, 'plan');
  } catch(e) {
    toast(e.message, 'err');
  }
}

// ─ Repetir sesión completada ─

async function repetirSesion(sesionId) {
  const s = _sessHistData[sesionId];
  if (!s) return toast(T('toast_session_not_found'), 'err');
  if (!s.temas_elegidos || !s.temas_elegidos.length) return toast(T('toast_no_topics'), 'err');
  try {
    const res = await api('/sesion/crear', {
      method: 'POST',
      body: JSON.stringify({
        usuario_id: uid,
        asignatura_id: s.asignatura_id,
        temas_elegidos: s.temas_elegidos,
        duration_type: s.duration_type || 'corta',
      }),
    });
    sessId = res.sesion_id;
    sessSubjectId = s.asignatura_id;
    sessSubjectName = s.asignatura_nombre;
    sessGreenCount = 0; sessYellowCount = 0; sessRedCount = 0;
    sessModoVoz = true;

    const counter = $('duel-counter');
    if (counter) counter.textContent = TF('label_question_counter', {n: 1, total: '—'});
    const question = $('duel-question');
    if (question) question.textContent = T('sess_starting');

    switchView('duelo');
    connectSessionWS(res.n_atomos);
  } catch(e) {
    toast(e.message, 'err');
  }
}

// ─ Borrar sesión ─

async function confirmDeleteSession(sesionId) {
  if (!confirm(T('confirm_delete_session'))) return;
  try {
    await api(`/sesion/${sesionId}`, { method: 'DELETE' });
    const card = $('sess-card-' + sesionId);
    if (card) card.remove();
    toast(T('toast_session_deleted'), 'ok');
  } catch(e) {
    toast(TF('toast_delete_error', {err: e.message}), 'err');
  }
}

// ─ Init ─
let _subjData = [];
// Forzar tema claro siempre — el tema oscuro fue eliminado del diseño
localStorage.removeItem('ar_theme');
document.documentElement.removeAttribute('data-theme');

// Apply cached subject header IMMEDIATELY — no "Cargando..." flash
if (curSubjectId && curSubjectName) {
  _applySubjectHeader(curSubjectName, curSubjectColor || COLORS[0]);
}

if (token && uid) {
  // Show app immediately with cached data, verify token in background
  $('screen-app').classList.add('active');
  goHome();
  // Background token check — logout if invalid
  api('/asignaturas/' + uid)
    .then(data => {
      // Token valid — refresh subjects silently
      _subjData = data;
      if (!curSubjectId && data.length > 0) {
        goSubject(data[0].id, data[0].nombre, data[0].color);
      }
    })
    .catch(() => {
      logout();
    });
} else {
  $('screen-auth').classList.add('active');
}