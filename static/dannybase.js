// dannybase.js - All main interactive logic for Dannybase UI


// ---- Toast Notification Logic ----
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast-box flex items-center gap-3 px-5 py-3 rounded-lg shadow-lg font-semibold mb-2 border-l-4 animate-fade-in ${type === 'error' ? 'bg-red-50 border-red-600 text-red-800' : 'bg-white border-teal-600 text-teal-900'}`;
    toast.style.transition = 'opacity 0.5s';
    toast.innerHTML = `
    <span class="material-icons text-2xl">${type === 'error' ? 'error_outline' : 'check_circle'}</span>
    <span class="flex-1">${message}</span>
    <button class="ml-2 text-xl text-gray-400 hover:text-gray-700 focus:outline-none" aria-label="Close notification">&times;</button>
  `;
    toast.querySelector('button').onclick = () => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 500);
    };
    container.appendChild(toast);
    setTimeout(() => {
        if (toast.parentNode) {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 500);
        }
    }, 4000);
}

// ---- Import Preview Logic ----
function displayImportPreview(data, modal, resetImportModal) {
    const { preview, columns, csv_b64 } = data;
    const step1Div = document.getElementById('import-step-1');
    const step2Div = document.getElementById('import-step-2');
    if (!preview || preview.length === 0) {
        showToast('The uploaded file is empty or could not be read.', 'error');
        return;
    }
    let tableHTML = `
      <h3 class="text-xl mb-2 font-semibold">Confirm Import (${preview.length} rows)</h3>
      <div class="overflow-auto border rounded" style="max-height: 40vh;">
        <table class="min-w-full bg-white text-sm">
          <thead class="bg-teal-100 sticky top-0"><tr>${columns.map(col => `<th class="px-2 py-1 border text-left">${col}</th>`).join('')}</tr></thead>
          <tbody>${preview.map(row => `
            <tr class="hover:bg-teal-50">${columns.map(col => `<td class="px-2 py-1 border whitespace-nowrap">${row[col] || 'N/A'}</td>`).join('')}</tr>
          `).join('')}</tbody>
        </table>
      </div>`;
    let formHTML = `
      <div class="mt-4 flex gap-2">
        <button id="confirm-import-btn" class="btn bg-green-600 text-white px-4 py-2 rounded shadow hover:bg-green-700">Confirm</button>
        <button id="cancel-import-btn" type="button" class="btn bg-gray-400 text-white px-4 py-2 rounded shadow hover:bg-gray-600">Cancel</button>
      </div>`;
    step2Div.innerHTML = tableHTML + formHTML;
    step1Div.classList.add('hidden');
    step2Div.classList.remove('hidden');
    document.getElementById('confirm-import-btn').addEventListener('click', async function() {
        this.disabled = true;
        this.textContent = 'Importing...';
        try {
            const confirmResponse = await fetch('/import/confirm', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    csv_b64: csv_b64
                })
            });
            const confirmData = await confirmResponse.json();
            if (!confirmResponse.ok) {
                throw new Error(confirmData.error || 'Failed to confirm import.');
            }
            showToast(confirmData.message || 'Import successful!');
            modal.classList.add('hidden');
            window.location.reload();
        } catch (error) {
            showToast(`Confirmation Error: ${error.message}`, 'error');
            this.disabled = false;
            this.textContent = 'Confirm';
        }
    });
    document.getElementById('cancel-import-btn').addEventListener('click', resetImportModal);
}

// ---- Column Visibility Persistence ----
const COL_KEY = 'dannybase_visible_columns';

function saveColPrefs() {
    const checked = Array.from(document.querySelectorAll('.toggle-col'))
        .filter(cb => cb.checked).map(cb => cb.getAttribute('data-col'));
    localStorage.setItem(COL_KEY, JSON.stringify(checked));
}

function loadColPrefs() {
    try {
        return JSON.parse(localStorage.getItem(COL_KEY));
    } catch {
        return null;
    }
}

function setColVisibility(col, visible) {
    document.querySelectorAll(`th[data-col="${col}"], td[data-col="${col}"]`)
        .forEach(el => el.style.display = visible ? '' : 'none');
}

function updateColVisibilityFromPrefs() {
    const prefs = loadColPrefs();
    document.querySelectorAll('.toggle-col').forEach(cb => {
        const col = cb.getAttribute('data-col');
        const show = !prefs || prefs.includes(col);
        cb.checked = show;
        setColVisibility(col, show);
    });
}

// ---- Auto-fit Columns ----
function autoFitColumns() {
    const table = document.getElementById('employee-table');
    if (!table) return;
    const ths = table.querySelectorAll('thead th');
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    if (rows.length === 0 || (rows.length === 1 && rows[0].textContent.includes('No employees found'))) {
        return;
    }
    ths.forEach((th, idx) => {
        if (th.getAttribute('data-col') === '#') {
            return; // Skip auto-sizing for the manually styled index column
        }
        let maxLen = th.innerText.length;
        rows.forEach(row => {
            const text = row.children[idx]?.innerText || '';
            if (text.length > maxLen) maxLen = text.length;
        });
        const width = Math.max(120, maxLen * 9 + 40);
        th.style.width = th.style.minWidth = width + 'px';
        rows.forEach(row => {
            const c = row.children[idx];
            if (c) c.style.width = c.style.minWidth = width + 'px';
        });
    });
}

// ---- Save Row on Blur ----
function saveRowToBackend(row) {
    const headers = Array.from(document.querySelectorAll('#employee-table thead th'))
        .map(th => th.getAttribute('data-col'));
    const emp = {};
    row.querySelectorAll('td[data-col]').forEach((cell, i) => {
        if (headers[i] && headers[i] !== 'Delete' && headers[i] !== '#') { // Exclude action and index columns
            emp[headers[i]] = cell.innerText.trim();
        }
    });

    const empId = emp['EmployeeID'];
    if (!empId) {
        showToast('Cannot save row without an EmployeeID.', 'error');
        return;
    }

    fetch(`/api/employees/${empId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(emp)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || 'Save failed')
                });
            }
            return response.json();
        })
        .then(data => {
            showToast(data.message || 'Row saved!', 'success');
        })
        .catch(error => {
            showToast(error.message, 'error');
        });
}

// ---- Make Cells Editable ----
function makeCellsEditable() {
    const table = document.getElementById('employee-table');
    if (!table) return;
    table.querySelectorAll('tbody tr').forEach((row, idx) => {
        row.querySelectorAll('td[data-col]').forEach(cell => {
            // The 'Delete' and '#' index columns should not be editable
            if (cell.getAttribute('data-col') !== 'Delete' && cell.getAttribute('data-col') !== '#') {
                cell.contentEditable = 'true';
                cell.classList.add('editable-cell');
                cell.addEventListener('blur', () => saveRowToBackend(row));
                cell.addEventListener('input', () => {
                    autoFitColumns();
                });
            }
        });
        row.classList.toggle('bg-gray-100', idx % 2 === 0);
    });
}

function reindexTable() {
    const table = document.getElementById('employee-table');
    if (!table) return;
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach((row, index) => {
        const indexCell = row.querySelector('td[data-col="#"]');
        // Ensure we're not trying to index the "No employees found" row
        if (indexCell && !row.querySelector('td[colspan]')) {
            indexCell.textContent = index + 1;
        }
    });
}

function reindexTable() {
    const table = document.getElementById('employee-table');
    if (!table) return;
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach((row, index) => {
        const indexCell = row.querySelector('td[data-col="#"]');
        // Ensure we're not trying to index the "No employees found" row
        if (indexCell && !row.querySelector('td[colspan]')) {
            indexCell.textContent = index + 1;
        }
    });
}

// ---- Table Sorting Logic ----
function sortTable(sortBy, sortDir = 'asc') {
    const table = document.getElementById('employee-table');
    const tbody = table.querySelector('tbody');
    if (!tbody) return;

    const rows = Array.from(tbody.querySelectorAll('tr'));

    // Ignore sorting if table is empty or has the "not found" message
    if (rows.length <= 1 && rows[0]?.textContent.includes('No employees found')) {
        return;
    }

    const getCellValue = (row, colName) => {
        const cell = row.querySelector(`td[data-col="${colName}"]`);
        return cell ? cell.innerText.trim() : '';
    };

    rows.sort((a, b) => {
        let valA, valB;

        switch (sortBy) {
            case 'id':
                valA = parseInt(getCellValue(a, 'EmployeeID'), 10) || 0;
                valB = parseInt(getCellValue(b, 'EmployeeID'), 10) || 0;
                return sortDir === 'asc' ? valA - valB : valB - valA;

            case 'department':
                valA = getCellValue(a, 'Department');
                valB = getCellValue(b, 'Department');
                return valA.localeCompare(valB);

            case 'joindate':
                valA = new Date(getCellValue(a, 'JoinDate'));
                valB = new Date(getCellValue(b, 'JoinDate'));
                if (isNaN(valA)) valA = sortDir === 'asc' ? new Date('9999-12-31') : new Date('1000-01-01');
                if (isNaN(valB)) valB = sortDir === 'asc' ? new Date('9999-12-31') : new Date('1000-01-01');
                return sortDir === 'asc' ? valA - valB : valB - valA;

            case 'birthday':
                const today = new Date();
                const todayMonth = today.getMonth() + 1;
                const todayDay = today.getDate();
                const getBirthdaySortValue = (dateStr) => {
                    if (!/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(dateStr)) return 99999;
                    const [month, day] = dateStr.split('/').map(Number);
                    if (sortDir === 'calendar') return month * 100 + day;
                    const isUpcoming = (month > todayMonth) || (month === todayMonth && day >= todayDay);
                    return isUpcoming ? (month * 100 + day) : 10000 + (month * 100 + day);
                };
                return getBirthdaySortValue(getCellValue(a, 'Birthday')) - getBirthdaySortValue(getCellValue(b, 'Birthday'));
            default:
                return 0;
        }
    });

    rows.forEach(row => tbody.appendChild(row));
    reindexTable(); // Re-apply the index numbers after the sort
    showToast(`Table sorted by ${sortBy}.`, 'success');
}

// ---- Single Initialization ----
document.addEventListener('DOMContentLoaded', function() {
    // --- Element Selectors ---
    const table = document.getElementById('employee-table');
    const openImportBtn = document.getElementById('open-import-modal');
    const closeImportBtn = document.getElementById('close-import-modal');
    const importForm = document.getElementById('import-form');
    const importModal = document.getElementById('import-modal');
    const settingsModal = document.getElementById('settings-modal');
    const openSettingsBtn = document.getElementById('open-settings');
    const closeSettingsBtn = document.getElementById('close-settings');
    const searchInput = document.getElementById('search-input');
    const exportBtn = document.getElementById('export-btn');
    const openSortBtn = document.getElementById('open-sort-modal');
    const closeSortBtn = document.getElementById('close-sort-modal');
    const sortModal = document.getElementById('sort-modal');

    // --- Initial Setup ---
    updateColVisibilityFromPrefs();
    makeCellsEditable();
    autoFitColumns();

    // --- Event Listeners ---

    // 1) Import Modal Logic
    if (openImportBtn && closeImportBtn && importModal) {
        const step1Div = document.getElementById('import-step-1');
        const step2Div = document.getElementById('import-step-2');

        const resetImportModal = () => {
            if (step2Div) {
                step2Div.innerHTML = '';
                step2Div.classList.add('hidden');
            }
            if (step1Div) step1Div.classList.remove('hidden');
            if (importForm) importForm.reset();
            importModal.classList.add('hidden');
        };

        openImportBtn.addEventListener('click', () => importModal.classList.remove('hidden'));
        closeImportBtn.addEventListener('click', resetImportModal);
        importModal.addEventListener('click', (e) => {
            if (e.target === importModal) resetImportModal();
        });

        importForm.addEventListener('submit', async e => {
            e.preventDefault();
            const fileInput = importForm.querySelector('input[name="file"]');
            if (!fileInput.files.length) {
                return showToast('Please choose a CSV to import.', 'error');
            }
            const fd = new FormData();
            fd.append('file', fileInput.files[0]);
            const submitButton = importForm.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.textContent = 'Uploading...';
            try {
                const resp = await fetch('/import/preview', {
                    method: 'POST',
                    body: fd
                });
                const data = await resp.json();
                if (!resp.ok) {
                    throw new Error(data.error || 'Unknown error during preview.');
                }
                displayImportPreview(data, importModal, resetImportModal);
            } catch (err) {
                showToast(`Import Error: ${err.message}`, 'error');
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = 'Preview Import';
            }
        });
    }

    // 2) Settings Modal & Column Preferences
    if (settingsModal && openSettingsBtn && closeSettingsBtn) {
        const openModal = () => {
            settingsModal.classList.remove('hidden');
            document.body.classList.add('overflow-hidden');
        };
        const closeModal = () => {
            settingsModal.classList.add('hidden');
            document.body.classList.remove('overflow-hidden');
        };

        openSettingsBtn.addEventListener('click', openModal);
        closeSettingsBtn.addEventListener('click', closeModal);
        settingsModal.addEventListener('click', e => {
            if (e.target === settingsModal) closeModal();
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && !settingsModal.classList.contains('hidden')) {
                closeModal();
            }
        });

        document.querySelectorAll('.toggle-col').forEach(cb => {
            cb.addEventListener('change', () => {
                setColVisibility(cb.getAttribute('data-col'), cb.checked);
                saveColPrefs();
            });
        });

        document.getElementById('show-all-cols')?.addEventListener('click', () => {
            document.querySelectorAll('.toggle-col').forEach(cb => {
                cb.checked = true;
                setColVisibility(cb.getAttribute('data-col'), true);
            });
            saveColPrefs();
        });

        document.getElementById('hide-all-cols')?.addEventListener('click', () => {
            document.querySelectorAll('.toggle-col').forEach(cb => {
                cb.checked = false;
                setColVisibility(cb.getAttribute('data-col'), false);
            });
            saveColPrefs();
        });
    }

    // 3) Sort Modal Logic
    if (openSortBtn && closeSortBtn && sortModal) {
        const openModal = () => sortModal.classList.remove('hidden');
        const closeModal = () => sortModal.classList.add('hidden');

        openSortBtn.addEventListener('click', openModal);
        closeSortBtn.addEventListener('click', closeModal);
        sortModal.addEventListener('click', e => {
            if (e.target === sortModal) closeModal();
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && !sortModal.classList.contains('hidden')) closeModal();
        });

        sortModal.addEventListener('click', e => {
            const sortBtn = e.target.closest('.sort-btn');
            if (sortBtn) {
                sortTable(sortBtn.dataset.sortBy, sortBtn.dataset.sortDir);
                closeModal();
            }
        });
    }

    // 3) Table-specific listeners (Delete and Search)
    if (table) {
        // Delete listener using event delegation
        table.addEventListener('click', async function(e) {
            const btn = e.target.closest('.delete-row-btn');
            if (!btn) return;
            
            const row = btn.closest('tr');
            const empId = btn.dataset.empId;
            const firstName = row.querySelector('td[data-col="FirstName"]')?.innerText || '';
            const lastName = row.querySelector('td[data-col="LastName"]')?.innerText || '';
            const fullName = `${firstName} ${lastName}`.trim();

            if (!empId) {
                showToast('Cannot delete row: Employee ID is missing.', 'error');
                return;
            }

            // Use a standard confirm dialog for the yes/no option
            if (confirm(`Are you sure you want to delete ${fullName || `employee ${empId}`}?`)) {
                // Optimistic UI update: remove the row immediately
                row.remove();
                reindexTable(); // Re-index the table after a row is removed

                try {
                    const response = await fetch(`/api/employees/${encodeURIComponent(empId)}`, {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        showToast('Employee deleted successfully.', 'success');
                    } else {
                        // If the delete failed, show an error. The user may need to refresh.
                        const errorData = await response.json();
                        showToast(errorData.detail || 'Failed to delete employee.', 'error');
                    }
                } catch (error) {
                    showToast('A network error occurred. Could not delete employee.', 'error');
                }
            }
            // If the user clicks "Cancel", the `if` block is skipped and nothing happens.
        });
    }
});
