// Estado
let authToken = localStorage.getItem('authToken');
let currentTeacher = null;
let googleClientId = null;
let classes = [];
let students = [];

// Helpers de API
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
        const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
        throw new Error(error.detail || `Error de API: ${response.status}`);
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

        if (result.student.role !== 'teacher') {
            errorEl.textContent = 'Acceso denegado. Se requiere cuenta de profesor.';
            errorEl.classList.remove('hidden');
            return;
        }

        authToken = result.token;
        currentTeacher = result.student;
        localStorage.setItem('authToken', authToken);
        showAdmin();
        loadInitialData();
    } catch (error) {
        console.error('Error de autenticacion:', error);
        errorEl.textContent = error.message || 'Error de autenticacion. Por favor intenta de nuevo.';
        errorEl.classList.remove('hidden');
    }
}

function initGoogleSignIn() {
    if (!googleClientId) {
        const errorEl = document.getElementById('login-error');
        errorEl.textContent = 'Google Sign-In no configurado. Por favor configura GOOGLE_CLIENT_ID.';
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
        console.error('Error al cerrar sesion:', error);
    }

    authToken = null;
    currentTeacher = null;
    localStorage.removeItem('authToken');
    showLogin();
    if (googleClientId) initGoogleSignIn();
}

// Funciones de UI
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
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('border-primary', 'text-primary');
        btn.classList.add('border-transparent', 'text-gray-500');
    });
    document.getElementById(`tab-${tabName}`).classList.add('border-primary', 'text-primary');
    document.getElementById(`tab-${tabName}`).classList.remove('border-transparent', 'text-gray-500');

    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.add('hidden'));
    document.getElementById(`panel-${tabName}`).classList.remove('hidden');

    if (tabName === 'classes') loadClasses();
    if (tabName === 'attendance') {
        populateClassSelectors();
        loadAttendanceSheet();
    }
    if (tabName === 'participation') {
        populateClassSelectors();
    }
    if (tabName === 'grades') {
        populateClassSelectors();
    }
}

// Carga de datos
async function loadInitialData() {
    await loadClasses();
}

// Classes
async function loadClasses() {
    try {
        classes = await apiCall('/classes/teaching');
        renderClasses();
        populateClassSelectors();
    } catch (error) {
        console.error('Error al cargar clases:', error);
        document.getElementById('classes-list').innerHTML =
            '<p class="text-center text-red-500 py-4">Error al cargar clases</p>';
    }
}

function renderClasses() {
    const container = document.getElementById('classes-list');

    if (classes.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8">
                <p class="text-gray-500 mb-4">No tienes clases creadas aun</p>
                <button onclick="openCreateClassModal()"
                        class="text-primary hover:text-indigo-700 font-medium">
                    Crear tu primera clase
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = classes.map(c => `
        <div class="border border-gray-200 rounded-lg p-4 hover:shadow-md transition">
            <div class="flex flex-col sm:flex-row justify-between gap-3">
                <div>
                    <h3 class="font-semibold text-gray-800">${c.name}</h3>
                    <div class="flex items-center gap-2 mt-1">
                        <code class="bg-gray-100 px-2 py-0.5 rounded text-sm font-mono">${c.code}</code>
                        <button onclick="copyCode('${c.code}')" class="text-gray-400 hover:text-gray-600" title="Copiar codigo">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                            </svg>
                        </button>
                    </div>
                    <p class="text-sm text-gray-500 mt-1">${c.student_count} estudiante(s) inscrito(s)</p>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="viewClassStudents(${c.id})"
                            class="px-3 py-1.5 text-sm border border-gray-300 text-gray-600 rounded hover:bg-gray-50">
                        Ver Estudiantes
                    </button>
                    <button onclick="deleteClass(${c.id})"
                            class="px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded hover:bg-red-50">
                        Eliminar
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

function copyCode(code) {
    navigator.clipboard.writeText(code).then(() => {
        alert('Codigo copiado: ' + code);
    });
}

async function viewClassStudents(classId) {
    try {
        const classData = await apiCall(`/classes/teaching/${classId}`);
        const studentsHtml = classData.students.length === 0
            ? '<p class="text-gray-500">No hay estudiantes inscritos</p>'
            : classData.students.map(s => `<li class="py-1">${s.name} (${s.email})</li>`).join('');

        alert(`Estudiantes en ${classData.name}:\n${classData.students.map(s => s.name).join('\n') || 'Ninguno'}`);
    } catch (error) {
        alert('Error al cargar estudiantes: ' + error.message);
    }
}

async function deleteClass(classId) {
    if (!confirm('¿Estas seguro de eliminar esta clase? Esta accion no se puede deshacer.')) {
        return;
    }

    try {
        await apiCall(`/classes/teaching/${classId}`, { method: 'DELETE' });
        await loadClasses();
    } catch (error) {
        alert('Error al eliminar clase: ' + error.message);
    }
}

function openCreateClassModal() {
    document.getElementById('create-class-modal').classList.remove('hidden');
}

function closeCreateClassModal() {
    document.getElementById('create-class-modal').classList.add('hidden');
    document.getElementById('class-name').value = '';
    document.getElementById('class-prefix').value = '';
}

document.getElementById('create-class-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const name = document.getElementById('class-name').value;
    const codePrefix = document.getElementById('class-prefix').value || null;

    try {
        await apiCall('/classes/', {
            method: 'POST',
            body: JSON.stringify({ name, code_prefix: codePrefix })
        });

        closeCreateClassModal();
        await loadClasses();
    } catch (error) {
        alert('Error al crear clase: ' + error.message);
    }
});

function populateClassSelectors() {
    const selectors = [
        'attendance-class-select',
        'participation-class-select',
        'grade-class'
    ];

    selectors.forEach(id => {
        const select = document.getElementById(id);
        if (select) {
            const currentValue = select.value;
            select.innerHTML = '<option value="">Selecciona una clase...</option>' +
                classes.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
            if (currentValue && classes.find(c => c.id == currentValue)) {
                select.value = currentValue;
            }
        }
    });
}

// Asistencia
async function loadAttendanceSheet() {
    const classId = document.getElementById('attendance-class-select').value;
    const dateInput = document.getElementById('attendance-date');
    const tbody = document.getElementById('attendance-table');

    if (!classId) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-4 text-center text-gray-500">Selecciona una clase</td></tr>';
        return;
    }

    if (!dateInput.value) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }

    try {
        // Load students for this class
        students = await apiCall(`/admin/students?class_id=${classId}`);
    } catch (error) {
        console.error('Error al cargar estudiantes:', error);
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-4 text-center text-red-500">Error al cargar estudiantes</td></tr>';
        return;
    }

    if (students.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-4 text-center text-gray-500">No hay estudiantes en esta clase</td></tr>';
        return;
    }

    let existingAttendance = {};
    try {
        const records = await apiCall(`/admin/attendance?class_id=${classId}&date=${dateInput.value}`);
        records.forEach(r => {
            existingAttendance[r.student_id] = r;
        });
    } catch (error) {
        console.error('Error al cargar asistencia:', error);
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
                    <input type="text" value="${notes}" placeholder="Notas opcionales"
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
    const classId = document.getElementById('attendance-class-select').value;
    if (!classId) {
        alert('Por favor selecciona una clase primero.');
        return;
    }

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
        alert('Por favor selecciona el estado de asistencia para al menos un estudiante.');
        return;
    }

    try {
        await apiCall('/admin/attendance', {
            method: 'POST',
            body: JSON.stringify({ date, class_id: parseInt(classId), records })
        });

        const successEl = document.getElementById('attendance-success');
        successEl.classList.remove('hidden');
        setTimeout(() => successEl.classList.add('hidden'), 3000);
    } catch (error) {
        alert('Error al guardar asistencia: ' + error.message);
    }
}

// Participacion
async function loadParticipation() {
    const classId = document.getElementById('participation-class-select').value;
    const filter = document.getElementById('participation-filter').value;
    const container = document.getElementById('participation-list');

    if (!classId) {
        container.innerHTML = '<p class="text-center text-gray-500 py-4">Selecciona una clase</p>';
        return;
    }

    try {
        let url = `/admin/participation?class_id=${classId}`;
        if (filter) url += `&status_filter=${filter}`;
        const participations = await apiCall(url);

        if (participations.length === 0) {
            container.innerHTML = '<p class="text-center text-gray-500 py-4">No se encontraron registros</p>';
            return;
        }

        const statusNames = {
            pending: 'Pendiente',
            approved: 'Aprobado',
            rejected: 'Rechazado'
        };

        const statusColors = {
            pending: 'bg-yellow-100 text-yellow-800',
            approved: 'bg-green-100 text-green-800',
            rejected: 'bg-red-100 text-red-800'
        };

        container.innerHTML = participations.map(p => {
            const statusColor = statusColors[p.approved] || 'bg-gray-100 text-gray-800';
            const statusName = statusNames[p.approved] || p.approved;

            return `
                <div class="border border-gray-200 rounded-lg p-4" data-participation-id="${p.id}">
                    <div class="flex flex-col sm:flex-row justify-between gap-3">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="font-medium text-gray-800">${p.student_name}</span>
                                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColor}">
                                    ${statusName}
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
                                    Aprobar
                                </button>
                                <button onclick="updateParticipation(${p.id}, 'rejected')"
                                        class="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200">
                                    Rechazar
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = `<p class="text-center text-red-500 py-4">Error al cargar: ${error.message}</p>`;
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
        alert('Error al actualizar: ' + error.message);
    }
}

// Calificaciones
async function loadStudentsForClass() {
    const classId = document.getElementById('grade-class').value;
    const studentSelect = document.getElementById('grade-student');

    if (!classId) {
        studentSelect.innerHTML = '<option value="">Selecciona un estudiante...</option>';
        return;
    }

    try {
        const classStudents = await apiCall(`/admin/students?class_id=${classId}`);
        studentSelect.innerHTML = '<option value="">Selecciona un estudiante...</option>' +
            classStudents.map(s => `<option value="${s.id}">${s.name} (${s.email})</option>`).join('');
    } catch (error) {
        console.error('Error al cargar estudiantes:', error);
    }
}

document.getElementById('grade-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const classId = parseInt(document.getElementById('grade-class').value);
    const studentId = parseInt(document.getElementById('grade-student').value);
    const category = document.getElementById('grade-category').value;
    const score = parseFloat(document.getElementById('grade-score').value);
    const maxScore = parseFloat(document.getElementById('grade-max').value);
    const date = document.getElementById('grade-date').value || null;

    if (!classId) {
        alert('Por favor selecciona una clase.');
        return;
    }

    try {
        await apiCall('/admin/grades', {
            method: 'POST',
            body: JSON.stringify({
                student_id: studentId,
                class_id: classId,
                category,
                score,
                max_score: maxScore,
                date
            })
        });

        const successEl = document.getElementById('grade-success');
        successEl.classList.remove('hidden');
        setTimeout(() => successEl.classList.add('hidden'), 3000);

        document.getElementById('grade-score').value = '';
        document.getElementById('grade-date').value = '';
    } catch (error) {
        alert('Error al agregar calificacion: ' + error.message);
    }
});

// Helpers
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' });
}

// Inicializacion
async function init() {
    try {
        const config = await fetch('/api/config').then(r => r.json());
        googleClientId = config.google_client_id;
    } catch (error) {
        console.error('Error al obtener configuracion:', error);
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
