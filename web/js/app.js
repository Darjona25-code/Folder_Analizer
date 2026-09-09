/* Folder Analyzer v2.0 - Frontend Logic */

const API_BASE = '';

let currentData = null;
let sortColumn = 'total_size';
let sortDir = 'desc';

/* ======================== INIT ======================== */

document.addEventListener('DOMContentLoaded', () => {
    hideSplash();
    loadDrives();
    setupEventListeners();
});

function hideSplash() {
    setTimeout(() => {
        const splash = document.getElementById('splash');
        if (splash) splash.classList.add('hidden');
    }, 1500);
}

function setupEventListeners() {
    const scanBtn = document.getElementById('scanBtn');
    const scanInput = document.getElementById('scanInput');
    const exportBtn = document.getElementById('exportBtn');

    scanBtn.addEventListener('click', startScan);
    scanInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') startScan();
    });
    exportBtn.addEventListener('click', toggleExportDropdown);

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.dropdown')) {
            const menu = document.getElementById('exportMenu');
            if (menu) menu.classList.remove('show');
        }
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
            renderTable(currentData.top_folders);
        });
    });
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
        showToast('Please enter a path to scan.', 'warning');
        return;
    }

    showLoading('Scanning ' + path + '...');

    try {
        const res = await fetch(`${API_BASE}/api/scan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Scan failed');
        }

        currentData = await res.json();
        renderAll();
        showToast(`Scan complete: ${formatSize(currentData.stats.total_size)} across ${currentData.stats.total_files.toLocaleString()} files`, 'success');
    } catch (err) {
        showToast('Scan error: ' + err.message, 'error');
    } finally {
        hideLoading();
    }
}

async function deleteFolders(paths) {
    showLoading('Deleting folders...');

    try {
        const res = await fetch(`${API_BASE}/api/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Delete failed');
        }

        const result = await res.json();

        if (result.total_blocked > 0) {
            showToast(`${result.total_blocked} critical system folder(s) blocked.`, 'warning');
        }

        if (result.total_deleted > 0) {
            showToast(`${result.total_deleted} folder(s) sent to Recycle Bin.`, 'success');
            await startScan();
        }
    } catch (err) {
        showToast('Delete error: ' + err.message, 'error');
    } finally {
        hideLoading();
    }
}

async function exportReport(format) {
    showLoading('Exporting report...');

    try {
        const res = await fetch(`${API_BASE}/api/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ format }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Export failed');
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report.${format}`;
        a.click();
        URL.revokeObjectURL(url);

        showToast(`Report exported as ${format.toUpperCase()}`, 'success');
    } catch (err) {
        showToast('Export error: ' + err.message, 'error');
    } finally {
        hideLoading();
    }

    const menu = document.getElementById('exportMenu');
    if (menu) menu.classList.remove('show');
}

/* ======================== RENDER ======================== */

function renderAll() {
    if (!currentData) return;

    updateScannedStats(currentData.stats);
    renderTable(currentData.top_folders);
    renderTreemap(currentData.top_folders);
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

function renderTable(folders) {
    const tbody = document.getElementById('folderTableBody');
    if (!tbody) return;

    let sorted = [...folders];
    sorted.sort((a, b) => {
        let va = a[sortColumn];
        let vb = b[sortColumn];
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
        const lockIcon = folder.risk === 'critical' ? ' &#128274;' : '';
        const cautionIcon = folder.risk === 'caution' ? ' &#9888;' : '';

        let actionBtn;
        if (!folder.deletable) {
            actionBtn = `<button class="btn btn-danger" disabled title="System folder - cannot be deleted">&#128274;</button>`;
        } else if (folder.risk === 'caution') {
            actionBtn = `<button class="btn btn-warning" onclick="confirmDelete('${escapeHtml(folder.path)}')">&#9888; Delete</button>`;
        } else {
            actionBtn = `<button class="btn btn-danger" onclick="confirmDelete('${escapeHtml(folder.path)}')">&#128465; Delete</button>`;
        }

        return `
            <tr>
                <td>${idx + 1}</td>
                <td class="path" title="${escapeHtml(folder.path)}">${escapeHtml(folder.name)}</td>
                <td class="size">${formatSize(folder.total_size)}</td>
                <td><span class="risk-badge ${riskClass}">${riskLabel}${lockIcon}${cautionIcon}</span></td>
                <td class="files">${folder.file_count.toLocaleString()}</td>
                <td>${actionBtn}</td>
            </tr>
        `;
    }).join('');
}

function renderTreemap(folders) {
    const container = document.getElementById('treemapContent');
    if (!container) return;

    const top15 = folders.slice(0, 15);
    if (top15.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted)">No data to display.</p>';
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
        <p>Are you sure you want to send this folder to the Recycle Bin?</p>
        <p style="margin-top: 12px; font-family: monospace; color: var(--caution);">${escapeHtml(path)}</p>
        <p style="margin-top: 12px; font-size: 12px; color: var(--text-muted);">This action is recoverable from the Recycle Bin.</p>
    `;

    confirmBtn.onclick = () => {
        modal.classList.remove('active');
        deleteFolders([path]);
    };

    modal.classList.add('active');
}

function toggleExportDropdown() {
    const menu = document.getElementById('exportMenu');
    if (menu) menu.classList.toggle('show');
}

function exportAs(format) {
    exportReport(format);
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
        loadingText.textContent = text || 'Loading...';
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
