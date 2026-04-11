// Estado
let authToken = localStorage.getItem('authToken');
let currentTeacher = null;
let classId = null;
let dashboardData = null;
let studentsData = [];
let categories = [];
let classGradingMode = 'points';
let currentAssignmentId = null;
let fileUploadsEnabled = false;
let onlineExamsData = [];

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
    } else if (tabName === 'assignments') {
        loadAssignments();
    } else if (tabName === 'justifications') {
        loadJustifications();
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
        classGradingMode = dashboardData.stats.grading_mode || 'points';

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

    // Update pending justifications
    const pendingJust = stats.pending_justifications || 0;
    const justCountEl = document.getElementById('pending-justifications-count');
    if (justCountEl) justCountEl.textContent = `${pendingJust} pendientes`;

    const justBadge = document.getElementById('justification-badge');
    if (justBadge) {
        if (pendingJust > 0) {
            justBadge.textContent = pendingJust;
            justBadge.classList.remove('hidden');
        } else {
            justBadge.classList.add('hidden');
        }
    }

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
    const weightWarning = classGradingMode === 'percentage' && Math.abs(totalWeight - 1) > 0.001;

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
        tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-gray-500">No se encontraron estudiantes</td></tr>';
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
                    <div class="font-medium">
                        <span onclick="openStudentDrawer(${s.id}, '${(s.name || '').replace(/'/g, "\\'")}')" style="cursor:pointer;color:var(--lime);font-weight:500">${s.name}</span>
                    </div>
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
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary-10 text-secondary">
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

// ==================== Grades / Exámenes Tab ====================

let examsData = [];
let currentExamGrading = null;

function initGradesTab() {
    populateStudentSelect();
    populateCategorySelect();
    populateExamCategorySelect();
    populateOnlineExamCategorySelect();
    renderGradeCategoriesList();
    loadExams();
    loadOnlineExams();
    // Show/hide online exam form based on R2 config
    if (!fileUploadsEnabled) {
        const formEl = document.getElementById('online-exam-form-section');
        const noR2El = document.getElementById('online-exam-no-r2');
        if (formEl) formEl.style.display = 'none';
        if (noR2El) noR2El.classList.remove('hidden');
    }
}

function populateExamCategorySelect() {
    const select = document.getElementById('exam-category');
    if (!select) return;
    select.innerHTML = '<option value="">Categoria (auto)</option>' +
        categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
}

async function loadExams() {
    const container = document.getElementById('exams-list');
    try {
        const allAssignments = await apiCall(`/admin/assignments?class_id=${classId}`);
        examsData = allAssignments.filter(a => a.exam_type === 'exam');
        renderExamsList();
    } catch (err) {
        if (container) container.innerHTML = `<p class="text-red-500 text-xs">Error: ${err.message}</p>`;
    }
}

function renderExamsList() {
    const container = document.getElementById('exams-list');
    if (!container) return;
    if (!examsData.length) {
        container.innerHTML = '<p class="text-gray-400 text-sm">No hay exámenes. Crea uno abajo.</p>';
        return;
    }
    container.innerHTML = examsData.map(exam => {
        const gradedLabel = exam.graded_count > 0
            ? `<span class="text-green-600 font-medium">${exam.graded_count}</span> calificados`
            : 'Sin calificar';
        return `
        <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
            <div class="min-w-0">
                <p class="font-medium text-gray-800 text-sm truncate">${exam.title}</p>
                <p class="text-xs text-gray-400 mt-0.5">${gradedLabel} · Máx ${exam.max_points} pts</p>
            </div>
            <button onclick="openExamGrading(${exam.id})"
                    class="ml-3 px-3 py-1.5 bg-primary hover:bg-secondary text-white text-sm rounded-lg transition shrink-0">
                Calificar
            </button>
        </div>`;
    }).join('');
}

async function createExam() {
    const titleEl = document.getElementById('exam-title');
    const maxPtsEl = document.getElementById('exam-max-points');
    const categoryEl = document.getElementById('exam-category');

    const title = titleEl ? titleEl.value.trim() : '';
    if (!title) {
        alert('Por favor ingresa un título para el examen.');
        return;
    }

    const maxPoints = parseFloat(maxPtsEl ? maxPtsEl.value : '100') || 100;
    const categoryId = categoryEl && categoryEl.value ? parseInt(categoryEl.value) : null;

    try {
        const exam = await apiCall('/admin/assignments', {
            method: 'POST',
            body: JSON.stringify({
                class_id: classId,
                title,
                max_points: maxPoints,
                category_id: categoryId,
                exam_type: 'exam',
            })
        });
        if (titleEl) titleEl.value = '';
        await loadExams();
        openExamGrading(exam.id);
    } catch (err) {
        alert('Error al crear examen: ' + err.message);
    }
}

async function openExamGrading(examId) {
    try {
        const data = await apiCall(`/admin/assignments/${examId}/exam-grading`);
        currentExamGrading = data;
        renderExamGradingModal();
        document.getElementById('exam-grading-modal').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        setTimeout(() => {
            const search = document.getElementById('exam-search');
            if (search) { search.value = ''; search.focus(); }
        }, 50);
    } catch (err) {
        alert('Error al cargar datos del examen: ' + err.message);
    }
}

function closeExamGradingModal() {
    document.getElementById('exam-grading-modal').classList.add('hidden');
    document.body.style.overflow = '';
    currentExamGrading = null;
    loadExams();
}


// ==================== Online Exams ====================

function populateOnlineExamCategorySelect() {
    const select = document.getElementById('online-exam-category');
    if (!select) return;
    select.innerHTML = '<option value="">Categoría (auto)</option>' +
        categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
}

async function loadOnlineExams() {
    const container = document.getElementById('online-exams-list');
    try {
        const allAssignments = await apiCall(`/admin/assignments?class_id=${classId}`);
        onlineExamsData = allAssignments.filter(a => a.exam_type === 'online');
        renderOnlineExamsList();
    } catch (err) {
        if (container) container.innerHTML = `<p class="text-red-500 text-xs">Error: ${err.message}</p>`;
    }
}

function getOnlineExamStatus(exam) {
    const now = new Date();
    if (!exam.available_from) return { label: 'Inactivo', color: 'gray' };
    const from = new Date(exam.available_from);
    const until = exam.available_until ? new Date(exam.available_until) : null;
    if (from > now) return { label: 'Programado', color: 'blue' };
    if (!until || now <= until) return { label: 'Activo', color: 'green' };
    return { label: 'Cerrado', color: 'red' };
}

function renderOnlineExamsList() {
    const container = document.getElementById('online-exams-list');
    if (!container) return;
    if (!onlineExamsData.length) {
        container.innerHTML = '<p class="text-gray-400 text-sm">No hay exámenes online.</p>';
        return;
    }
    container.innerHTML = onlineExamsData.map(exam => {
        const status = getOnlineExamStatus(exam);
        const badgeColors = {
            gray: 'bg-gray-100 text-gray-600',
            blue: 'bg-blue-100 text-blue-700',
            green: 'bg-green-100 text-green-700',
            red: 'bg-red-100 text-red-600',
        };
        const htmlBadge = exam.has_exam_html
            ? ''
            : '<span class="text-xs text-amber-600 font-medium">Sin archivo HTML</span>';
        const subCount = `${exam.graded_count}/${exam.submission_count > 0 ? exam.submission_count : '—'} entregados`;
        return `
        <div class="p-3 bg-gray-50 rounded-lg border border-gray-100 space-y-2">
            <div class="flex items-center justify-between">
                <div class="min-w-0">
                    <p class="font-medium text-gray-800 text-sm truncate">${exam.title}</p>
                    <p class="text-xs text-gray-400 mt-0.5">${subCount} · Máx ${exam.max_points} pts ${htmlBadge}</p>
                </div>
                <span class="ml-2 px-2 py-0.5 rounded-full text-xs font-medium ${badgeColors[status.color]}">${status.label}</span>
            </div>
            <div class="flex gap-2 flex-wrap">
                ${status.color === 'gray' ? `<button onclick="activateOnlineExam(${exam.id})" class="text-xs px-3 py-1 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition">Activar ahora</button>` : ''}
                ${status.color === 'green' ? `<button onclick="closeOnlineExam(${exam.id})" class="text-xs px-3 py-1 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition">Cerrar</button>` : ''}
                ${status.color !== 'gray' ? `<button onclick="extendOnlineExam(${exam.id})" class="text-xs px-3 py-1 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition">Extender plazo</button>` : ''}
                ${exam.has_exam_html ? `<a href="/exam/${exam.id}" target="_blank" class="text-xs px-3 py-1 bg-primary-10 text-secondary rounded-lg hover:bg-primary-5 transition font-medium">👁 Vista previa</a>` : ''}
                <button onclick="viewOnlineSubmissions(${exam.id}, '${exam.title.replace(/'/g, "\\'")}')" class="text-xs px-3 py-1 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition">Ver entregas</button>
                <button onclick="openExamGrading(${exam.id})" class="text-xs px-3 py-1 bg-primary text-white rounded-lg hover:bg-secondary transition">Calificar</button>
            </div>
        </div>`;
    }).join('');
}

async function createOnlineExam() {
    const titleEl = document.getElementById('online-exam-title');
    const title = titleEl ? titleEl.value.trim() : '';
    if (!title) { alert('Ingresa un título para el examen.'); return; }

    const fileInput = document.getElementById('online-exam-file');
    if (!fileInput || !fileInput.files.length) { alert('Selecciona el archivo HTML del examen.'); return; }

    const maxPoints = parseFloat(document.getElementById('online-exam-max-points')?.value) || 100;
    const categoryId = document.getElementById('online-exam-category')?.value || null;
    const fromVal = document.getElementById('online-exam-from')?.value || null;
    const untilVal = document.getElementById('online-exam-until')?.value || null;
    const timeLimitMin = parseInt(document.getElementById('online-exam-time-limit')?.value) || 90;
    const allowSave = document.getElementById('online-exam-allow-save')?.checked ?? true;

    try {
        // 1. Create assignment
        const exam = await apiCall('/admin/assignments', {
            method: 'POST',
            body: JSON.stringify({
                class_id: classId,
                title,
                max_points: maxPoints,
                category_id: categoryId ? parseInt(categoryId) : null,
                exam_type: 'online',
                available_from: fromVal ? new Date(fromVal).toISOString() : null,
                available_until: untilVal ? new Date(untilVal).toISOString() : null,
                time_limit_min: timeLimitMin,
                allow_save: allowSave,
            })
        });

        // 2. Upload HTML file
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        const uploadRes = await fetch(`/api/admin/assignments/${exam.id}/upload-exam-html`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
            body: formData,
        });
        if (!uploadRes.ok) {
            const err = await uploadRes.json().catch(() => ({ detail: 'Error al subir archivo' }));
            throw new Error(err.detail || 'Error al subir HTML');
        }

        // Clear form
        if (titleEl) titleEl.value = '';
        if (fileInput) fileInput.value = '';
        await loadOnlineExams();
    } catch (err) {
        alert('Error al crear examen online: ' + err.message);
    }
}

async function activateOnlineExam(examId) {
    try {
        await apiCall(`/admin/assignments/${examId}/settings`, {
            method: 'PATCH',
            body: JSON.stringify({ available_from: 'now' })
        });
        await loadOnlineExams();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function closeOnlineExam(examId) {
    if (!confirm('¿Cerrar el examen? Los estudiantes no podrán seguir contestando.')) return;
    try {
        await apiCall(`/admin/assignments/${examId}/settings`, {
            method: 'PATCH',
            body: JSON.stringify({ available_until: 'now' })
        });
        await loadOnlineExams();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function extendOnlineExam(examId) {
    const newUntil = prompt('Nueva fecha y hora de cierre (AAAA-MM-DD HH:MM):');
    if (!newUntil) return;
    try {
        const parsed = new Date(newUntil.replace(' ', 'T'));
        if (isNaN(parsed)) { alert('Formato de fecha inválido.'); return; }
        await apiCall(`/admin/assignments/${examId}/settings`, {
            method: 'PATCH',
            body: JSON.stringify({ available_until: parsed.toISOString() })
        });
        await loadOnlineExams();
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function viewOnlineSubmissions(examId, examTitle) {
    document.getElementById('online-subs-title').textContent = examTitle;
    document.getElementById('online-subs-list').innerHTML = '<p class="text-gray-400 text-sm">Cargando...</p>';
    document.getElementById('online-subs-modal').classList.remove('hidden');

    try {
        const subs = await apiCall(`/admin/assignments/${examId}/online-submissions`);
        const container = document.getElementById('online-subs-list');
        const submitted = subs.filter(s => s.submitted);
        const pending = subs.filter(s => !s.submitted);
        document.getElementById('online-subs-subtitle').textContent = `${submitted.length}/${subs.length} entregados`;

        let html = '';
        if (submitted.length) {
            html += submitted.map(s => `
                <div class="flex items-center justify-between p-2 bg-green-50 rounded-lg">
                    <div>
                        <p class="text-sm font-medium text-gray-800">${s.student_name}</p>
                        <p class="text-xs text-gray-500">${new Date(s.submitted_at).toLocaleString('es-MX')}</p>
                    </div>
                    <span class="text-sm font-semibold text-green-700">${s.score ?? '—'} pts</span>
                </div>`).join('');
        }
        if (pending.length) {
            html += '<p class="text-xs text-gray-400 mt-3 mb-1 font-medium">Sin entregar:</p>';
            html += pending.map(s => `
                <div class="flex items-center p-2 bg-gray-50 rounded-lg">
                    <p class="text-sm text-gray-500">${s.student_name}</p>
                </div>`).join('');
        }
        container.innerHTML = html || '<p class="text-gray-400 text-sm">No hay estudiantes inscritos.</p>';
    } catch (err) {
        document.getElementById('online-subs-list').innerHTML = `<p class="text-red-500 text-sm">Error: ${err.message}</p>`;
    }
}

function renderExamGradingModal() {
    const d = currentExamGrading;
    document.getElementById('exam-modal-title').textContent = `Calificando: ${d.title}`;
    document.getElementById('exam-modal-subtitle').textContent = `Máximo: ${d.max_points} pts`;
    filterExamStudents('');
}

function filterExamStudents(query) {
    const d = currentExamGrading;
    if (!d) return;
    const q = query.trim().toLowerCase();
    const filtered = q ? d.students.filter(s => s.name.toLowerCase().includes(q)) : d.students;

    const ungraded = filtered.filter(s => s.grade === null || s.grade === undefined);
    const graded = filtered.filter(s => s.grade !== null && s.grade !== undefined);

    document.getElementById('exam-ungraded-count').textContent = ungraded.length;
    document.getElementById('exam-graded-count').textContent = graded.length;

    document.getElementById('exam-ungraded-list').innerHTML = ungraded.length
        ? ungraded.map(s => examStudentRow(s, d.max_points)).join('')
        : '<p class="text-gray-400 text-sm py-2 text-center">Todos calificados</p>';

    document.getElementById('exam-graded-list').innerHTML = graded.length
        ? graded.map(s => examStudentRow(s, d.max_points)).join('')
        : '<p class="text-gray-400 text-sm py-2 text-center">Ninguno calificado aún</p>';
}

function examStudentRow(student, maxPoints) {
    const scoreVal = student.grade !== null && student.grade !== undefined ? student.grade : '';
    const checkmark = student.grade !== null && student.grade !== undefined
        ? '<span class="text-green-500 text-sm font-bold ml-1">✓</span>' : '<span class="w-4 ml-1"></span>';
    return `
        <div class="flex items-center gap-3 py-2.5 border-b border-gray-50 last:border-0" id="exam-row-${student.student_id}">
            <span class="flex-1 text-sm text-gray-800 font-medium">${student.name}</span>
            <input type="number"
                   class="exam-score-input w-20 px-2 py-1.5 border border-gray-300 rounded-lg text-sm text-right focus:ring-2 focus:ring-primary outline-none"
                   min="0" max="${maxPoints}" step="0.5"
                   value="${scoreVal}"
                   placeholder="—"
                   data-student-id="${student.student_id}"
                   onkeydown="handleExamScoreKey(event, ${student.student_id})">
            <span class="text-gray-400 text-xs shrink-0">/ ${maxPoints}</span>
            ${checkmark}
        </div>`;
}

function handleExamSearchKey(event) {
    if (event.key === 'ArrowDown' || event.key === 'Tab') {
        // Focus first visible score input
        const inputs = document.querySelectorAll('#exam-ungraded-list .exam-score-input, #exam-graded-list .exam-score-input');
        if (inputs.length) {
            event.preventDefault();
            inputs[0].focus();
            inputs[0].select();
        }
    } else if (event.key === 'Escape') {
        closeExamGradingModal();
    }
}

async function handleExamScoreKey(event, studentId) {
    if (event.key === 'Enter') {
        event.preventDefault();
        const input = event.target;
        const score = parseFloat(input.value);
        if (isNaN(score)) return;
        await saveExamGrade(studentId, score);
        // Clear search, re-render, refocus search
        const searchEl = document.getElementById('exam-search');
        if (searchEl) { searchEl.value = ''; searchEl.focus(); }
        filterExamStudents('');
    } else if (event.key === 'Escape') {
        const searchEl = document.getElementById('exam-search');
        if (searchEl) searchEl.focus();
    }
}

async function saveExamGrade(studentId, score) {
    const d = currentExamGrading;
    try {
        await apiCall(`/admin/assignments/${d.assignment_id}/exam-grade`, {
            method: 'POST',
            body: JSON.stringify({ student_id: studentId, score })
        });
        // Update local state so re-render shows checkmark
        const student = d.students.find(s => s.student_id === studentId);
        if (student) student.grade = score;
    } catch (err) {
        alert('Error al guardar calificacion: ' + err.message);
    }
}

function toggleExamSection(section) {
    const body = document.getElementById(`exam-${section}-body`);
    const chevron = document.getElementById(`exam-${section}-chevron`);
    if (!body || !chevron) return;
    body.classList.toggle('hidden');
    chevron.classList.toggle('rotate-180');
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
    const weightWarning = classGradingMode === 'percentage' && Math.abs(totalWeight - 1) > 0.001;

    const weightNote = weightWarning
        ? `<p class="text-yellow-600 text-sm mt-2">Los pesos suman ${(totalWeight * 100).toFixed(0)}%. Deben sumar 100% para calcular correctamente.</p>`
        : classGradingMode === 'points'
            ? `<p class="text-gray-400 text-xs mt-2">Modo puntos: los pesos no necesitan sumar 100%</p>`
            : '';

    const toggle = `
        <div class="flex gap-4 mt-4 pt-3 border-t border-gray-100">
            <label class="flex items-center gap-1.5 cursor-pointer text-sm text-gray-700">
                <input type="radio" name="grading_mode" value="points" ${classGradingMode === 'points' ? 'checked' : ''}
                       onchange="saveGradingMode('points')" class="text-primary">
                Puntos (sin límite)
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer text-sm text-gray-700">
                <input type="radio" name="grading_mode" value="percentage" ${classGradingMode === 'percentage' ? 'checked' : ''}
                       onchange="saveGradingMode('percentage')" class="text-primary">
                Porcentajes (cap 100%)
            </label>
        </div>
    `;

    container.innerHTML = categories.map(cat => `
        <div class="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
            <div class="flex items-center gap-3">
                <span class="font-medium text-gray-800">${cat.name}</span>
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary-10 text-primary">
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
    `).join('') + weightNote + toggle;
}


async function saveGradingMode(mode) {
    try {
        await apiCall(`/admin/classes/${classId}/settings`, {
            method: 'PATCH',
            body: JSON.stringify({ grading_mode: mode }),
        });
        classGradingMode = mode;
        renderCategoriesOverview();
        renderGradeCategoriesList();
    } catch (err) {
        alert('Error al guardar el modo de calificacion: ' + err.message);
    }
}

document.getElementById('grade-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const studentId = parseInt(document.getElementById('grade-student').value);
    const categorySelect = document.getElementById('grade-category');
    const categoryId = categorySelect && categorySelect.value ? parseInt(categorySelect.value) : null;
    const nameInput = document.getElementById('grade-name');
    const name = nameInput ? nameInput.value.trim() || null : null;
    const score = parseFloat(document.getElementById('grade-score').value);
    const maxScore = parseFloat(document.getElementById('grade-max').value);

    if (!studentId) {
        alert('Por favor selecciona un estudiante.');
        return;
    }

    if (!categoryId) {
        alert('Por favor selecciona una categoría.');
        return;
    }

    try {
        await apiCall('/admin/grades', {
            method: 'POST',
            body: JSON.stringify({
                student_id: studentId,
                class_id: classId,
                category_id: categoryId,
                name,
                score,
                max_score: maxScore
            })
        });

        const successEl = document.getElementById('grade-success');
        successEl.classList.remove('hidden');
        setTimeout(() => successEl.classList.add('hidden'), 3000);

        // Reset form
        document.getElementById('grade-score').value = '';
        if (nameInput) nameInput.value = '';

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
    const btnApproveAll = document.getElementById('btn-approve-all');

    container.innerHTML = '<p class="text-center text-gray-500 py-4">Cargando...</p>';
    btnApproveAll.classList.add('hidden');

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

        // Show "Aprobar Todo" button if there are pending records visible
        const hasPending = participations.some(p => p.approved === 'pending');
        if (hasPending) {
            btnApproveAll.classList.remove('hidden');
        }
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

async function bulkApproveAll() {
    const pendingCards = document.querySelectorAll('#participation-list [data-participation-id]');
    const items = [];

    pendingCards.forEach(card => {
        const id = parseInt(card.dataset.participationId);
        const pointsInput = card.querySelector('.points-input');
        const points = pointsInput ? parseInt(pointsInput.value) : null;
        items.push({ id, points });
    });

    if (items.length === 0) return;

    if (!confirm(`¿Aprobar ${items.length} participacion(es) pendiente(s)?`)) return;

    try {
        await apiCall('/admin/participation/bulk-approve', {
            method: 'PATCH',
            body: JSON.stringify({ class_id: classId, items })
        });

        loadParticipation();
        loadDashboard();
    } catch (error) {
        alert('Error al aprobar: ' + error.message);
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
                    <div class="text-2xl font-bold text-primary">${student.attendance_rate.toFixed(0)}%</div>
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
                    <span class="text-sm font-medium">${student.participation_points} pts</span>
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

// ==================== Assignments Tab ====================

function toggleAssignmentForm() {
    const container = document.getElementById('assignment-form-container');
    container.classList.toggle('hidden');

    // Populate category dropdown
    if (!container.classList.contains('hidden')) {
        const catSelect = document.getElementById('assignment-category');
        catSelect.innerHTML = categories.map(c =>
            `<option value="${c.id}">${c.name} (${(c.weight * 100).toFixed(0)}%)</option>`
        ).join('');

        const dueDateInput = document.getElementById('assignment-due-date');
        if (!dueDateInput.value) {
            const today = new Date();
            const daysUntilSunday = (7 - today.getDay()) % 7 || 7;
            const nextSunday = new Date(today);
            nextSunday.setDate(today.getDate() + daysUntilSunday);
            nextSunday.setHours(23, 59, 0, 0);
            // Format for datetime-local input
            const pad = n => String(n).padStart(2, '0');
            dueDateInput.value = `${nextSunday.getFullYear()}-${pad(nextSunday.getMonth() + 1)}-${pad(nextSunday.getDate())}T${pad(nextSunday.getHours())}:${pad(nextSunday.getMinutes())}`;
        }
    }
}

document.getElementById('assignment-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const title = document.getElementById('assignment-title').value.trim();
    const description = document.getElementById('assignment-description').value.trim() || null;
    const dueDateInput = document.getElementById('assignment-due-date').value;
    const maxPoints = parseFloat(document.getElementById('assignment-max-points').value) || 100;
    const categoryId = parseInt(document.getElementById('assignment-category').value) || null;

    if (!title) {
        alert('Por favor ingresa un titulo.');
        return;
    }

    const payload = {
        class_id: classId,
        title,
        description,
        max_points: maxPoints,
        category_id: categoryId,
    };

    if (dueDateInput) {
        payload.due_date = new Date(dueDateInput).toISOString();
    }

    try {
        await apiCall('/admin/assignments', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        // Reset form and hide
        document.getElementById('assignment-title').value = '';
        document.getElementById('assignment-description').value = '';
        document.getElementById('assignment-due-date').value = '';
        document.getElementById('assignment-max-points').value = '100';
        document.getElementById('assignment-form-container').classList.add('hidden');

        loadAssignments();
    } catch (error) {
        alert('Error al crear reto: ' + error.message);
    }
});

async function loadAssignments() {
    const container = document.getElementById('assignments-list');
    container.innerHTML = '<p class="text-center text-gray-500 py-4">Cargando...</p>';

    try {
        const assignments = await apiCall(`/admin/assignments?class_id=${classId}`);
        const totalStudents = dashboardData?.stats?.total_students || 0;

        if (assignments.length === 0) {
            container.innerHTML = '<p class="text-center text-gray-500 py-4">No hay retos creados. Crea el primero!</p>';
            return;
        }

        container.innerHTML = assignments.map(a => {
            const now = new Date();
            const due = new Date(a.due_date + 'Z');
            const isPast = now > due;
            const dueBadge = isPast
                ? '<span class="text-xs px-2 py-0.5 rounded bg-red-100 text-red-700">Vencido</span>'
                : '<span class="text-xs px-2 py-0.5 rounded bg-green-100 text-green-700">Activo</span>';

            return `
                <div class="border border-gray-200 rounded-lg p-4 cursor-pointer hover:border-primary transition" onclick="openSubmissionsModal(${a.id})">
                    <div class="flex flex-col sm:flex-row justify-between gap-3">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="font-medium text-gray-800">${a.title}</span>
                                ${dueBadge}
                            </div>
                            ${a.description ? `<p class="text-gray-600 text-sm mb-2">${a.description}</p>` : ''}
                            <div class="flex items-center gap-4 text-xs text-gray-500">
                                <span>Fecha limite: ${formatDate(a.due_date.split('T')[0])} ${due.toLocaleTimeString('es-MX', {hour: '2-digit', minute: '2-digit'})}</span>
                                <span>Puntos: ${a.max_points}</span>
                            </div>
                        </div>
                        <div class="flex items-center gap-4">
                            <div class="text-center">
                                <div class="text-lg font-bold text-primary">${a.submission_count}/${totalStudents}</div>
                                <div class="text-xs text-gray-500">Entregas</div>
                            </div>
                            <div class="text-center">
                                <div class="text-lg font-bold text-green-600">${a.graded_count}</div>
                                <div class="text-xs text-gray-500">Calificados</div>
                            </div>
                            <button onclick="event.stopPropagation(); deleteAssignment(${a.id})"
                                    class="text-red-400 hover:text-red-600" title="Eliminar">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = `<p class="text-center text-red-500 py-4">Error al cargar: ${error.message}</p>`;
    }
}

async function deleteAssignment(id) {
    if (!confirm('¿Estas seguro de eliminar este reto? Se eliminaran todas las entregas asociadas.')) {
        return;
    }

    try {
        await apiCall(`/admin/assignments/${id}`, { method: 'DELETE' });
        loadAssignments();
    } catch (error) {
        alert('Error al eliminar: ' + error.message);
    }
}

// ==================== Submissions Modal ====================

function openSubmissionsModal(assignmentId) {
    currentAssignmentId = assignmentId;
    document.getElementById('submissions-modal').classList.remove('hidden');
    document.getElementById('submissions-filter').value = '';
    loadSubmissions(assignmentId);
}

function closeSubmissionsModal() {
    document.getElementById('submissions-modal').classList.add('hidden');
    currentAssignmentId = null;
    loadAssignments();
}

async function loadSubmissions(assignmentId, filter) {
    const container = document.getElementById('submissions-list');
    container.innerHTML = '<p class="text-center text-gray-500 py-4">Cargando...</p>';

    try {
        let url = `/admin/assignments/${assignmentId}/submissions`;
        if (filter) url += `?filter=${filter}`;

        const data = await apiCall(url);

        // Update header
        document.getElementById('submissions-modal-title').textContent = data.assignment_title;
        document.getElementById('submissions-modal-subtitle').textContent =
            `${data.submissions.length} entrega(s) de ${data.total_enrolled} estudiantes | Max: ${data.max_points} pts`;

        if (data.submissions.length === 0) {
            container.innerHTML = '<p class="text-center text-gray-500 py-4">No hay entregas</p>';
        } else {
            container.innerHTML = data.submissions.map(s => renderSubmissionRow(s, data.max_points)).join('');
        }

        // Not submitted section
        const notSection = document.getElementById('not-submitted-section');
        const notList = document.getElementById('not-submitted-list');
        const notTitle = document.getElementById('not-submitted-title');

        if (data.not_submitted.length > 0) {
            notSection.classList.remove('hidden');
            notTitle.textContent = `Sin entregar (${data.not_submitted.length})`;
            notList.innerHTML = data.not_submitted.map(s => `
                <div class="flex items-center justify-between p-2 bg-gray-50 rounded text-sm">
                    <span class="text-gray-700">${s.name}</span>
                    <span class="text-gray-400 text-xs">${s.email}</span>
                </div>
            `).join('');
        } else {
            notSection.classList.add('hidden');
        }
    } catch (error) {
        container.innerHTML = `<p class="text-center text-red-500 py-4">Error: ${error.message}</p>`;
    }
}

function renderSubmissionRow(s, maxPoints) {
    const isGraded = s.grade !== null && s.grade !== undefined;
    const gradedBadge = isGraded
        ? `<span class="text-xs px-2 py-0.5 rounded bg-green-100 text-green-700">Calificado: ${s.grade}/${maxPoints}</span>`
        : `<span class="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">Sin calificar</span>`;
    const lateBadge = s.is_late
        ? `<span class="text-xs px-2 py-0.5 rounded bg-red-100 text-red-700">Tarde (${s.penalty_pct}%)</span>`
        : '';
    const resubmitBadge = (s.resubmit_count || 0) > 0
        ? `<span class="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-700">Re-entregado${s.resubmit_count > 1 ? ' (' + s.resubmit_count + 'x)' : ''}</span>`
        : '';
    const driveLink = s.drive_url
        ? `<a href="${s.drive_url}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()" class="text-xs text-blue-600 hover:underline">Ver entrega (Drive)</a>`
        : '';
    const fileLink = s.has_file
        ? `<button onclick="event.stopPropagation(); viewSubmissionFileAdmin(${s.id})" class="text-xs text-blue-600 hover:underline">Ver archivo (${s.file_name || 'archivo'}${s.file_size ? ', ' + formatFileSizeAdmin(s.file_size) : ''})</button>`
        : '';

    const submittedDate = new Date(s.submitted_at + 'Z').toLocaleString('es-MX', {
        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
    });

    const buttonLabel = isGraded ? 'Actualizar' : 'Calificar';
    const buttonColor = isGraded ? 'bg-gray-600 hover:bg-gray-700' : 'bg-primary hover:bg-secondary';

    return `
        <div class="border border-gray-200 rounded-lg p-3" data-submission-id="${s.id}">
            <div class="flex flex-col sm:flex-row justify-between gap-3">
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1 flex-wrap">
                        <span class="font-medium text-gray-800">${s.student_name}</span>
                        ${lateBadge}
                        ${resubmitBadge}
                        ${gradedBadge}
                    </div>
                    <div class="flex items-center gap-3 text-xs text-gray-500">
                        <span>Enviado: ${submittedDate}</span>
                        ${driveLink}
                        ${fileLink}
                    </div>
                    <div class="text-xs text-gray-400 mt-1">
                        Auto-calificacion: ${s.auto_grade.toFixed(1)}/${maxPoints}
                        ${s.feedback ? `<span class="ml-2 text-gray-500">Feedback: ${s.feedback}</span>` : ''}
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <input type="number" id="score-${s.id}" min="0" max="${maxPoints}" step="0.5"
                           value="${isGraded ? s.grade : s.auto_grade.toFixed(1)}"
                           class="w-20 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-primary outline-none">
                    <span class="text-xs text-gray-500">/${maxPoints}</span>
                    <button onclick="gradeSubmission(${s.id})"
                            class="px-3 py-1 text-sm text-white rounded ${buttonColor} transition">
                        ${buttonLabel}
                    </button>
                </div>
            </div>
        </div>
    `;
}

function filterSubmissions() {
    const filter = document.getElementById('submissions-filter').value;
    if (currentAssignmentId) {
        loadSubmissions(currentAssignmentId, filter || undefined);
    }
}

async function gradeSubmission(submissionId) {
    const scoreInput = document.getElementById(`score-${submissionId}`);
    const score = parseFloat(scoreInput.value);

    if (isNaN(score)) {
        alert('Por favor ingresa una calificacion valida.');
        return;
    }

    try {
        await apiCall(`/admin/submissions/${submissionId}/grade`, {
            method: 'PATCH',
            body: JSON.stringify({ score })
        });

        // Refresh submissions
        const filter = document.getElementById('submissions-filter').value;
        loadSubmissions(currentAssignmentId, filter || undefined);
    } catch (error) {
        alert('Error al calificar: ' + error.message);
    }
}

async function autoGradeAll() {
    if (!currentAssignmentId) return;

    if (!confirm('¿Aceptar las auto-calificaciones para todas las entregas sin calificar? La calificacion se basa en el porcentaje de penalizacion por entrega tardia.')) {
        return;
    }

    try {
        const result = await apiCall(`/admin/assignments/${currentAssignmentId}/auto-grade`, {
            method: 'POST'
        });

        alert(`${result.graded_count} entrega(s) calificada(s) automaticamente.`);

        // Refresh submissions
        const filter = document.getElementById('submissions-filter').value;
        loadSubmissions(currentAssignmentId, filter || undefined);
    } catch (error) {
        alert('Error al auto-calificar: ' + error.message);
    }
}

// ==================== Justifications Tab ====================

async function loadJustifications() {
    const container = document.getElementById('justifications-list');
    const filter = document.getElementById('justification-filter').value;
    container.innerHTML = '<p class="text-center text-gray-500 py-4">Cargando...</p>';

    try {
        let url = `/admin/justifications?class_id=${classId}`;
        if (filter) url += `&status_filter=${filter}`;

        const justifications = await apiCall(url);

        if (justifications.length === 0) {
            container.innerHTML = '<p class="text-center text-gray-500 py-4">No hay justificaciones para mostrar</p>';
            return;
        }

        const statusNames = {
            pending: 'Pendiente',
            approved: 'Aprobada',
            rejected: 'Rechazada'
        };

        const statusColors = {
            pending: 'bg-yellow-100 text-yellow-800',
            approved: 'bg-green-100 text-green-800',
            rejected: 'bg-red-100 text-red-800'
        };

        const attStatusNames = {
            absent: 'Ausente',
            late: 'Tarde',
            excused: 'Justificado'
        };

        container.innerHTML = justifications.map(j => {
            const statusColor = statusColors[j.justification_status] || 'bg-gray-100 text-gray-800';
            const statusName = statusNames[j.justification_status] || j.justification_status;
            const attStatus = attStatusNames[j.status] || j.status;
            const submittedDate = j.justification_submitted_at
                ? new Date(j.justification_submitted_at + 'Z').toLocaleString('es-MX', {
                    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
                })
                : '';

            const fileBtn = j.has_justification_file
                ? `<button onclick="viewJustificationFileAdmin(${j.id})" class="text-xs text-blue-600 hover:underline">
                    Ver archivo (${j.justification_file_name || 'archivo'})
                   </button>`
                : '';

            const actionBtns = j.justification_status === 'pending'
                ? `<div class="flex items-center gap-2">
                        <button onclick="reviewJustification(${j.id}, 'approved')"
                                class="px-3 py-1 text-sm bg-green-100 text-green-700 rounded hover:bg-green-200">
                            Aprobar
                        </button>
                        <button onclick="reviewJustification(${j.id}, 'rejected')"
                                class="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200">
                            Rechazar
                        </button>
                   </div>`
                : '';

            return `
                <div class="border border-gray-200 rounded-lg p-4">
                    <div class="flex flex-col sm:flex-row justify-between gap-3">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1 flex-wrap">
                                <span class="font-medium text-gray-800">${j.student_name}</span>
                                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColor}">
                                    ${statusName}
                                </span>
                                <span class="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                                    ${attStatus} - ${formatDate(j.date)}
                                </span>
                            </div>
                            <div class="text-xs text-gray-500 mt-1">
                                <span>Enviado: ${submittedDate}</span>
                            </div>
                            ${j.justification_text ? `<p class="text-sm text-gray-600 mt-1">${j.justification_text}</p>` : ''}
                            <div class="mt-1">${fileBtn}</div>
                        </div>
                        ${actionBtns}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = `<p class="text-center text-red-500 py-4">Error al cargar: ${error.message}</p>`;
    }
}

async function reviewJustification(attendanceId, status) {
    try {
        await apiCall(`/admin/justifications/${attendanceId}`, {
            method: 'PATCH',
            body: JSON.stringify({ status })
        });

        loadJustifications();
        loadDashboard();
    } catch (error) {
        alert('Error al revisar justificacion: ' + error.message);
    }
}

async function viewJustificationFileAdmin(attendanceId) {
    try {
        const data = await apiCall(`/students/attendance/${attendanceId}/justification-file`);
        window.open(data.download_url, '_blank');
    } catch (error) {
        alert('Error al abrir archivo: ' + error.message);
    }
}

// ==================== File Helpers ====================

function formatFileSizeAdmin(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function viewSubmissionFileAdmin(submissionId) {
    try {
        const data = await apiCall(`/students/submissions/${submissionId}/file`);
        window.open(data.download_url, '_blank');
    } catch (error) {
        alert('Error al abrir archivo: ' + error.message);
    }
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

        // Fetch config (file uploads flag)
        try {
            const config = await apiCall('/config');
            fileUploadsEnabled = config.file_uploads_enabled || false;
        } catch (e) { /* non-critical */ }

        // Load dashboard
        showSection('dashboard-section');
        await loadDashboard();
    } catch (error) {
        console.error('Auth error:', error);
        showSection('login-section');
    }
}

init();

// ==================== Student Detail Drawer ====================

async function openStudentDrawer(studentId, studentName) {
    document.getElementById('drawerStudentName').textContent = studentName;
    document.getElementById('drawerGrade').textContent = '…';
    document.getElementById('drawerParticipation').textContent = '…';
    document.getElementById('drawerAbsences').textContent = '…';
    document.getElementById('drawerAttendancePct').textContent = '…';
    document.getElementById('drawerForumPts').textContent = '…';
    document.getElementById('studentDrawer').style.right = '0';
    document.getElementById('drawerOverlay').style.display = 'block';

    try {
        const gradeData = await apiCall(
            `/students/me/grade-calculation/${classId}`,
            { method: 'GET', headers: { 'X-Impersonate': String(studentId) } }
        );

        const grade = gradeData.final_grade != null ? gradeData.final_grade.toFixed(1) : '—';
        const absences = gradeData.absence_count != null ? gradeData.absence_count : '—';
        const partPts = gradeData.participation_points != null ? gradeData.participation_points.toFixed(1) : '—';
        const forumPts = gradeData.forum_points != null ? gradeData.forum_points.toFixed(2) : '—';

        const attendanceData = await apiCall(
            `/students/me/attendance?class_id=${classId}`,
            { method: 'GET', headers: { 'X-Impersonate': String(studentId) } }
        );
        const total = attendanceData.length;
        const present = attendanceData.filter(function(a) {
            return a.status === 'present' || a.status === 'late' || a.status === 'excused';
        }).length;
        const attendancePct = total > 0 ? Math.round((present / total) * 100) + '%' : '—';

        document.getElementById('drawerGrade').textContent = grade;
        document.getElementById('drawerParticipation').textContent = partPts + ' pts';
        document.getElementById('drawerAbsences').textContent = absences;
        document.getElementById('drawerAttendancePct').textContent = attendancePct;
        document.getElementById('drawerForumPts').textContent = forumPts + ' pts';
    } catch(e) {
        document.getElementById('drawerGrade').textContent = 'Error';
        console.error('openStudentDrawer error:', e);
    }
}

function closeStudentDrawer() {
    document.getElementById('studentDrawer').style.right = '-400px';
    document.getElementById('drawerOverlay').style.display = 'none';
}
