// Estado
let authToken = localStorage.getItem('authToken');
let currentTeacher = null;
let classId = null;
let dashboardData = null;
let studentsData = [];
let categories = [];

// Extraer classId de la URL
const pathParts = window.location.pathname.split('/');
classId = parseInt(pathParts[pathParts.length - 1]);

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

    console.log(`API Call: ${options.method || 'GET'} ${endpoint}`, options.body ? JSON.parse(options.body) : '');

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
        console.error(`API Error ${response.status}:`, error);

        if (response.status === 401) {
            alert('Tu sesion ha expirado. Por favor inicia sesion de nuevo.');
            logout();
        }

        // Handle different error formats from FastAPI
        let errorMessage = `Error de API: ${response.status}`;
        if (error.detail) {
            if (typeof error.detail === 'string') {
                errorMessage = error.detail;
            } else if (Array.isArray(error.detail)) {
                // Pydantic validation errors
                errorMessage = error.detail.map(e => `${e.loc?.join('.')}: ${e.msg}`).join(', ');
            } else if (typeof error.detail === 'object') {
                errorMessage = JSON.stringify(error.detail);
            }
        }
        console.error('Parsed error message:', errorMessage);

        throw new Error(errorMessage);
    }

    return response.json();
}

function logout() {
    authToken = null;
    currentTeacher = null;
    localStorage.removeItem('authToken');
    window.location.href = '/admin';
}

// UI Functions
function showSection(sectionId) {
    ['loading-section', 'login-section', 'dashboard-section'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
    });
    document.getElementById(sectionId).classList.remove('hidden');
}

function showTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('tab-active');
        btn.classList.add('border-transparent', 'text-gray-500');
    });
    const activeTab = document.getElementById(`tab-${tabName}`);
    activeTab.classList.add('tab-active');
    activeTab.classList.remove('border-transparent', 'text-gray-500');

    // Update tab panels
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.add('hidden'));
    document.getElementById(`panel-${tabName}`).classList.remove('hidden');

    // Load tab-specific data
    if (tabName === 'attendance') {
        initAttendanceTab();
    } else if (tabName === 'grades') {
        initGradesTab();
    } else if (tabName === 'participation') {
        loadParticipation();
    }
}

// Data Loading
async function loadDashboard() {
    try {
        // Get sort/filter values
        const sortSelect = document.getElementById('sort-select');
        const statusSelect = document.getElementById('status-select');
        const searchInput = document.getElementById('search-input');

        let sortBy = 'name';
        let sortOrder = 'asc';

        if (sortSelect?.value) {
            const [field, order] = sortSelect.value.split('-');
            sortBy = field;
            sortOrder = order;
        }

        let url = `/admin/classes/${classId}/dashboard?sort_by=${sortBy}&sort_order=${sortOrder}`;

        if (searchInput?.value) {
            url += `&search=${encodeURIComponent(searchInput.value)}`;
        }

        if (statusSelect?.value && statusSelect.value !== 'all') {
            url += `&status_filter=${statusSelect.value}`;
        }

        console.log('Dashboard URL:', url);
        dashboardData = await apiCall(url);
        studentsData = dashboardData.students;
        categories = dashboardData.stats.categories;

        updateDashboardUI();
    } catch (error) {
        console.error('Dashboard load error:', error);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);

        // Show error inline instead of just an alert
        const statsSection = document.querySelector('.grid.grid-cols-2');
        if (statsSection) {
            statsSection.insertAdjacentHTML('beforebegin',
                `<div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
                    <strong>Error al cargar dashboard:</strong> ${error.message}
                </div>`
            );
        }
        alert('Error al cargar el dashboard: ' + error.message);
    }
}

function updateDashboardUI() {
    const stats = dashboardData.stats;

    // Update header
    document.getElementById('class-name').textContent = stats.class_name;
    document.getElementById('class-code').textContent = `Codigo: ${stats.class_code}`;

    // Update stats cards
    document.getElementById('stat-students').textContent = stats.total_students;
    document.getElementById('stat-attendance').textContent = `${stats.overall_attendance_rate.toFixed(0)}%`;
    document.getElementById('stat-grade').textContent = stats.average_grade.toFixed(1);
    document.getElementById('stat-at-risk').textContent = stats.students_at_risk;
    document.getElementById('stat-top').textContent = stats.top_performers;
    document.getElementById('stat-pending').textContent = stats.pending_participation;

    // Update pending count in overview
    document.getElementById('pending-count').textContent = `${stats.pending_participation} pendientes`;

    // Update overview tab
    renderStudentsAtRisk();
    renderRecentActivity();
    renderCategoriesOverview();

    // Update roster tab
    renderRosterTable();
}

function renderStudentsAtRisk() {
    const container = document.getElementById('at-risk-list');
    const atRisk = studentsData.filter(s => s.status === 'at_risk').slice(0, 5);

    if (atRisk.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm">No hay estudiantes en riesgo</p>';
        return;
    }

    container.innerHTML = atRisk.map(s => `
        <div class="flex items-center justify-between p-2 bg-red-50 rounded-lg">
            <div>
                <div class="font-medium text-gray-800 text-sm">${s.name}</div>
                <div class="text-xs text-gray-500">
                    Asistencia: ${s.attendance_rate.toFixed(0)}% | Calificacion: ${s.final_grade.toFixed(1)}
                </div>
            </div>
            <button onclick="openStudentModal(${s.id})" class="text-primary text-xs hover:underline">Ver</button>
        </div>
    `).join('');
}

function renderRecentActivity() {
    const container = document.getElementById('recent-activity');
    const activity = dashboardData.recent_activity.slice(0, 5);

    if (activity.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm">No hay actividad reciente</p>';
        return;
    }

    const icons = {
        attendance: '📋',
        participation: '🙋',
        grade: '📝'
    };

    const statusColors = {
        pending: 'bg-yellow-100 text-yellow-800',
        approved: 'bg-green-100 text-green-800',
        rejected: 'bg-red-100 text-red-800',
        present: 'bg-green-100 text-green-800',
        absent: 'bg-red-100 text-red-800',
        late: 'bg-yellow-100 text-yellow-800'
    };

    container.innerHTML = activity.map(a => `
        <div class="flex items-start gap-3 p-2 bg-gray-50 rounded-lg">
            <span class="text-lg">${icons[a.type] || '📌'}</span>
            <div class="flex-1 min-w-0">
                <div class="font-medium text-gray-800 text-sm truncate">${a.student_name}</div>
                <div class="text-xs text-gray-500 truncate">${a.detail}</div>
                <div class="text-xs text-gray-400">${formatDate(a.date)}</div>
            </div>
            ${a.status ? `<span class="text-xs px-2 py-0.5 rounded ${statusColors[a.status] || 'bg-gray-100'}">${a.status}</span>` : ''}
        </div>
    `).join('');
}

function renderCategoriesOverview() {
    const container = document.getElementById('categories-overview');

    if (categories.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm col-span-4">No hay categorias configuradas. <a href="#" onclick="showTab(\'grades\')" class="text-primary hover:underline">Agregar categorias</a></p>';
        return;
    }

    const totalWeight = categories.reduce((sum, c) => sum + c.weight, 0);
    const weightWarning = Math.abs(totalWeight - 1) > 0.001;

    container.innerHTML = categories.map(c => `
        <div class="bg-gray-50 rounded-lg p-3">
            <div class="font-medium text-gray-800">${c.name}</div>
            <div class="text-2xl font-bold text-primary">${(c.weight * 100).toFixed(0)}%</div>
        </div>
    `).join('') + (weightWarning ? `
        <div class="col-span-full bg-yellow-50 text-yellow-800 text-sm p-3 rounded-lg">
            Los pesos suman ${(totalWeight * 100).toFixed(0)}%. Deben sumar 100%.
        </div>
    ` : '');
}

function renderRosterTable() {
    const tbody = document.getElementById('roster-table');

    if (studentsData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-gray-500">No se encontraron estudiantes</td></tr>';
        return;
    }

    tbody.innerHTML = studentsData.map(s => {
        const statusClasses = {
            good: 'status-good',
            warning: 'status-warning',
            at_risk: 'status-at_risk'
        };
        const statusLabels = {
            good: 'Bien',
            warning: 'Advertencia',
            at_risk: 'En riesgo'
        };

        return `
            <tr class="hover:bg-gray-50">
                <td class="px-4 py-3">
                    <div class="font-medium text-gray-800">${s.name}</div>
                    <div class="text-xs text-gray-500">${s.email}</div>
                </td>
                <td class="px-4 py-3 text-center">
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusClasses[s.status]}">
                        ${statusLabels[s.status]}
                    </span>
                </td>
                <td class="px-4 py-3 text-center">
                    <span class="${s.attendance_rate >= 80 ? 'text-green-600' : s.attendance_rate >= 60 ? 'text-yellow-600' : 'text-red-600'} font-medium">
                        ${s.attendance_rate.toFixed(0)}%
                    </span>
                    <div class="text-xs text-gray-400">${s.attendance_present}/${s.attendance_total}</div>
                </td>
                <td class="px-4 py-3 text-center">
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                        ${s.participation_points} pts
                    </span>
                    ${s.participation_pending > 0 ? `<div class="text-xs text-yellow-600">${s.participation_pending} pendiente(s)</div>` : ''}
                </td>
                <td class="px-4 py-3 text-center">
                    <span class="text-lg font-bold ${s.final_grade >= 70 ? 'text-green-600' : s.final_grade >= 60 ? 'text-yellow-600' : 'text-red-600'}">
                        ${s.final_grade.toFixed(1)}
                    </span>
                </td>
                <td class="px-4 py-3 text-center text-sm text-gray-500">
                    ${s.last_activity ? formatDate(s.last_activity.split('T')[0]) : '-'}
                </td>
                <td class="px-4 py-3 text-center">
                    <button onclick="openStudentModal(${s.id})" class="text-primary hover:text-indigo-700 text-sm font-medium">
                        Ver detalle
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function applyFilters() {
    loadDashboard();
}

// ==================== Attendance Tab ====================

function initAttendanceTab() {
    const dateInput = document.getElementById('attendance-date');
    if (!dateInput.value) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }
    loadAttendanceForDate();
}

async function loadAttendanceForDate() {
    const dateInput = document.getElementById('attendance-date');
    const tbody = document.getElementById('attendance-table');

    if (!dateInput.value) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }

    tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-4 text-center text-gray-500">Cargando...</td></tr>';

    try {
        // Get students for class
        const students = await apiCall(`/admin/students?class_id=${classId}`);

        if (students.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-4 text-center text-gray-500">No hay estudiantes en esta clase</td></tr>';
            return;
        }

        // Get existing attendance for this date
        let existingAttendance = {};
        try {
            const records = await apiCall(`/admin/attendance?class_id=${classId}&date=${dateInput.value}`);
            records.forEach(r => {
                existingAttendance[r.student_id] = r;
            });
        } catch (error) {
            console.error('Error loading existing attendance:', error);
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
    } catch (error) {
        console.error('Error loading attendance:', error);
        tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-4 text-center text-red-500">Error: ${error.message}</td></tr>`;
    }
}

async function saveAttendance() {
    const date = document.getElementById('attendance-date').value;

    if (!date) {
        alert('Por favor selecciona una fecha.');
        return;
    }

    if (!classId || isNaN(classId)) {
        alert('Error: ID de clase no valido. Recarga la pagina.');
        console.error('Invalid classId:', classId);
        return;
    }

    const records = [];

    document.querySelectorAll('#attendance-table tr[data-student-id]').forEach(row => {
        const studentId = parseInt(row.dataset.studentId);
        const statusInput = row.querySelector(`input[name="status-${studentId}"]:checked`);
        const notesInput = row.querySelector('.notes-input');

        if (statusInput && !isNaN(studentId)) {
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

    const payload = {
        date: date,  // Ensure it's a string in YYYY-MM-DD format
        class_id: parseInt(classId),  // Ensure it's an integer
        records: records
    };
    console.log('Saving attendance payload:', JSON.stringify(payload, null, 2));

    try {
        const result = await apiCall('/admin/attendance', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        console.log('Attendance save result:', result);

        const successEl = document.getElementById('attendance-success');
        successEl.classList.remove('hidden');
        setTimeout(() => successEl.classList.add('hidden'), 3000);

        // Refresh dashboard data
        loadDashboard();
    } catch (error) {
        console.error('Attendance save error:', error);
        alert('Error al guardar asistencia: ' + error.message);
    }
}

// ==================== Grades Tab ====================

function initGradesTab() {
    populateStudentSelect();
    populateCategorySelect();
    renderGradeCategoriesList();
}

async function populateStudentSelect() {
    const select = document.getElementById('grade-student');

    try {
        const students = await apiCall(`/admin/students?class_id=${classId}`);
        select.innerHTML = '<option value="">Selecciona un estudiante...</option>' +
            students.map(s => `<option value="${s.id}">${s.name} (${s.email})</option>`).join('');
    } catch (error) {
        console.error('Error loading students:', error);
    }
}

function populateCategorySelect() {
    const select = document.getElementById('grade-category');

    if (categories.length === 0) {
        select.innerHTML = '<option value="">No hay categorias - crea una primero</option>';
        return;
    }

    select.innerHTML = '<option value="">Selecciona una categoria...</option>' +
        categories.map(c => `<option value="${c.id}">${c.name} (${(c.weight * 100).toFixed(0)}%)</option>`).join('');
}

function renderGradeCategoriesList() {
    const container = document.getElementById('grade-categories-list');

    if (categories.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-sm">No hay categorias configuradas</p>';
        return;
    }

    const totalWeight = categories.reduce((sum, c) => sum + c.weight, 0);

    container.innerHTML = categories.map(cat => `
        <div class="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
            <div class="flex items-center gap-3">
                <span class="font-medium text-gray-800">${cat.name}</span>
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800">
                    ${(cat.weight * 100).toFixed(0)}%
                </span>
            </div>
            <div class="flex items-center gap-2">
                <button onclick="editCategory(${cat.id}, '${cat.name}', ${cat.weight})"
                        class="text-gray-400 hover:text-gray-600" title="Editar">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path>
                    </svg>
                </button>
                <button onclick="deleteCategory(${cat.id})"
                        class="text-red-400 hover:text-red-600" title="Eliminar">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                </button>
            </div>
        </div>
    `).join('') + (Math.abs(totalWeight - 1) > 0.001 ? `
        <p class="text-yellow-600 text-sm mt-2">
            Los pesos suman ${(totalWeight * 100).toFixed(0)}%. Deben sumar 100% para calcular correctamente.
        </p>
    ` : '');
}

document.getElementById('grade-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const studentId = parseInt(document.getElementById('grade-student').value);
    const categorySelect = document.getElementById('grade-category');
    const category = categorySelect ? categorySelect.value : null;
    const score = parseFloat(document.getElementById('grade-score').value);
    const maxScore = parseFloat(document.getElementById('grade-max').value);

    if (!studentId) {
        alert('Por favor selecciona un estudiante.');
        return;
    }

    try {
        await apiCall('/admin/grades', {
            method: 'POST',
            body: JSON.stringify({
                student_id: studentId,
                class_id: classId,
                category: category || null,
                score,
                max_score: maxScore
            })
        });

        const successEl = document.getElementById('grade-success');
        successEl.classList.remove('hidden');
        setTimeout(() => successEl.classList.add('hidden'), 3000);

        // Reset form
        document.getElementById('grade-score').value = '';

        // Refresh dashboard
        loadDashboard();
    } catch (error) {
        alert('Error al agregar calificacion: ' + error.message);
    }
});

async function addCategory() {
    const name = document.getElementById('new-category-name').value.trim();
    const weightPercent = parseFloat(document.getElementById('new-category-weight').value);

    if (!name || !weightPercent) {
        alert('Por favor ingresa nombre y peso de la categoria.');
        return;
    }

    try {
        await apiCall(`/admin/categories/${classId}`, {
            method: 'POST',
            body: JSON.stringify({
                name,
                weight: weightPercent / 100
            })
        });

        document.getElementById('new-category-name').value = '';
        document.getElementById('new-category-weight').value = '';

        // Reload dashboard to get updated categories
        await loadDashboard();
        initGradesTab();
    } catch (error) {
        alert('Error al agregar categoria: ' + error.message);
    }
}

async function editCategory(categoryId, currentName, currentWeight) {
    const newName = prompt('Nombre de la categoria:', currentName);
    if (newName === null) return;

    const newWeightPercent = prompt('Peso (%):', (currentWeight * 100).toFixed(0));
    if (newWeightPercent === null) return;

    try {
        await apiCall(`/admin/categories/${classId}/${categoryId}`, {
            method: 'PUT',
            body: JSON.stringify({
                name: newName,
                weight: parseFloat(newWeightPercent) / 100
            })
        });

        await loadDashboard();
        initGradesTab();
    } catch (error) {
        alert('Error al actualizar: ' + error.message);
    }
}

async function deleteCategory(categoryId) {
    if (!confirm('¿Estas seguro de eliminar esta categoria? Las calificaciones asociadas perderan su categoria.')) {
        return;
    }

    try {
        await apiCall(`/admin/categories/${classId}/${categoryId}`, {
            method: 'DELETE'
        });

        await loadDashboard();
        initGradesTab();
    } catch (error) {
        alert('Error al eliminar: ' + error.message);
    }
}

// ==================== Participation Tab ====================

async function loadParticipation() {
    const filter = document.getElementById('participation-filter').value;
    const container = document.getElementById('participation-list');

    container.innerHTML = '<p class="text-center text-gray-500 py-4">Cargando...</p>';

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
        loadDashboard();
    } catch (error) {
        alert('Error al actualizar: ' + error.message);
    }
}

// ==================== Student Modal ====================

async function openStudentModal(studentId) {
    const modal = document.getElementById('student-modal');
    const nameEl = document.getElementById('modal-student-name');
    const emailEl = document.getElementById('modal-student-email');
    const contentEl = document.getElementById('modal-content');

    modal.classList.remove('hidden');
    contentEl.innerHTML = '<p class="text-center text-gray-500">Cargando...</p>';

    try {
        const roster = await apiCall(`/admin/roster/${classId}`);
        const student = roster.find(r => r.student.id === studentId);

        if (!student) {
            contentEl.innerHTML = '<p class="text-center text-red-500">Estudiante no encontrado</p>';
            return;
        }

        nameEl.textContent = student.student.name;
        emailEl.textContent = student.student.email;

        const specialTotal = student.special_points
            .filter(sp => sp.opted_in && sp.awarded)
            .reduce((sum, sp) => sum + sp.points_value, 0);

        contentEl.innerHTML = `
            <!-- Summary -->
            <div class="grid grid-cols-3 gap-4 text-center">
                <div class="bg-gray-50 rounded-lg p-3">
                    <div class="text-2xl font-bold ${student.final_grade >= 70 ? 'text-green-600' : 'text-red-600'}">${student.final_grade.toFixed(1)}</div>
                    <div class="text-xs text-gray-500">Calificacion Final</div>
                </div>
                <div class="bg-gray-50 rounded-lg p-3">
                    <div class="text-2xl font-bold text-blue-600">${student.participation_points}</div>
                    <div class="text-xs text-gray-500">Puntos Participacion</div>
                </div>
                <div class="bg-gray-50 rounded-lg p-3">
                    <div class="text-2xl font-bold text-purple-600">${student.attendance_rate.toFixed(0)}%</div>
                    <div class="text-xs text-gray-500">Asistencia</div>
                </div>
            </div>

            <!-- Grade Breakdown -->
            <div>
                <h3 class="text-sm font-medium text-gray-700 mb-2">Desglose de Calificaciones</h3>
                <div class="space-y-2">
                    ${student.grade_breakdown.map(cat => `
                        <div class="flex justify-between items-center p-2 bg-gray-50 rounded">
                            <span class="text-sm">${cat.category_name} (${(cat.weight * 100).toFixed(0)}%)</span>
                            <span class="text-sm font-medium">${cat.average.toFixed(1)}% → ${cat.weighted_contribution.toFixed(1)} pts</span>
                        </div>
                    `).join('') || '<p class="text-sm text-gray-500">No hay calificaciones</p>'}
                </div>
            </div>

            <!-- Participation -->
            <div>
                <h3 class="text-sm font-medium text-gray-700 mb-2">Participacion</h3>
                <div class="flex justify-between items-center p-2 bg-gray-50 rounded">
                    <span class="text-sm">Puntos aprobados</span>
                    <span class="text-sm font-medium">${student.participation_points} pts × 0.1 = ${(student.participation_points * 0.1).toFixed(1)} pts</span>
                </div>
            </div>

            <!-- Special Points -->
            <div>
                <h3 class="text-sm font-medium text-gray-700 mb-2">Puntos Especiales (+${specialTotal.toFixed(1)})</h3>
                <div class="space-y-2">
                    ${renderSpecialPointsEditor(studentId, student.special_points)}
                </div>
            </div>
        `;
    } catch (error) {
        contentEl.innerHTML = `<p class="text-center text-red-500">Error: ${error.message}</p>`;
    }
}

function renderSpecialPointsEditor(studentId, specialPoints) {
    const englishSp = specialPoints.find(sp => sp.category === 'english');
    const notebookSp = specialPoints.find(sp => sp.category === 'notebook');

    const renderRow = (label, category, sp) => {
        const optedIn = sp?.opted_in || false;
        const awarded = sp?.awarded || false;
        const pointsValue = sp?.points_value || 0.5;

        return `
            <div class="flex justify-between items-center p-2 bg-gray-50 rounded">
                <div>
                    <span class="text-sm font-medium">${label}</span>
                    <span class="text-xs text-gray-500 ml-2">(+${pointsValue} pts)</span>
                </div>
                <div class="flex items-center gap-3">
                    <label class="flex items-center gap-1 text-xs">
                        <input type="checkbox" ${optedIn ? 'checked' : ''}
                               onchange="updateSpecialPoint(${studentId}, '${category}', 'opted_in', this.checked)"
                               class="rounded border-gray-300 text-primary focus:ring-primary">
                        Inscrito
                    </label>
                    <label class="flex items-center gap-1 text-xs">
                        <input type="checkbox" ${awarded ? 'checked' : ''} ${!optedIn ? 'disabled' : ''}
                               onchange="updateSpecialPoint(${studentId}, '${category}', 'awarded', this.checked)"
                               class="rounded border-gray-300 text-green-600 focus:ring-green-500 disabled:opacity-50">
                        Otorgado
                    </label>
                </div>
            </div>
        `;
    };

    return renderRow('Ingles', 'english', englishSp) + renderRow('Cuaderno', 'notebook', notebookSp);
}

async function updateSpecialPoint(studentId, category, field, value) {
    try {
        const existingPoints = await apiCall(`/admin/special-points?class_id=${classId}&student_id=${studentId}`);
        const existing = existingPoints.find(sp => sp.category === category);

        if (existing) {
            const updateData = {};
            updateData[field] = value;
            await apiCall(`/admin/special-points/${existing.id}`, {
                method: 'PATCH',
                body: JSON.stringify(updateData)
            });
        } else {
            await apiCall('/admin/special-points', {
                method: 'POST',
                body: JSON.stringify({
                    student_id: studentId,
                    class_id: classId,
                    category,
                    opted_in: field === 'opted_in' ? value : false
                })
            });
        }

        // Refresh modal and dashboard
        openStudentModal(studentId);
        loadDashboard();
    } catch (error) {
        alert('Error al actualizar: ' + error.message);
    }
}

function closeStudentModal() {
    document.getElementById('student-modal').classList.add('hidden');
}

// ==================== Helpers ====================

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ==================== Initialization ====================

async function init() {
    if (!classId || isNaN(classId)) {
        alert('ID de clase invalido');
        window.location.href = '/admin';
        return;
    }

    if (!authToken) {
        showSection('login-section');
        return;
    }

    try {
        // Verify teacher auth
        const result = await apiCall('/students/me');
        if (result.role !== 'teacher') {
            showSection('login-section');
            return;
        }
        currentTeacher = result;
        document.getElementById('teacher-name').textContent = currentTeacher.name;

        // Load dashboard
        showSection('dashboard-section');
        await loadDashboard();
    } catch (error) {
        console.error('Auth error:', error);
        showSection('login-section');
    }
}

init();
