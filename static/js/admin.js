// State
let authToken = localStorage.getItem('authToken');
let currentTeacher = null;
let googleClientId = null;
let students = [];

// API helpers
const API_BASE = '/api';

async function apiCall(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
}

// Google OAuth
async function handleGoogleCredentialResponse(response) {
    const errorEl = document.getElementById('login-error');
    errorEl.classList.add('hidden');

    try {
        const result = await apiCall('/auth/google', {
            method: 'POST',
            body: JSON.stringify({ credential: response.credential })
        });

        // Check if user is a teacher
        if (result.student.role !== 'teacher') {
            errorEl.textContent = 'Access denied. Teacher account required.';
            errorEl.classList.remove('hidden');
            return;
        }

        authToken = result.token;
        currentTeacher = result.student;
        localStorage.setItem('authToken', authToken);
        showAdmin();
        loadInitialData();
    } catch (error) {
        console.error('Auth failed:', error);
        errorEl.textContent = error.message || 'Authentication failed. Please try again.';
        errorEl.classList.remove('hidden');
    }
}

function initGoogleSignIn() {
    if (!googleClientId) {
        const errorEl = document.getElementById('login-error');
        errorEl.textContent = 'Google Sign-In not configured. Please set GOOGLE_CLIENT_ID.';
        errorEl.classList.remove('hidden');
        return;
    }

    google.accounts.id.initialize({
        client_id: googleClientId,
        callback: handleGoogleCredentialResponse,
    });

    google.accounts.id.renderButton(
        document.getElementById('google-signin-container'),
        { theme: 'outline', size: 'large', width: 280 }
    );
}

async function logout() {
    try {
        await apiCall('/auth/logout', { method: 'POST' });
    } catch (error) {
        console.error('Logout error:', error);
    }

    authToken = null;
    currentTeacher = null;
    localStorage.removeItem('authToken');
    showLogin();
    if (googleClientId) initGoogleSignIn();
}

// UI functions
function showLogin() {
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('admin-section').classList.add('hidden');
}

function showAdmin() {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('admin-section').classList.remove('hidden');
    if (currentTeacher) {
        document.getElementById('teacher-name').textContent = currentTeacher.name;
    }
}

function showTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('border-primary', 'text-primary');
        btn.classList.add('border-transparent', 'text-gray-500');
    });
    document.getElementById(`tab-${tabName}`).classList.add('border-primary', 'text-primary');
    document.getElementById(`tab-${tabName}`).classList.remove('border-transparent', 'text-gray-500');

    // Show/hide panels
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.add('hidden'));
    document.getElementById(`panel-${tabName}`).classList.remove('hidden');

    // Load data for the tab
    if (tabName === 'participation') loadParticipation();
}

// Data loading
async function loadInitialData() {
    await loadStudents();
    loadAttendanceSheet();
}

async function loadStudents() {
    try {
        students = await apiCall('/admin/students');
        populateStudentDropdown();
    } catch (error) {
        console.error('Failed to load students:', error);
    }
}

function populateStudentDropdown() {
    const select = document.getElementById('grade-student');
    select.innerHTML = '<option value="">Select a student...</option>';
    students.forEach(s => {
        select.innerHTML += `<option value="${s.id}">${s.name} (${s.email})</option>`;
    });
}

// Attendance
async function loadAttendanceSheet() {
    const dateInput = document.getElementById('attendance-date');
    if (!dateInput.value) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }

    const tbody = document.getElementById('attendance-table');

    if (students.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-4 text-center text-gray-500">No students found</td></tr>';
        return;
    }

    // Load existing attendance for the date
    let existingAttendance = {};
    try {
        const records = await apiCall(`/admin/attendance?date=${dateInput.value}`);
        records.forEach(r => {
            existingAttendance[r.student_id] = r;
        });
    } catch (error) {
        console.error('Failed to load attendance:', error);
    }

    tbody.innerHTML = students.map(student => {
        const existing = existingAttendance[student.id];
        const status = existing?.status || '';
        const notes = existing?.notes || '';

        return `
            <tr data-student-id="${student.id}">
                <td class="px-4 py-3">
                    <div class="font-medium text-gray-800">${student.name}</div>
                    <div class="text-xs text-gray-500">${student.email}</div>
                </td>
                <td class="px-4 py-3 text-center">
                    <input type="radio" name="status-${student.id}" value="present" ${status === 'present' ? 'checked' : ''}
                           class="w-4 h-4 text-green-600 focus:ring-green-500">
                </td>
                <td class="px-4 py-3 text-center">
                    <input type="radio" name="status-${student.id}" value="absent" ${status === 'absent' ? 'checked' : ''}
                           class="w-4 h-4 text-red-600 focus:ring-red-500">
                </td>
                <td class="px-4 py-3 text-center">
                    <input type="radio" name="status-${student.id}" value="late" ${status === 'late' ? 'checked' : ''}
                           class="w-4 h-4 text-yellow-600 focus:ring-yellow-500">
                </td>
                <td class="px-4 py-3">
                    <input type="text" value="${notes}" placeholder="Optional notes"
                           class="notes-input w-full px-2 py-1 text-sm border border-gray-200 rounded focus:ring-1 focus:ring-primary focus:border-transparent outline-none">
                </td>
            </tr>
        `;
    }).join('');
}

function loadAttendanceForDate() {
    loadAttendanceSheet();
}

async function submitAttendance() {
    const date = document.getElementById('attendance-date').value;
    const records = [];

    document.querySelectorAll('#attendance-table tr[data-student-id]').forEach(row => {
        const studentId = parseInt(row.dataset.studentId);
        const statusInput = row.querySelector(`input[name="status-${studentId}"]:checked`);
        const notesInput = row.querySelector('.notes-input');

        if (statusInput) {
            records.push({
                student_id: studentId,
                status: statusInput.value,
                notes: notesInput?.value || null
            });
        }
    });

    if (records.length === 0) {
        alert('Please select attendance status for at least one student.');
        return;
    }

    try {
        await apiCall('/admin/attendance', {
            method: 'POST',
            body: JSON.stringify({ date, records })
        });

        const successEl = document.getElementById('attendance-success');
        successEl.classList.remove('hidden');
        setTimeout(() => successEl.classList.add('hidden'), 3000);
    } catch (error) {
        alert('Failed to save attendance: ' + error.message);
    }
}

// Participation
async function loadParticipation() {
    const filter = document.getElementById('participation-filter').value;
    const container = document.getElementById('participation-list');

    try {
        const url = filter ? `/admin/participation?status_filter=${filter}` : '/admin/participation';
        const participations = await apiCall(url);

        if (participations.length === 0) {
            container.innerHTML = '<p class="text-center text-gray-500 py-4">No submissions found</p>';
            return;
        }

        container.innerHTML = participations.map(p => {
            const statusColors = {
                pending: 'bg-yellow-100 text-yellow-800',
                approved: 'bg-green-100 text-green-800',
                rejected: 'bg-red-100 text-red-800'
            };
            const statusColor = statusColors[p.approved] || 'bg-gray-100 text-gray-800';

            return `
                <div class="border border-gray-200 rounded-lg p-4" data-participation-id="${p.id}">
                    <div class="flex flex-col sm:flex-row justify-between gap-3">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="font-medium text-gray-800">${p.student_name}</span>
                                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColor}">
                                    ${p.approved}
                                </span>
                            </div>
                            <p class="text-gray-600 text-sm">${p.description}</p>
                            <p class="text-gray-400 text-xs mt-1">${formatDate(p.date)}</p>
                        </div>
                        <div class="flex items-center gap-2">
                            <input type="number" min="1" max="5" value="${p.points}"
                                   class="points-input w-16 px-2 py-1 text-sm border border-gray-200 rounded focus:ring-1 focus:ring-primary outline-none">
                            <span class="text-sm text-gray-500">pts</span>
                            ${p.approved === 'pending' ? `
                                <button onclick="updateParticipation(${p.id}, 'approved')"
                                        class="px-3 py-1 text-sm bg-green-100 text-green-700 rounded hover:bg-green-200">
                                    Approve
                                </button>
                                <button onclick="updateParticipation(${p.id}, 'rejected')"
                                        class="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200">
                                    Reject
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = `<p class="text-center text-red-500 py-4">Failed to load: ${error.message}</p>`;
    }
}

async function updateParticipation(id, status) {
    const container = document.querySelector(`[data-participation-id="${id}"]`);
    const pointsInput = container?.querySelector('.points-input');
    const points = pointsInput ? parseInt(pointsInput.value) : null;

    try {
        await apiCall(`/admin/participation/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ approved: status, points })
        });
        loadParticipation();
    } catch (error) {
        alert('Failed to update: ' + error.message);
    }
}

// Grades
document.getElementById('grade-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const studentId = parseInt(document.getElementById('grade-student').value);
    const category = document.getElementById('grade-category').value;
    const score = parseFloat(document.getElementById('grade-score').value);
    const maxScore = parseFloat(document.getElementById('grade-max').value);
    const date = document.getElementById('grade-date').value || null;

    try {
        await apiCall('/admin/grades', {
            method: 'POST',
            body: JSON.stringify({
                student_id: studentId,
                category,
                score,
                max_score: maxScore,
                date
            })
        });

        const successEl = document.getElementById('grade-success');
        successEl.classList.remove('hidden');
        setTimeout(() => successEl.classList.add('hidden'), 3000);

        // Reset form
        document.getElementById('grade-score').value = '';
        document.getElementById('grade-date').value = '';
    } catch (error) {
        alert('Failed to add grade: ' + error.message);
    }
});

// Helpers
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// Initialize
async function init() {
    try {
        const config = await fetch('/api/config').then(r => r.json());
        googleClientId = config.google_client_id;
    } catch (error) {
        console.error('Failed to fetch config:', error);
    }

    if (authToken) {
        try {
            const result = await apiCall('/students/me');
            if (result.role !== 'teacher') {
                logout();
                return;
            }
            currentTeacher = result;
            showAdmin();
            loadInitialData();
        } catch (error) {
            logout();
        }
    } else {
        showLogin();
        if (typeof google !== 'undefined') {
            initGoogleSignIn();
        } else {
            window.addEventListener('load', () => setTimeout(initGoogleSignIn, 100));
        }
    }
}

init();
