// dannybase.js - All main interactive logic for Dannybase UI

// Show/hide columns with persistence and scroll sync (modal version)
const COL_KEY = 'dannybase_visible_columns';
const allCols = [
    "Employee ID", "Work Email", "First Name", "Last Name", "Nickname", "Department Code", "Department / Department Description", "Position", "Join Date", "Birthday", "Office Location", "Supervisor", "Office Phone & Extension", "Mobile Phone (if applicable)", "Employment Type", "Employment Status", "Years of Service", "Actions"
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
    document.querySelectorAll('#employee-table tbody tr').forEach(function(row) {
        row.querySelectorAll('td:not([data-col="Actions"])').forEach(function(cell) {
            cell.setAttribute('contenteditable', 'true');
            cell.classList.add('editable-cell');
        });
    });
}
makeCellsEditable();

// Edit button: focus first cell, show Save button
window.editRow = function(btn) {
    var row = btn.closest('tr');
    row.querySelectorAll('td:not([data-col="Actions"])').forEach(function(cell) {
        cell.setAttribute('contenteditable', 'true');
        cell.classList.add('editable-cell');
    });
    var firstEditable = row.querySelector('td[contenteditable]');
    if (firstEditable) {
        firstEditable.focus();
    }
    btn.style.display = 'none';
    row.querySelector('.btn-save').style.display = '';
}

// Save button: disable editing, show Edit button
window.saveRow = function(btn) {
    var row = btn.closest('tr');
    row.querySelectorAll('td:not([data-col="Actions"])').forEach(function(cell) {
        cell.setAttribute('contenteditable', 'false');
        cell.classList.remove('editable-cell');
    });
    btn.style.display = 'none';
    row.querySelector('.btn-edit').style.display = '';
    autoFitColumns();
}

// Delete button: remove row
window.deleteRow = function(btn) {
    if (confirm('Delete this employee?')) {
        var row = btn.closest('tr');
        row.remove();
        autoFitColumns();
    }
}

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

// Fetch and render the latest employee data from backend on page load/refresh
async function fetchAndRenderEmployees() {
    try {
        const resp = await fetch('/api/employees');
        if (!resp.ok) return;
        const data = await resp.json();
        const tbody = document.querySelector('#employee-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (data.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="19" class="py-4 text-center text-gray-500">No employees found.</td>';
            tbody.appendChild(tr);
        } else {
            data.forEach(emp => {
                const tr = document.createElement('tr');
                tr.className = 'border-b hover:bg-teal-100';
                tr.innerHTML = `
                    <td class="py-2 px-4" data-col="Employee ID">${emp.EmployeeID || ''}</td>
                    <td class="py-2 px-4" data-col="Username">${emp.Username || ''}</td>
                    <td class="py-2 px-4" data-col="Work Email">${emp.Username ? emp.Username + '@mywinterhaven.com' : (emp.WorkEmail || '')}</td>
                    <td class="py-2 px-4" data-col="First Name">${emp.FirstName || ''}</td>
                    <td class="py-2 px-4" data-col="Last Name">${emp.LastName || ''}</td>
                    <td class="py-2 px-4" data-col="Nickname">${emp.Nickname || ''}</td>
                    <td class="py-2 px-4" data-col="Department Code">${emp.DepartmentCode || ''}</td>
                    <td class="py-2 px-4" data-col="Department / Department Description">${emp.Department || ''}</td>
                    <td class="py-2 px-4" data-col="Position">${emp.Position || ''}</td>
                    <td class="py-2 px-4" data-col="Join Date">${emp.JoinDate || ''}</td>
                    <td class="py-2 px-4" data-col="Birthday">${emp.Birthday || ''}</td>
                    <td class="py-2 px-4" data-col="Office Location">${emp.OfficeLocation || ''}</td>
                    <td class="py-2 px-4" data-col="Supervisor">${emp.Supervisor || ''}</td>
                    <td class="py-2 px-4" data-col="Office Phone & Extension">${emp.OfficePhoneAndExtension || ''}</td>
                    <td class="py-2 px-4" data-col="Mobile Phone (if applicable)">${emp.MobilePhone || ''}</td>
                    <td class="py-2 px-4" data-col="Employment Type">${emp.EmploymentType || ''}</td>
                    <td class="py-2 px-4" data-col="Employment Status">${emp.EmploymentStatus || ''}</td>
                    <td class="py-2 px-4" data-col="Years of Service">${emp.YearsOfService || ''}</td>
                    <td class="py-2 px-4 flex gap-2" data-col="Actions">
                        <button class="btn btn-edit text-white px-2 py-1 rounded shadow" onclick="editRow(this)">&#9998; Edit</button>
                        <button class="btn btn-save text-white px-2 py-1 rounded shadow" style="display:none;" onclick="saveRow(this)">&#128190; Save</button>
                        <button class="btn btn-delete text-white px-2 py-1 rounded shadow" onclick="deleteRow(this)">&#10006; Delete</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
        autoFitColumns();
    } catch (e) { /* ignore */ }
}

window.addEventListener('DOMContentLoaded', fetchAndRenderEmployees);
// Re-fit on input
document.querySelectorAll('#employee-table tbody').forEach(function(tbody) {
    tbody.addEventListener('input', function() {
        autoFitColumns();
    });
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
