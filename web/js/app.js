/* Folder Analyzer v2.0 - Frontend Logic
 *
 * Consumes the v2 API surfaces only:
 *   POST /api/scan?lang=       -> ScanResponse (per-folder assessment + recursive composition)
 *   GET  /api/i18n?lang=       -> single-source ui/reasons locale payload
 *   GET  /api/folder/files?path=&lang= -> retained per-file records (zero re-classification)
 *   POST /api/delete, POST /api/export, GET /api/drives
 *
 * I10 (item-vs-folder authority): a FOLDER's bulk-delete is gated by the
 * folder's own assessment (enabled only when deletable AND its
 * recommendation is safe_to_delete); an INDIVIDUAL file keeps its own
 * authority and stays actionable when it is independently safe_to_delete,
 * even inside a REVIEW_FIRST folder. Decisions only ever use the localized
 * `reason` text the API serves — raw reason_key values are never rendered.
 */

const API_BASE = '';
const DEFAULT_LANG = 'en';

let currentData = null;
let currentFiles = [];
let currentFilesFolder = null;
let sortColumn = 'total_size';
let sortDir = 'desc';
let locale = { ui: {}, reasons: {} };
let lang = localStorage.getItem('fa_lang') || DEFAULT_LANG;

/* ======================== i18n ======================== */

function t(key, params) {
    let s = (locale.ui && locale.ui[key]) || key;
    if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => params[k] !== undefined ? params[k] : m);
    return s;
}

function confLabel(value) {
    return { 'high': t('conf_high'), 'medium': t('conf_medium'), 'low': t('conf_low') }[value] || value || t('no_data');
}

function impLabel(value) {
    const map = {
        'none': t('imp_none'), 'low': t('imp_low'), 'moderate': t('imp_moderate'),
        'high': t('imp_high'), 'critical': t('imp_critical'), 'unknown': t('imp_unknown'),
    };
    return map[value] || value || t('no_data');
}

function recLabel(value) {
    const map = {
        'safe_to_delete': t('rec_safe_to_delete'), 'review_first': t('rec_review_first'),
        'keep': t('rec_keep'), 'do_not_delete': t('rec_do_not_delete'),
    };
    return map[value] || value || t('no_data');
}

/* I10 — the single enable rule used for folder bulk actions AND file actions.
 * A protected path always wins; otherwise each item acts on its own authority. */
function isActionEnabled(deletable, recommendation) {
    return Boolean(deletable && recommendation === 'safe_to_delete');
}

function applyStaticI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (locale.ui[key]) el.textContent = locale.ui[key];
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
        const key = el.getAttribute('data-i18n-ph');
        if (locale.ui[key]) el.setAttribute('placeholder', locale.ui[key]);
    });
    document.title = t('app_title') + ' - Caza Bytes';
}

/* ======================== INIT ======================== */

async function initLocale() {
    try {
        const res = await fetch(`${API_BASE}/api/i18n?lang=${lang}`);
        if (!res.ok) throw new Error('i18n');
        const data = await res.json();
        if (!data.ui || !data.reasons) throw new Error('i18n_shape');
        locale = data;
    } catch (err) {
        const res = await fetch(`${API_BASE}/api/i18n?lang=${DEFAULT_LANG}`);
        const data = await res.json();
        locale = data;
        lang = DEFAULT_LANG;
    }
    applyStaticI18n();
    document.documentElement.lang = lang;
}

document.addEventListener('DOMContentLoaded', async () => {
    await initLocale();
    hideSplash();
    setupEventListeners();
    loadDrives();
});

function hideSplash() {
    setTimeout(() => {
        const splash = document.getElementById('splash');
        if (splash) splash.classList.add('hidden');
    }, 1500);
}

function setupEventListeners() {
    document.getElementById('scanBtn').addEventListener('click', startScan);
    document.getElementById('scanInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') startScan();
    });
    document.getElementById('exportBtn').addEventListener('click', () => exportAs('json'));
    document.querySelectorAll('[data-lang]').forEach(btn => {
        btn.addEventListener('click', () => setLanguage(btn.dataset.lang));
    });

    document.querySelectorAll('thead th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.sort;
            if (sortColumn === col) {
                sortDir = sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn = col;
                sortDir = 'desc';
            }
            renderTable((currentData && currentData.top_folders) || []);
        });
    });
}

function setLanguage(next) {
    lang = next;
    localStorage.setItem('fa_lang', next);
    initLocale().then(() => {
        document.getElementById('langMenu').classList.remove('show');
        if (currentData) {
            fetchAndRender(next);
        } else {
            applyStaticI18n();
        }
    });
}

async function fetchAndRender(nextLang) {
    try {
        showLoading(t('loading'));
        const res = await fetch(`${API_BASE}/api/scan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: currentData.stats.scan_path }),
        }).then(r => r.json());
        currentData = res;
        renderAll();
        if (currentFilesFolder) {
            await loadFolderFiles(currentFilesFolder, true);
        }
        hideLoading();
    } catch (err) {
        hideLoading();
        showToast(t('scan_error_detail', { message: err.message }), 'error');
    }
}

/* ======================== API CALLS ======================== */

async function loadDrives() {
    try {
        const res = await fetch(`${API_BASE}/api/drives`);
        const drives = await res.json();
        if (drives.length > 0) {
            const mainDrive = drives[0];
            document.getElementById('scanInput').value = mainDrive.label;
            updateDiskStats(mainDrive);
        }
    } catch (err) {
        console.error('Failed to load drives:', err);
    }
}

async function startScan() {
    const path = document.getElementById('scanInput').value.trim();
    if (!path) {
        showToast(t('scan_placeholder'), 'warning');
        return;
    }

    showLoading(t('scanning', { path }));

    try {
        const res = await fetch(`${API_BASE}/api/scan?lang=${lang}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || t('scan_error', { path, error: '' }));
        }

        currentData = await res.json();
        currentFilesFolder = null;
        hideFilesPanel();
        renderAll();
        const cancelled = currentData.cancelled === true;
        const message = cancelled
            ? t('scan_cancelled')
            : t('scan_complete_detail', {
                size: formatSize(currentData.stats.total_size),
                count: currentData.stats.total_files.toLocaleString(),
            });
        showToast(message, cancelled ? 'warning' : 'success');
    } catch (err) {
        showToast(t('scan_error_detail', { message: err.message }), 'error');
    } finally {
        hideLoading();
    }
}

async function loadFolderFiles(path, silent) {
    showFilesPanel();
    currentFilesFolder = path;
    if (!silent) showLoading(t('loading'));
    try {
        const res = await fetch(`${API_BASE}/api/folder/files?path=${encodeURIComponent(path)}&lang=${lang}`);
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || t('scan_error', { path, error: '' }));
        }
        const payload = await res.json();
        currentFiles = payload.files || [];
        renderFilesPanel(path, payload);
    } catch (err) {
        showToast(t('scan_error_detail', { message: err.message }), 'error');
    } finally {
        if (!silent) hideLoading();
    }
}

async function deletePaths(paths) {
    showLoading(t('loading'));
    try {
        const res = await fetch(`${API_BASE}/api/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || t('delete_failed', { path: '', error: '' }));
        }

        const result = await res.json();

        if (result.total_blocked > 0) {
            showToast(t('block_items', { count: result.total_blocked }), 'warning');
        }

        if (result.total_deleted > 0) {
            const isFile = paths.length === 1 && currentFilesFolder;
            const key = isFile ? 'deleted_files' : 'deleted_folders';
            showToast(t(key, { count: result.total_deleted }), 'success');
            await startScan();
        } else if (result.total_blocked > 0) {
            showToast(t('toast_delete_blocked', { b: result.total_blocked, d: result.total_deleted }), 'warning');
        }
    } catch (err) {
        showToast(t('scan_error_detail', { message: err.message }), 'error');
    } finally {
        hideLoading();
    }
}

function exportAs(format) {
    showLoading(t('loading'));
    fetch(`${API_BASE}/api/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format, lang }),
    })
        .then(async (res) => {
            if (!res.ok) throw new Error((await res.json()).detail || t('export_failed', { error: '' }));
            return res.blob();
        })
        .then((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `report.${format}`;
            a.click();
            URL.revokeObjectURL(url);
            showToast(t('export_success', { path: `report.${format}` }), 'success');
            hideLoading();
        })
        .catch((err) => {
            showToast(t('scan_error_detail', { message: err.message }), 'error');
            hideLoading();
        });
}

/* ======================== RENDER ======================== */

function renderAll() {
    if (!currentData) return;

    updateScannedStats(currentData.stats);
    renderScanNotice();
    renderTable(currentData.top_folders);
    renderTreemap(currentData.top_folders);
}

function renderScanNotice() {
    const el = document.getElementById('scanCancelledNotice');
    if (!el) return;
    if (currentData && currentData.cancelled) {
        el.textContent = t('scan_cancelled') + ' ' + t('scan_cancelled_detail', {
            size: formatSize(currentData.stats.total_size),
            count: currentData.stats.total_files.toLocaleString(),
        });
        el.style.display = '';
    } else {
        el.style.display = 'none';
    }
}

function updateScannedStats(stats) {
    document.getElementById('scannedPath').textContent = stats.scan_path;
    document.getElementById('scannedTotal').textContent = formatSize(stats.total_size);
    document.getElementById('scannedFiles').textContent = stats.total_files.toLocaleString();
    document.getElementById('scannedFolders').textContent = stats.total_folders.toLocaleString();
}

function updateDiskStats(drive) {
    const totalGB = (drive.total / (1024 ** 3)).toFixed(0);
    const usedGB = (drive.used / (1024 ** 3)).toFixed(0);
    const freeGB = (drive.free / (1024 ** 3)).toFixed(0);

    document.getElementById('diskLabel').textContent = drive.label;
    document.getElementById('diskUsed').textContent = usedGB + ' GB';
    document.getElementById('diskFree').textContent = freeGB + ' GB';
    document.getElementById('diskBarFill').style.width = drive.percent + '%';
}

function folderSortValue(folder, col) {
    if (col === 'rec') {
        return folder.assessment ? folder.assessment.recommendation : '';
    }
    if (col === 'conf') {
        return folder.assessment ? folder.assessment.confidence : '';
    }
    return folder[col];
}

function renderTable(folders) {
    const tbody = document.getElementById('folderTableBody');
    if (!tbody) return;

    let sorted = [...folders];
    sorted.sort((a, b) => {
        let va = folderSortValue(a, sortColumn);
        let vb = folderSortValue(b, sortColumn);
        if (typeof va === 'string') {
            va = va.toLowerCase();
            vb = vb.toLowerCase();
        }
        if (sortDir === 'asc') return va > vb ? 1 : -1;
        return va < vb ? 1 : -1;
    });

    tbody.innerHTML = sorted.map((folder, idx) => {
        const riskClass = `risk-${folder.risk}`;
        const riskLabel = folder.risk.toUpperCase();

        const a = folder.assessment || {};
        const rec = a.recommendation || '';
        const recLabelText = recLabel(rec);
        const confText = confLabel(a.confidence);
        const impText = impLabel(a.impact);
        const reasonText = a.reason || '';
        const recClass = rec === 'safe_to_delete' ? 'rec-safe' : (rec === 'review_first' ? 'rec-review' : 'rec-keep');

        /* I10: folder bulk action uses the folder's OWN authority. */
        const actionEnabled = isActionEnabled(folder.deletable, rec);
        const actionTitle = actionEnabled ? '' : t('toast_delete_blocked', { b: 1, d: 0 });
        const actionBtn = actionEnabled
            ? `<button class="btn btn-danger" onclick="confirmDelete('${escapeHtml(folder.path)}')">&#128465; Delete</button>`
            : `<button class="btn btn-danger" disabled ${actionTitle ? `title="${escapeHtml(actionTitle)}"` : ''}>&#128274;</button>`;

        const rowClick = folder.deletable ? ` onclick="openFolder('${escapeHtml(folder.path)}')" style="cursor:pointer"` : '';

        return `
            <tr${rowClick}>
                <td>${idx + 1}</td>
                <td class="path" title="${escapeHtml(folder.path)}">${escapeHtml(folder.name)}</td>
                <td class="size">${formatSize(folder.total_size)}</td>
                <td><span class="risk-badge ${riskClass}">${riskLabel}</span></td>
                <td><span class="rec-badge ${recClass}">${escapeHtml(recLabelText)}</span></td>
                <td>${escapeHtml(confText)}</td>
                <td>${escapeHtml(impText)}</td>
                <td class="reason" title="${escapeHtml(reasonText)}">${escapeHtml(reasonText)}</td>
                <td class="files">${(folder.file_count || 0).toLocaleString()}</td>
                <td>${actionBtn}</td>
            </tr>
        `;
    }).join('');
}

function showFilesPanel() {
    document.getElementById('filesPanel').style.display = '';
}

function hideFilesPanel() {
    document.getElementById('filesPanel').style.display = 'none';
    currentFilesFolder = null;
    currentFiles = [];
}

function openFolder(path) {
    loadFolderFiles(path);
}

function renderFilesPanel(path, payload) {
    if (!payload) return;

    document.getElementById('filesPanelTitle').textContent = t('folder_files_title', { path });

    const notice = document.getElementById('filesPanelNotice');
    const evicted = Boolean(payload.evicted);

    const a = payload.folder_assessment || {};
    const summaryParts = [];
    if (a.reason) summaryParts.push(a.reason);
    if (payload.folder_assessment) {
        summaryParts.push(`${t('col_recommendation')}: ${recLabel(a.recommendation)} · ${t('col_confidence')}: ${confLabel(a.confidence)}`);
    }
    const folder = findFolder(currentData, path);
    if (folder && (folder.recursive_total !== null && folder.recursive_total !== undefined)) {
        summaryParts.push(`${t('col_recursive_total')}: ${formatSize(folder.recursive_total)}`);
    }
    document.getElementById('filesPanelSummary').textContent = summaryParts.join('  ·  ');

    if (evicted) {
        notice.style.display = '';
        notice.textContent = t('records_evicted');
    } else {
        notice.style.display = 'none';
    }

    const tbody = document.getElementById('filesTableBody');
    if (evicted || !currentFiles.length) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted)">${t('no_data')}</td></tr>`;
        return;
    }

    tbody.innerHTML = currentFiles.map((file, idx) => {
        const rec = file.recommendation || '';
        const recClass = rec === 'safe_to_delete' ? 'rec-safe' : (rec === 'review_first' ? 'rec-review' : 'rec-keep');
        /* I10: the file acts on ITS OWN authority, independent of its folder. */
        const actionEnabled = isActionEnabled(file.deletable, rec);
        const actionBtn = actionEnabled
            ? `<button class="btn btn-danger" onclick="confirmDeleteFile('${escapeHtml(file.path)}')">&#128465; Delete</button>`
            : `<button class="btn btn-danger" disabled>&#128274;</button>`;

        return `
            <tr>
                <td>${idx + 1}</td>
                <td class="path" title="${escapeHtml(file.path)}">${escapeHtml(file.name)}</td>
                <td class="size">${formatSize(file.size)}</td>
                <td><span class="rec-badge ${recClass}">${escapeHtml(recLabel(rec))}</span></td>
                <td>${escapeHtml(confLabel(file.confidence))}</td>
                <td>${escapeHtml(impLabel(file.impact))}</td>
                <td class="reason" title="${escapeHtml(file.reason)}">${escapeHtml(file.reason)}</td>
                <td>${actionBtn}</td>
            </tr>
        `;
    }).join('');
}

function findFolder(root, path) {
    if (!root) return null;
    if (root.path === path) return root;
    for (const child of (root.children || [])) {
        const found = findFolder(child, path);
        if (found) return found;
    }
    return null;
}

function renderTreemap(folders) {
    const container = document.getElementById('treemapContent');
    if (!container) return;

    const top15 = folders.slice(0, 15);
    if (top15.length === 0) {
        container.innerHTML = `<p style="color: var(--text-muted)">${t('no_data')}</p>`;
        return;
    }

    const maxSize = Math.max(...top15.map(f => f.total_size));
    const totalSize = folders.reduce((sum, f) => sum + f.total_size, 0);

    container.innerHTML = top15.map(folder => {
        const pct = totalSize > 0 ? ((folder.total_size / totalSize) * 100).toFixed(1) : 0;
        const barWidth = maxSize > 0 ? ((folder.total_size / maxSize) * 100) : 0;
        const name = folder.name.length > 30 ? folder.name.substring(0, 27) + '...' : folder.name;

        return `
            <div class="treemap-bar-row">
                <div class="treemap-bar-label" title="${escapeHtml(folder.path)}">${escapeHtml(name)}</div>
                <div class="treemap-bar-track">
                    <div class="treemap-bar-fill ${folder.risk}" style="width: ${Math.max(barWidth, 2)}%">
                        ${barWidth > 15 ? `${pct}%` : ''}
                    </div>
                </div>
                <div class="treemap-bar-info">${formatSize(folder.total_size)}</div>
            </div>
        `;
    }).join('');
}

/* ======================== ACTIONS ======================== */

function confirmDelete(path) {
    const modal = document.getElementById('confirmModal');
    const body = document.getElementById('confirmModalBody');
    const confirmBtn = document.getElementById('confirmDeleteBtn');

    body.innerHTML = `
        <p>${t('confirm_folder_body')}</p>
        <p style="margin-top: 12px; font-family: monospace; color: var(--caution);">${escapeHtml(path)}</p>
        <p style="margin-top: 12px; font-size: 12px; color: var(--text-muted);">${t('delete_recoverable_hint')}</p>
    `;

    confirmBtn.onclick = () => {
        modal.classList.remove('active');
        deletePaths([path]);
    };

    modal.classList.add('active');
}

function confirmDeleteFile(path) {
    const modal = document.getElementById('confirmModal');
    const body = document.getElementById('confirmModalBody');
    const confirmBtn = document.getElementById('confirmDeleteBtn');

    body.innerHTML = `
        <p>${t('confirm_file_body')}</p>
        <p style="margin-top: 12px; font-family: monospace; color: var(--caution);">${escapeHtml(path)}</p>
        <p style="margin-top: 12px; font-size: 12px; color: var(--text-muted);">${t('delete_recoverable_hint')}</p>
    `;

    confirmBtn.onclick = () => {
        modal.classList.remove('active');
        deletePaths([path]);
    };

    modal.classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

/* ======================== UTILITIES ======================== */

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let val = bytes;
    for (const unit of units) {
        if (val < 1024) {
            return unit === 'B' ? `${Math.round(val)} ${unit}` : `${val.toFixed(2)} ${unit}`;
        }
        val /= 1024;
    }
    return `${val.toFixed(2)} PB`;
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function showLoading(text) {
    const overlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    if (overlay && loadingText) {
        loadingText.textContent = text || t('loading');
        overlay.classList.add('active');
    }
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('active');
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}