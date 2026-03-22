/**
 * Face Unlock System — v2.0
 * Professional biometric authentication frontend
 */

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const App = {
    cameraActive: false,
    authRunning: false,
    authInterval: null,
    videoStream: null,
    useServerCamera: false,
    isLocked: true,
    lastUser: null,
    settings: {},
    ws: null,
    _lastToast: '',
    _lastToastTime: 0,
};

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadSettings();
    loadUsers();
    loadActivity();
    loadAuthStatus();
    connectWebSocket();

    $('#btn-start-camera').onclick = toggleCamera;
    $('#btn-authenticate').onclick = toggleAuthentication;
    $('#btn-lock').onclick = lockSystem;
    $('#btn-reg-camera').onclick = toggleRegCamera;
    $('#btn-capture').onclick = captureFrame;
    $('#btn-register').onclick = registerUser;
    $('#btn-save-settings').onclick = saveSettings;

    const slider = $('#threshold-slider');
    if (slider) slider.oninput = (e) => {
        $('#threshold-value').textContent = parseFloat(e.target.value).toFixed(2);
    };
});

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
function initTabs() {
    $$('.nav-tab').forEach((tab) => {
        tab.onclick = () => {
            $$('.nav-tab').forEach((t) => t.classList.remove('active'));
            $$('.tab-content').forEach((c) => c.classList.remove('active'));
            tab.classList.add('active');
            $(`#tab-${tab.dataset.tab}`).classList.add('active');
            if (tab.dataset.tab === 'logs') loadActivity();
            if (tab.dataset.tab === 'users') loadUsers();
        };
    });
}

// ---------------------------------------------------------------------------
// Camera — Auth
// ---------------------------------------------------------------------------
function toggleCamera() {
    App.cameraActive ? stopCamera() : startCamera();
}

async function startCamera() {
    const btn = $('#btn-start-camera');
    setBtn(btn, 'spinner', 'Starting…');

    const hasBrowserCam = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

    if (hasBrowserCam) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' },
            });
            App.videoStream = stream;
            App.useServerCamera = false;
            $('#camera-feed').srcObject = stream;
            show('#camera-feed'); hide('#camera-feed-img');
        } catch (_) {
            await useServerCam('#camera-feed-img', '#camera-feed');
        }
    } else {
        await useServerCam('#camera-feed-img', '#camera-feed');
    }

    hide('#camera-placeholder');
    $('#camera-container').classList.add('active');
    $('.scan-overlay').classList.add('active');
    $('#rec-dot').classList.add('active');
    App.cameraActive = true;

    setBtn(btn, 'stop', 'Stop Camera', 'btn-danger', 'btn-primary');
    showToast('Camera active', 'success');
}

async function stopCamera() {
    stopAuthentication();

    if (App.videoStream) {
        App.videoStream.getTracks().forEach((t) => t.stop());
        App.videoStream = null;
    }
    if (App.useServerCamera) {
        // 1. Kill the <img> src first to close the HTTP MJPEG stream
        $('#camera-feed-img').src = '';
        hide('#camera-feed-img');
        // 2. Small delay so the browser drops the connection and the
        //    server-side MJPEG generator loop exits
        await sleep(150);
        // 3. Now tell the server to release the hardware camera
        await fetch('/api/camera/stop', { method: 'POST' }).catch(() => {});
    }

    $('#camera-feed').srcObject = null;
    hide('#camera-feed');
    show('#camera-placeholder');
    $('#camera-container').classList.remove('active', 'authenticated');
    $('.scan-overlay').classList.remove('active');
    $('#rec-dot').classList.remove('active');

    App.cameraActive = false;
    App.useServerCamera = false;
    const btn = $('#btn-start-camera');
    setBtn(btn, 'camera', 'Start Camera', 'btn-primary', 'btn-danger');
}

// ---------------------------------------------------------------------------
// Authentication
// ---------------------------------------------------------------------------
function toggleAuthentication() {
    App.authRunning ? stopAuthentication() : startAuthentication();
}

function startAuthentication() {
    if (!App.cameraActive) return showToast('Start the camera first', 'warning');

    App.authRunning = true;
    const btn = $('#btn-authenticate');
    setBtn(btn, 'spinner', 'Scanning…', 'btn-danger', 'btn-success');

    doAuthenticate();
    App.authInterval = setInterval(doAuthenticate, 2000);
}

function stopAuthentication() {
    App.authRunning = false;
    clearInterval(App.authInterval);
    App.authInterval = null;
    const btn = $('#btn-authenticate');
    setBtn(btn, 'shield', 'Authenticate', 'btn-success', 'btn-danger');
}

async function doAuthenticate() {
    if (!App.cameraActive || !App.authRunning) return;

    try {
        let dataUrl;
        if (App.useServerCamera) {
            const r = await fetch('/api/camera/frame');
            dataUrl = (await r.json()).image;
        } else {
            const video = $('#camera-feed');
            const c = document.createElement('canvas');
            c.width = video.videoWidth || 640;
            c.height = video.videoHeight || 480;
            c.getContext('2d').drawImage(video, 0, 0);
            dataUrl = c.toDataURL('image/jpeg', 0.85);
        }

        const res = await fetch('/api/auth/authenticate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: dataUrl }),
        });
        const data = await res.json();
        handleAuthResult(data);
    } catch (e) {
        console.error('Auth error:', e);
    }
}

function handleAuthResult(data) {
    const container = $('#camera-container');

    if (data.authenticated) {
        // Stop scanning immediately — we got a match
        stopAuthentication();

        App.isLocked = false;
        App.lastUser = data.username;

        // Lock widget → unlocked
        $('#lock-widget').className = 'lock-widget unlocked';
        $('#lock-icon').textContent = '🔓';
        $('#lock-status-text').textContent = 'UNLOCKED';
        $('#lock-sub-text').textContent = `Welcome back, ${data.username}`;

        container.classList.add('authenticated');
        container.classList.remove('active');

        // Info
        $('#auth-user-value').textContent = data.username;
        $('#auth-user-value').className = 'auth-info-value success';
        $('#auth-time-value').textContent = new Date().toLocaleTimeString();

        const conf = Math.round(data.confidence * 100);
        $('#confidence-percent').textContent = `${conf}%`;
        $('#confidence-fill').style.width = `${conf}%`;

        updateStatusBadge(false);
        showToast(`Welcome, ${data.username}`, 'success');
    } else {
        // Silently update UI, no toast spam for failed scans
        $('#auth-user-value').textContent = 'Scanning…';
        $('#auth-user-value').className = 'auth-info-value';
    }
}

async function lockSystem() {
    await fetch('/api/auth/lock', { method: 'POST' }).catch(() => {});
    App.isLocked = true;
    App.lastUser = null;

    $('#lock-widget').className = 'lock-widget locked';
    $('#lock-icon').textContent = '🔒';
    $('#lock-status-text').textContent = 'LOCKED';
    $('#lock-sub-text').textContent = 'Authenticate to unlock';
    $('#camera-container').classList.remove('authenticated');
    if (App.cameraActive) $('#camera-container').classList.add('active');

    $('#auth-user-value').textContent = '—';
    $('#auth-user-value').className = 'auth-info-value';
    $('#auth-time-value').textContent = '—';
    $('#confidence-percent').textContent = '0%';
    $('#confidence-fill').style.width = '0%';

    updateStatusBadge(true);
    showToast('System locked', 'info');
}

function updateStatusBadge(locked) {
    const b = $('#status-badge');
    b.className = locked ? 'status-badge locked' : 'status-badge unlocked';
    b.querySelector('.status-text').textContent = locked ? 'LOCKED' : 'UNLOCKED';
}

async function loadAuthStatus() {
    try {
        const data = await (await fetch('/api/auth/status')).json();
        App.isLocked = data.locked;
        updateStatusBadge(data.locked);
        if (!data.locked && data.user) {
            $('#lock-widget').className = 'lock-widget unlocked';
            $('#lock-icon').textContent = '🔓';
            $('#lock-status-text').textContent = 'UNLOCKED';
            $('#lock-sub-text').textContent = `Welcome, ${data.user}`;
            $('#auth-user-value').textContent = data.user;
            if (data.confidence) {
                const c = Math.round(data.confidence * 100);
                $('#confidence-percent').textContent = `${c}%`;
                $('#confidence-fill').style.width = `${c}%`;
            }
        }
    } catch (_) {}
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------
let regStream = null;
let regCameraActive = false;
let regUseServer = false;

function toggleRegCamera() {
    regCameraActive ? stopRegCamera() : startRegCamera();
}

async function startRegCamera() {
    const hasBrowserCam = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

    if (hasBrowserCam) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' },
            });
            regStream = stream;
            regUseServer = false;
            $('#reg-camera-feed').srcObject = stream;
            show('#reg-camera-feed'); hide('#reg-camera-feed-img');
        } catch (_) {
            await useServerCam('#reg-camera-feed-img', '#reg-camera-feed');
            regUseServer = true;
        }
    } else {
        await useServerCam('#reg-camera-feed-img', '#reg-camera-feed');
        regUseServer = true;
    }

    hide('#reg-camera-placeholder');
    $('#reg-camera-container').classList.add('active');
    regCameraActive = true;

    const btn = $('#btn-reg-camera');
    setBtn(btn, 'stop', 'Stop', 'btn-danger', 'btn-primary');
}

async function stopRegCamera() {
    if (regStream) { regStream.getTracks().forEach((t) => t.stop()); regStream = null; }
    if (regUseServer) {
        $('#reg-camera-feed-img').src = '';
        hide('#reg-camera-feed-img');
        await sleep(150);
        await fetch('/api/camera/stop', { method: 'POST' }).catch(() => {});
    }
    $('#reg-camera-feed').srcObject = null;
    hide('#reg-camera-feed');
    show('#reg-camera-placeholder');
    $('#reg-camera-container').classList.remove('active');
    regCameraActive = false;
    regUseServer = false;

    const btn = $('#btn-reg-camera');
    setBtn(btn, 'camera', 'Start Camera', 'btn-primary', 'btn-danger');
}

async function captureFrame() {
    if (!regCameraActive) return showToast('Start the camera first', 'warning');

    let dataUrl;
    if (regUseServer) {
        try {
            const data = await (await fetch('/api/camera/frame')).json();
            dataUrl = data.image;
        } catch (_) { return showToast('Capture failed', 'error'); }
    } else {
        const v = $('#reg-camera-feed');
        const c = document.createElement('canvas');
        c.width = v.videoWidth || 640; c.height = v.videoHeight || 480;
        c.getContext('2d').drawImage(v, 0, 0);
        dataUrl = c.toDataURL('image/jpeg', 0.9);
    }

    const preview = $('#capture-preview');
    preview.innerHTML = `<img src="${dataUrl}" alt="Captured">`;
    preview.classList.add('has-image');
    preview.dataset.image = dataUrl;
    show('#face-quality');
    $('#face-quality').className = 'face-quality-badge good';
    $('#face-quality').innerHTML = '<span class="quality-dot"></span> Face Detected';
    showToast('Face captured', 'success');
}

async function registerUser() {
    const username = $('#reg-username').value.trim();
    if (!username) return showToast('Enter a username', 'warning');
    if (username.length < 2) return showToast('Username too short', 'warning');

    const preview = $('#capture-preview');
    if (!preview.dataset.image) return showToast('Capture a face first', 'warning');

    const btn = $('#btn-register');
    setBtn(btn, 'spinner', 'Registering…');
    btn.disabled = true;

    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, image: preview.dataset.image }),
        });
        const data = await res.json();

        if (data.success) {
            showToast(`${username} registered!`, 'success');
            $('#reg-username').value = '';
            preview.innerHTML = '<span class="capture-placeholder">👤</span>';
            preview.classList.remove('has-image');
            delete preview.dataset.image;
            hide('#face-quality');
            loadUsers();
        } else {
            showToast(data.message || 'Registration failed', 'error');
        }
    } catch (_) {
        showToast('Registration error', 'error');
    }

    setBtn(btn, 'user-plus', 'Register Face');
    btn.disabled = false;
}

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------
async function loadUsers() {
    try {
        const data = await (await fetch('/api/users')).json();
        renderUsers(data.users);
        $('#stat-users').textContent = data.users.length;
    } catch (_) {}
}

const AVATAR_COLORS = [
    ['#6366f1','#818cf8'], ['#a855f7','#c084fc'], ['#ec4899','#f472b6'],
    ['#f43f5e','#fb7185'], ['#f97316','#fb923c'], ['#eab308','#facc15'],
    ['#22c55e','#4ade80'], ['#14b8a6','#2dd4bf'], ['#3b82f6','#60a5fa'],
];

function renderUsers(users) {
    const lists = ['#auth-users-list', '#users-list'];
    if (!users.length) {
        const html = `<div class="empty-state"><div class="empty-state-icon">👤</div>
            <p class="empty-state-text">No registered users</p></div>`;
        lists.forEach(s => { const el = $(s); if (el) el.innerHTML = html; });
        return;
    }
    const html = users.map((u, i) => {
        const [c1, c2] = AVATAR_COLORS[i % AVATAR_COLORS.length];
        return `<div class="user-item">
            <div class="user-item-info">
                <div class="user-avatar" style="background:linear-gradient(135deg,${c1},${c2})">${esc(u).substring(0,2).toUpperCase()}</div>
                <div><div class="user-name">${esc(u)}</div><div class="user-meta">Registered user</div></div>
            </div>
            <button class="btn btn-ghost btn-sm" onclick="deleteUser('${esc(u)}')" title="Delete">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
            </button></div>`;
    }).join('');
    lists.forEach(s => { const el = $(s); if (el) el.innerHTML = html; });
}

async function deleteUser(username) {
    if (!confirm(`Delete "${username}"?`)) return;
    try {
        const data = await (await fetch(`/api/users/${encodeURIComponent(username)}`, { method: 'DELETE' })).json();
        if (data.success) { showToast(`${username} deleted`, 'info'); loadUsers(); }
        else showToast('Delete failed', 'error');
    } catch (_) { showToast('Delete error', 'error'); }
}

// ---------------------------------------------------------------------------
// Activity
// ---------------------------------------------------------------------------
async function loadActivity() {
    try {
        const data = await (await fetch('/api/activity')).json();
        renderActivity(data.logs);
        $('#stat-events').textContent = data.logs.length;
    } catch (_) {}
}

function renderActivity(logs) {
    const list = $('#activity-list');
    if (!list) return;
    if (!logs.length) {
        list.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📋</div>
            <p class="empty-state-text">No activity yet</p></div>`;
        return;
    }
    list.innerHTML = logs.map(l => `
        <div class="activity-item">
            <div class="activity-dot ${l.status}"></div>
            <div class="activity-content">
                <span class="activity-action">${esc(l.action)}</span>
                <span class="activity-detail">${esc(l.detail)}</span>
            </div>
            <span class="activity-time">${l.time}</span>
        </div>`).join('');
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
async function loadSettings() {
    try {
        App.settings = await (await fetch('/api/settings')).json();
        const s = App.settings;
        if ($('#camera-index')) $('#camera-index').value = s.camera_index ?? 0;
        if ($('#threshold-slider')) {
            $('#threshold-slider').value = s.threshold ?? 0.5;
            $('#threshold-value').textContent = (s.threshold ?? 0.5).toFixed(2);
        }
        if ($('#auto-lock')) $('#auto-lock').checked = s.auto_lock ?? true;
        if ($('#auto-lock-timeout')) $('#auto-lock-timeout').value = s.auto_lock_timeout ?? 60;
        if ($('#show-confidence')) $('#show-confidence').checked = s.show_confidence ?? true;
    } catch (_) {}
}

async function saveSettings() {
    const btn = $('#btn-save-settings');
    setBtn(btn, 'spinner', 'Saving…');
    btn.disabled = true;
    try {
        const res = await fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_index: parseInt($('#camera-index').value, 10),
                threshold: parseFloat($('#threshold-slider').value),
                auto_lock: $('#auto-lock').checked,
                auto_lock_timeout: parseInt($('#auto-lock-timeout').value, 10),
                show_confidence: $('#show-confidence').checked,
            }),
        });
        App.settings = await res.json();
        showToast('Settings saved', 'success');
    } catch (_) {
        showToast('Save failed', 'error');
    }
    setBtn(btn, 'save', 'Save Settings');
    btn.disabled = false;
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------
function connectWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    App.ws = new WebSocket(`${proto}//${location.host}/ws`);
    App.ws.onmessage = (e) => {
        try {
            const d = JSON.parse(e.data);
            if (d.type === 'auth' && d.success) handleAuthResult({ authenticated: true, username: d.username, confidence: d.confidence });
            if (d.type === 'lock' && d.locked) lockSystem();
        } catch (_) {}
    };
    App.ws.onclose = () => setTimeout(connectWebSocket, 3000);
    App.ws.onerror = () => App.ws.close();
}

// ---------------------------------------------------------------------------
// Toasts — debounced, max 3 visible
// ---------------------------------------------------------------------------
function showToast(msg, type = 'info') {
    const now = Date.now();
    // Debounce identical messages within 3s
    if (msg === App._lastToast && now - App._lastToastTime < 3000) return;
    App._lastToast = msg;
    App._lastToastTime = now;

    const container = $('#toast-container');
    // Max 3 toasts
    while (container.children.length >= 3) container.firstChild.remove();

    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ'}</span><span>${esc(msg)}</span>`;
    container.appendChild(toast);
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 3500);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
async function useServerCam(imgSel, videoSel) {
    try { await fetch('/api/camera/start', { method: 'POST' }); } catch (_) {}
    App.useServerCamera = true;
    $(imgSel).src = '/api/camera/stream';
    show(imgSel); hide(videoSel);
}

function show(sel) { $(sel).classList.remove('hidden'); }
function hide(sel) { $(sel).classList.add('hidden'); }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

const SVG_ICONS = {
    camera: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    stop: '<rect x="3" y="3" width="18" height="18" rx="2"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    'user-plus': '<path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/>',
    spinner: null,
};

function setBtn(btn, icon, text, addClass, removeClass) {
    if (icon === 'spinner') {
        btn.innerHTML = `<span class="spinner"></span> ${text}`;
    } else {
        const svg = SVG_ICONS[icon] ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${SVG_ICONS[icon]}</svg> ` : '';
        btn.innerHTML = `${svg}${text}`;
    }
    if (addClass) { btn.classList.add(addClass); }
    if (removeClass) { btn.classList.remove(removeClass); }
}
