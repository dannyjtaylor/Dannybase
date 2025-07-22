// dannybase.js - All main interactive logic for Dannybase UI
// --- Import Modal AJAX logic ---
// Excel-like table logic: show Save All button only after a change, handle row delete, and keep best practices
document.addEventListener('DOMContentLoaded', function() {
  const importForm = document.querySelector('#import-modal form');
  const importModal = document.getElementById('import-modal');
  if (importForm && importModal) {
    importForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const fileInput = importForm.querySelector('input[type="file"]');
      if (!fileInput.files.length) return;
      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      // Step 1: Preview
      fetch('/import/preview', { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
          if (data.error) throw new Error(data.error);
          // Show preview table and confirm button in modal
          showImportPreview(data.preview, data.columns, data.csv_b64);
        })
        .catch(err => {
          alert('Import error: ' + err.message);
        });
    });
  }

function showImportPreview(preview, columns, csv_b64) {
  const modal = document.getElementById('import-modal');
  const form = modal.querySelector('form');
  form.style.display = 'none';
  // Canonical columns for preview (including auto-calculated)
  const canonicalCols = [
    'EmployeeID','Username','WorkEmail','FirstName','LastName','Nickname','DepartmentCode','Department','Position','JoinDate','Birthday','OfficeLocation','Supervisor','OfficePhoneAndExtension','MobilePhone','EmploymentType','EmploymentStatus','YearsOfService'
  ];
  // Map possible CSV headers to canonical
  const headerMap = {
    'EmployeeID': ['EmployeeID','Employee Id','Employee ID','ID'],
    'Username': ['Username','User Name','User'],
    'FirstName': ['FirstName','First Name','First'],
    'LastName': ['LastName','Last Name','Last'],
    'Nickname': ['Nickname','Nick Name'],
    'DepartmentCode': ['DepartmentCode','Department Code'],
    'Department': ['Department','Department / Department Description','Department Description'],
    'Position': ['Position','Title'],
    'JoinDate': ['JoinDate','Join Date'],
    'Birthday': ['Birthday','Birth Date'],
    'OfficeLocation': ['OfficeLocation','Office Location'],
    'Supervisor': ['Supervisor'],
    'OfficePhoneAndExtension': ['OfficePhoneAndExtension','Office Phone & Extension','Office Phone'],
    'MobilePhone': ['MobilePhone','Mobile Phone'],
    'EmploymentType': ['EmploymentType','Employment Type'],
    'EmploymentStatus': ['EmploymentStatus','Employment Status'],
  };
  // Build preview rows with correct mapping and calculated fields
  const now = new Date();
  const currentYear = now.getFullYear();
  const previewRows = preview.map(row => {
    let r = {};
    // Map all canonical fields from possible CSV headers
    canonicalCols.forEach(col => {
      if (col === 'WorkEmail') return; // handled below
      if (col === 'YearsOfService') return; // handled below
      let found = null;
      if (headerMap[col]) {
        for (const h of headerMap[col]) {
          if (row[h] !== undefined && row[h] !== null && row[h] !== '') {
            found = row[h];
            break;
          }
        }
      } else if (row[col] !== undefined && row[col] !== null && row[col] !== '') {
        found = row[col];
      }
      r[col] = found !== null ? found : '';
    });
    // WorkEmail: username@mywinterhaven.com
    r.WorkEmail = r.Username ? (r.Username + '@mywinterhaven.com') : '';
    // YearsOfService: current year - join year (from MM/DD/YYYY)
    let joinYear = null;
    if (r.JoinDate && /^\d{1,2}\/\d{1,2}\/\d{4}$/.test(r.JoinDate)) {
      joinYear = parseInt(r.JoinDate.split('/')[2], 10);
    }
    r.YearsOfService = (joinYear && !isNaN(joinYear)) ? (currentYear - joinYear).toString() : '';
    // Only fill N/A for truly missing fields
    canonicalCols.forEach(col => { if (r[col] === undefined || r[col] === null || r[col] === '') r[col] = 'N/A'; });
    return r;
  });
  // Build preview table with canonical columns, center data
  let previewDiv = document.createElement('div');
  previewDiv.className = 'mb-4 w-full h-full flex flex-col items-center justify-center';
  let table = `<table class=\"w-full bg-white border border-teal-200 rounded shadow text-xs max-h-[60vh] overflow-y-auto\"><thead class=\"bg-teal-100\"><tr>`;
  canonicalCols.forEach(col => { table += `<th class='py-2 px-3 border-b text-center whitespace-nowrap'>${col}</th>`; });
  table += '</tr></thead><tbody>';
  previewRows.forEach(row => {
    table += '<tr class=\"border-b hover:bg-teal-50\">';
    canonicalCols.forEach(col => { table += `<td class='py-1 px-2 text-center'>${row[col]}</td>`; });
    table += '</tr>';
  });
  table += '</tbody></table>';
  previewDiv.innerHTML = `<h3 class='text-lg font-semibold text-primary-dark mb-4 text-center'>Please confirm the import:</h3>${table}`;
  // Confirm/cancel buttons
  let btns = document.createElement('div');
  btns.className = 'flex gap-2 justify-center mt-6';
  let confirmBtn = document.createElement('button');
  confirmBtn.className = 'btn bg-emerald-600 text-white px-6 py-3 rounded shadow hover:bg-emerald-700 text-lg font-bold';
  confirmBtn.textContent = 'Confirm Import';
  let cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn bg-gray-400 text-white px-6 py-3 rounded shadow hover:bg-gray-600 text-lg font-bold';
  cancelBtn.textContent = 'Cancel';
  btns.appendChild(confirmBtn);
  btns.appendChild(cancelBtn);
  previewDiv.appendChild(btns);
  // Make modal fill screen and match preview size
  const modalContent = modal.querySelector('.bg-white');
  modalContent.innerHTML = '';
  modalContent.classList.add('w-full','h-full','max-w-none','flex','flex-col','justify-center','items-center','p-0');
  modalContent.appendChild(previewDiv);
  // Confirm import
  confirmBtn.onclick = function(ev) {
    ev.preventDefault();
    fetch('/import/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ csv_b64 })
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) throw new Error(data.error);
        window.location.reload();
      })
      .catch(err => {
        alert('Import error: ' + err.message);
      });
  };
  // Cancel import
  cancelBtn.onclick = function(ev) {
    ev.preventDefault();
    // Close the modal overlay
    const modal = document.getElementById('import-modal');
    if (modal) {
      modal.classList.add('hidden');
    }
    // Reset modal content for next open (restore upload form)
    setTimeout(() => {
      if (modalContent && form) {
        modalContent.innerHTML = '';
        form.reset();
        form.style.display = '';
        modalContent.appendChild(form);
      }
    }, 200);
  };
}

// Show/hide columns with persistence and scroll sync (modal version)
const COL_KEY = 'dannybase_visible_columns';
const allCols = [
    "EmployeeID", "Username", "WorkEmail", "FirstName", "LastName", "Nickname", "DepartmentCode", "Department", "Position", "JoinDate", "Birthday", "Office Location", "Supervisor", "OfficePhone&Extension", "MobilePhone", "EmploymentType", "EmploymentStatus", "YearsOfService"
];
function saveColPrefs() {
    const checked = Array.from(document.querySelectorAll('.toggle-col')).filter(cb => cb.checked).map(cb => cb.getAttribute('data-col'));
    localStorage.setItem(COL_KEY, JSON.stringify(checked));
}
function loadColPrefs() {
    try {
        return JSON.parse(localStorage.getItem(COL_KEY));
    } catch { return null; }
}
function setColVisibility(col, visible) {
    var ths = document.querySelectorAll('th[data-col="' + col + '"]');
    var tds = document.querySelectorAll('td[data-col="' + col + '"]');
    if (visible) {
        ths.forEach(e => e.style.display = '');
        tds.forEach(e => e.style.display = '');
    } else {
        ths.forEach(e => e.style.display = 'none');
        tds.forEach(e => e.style.display = 'none');
    }
}
function updateColVisibilityFromPrefs() {
    const prefs = loadColPrefs();
    document.querySelectorAll('.toggle-col').forEach(cb => {
        const col = cb.getAttribute('data-col');
        cb.checked = !prefs || prefs.includes(col);
        setColVisibility(col, cb.checked);
    });
}
function attachToggleListeners() {
    document.querySelectorAll('.toggle-col').forEach(function(checkbox) {
        checkbox.addEventListener('change', function() {
            var col = this.getAttribute('data-col');
            setColVisibility(col, this.checked);
            saveColPrefs();
        });
    });
}
function attachShowHideAllListeners() {
    document.getElementById('show-all-cols').onclick = function() {
        document.querySelectorAll('.toggle-col').forEach(cb => { cb.checked = true; setColVisibility(cb.getAttribute('data-col'), true); });
        saveColPrefs();
    };
    document.getElementById('hide-all-cols').onclick = function() {
        document.querySelectorAll('.toggle-col').forEach(cb => { cb.checked = false; setColVisibility(cb.getAttribute('data-col'), false); });
        saveColPrefs();
    };
}
// On load, apply saved prefs and attach listeners
updateColVisibilityFromPrefs();
attachToggleListeners();
attachShowHideAllListeners();

// Responsive table: make table scroll horizontally on small screens
window.addEventListener('resize', function() {
    var table = document.getElementById('employee-table');
    if (window.innerWidth < 900) {
        table.parentElement.style.overflowX = 'auto';
    } else {
        table.parentElement.style.overflowX = '';
    }
});
window.dispatchEvent(new Event('resize'));

// Make table cells editable like Excel
function makeCellsEditable() {
    var table = document.getElementById('employee-table');
    if (!table) return;
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(function(row, idx) {
        row.querySelectorAll('td').forEach(function(cell) {
            cell.setAttribute('contenteditable', 'true');
            cell.classList.add('editable-cell');
            cell.addEventListener('blur', function() {
                // On cell exit, save the row to backend
                saveRowToBackend(row);
            });
        });
        // Alternate row color (Excel style)
        if (idx % 2 === 0) {
            row.classList.add('bg-gray-100');
        } else {
            row.classList.remove('bg-gray-100');
        }
    });
// Save a single row to backend (on cell blur)
function saveRowToBackend(row) {
    const cells = row.querySelectorAll('td');
    const headers = Array.from(document.querySelectorAll('#employee-table thead th')).map(th => th.getAttribute('data-col'));
    let emp = {};
    cells.forEach((cell, i) => {
        if (headers[i]) emp[headers[i]] = cell.innerText.trim();
    });
    // Use EmployeeID as unique key
    if (emp.EmployeeID) {
        fetch(`/api/employees/${emp.EmployeeID}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(emp)
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) showToast('Save failed: ' + data.error, 'error');
            else showToast('Row saved!', 'success');
        })
        .catch(() => showToast('Save failed', 'error'));
    }
}
// Save all rows to backend (bulk save)
document.addEventListener('DOMContentLoaded', function() {
    const saveAllBtn = document.getElementById('save-all-btn');
    var table = document.getElementById('employee-table');
    const saveAllContainer = document.getElementById('save-all-container');
  if (saveAllBtn) {
    saveAllBtn.addEventListener('click', function() {
      const rows = document.querySelectorAll('#employee-table tbody tr');
      const headers = Array.from(document.querySelectorAll('#employee-table thead th')).map(th => th.getAttribute('data-col'));
      let allEmps = [];
      rows.forEach(row => {
        let emp = {};
        row.querySelectorAll('td').forEach((cell, i) => {
          if (headers[i]) emp[headers[i]] = cell.innerText.trim();
        });
        if (emp.EmployeeID) allEmps.push(emp);
      });
      fetch('/api/employees', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ employees: allEmps })
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) showToast('Bulk save failed: ' + data.error, 'error');
        else showToast('All changes saved!', 'success');
      })
      .catch(() => showToast('Bulk save failed', 'error'));
    });
  }
});
}
    // Show Save All button if any change
    function showSaveAll() {
      if (saveAllContainer) saveAllContainer.style.display = 'flex';
    }
    function hideSaveAll() {
      if (saveAllContainer) saveAllContainer.style.display = 'none';
      changedRows.clear();
      deletedRows.clear();
    }
    // Mark row as changed on cell edit
    table.addEventListener('blur', function (e) {
      if (e.target && e.target.matches('td[contenteditable]')) {
        const row = e.target.closest('tr');
        if (row && row.dataset.rowid) {
          changedRows.add(row.dataset.rowid);
          showSaveAll();
        }
      }
    }, true);
    // Handle delete button
    table.addEventListener('click', function (e) {
      if (e.target.closest('.delete-row-btn')) {
        const btn = e.target.closest('.delete-row-btn');
        const row = btn.closest('tr');
        if (row && row.dataset.rowid) {
          // Remove visually
          row.remove();
          // Remove from backend immediately
          fetch(`/api/employees/${row.dataset.rowid}`, {
            method: 'DELETE',
          })
            .then(r => r.json())
            .then(data => {
              if (data.error) showToast('Delete failed: ' + data.error, 'error');
              else showToast('Employee deleted!', 'success');
            })
            .catch(() => showToast('Delete failed', 'error'));
          showSaveAll();
        }
      }
    });
    // Save All logic
    if (saveAllBtn) {
      saveAllBtn.addEventListener('click', function () {
        // Gather all changed and deleted rows
        const rows = Array.from(table.querySelectorAll('tbody tr'));
        const data = rows.map(row => {
          if (deletedRows.has(row.dataset.rowid)) {
            return { _rowid: row.dataset.rowid, _delete: true };
          }
          // Gather cell data
          const cells = row.querySelectorAll('td[data-col]');
          const rowData = { _rowid: row.dataset.rowid };
          cells.forEach(cell => {
            rowData[cell.dataset.col] = cell.innerText.trim();
          });
          return rowData;
        });
        // Send to backend (bulk update endpoint)
        fetch('/api/employees/bulk_update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data })
        })
          .then(res => res.json())
          .then(resp => {
            if (resp.success) {
              window.dispatchEvent(new Event('employee-edited'));
              // Optionally reload table
              location.reload();
            } else {
              showToast('Save failed: ' + (resp.error || 'Unknown error'), 'error');
            }
          })
          .catch(() => showToast('Save failed', 'error'));
      });
    }
    // Optionally, hide Save All on page load
    hideSaveAll();
    // Add data-rowid to each row for tracking (assume EmployeeID is unique)
    Array.from(table.querySelectorAll('tbody tr')).forEach(row => {
      const idCell = row.querySelector('td[data-col="EmployeeID"]');
      if (idCell) row.dataset.rowid = idCell.innerText.trim();
    });
    // Make all cells editable except delete column
    Array.from(table.querySelectorAll('tbody tr')).forEach(row => {
      Array.from(row.querySelectorAll('td[data-col]')).forEach(cell => {
        cell.setAttribute('contenteditable', 'true');
      });
    });
    // Always show EmployeeID and WorkEmail columns on load
    setColVisibility('EmployeeID', true);
    setColVisibility('WorkEmail', true);
  // End of DOMContentLoaded for Excel-like logic
});
// Ensure search input triggers live filtering (in case of dynamic reloads)
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('search-input');
    var table = document.getElementById('employee-table');
  if (searchInput && table) {
    searchInput.addEventListener('input', function() {
      const filter = searchInput.value.toLowerCase();
      const rows = table.querySelectorAll('tbody tr');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(filter) ? '' : 'none';
      });
    });
  }
});

// Edit button: focus first cell, show Save button

// Auto-fit columns based on max content length in each column (like Excel)
function autoFitColumns() {
    var table = document.getElementById('employee-table');
    if (!table) return;
    var ths = table.querySelectorAll('thead th');
    var rows = table.querySelectorAll('tbody tr');
    ths.forEach(function(th, colIdx) {
        var maxLen = th.innerText.length;
        rows.forEach(function(row) {
            var cell = row.children[colIdx];
            if (cell) {
                var text = cell.innerText || '';
                if (text.length > maxLen) maxLen = text.length;
            }
        });
        // Estimate width: 10px per char, min 80px, max 500px
        var width = Math.max(80, Math.min(500, maxLen * 10));
        th.style.width = width + 'px';
        th.style.minWidth = width + 'px';
        th.style.maxWidth = width + 'px';
        rows.forEach(function(row) {
            var cell = row.children[colIdx];
            if (cell) {
                cell.style.width = width + 'px';
                cell.style.minWidth = width + 'px';
                cell.style.maxWidth = width + 'px';
            }
        });
    });
}

// Initial fit
autoFitColumns();
// Re-fit on input
document.querySelectorAll('#employee-table tbody').forEach(function(tbody) {
    tbody.addEventListener('input', function() {
        autoFitColumns();
    });
});

// Export button: gray out if no data
document.addEventListener('DOMContentLoaded', function() {
  const exportBtn = document.getElementById('export-btn');
  const table = document.getElementById('employee-table');
  if (exportBtn && table) {
    const hasData = table.querySelectorAll('tbody tr').length > 1 || (table.querySelector('tbody tr') && !table.querySelector('tbody tr').textContent.includes('No employees found.'));
    if (!hasData) {
      exportBtn.classList.add('opacity-50','cursor-not-allowed');
      exportBtn.setAttribute('tabindex','-1');
      exportBtn.setAttribute('aria-disabled','true');
      exportBtn.onclick = e => e.preventDefault();
    } else {
      exportBtn.classList.remove('opacity-50','cursor-not-allowed');
      exportBtn.removeAttribute('aria-disabled');
      exportBtn.onclick = null;
    }
  }
});

// Modal open/close logic (moved here for proper functioning)
document.addEventListener('DOMContentLoaded', function() {
  const settingsModal = document.getElementById('settings-modal');
  const openSettingsBtn = document.getElementById('open-settings');
  const closeSettingsBtn = document.getElementById('close-settings');
  if (openSettingsBtn && settingsModal && closeSettingsBtn) {
    openSettingsBtn.addEventListener('click', () => {
      settingsModal.classList.remove('hidden');
      document.body.classList.add('overflow-hidden');
      document.getElementById('settings-title').focus();
    });
    closeSettingsBtn.addEventListener('click', () => {
      settingsModal.classList.add('hidden');
      document.body.classList.remove('overflow-hidden');
      openSettingsBtn.focus();
    });
    settingsModal.addEventListener('click', (e) => {
      if (e.target === settingsModal) {
        settingsModal.classList.add('hidden');
        document.body.classList.remove('overflow-hidden');
        openSettingsBtn.focus();
      }
    });
    document.addEventListener('keydown', (e) => {
      if (!settingsModal.classList.contains('hidden') && e.key === 'Escape') {
        settingsModal.classList.add('hidden');
        document.body.classList.remove('overflow-hidden');
        openSettingsBtn.focus();
      }
    });
  }
});
