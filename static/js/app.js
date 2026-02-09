// Estado
let authToken = localStorage.getItem('authToken');
let currentStudent = null;
let googleClientId = null;
let enrolledClasses = [];
let selectedClassId = localStorage.getItem('selectedClassId') ? parseInt(localStorage.getItem('selectedClassId')) : null;
let previewMode = false;
let previewStudentId = null;

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

    if (previewMode && previewStudentId) {
        headers['X-Impersonate'] = previewStudentId.toString();
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

// Funciones de Google OAuth
async function handleGoogleCredentialResponse(response) {
    const errorEl = document.getElementById('login-error');
    errorEl.classList.add('hidden');

    try {
        const result = await apiCall('/auth/google', {
            method: 'POST',
            body: JSON.stringify({ credential: response.credential })
        });

        authToken = result.token;
        currentStudent = result.student;
        localStorage.setItem('authToken', authToken);

        // Check enrollment status
        await checkEnrollment();
    } catch (error) {
        console.error('Error de autenticacion:', error);
        errorEl.textContent = 'Error de autenticacion. Por favor intenta de nuevo.';
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
        {
            theme: 'outline',
            size: 'large',
            width: 280,
        }
    );
}

async function logout() {
    try {
        await apiCall('/auth/logout', { method: 'POST' });
    } catch (error) {
        console.error('Error al cerrar sesion:', error);
    }

    authToken = null;
    currentStudent = null;
    enrolledClasses = [];
    selectedClassId = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('selectedClassId');
    showLogin();

    if (googleClientId) {
        initGoogleSignIn();
    }
}

function exitPreviewMode() {
    sessionStorage.removeItem('teacherPreviewMode');
    sessionStorage.removeItem('previewClassId');
    sessionStorage.removeItem('previewStudentId');
    sessionStorage.removeItem('previewClassName');
    window.location.href = '/admin';
}

// Funciones de UI
function showLogin() {
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('join-class-section').classList.add('hidden');
    document.getElementById('dashboard-section').classList.add('hidden');
}

function showJoinClass() {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('join-class-section').classList.remove('hidden');
    document.getElementById('dashboard-section').classList.add('hidden');

    if (currentStudent) {
        document.getElementById('join-student-name').textContent = currentStudent.name;
    }

    // Show enrolled classes if any
    renderEnrolledClassesList();
}

function showDashboard() {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('join-class-section').classList.add('hidden');
    document.getElementById('dashboard-section').classList.remove('hidden');

    if (currentStudent) {
        document.getElementById('student-name').textContent = currentStudent.name;
    }

    if (previewMode) {
        document.getElementById('preview-banner').classList.remove('hidden');
        const previewClassName = sessionStorage.getItem('previewClassName') || 'Clase';
        const classNameSpan = document.getElementById('preview-class-name');
        if (classNameSpan) {
            classNameSpan.textContent = previewClassName;
        }
        // Hide participation form in preview mode
        const participationSection = document.getElementById('participation-section');
        if (participationSection) {
            participationSection.classList.add('hidden');
        }
    }

    populateClassSelector();
}

// Class enrollment
async function checkEnrollment() {
    try {
        enrolledClasses = await apiCall('/classes/enrolled');

        if (enrolledClasses.length === 0) {
            showJoinClass();
        } else {
            // Set selected class if not already set or if the saved one is no longer valid
            const validClass = enrolledClasses.find(c => c.class_id === selectedClassId);
            if (!validClass) {
                selectedClassId = enrolledClasses[0].class_id;
                localStorage.setItem('selectedClassId', selectedClassId);
            }
            showDashboard();
            loadDashboardData();
        }
    } catch (error) {
        console.error('Error al verificar inscripcion:', error);
        showJoinClass();
    }
}

function populateClassSelector() {
    const selector = document.getElementById('class-selector');
    selector.innerHTML = enrolledClasses.map(c =>
        `<option value="${c.class_id}" ${c.class_id === selectedClassId ? 'selected' : ''}>${c.class_name}</option>`
    ).join('');
}

function onClassChange() {
    const selector = document.getElementById('class-selector');
    selectedClassId = parseInt(selector.value);
    localStorage.setItem('selectedClassId', selectedClassId);
    loadDashboardData();
}

function renderEnrolledClassesList() {
    const container = document.getElementById('enrolled-classes-list');
    const listEl = document.getElementById('my-classes');

    if (enrolledClasses.length === 0) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    listEl.innerHTML = enrolledClasses.map(c => `
        <div class="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
            <div>
                <span class="font-medium text-gray-800">${c.class_name}</span>
                <span class="text-gray-400 text-xs ml-2">${c.class_code}</span>
            </div>
            <button onclick="goToClass(${c.class_id})"
                    class="px-3 py-1 text-sm bg-primary text-white rounded hover:bg-indigo-700">
                Ir
            </button>
        </div>
    `).join('');
}

function goToClass(classId) {
    selectedClassId = classId;
    localStorage.setItem('selectedClassId', selectedClassId);
    showDashboard();
    loadDashboardData();
}

// Join class form
document.getElementById('join-class-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const codeInput = document.getElementById('class-code');
    const errorEl = document.getElementById('join-error');
    errorEl.classList.add('hidden');

    try {
        const result = await apiCall('/classes/join', {
            method: 'POST',
            body: JSON.stringify({ code: codeInput.value.toUpperCase() })
        });

        enrolledClasses.push(result);
        selectedClassId = result.class_id;
        localStorage.setItem('selectedClassId', selectedClassId);

        codeInput.value = '';
        showDashboard();
        loadDashboardData();
    } catch (error) {
        errorEl.textContent = error.message;
        errorEl.classList.remove('hidden');
    }
});

// Carga de datos
async function loadDashboardData() {
    if (!selectedClassId) return;

    await Promise.all([
        loadGradeCalculation(),
        loadGrades(),
        loadAttendance(),
        loadParticipationPoints(),
        loadAssignments()
    ]);
}

async function loadGradeCalculation() {
    const breakdownEl = document.getElementById('grade-breakdown');
    const finalGradeEl = document.getElementById('final-grade');
    const specialPointsEl = document.getElementById('special-points');

    try {
        const calc = await apiCall(`/students/me/grade-calculation/${selectedClassId}`);
        renderGradeBreakdown(calc);

        // Update summary stats
        finalGradeEl.textContent = calc.final_grade.toFixed(1);
        finalGradeEl.className = `text-3xl font-bold ${calc.final_grade >= 70 ? 'text-green-600' : calc.final_grade >= 60 ? 'text-yellow-600' : 'text-red-600'}`;

        specialPointsEl.textContent = `+${calc.special_points_total.toFixed(1)}`;

    } catch (error) {
        console.error('Error al cargar calculo de calificacion:', error);
        breakdownEl.innerHTML = '<p class="text-center text-gray-500 py-4">No se pudo cargar el desglose</p>';
        finalGradeEl.textContent = '--';
        specialPointsEl.textContent = '--';
    }
}

function renderGradeBreakdown(calc) {
    const container = document.getElementById('grade-breakdown');

    if (calc.categories.length === 0 && calc.participation_points === 0 && calc.special_points.length === 0) {
        container.innerHTML = '<p class="text-center text-gray-500 py-4">No hay datos de calificacion aun</p>';
        return;
    }

    let html = '';

    // Category breakdowns
    if (calc.categories.length > 0) {
        html += '<div class="space-y-2">';
        calc.categories.forEach(cat => {
            const gradeCount = cat.grades.length;
            const totalAssignments = cat.total_assignments || 0;
            const gradedCount = cat.graded_count || 0;
            const pendingCount = cat.pending_count || 0;

            // Build assignment context line
            let assignmentInfo = `${gradeCount} calificacion(es)`;
            if (totalAssignments > 0) {
                const parts = [];
                if (gradedCount > 0) parts.push(`${gradedCount} calificada(s)`);
                if (pendingCount > 0) parts.push(`${pendingCount} pendiente(s)`);
                const notSubmitted = totalAssignments - gradedCount - pendingCount;
                if (notSubmitted > 0) parts.push(`${notSubmitted} sin entregar`);
                assignmentInfo = parts.join(', ');
            }

            html += `
                <div class="p-3 bg-gray-50 rounded-lg">
                    <div class="flex justify-between items-center">
                        <div>
                            <span class="font-medium text-gray-800">${cat.category_name}</span>
                            <span class="text-xs text-gray-500 ml-2">(${(cat.weight * 100).toFixed(0)}% del total)</span>
                        </div>
                        <div class="text-right">
                            <span class="font-medium ${cat.average >= 70 ? 'text-green-600' : cat.average >= 60 ? 'text-yellow-600' : 'text-red-600'}">
                                ${cat.average.toFixed(1)}%
                            </span>
                            <span class="text-gray-400 text-sm ml-2">&rarr; ${cat.weighted_contribution.toFixed(1)} pts</span>
                        </div>
                    </div>
                    <div class="text-xs text-gray-400 mt-1">
                        ${assignmentInfo}
                        ${gradedCount > 0 ? `<span class="ml-1 text-gray-500">&mdash; Tu calificacion se calcula sobre ${gradedCount} tarea(s) completada(s)</span>` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';
    }

    // Participation contribution
    html += `
        <div class="flex justify-between items-center p-3 bg-purple-50 rounded-lg mt-3">
            <div>
                <span class="font-medium text-purple-800">Participacion</span>
                <span class="text-xs text-purple-600 ml-2">(${calc.participation_points} pts aprobados × 0.1)</span>
            </div>
            <span class="font-medium text-purple-800">+${calc.participation_contribution.toFixed(1)} pts</span>
        </div>
    `;

    // Special points
    if (calc.special_points.length > 0) {
        const englishSp = calc.special_points.find(sp => sp.category === 'english');
        const notebookSp = calc.special_points.find(sp => sp.category === 'notebook');

        html += '<div class="mt-3 space-y-2">';

        if (englishSp) {
            html += renderSpecialPointRow('Ingles', englishSp);
        }
        if (notebookSp) {
            html += renderSpecialPointRow('Cuaderno', notebookSp);
        }

        html += '</div>';
    }

    // Total
    html += `
        <div class="flex justify-between items-center p-3 bg-primary/10 rounded-lg mt-4 border-t-2 border-primary">
            <span class="font-bold text-gray-800">Calificacion Final</span>
            <span class="text-2xl font-bold ${calc.final_grade >= 70 ? 'text-green-600' : calc.final_grade >= 60 ? 'text-yellow-600' : 'text-red-600'}">
                ${calc.final_grade.toFixed(1)}
            </span>
        </div>
    `;

    container.innerHTML = html;
}

function renderSpecialPointRow(label, sp) {
    const statusClass = sp.opted_in
        ? (sp.awarded ? 'bg-green-50 text-green-800' : 'bg-amber-50 text-amber-800')
        : 'bg-gray-50 text-gray-500';

    const statusText = sp.opted_in
        ? (sp.awarded ? 'Otorgado' : 'Inscrito - Pendiente')
        : 'No inscrito';

    const pointsText = sp.opted_in && sp.awarded
        ? `+${sp.points_value.toFixed(1)} pts`
        : '+0 pts';

    return `
        <div class="flex justify-between items-center p-3 ${statusClass} rounded-lg">
            <div>
                <span class="font-medium">${label}</span>
                <span class="text-xs ml-2">(${statusText})</span>
            </div>
            <span class="font-medium">${pointsText}</span>
        </div>
    `;
}

async function loadParticipationPoints() {
    try {
        const result = await apiCall(`/students/me/participation/points?class_id=${selectedClassId}`);
        console.log('Participation points loaded:', result);
        document.getElementById('total-participation').textContent = result.total_points;
    } catch (error) {
        console.error('Error al cargar puntos de participacion:', error);
        document.getElementById('total-participation').textContent = '0';
    }
}

async function loadGrades() {
    try {
        const grades = await apiCall(`/students/me/grades?class_id=${selectedClassId}`);
        renderGrades(grades);
    } catch (error) {
        console.error('Error al cargar calificaciones:', error);
        document.getElementById('grades-table').innerHTML = `
            <tr><td colspan="3" class="px-6 py-4 text-center text-gray-500">Error al cargar calificaciones</td></tr>
        `;
    }
}

async function loadAttendance() {
    try {
        const attendance = await apiCall(`/students/me/attendance?class_id=${selectedClassId}`);
        renderAttendance(attendance);
        calculateAttendanceRate(attendance);
    } catch (error) {
        console.error('Error al cargar asistencia:', error);
        document.getElementById('attendance-table').innerHTML = `
            <tr><td colspan="3" class="px-6 py-4 text-center text-gray-500">Error al cargar asistencia</td></tr>
        `;
    }
}

// Funciones de renderizado
function renderGrades(grades) {
    const tbody = document.getElementById('grades-table');

    if (grades.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="3" class="px-6 py-4 text-center text-gray-500">Sin calificaciones aun</td></tr>
        `;
        return;
    }

    // Legacy category names (for backward compatibility)
    const legacyCategoryNames = {
        homework: 'Tarea',
        quiz: 'Quiz',
        exam: 'Examen',
        project: 'Proyecto'
    };

    tbody.innerHTML = grades.map(grade => {
        const percentage = ((grade.score / grade.max_score) * 100).toFixed(1);
        const colorClass = percentage >= 70 ? 'text-green-600' : percentage >= 50 ? 'text-yellow-600' : 'text-red-600';

        // Use name if available, otherwise category (legacy)
        let displayName = grade.name || legacyCategoryNames[grade.category] || grade.category || 'Sin categoria';

        return `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        ${displayName}
                    </span>
                </td>
                <td class="px-6 py-4">
                    <span class="${colorClass} font-medium">${grade.score}/${grade.max_score}</span>
                    <span class="text-gray-400 text-sm ml-1">(${percentage}%)</span>
                </td>
                <td class="px-6 py-4 text-gray-500 text-sm">${formatDate(grade.date)}</td>
            </tr>
        `;
    }).join('');
}

function renderAttendance(attendance) {
    const tbody = document.getElementById('attendance-table');

    if (attendance.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="3" class="px-6 py-4 text-center text-gray-500">Sin registros de asistencia</td></tr>
        `;
        return;
    }

    const statusNames = {
        present: 'Presente',
        absent: 'Ausente',
        late: 'Tarde',
        excused: 'Justificado'
    };

    const statusColors = {
        present: 'bg-green-100 text-green-800',
        absent: 'bg-red-100 text-red-800',
        late: 'bg-yellow-100 text-yellow-800',
        excused: 'bg-blue-100 text-blue-800'
    };

    tbody.innerHTML = attendance.map(record => {
        const colorClass = statusColors[record.status] || 'bg-gray-100 text-gray-800';
        const statusName = statusNames[record.status] || record.status;

        return `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 text-gray-700">${formatDate(record.date)}</td>
                <td class="px-6 py-4">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}">
                        ${statusName}
                    </span>
                </td>
                <td class="px-6 py-4 text-gray-500 text-sm">${record.notes || '-'}</td>
            </tr>
        `;
    }).join('');
}

// Calculos
function calculateAttendanceRate(attendance) {
    const rateEl = document.getElementById('attendance-rate');

    if (attendance.length === 0) {
        rateEl.textContent = 'N/A';
        return;
    }

    const present = attendance.filter(r => r.status === 'present' || r.status === 'late').length;
    const rate = ((present / attendance.length) * 100).toFixed(1);
    rateEl.textContent = `${rate}%`;
}

// Assignments (Retos)
async function loadAssignments() {
    const container = document.getElementById('assignments-container');
    if (!container) return;

    try {
        const assignments = await apiCall(`/students/me/assignments?class_id=${selectedClassId}`);

        if (assignments.length === 0) {
            container.innerHTML = '<p class="text-center text-gray-500 py-4">No hay retos asignados</p>';
            return;
        }

        container.innerHTML = assignments.map(a => {
            const now = new Date();
            const due = new Date(a.due_date);
            const isPast = now > due;
            const diff = due - now;

            // Status and badge
            let statusBadge, statusColor;
            if (a.submission?.grade !== null && a.submission?.grade !== undefined) {
                statusBadge = `Calificado: ${a.submission.grade}/${a.max_points}`;
                statusColor = 'bg-blue-100 text-blue-800';
            } else if (a.submission) {
                statusBadge = 'Entregado';
                statusColor = 'bg-green-100 text-green-800';
            } else if (isPast) {
                statusBadge = 'Vencido';
                statusColor = 'bg-red-100 text-red-800';
            } else {
                statusBadge = 'Pendiente';
                statusColor = 'bg-yellow-100 text-yellow-800';
            }

            // Countdown
            let countdown = '';
            if (!a.submission && !isPast) {
                const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                if (days > 0) {
                    countdown = `${days}d ${hours}h restantes`;
                } else {
                    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                    countdown = `${hours}h ${minutes}m restantes`;
                }
            }

            // Penalty badge for submitted assignments
            let penaltyHtml = '';
            if (a.submission) {
                const pct = a.submission.penalty_pct ?? 100;
                let penaltyColor, penaltyLabel;
                if (pct === 100) {
                    penaltyColor = 'bg-green-100 text-green-800';
                    penaltyLabel = 'A tiempo';
                } else if (pct === 90) {
                    penaltyColor = 'bg-yellow-100 text-yellow-800';
                    penaltyLabel = `Penalizacion: ${100 - pct}%`;
                } else if (pct === 50) {
                    penaltyColor = 'bg-orange-100 text-orange-800';
                    penaltyLabel = `Penalizacion: ${100 - pct}%`;
                } else {
                    penaltyColor = 'bg-red-100 text-red-800';
                    penaltyLabel = `Penalizacion: ${100 - pct}%`;
                }
                penaltyHtml = `<span class="text-xs px-2 py-0.5 rounded ${penaltyColor}">${penaltyLabel}</span>`;
            }

            // Drive link for submitted assignments
            const driveLinkHtml = a.submission?.drive_url ? `
                <div class="mt-2">
                    <a href="${a.submission.drive_url}" target="_blank" rel="noopener noreferrer"
                       class="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-800 underline">
                        Ver entrega
                    </a>
                </div>
            ` : '';

            // Submit form (hidden in preview mode or if already submitted)
            const showSubmit = !a.submission && !previewMode;
            const submitHtml = showSubmit ? `
                <div class="mt-3 pt-3 border-t border-gray-100">
                    <div class="flex gap-2">
                        <input type="url" id="submit-url-${a.id}" placeholder="https://drive.google.com/..."
                               class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none" />
                        <button onclick="submitAssignment(${a.id})"
                                class="self-end px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-indigo-700 transition">
                            Enviar
                        </button>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">Comparte tu archivo de Google Drive y pega el enlace aqui</p>
                </div>
            ` : '';

            // Feedback display
            const feedbackHtml = a.submission?.feedback ? `
                <div class="mt-2 p-2 bg-blue-50 rounded text-sm text-blue-800">
                    <span class="font-medium">Retroalimentacion:</span> ${a.submission.feedback}
                </div>
            ` : '';

            return `
                <div class="border border-gray-200 rounded-lg p-4">
                    <div class="flex flex-col sm:flex-row justify-between gap-2">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="font-medium text-gray-800">${a.title}</span>
                                <span class="text-xs px-2 py-0.5 rounded ${statusColor}">${statusBadge}</span>
                            </div>
                            ${a.description ? `<p class="text-gray-600 text-sm mb-1">${a.description}</p>` : ''}
                            <div class="flex items-center gap-3 text-xs text-gray-500">
                                <span>Fecha limite: ${formatDate(a.due_date.split('T')[0])}</span>
                                ${countdown ? `<span class="text-amber-600 font-medium">${countdown}</span>` : ''}
                            </div>
                        </div>
                    </div>
                    ${feedbackHtml}
                    ${driveLinkHtml}
                    ${a.submission?.is_late ? `<div class="mt-1 flex items-center gap-2">${penaltyHtml}</div>` : ''}
                    ${submitHtml}
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error al cargar retos:', error);
        container.innerHTML = '<p class="text-center text-gray-500 py-4">No se pudieron cargar los retos</p>';
    }
}

async function submitAssignment(assignmentId) {
    const urlInput = document.getElementById(`submit-url-${assignmentId}`);
    const driveUrl = urlInput?.value.trim();

    if (!driveUrl) {
        alert('Por favor ingresa un enlace de Google Drive');
        return;
    }

    try {
        await apiCall(`/students/me/assignments/${assignmentId}/submit`, {
            method: 'POST',
            body: JSON.stringify({ drive_url: driveUrl })
        });

        loadAssignments();
    } catch (error) {
        alert('Error al enviar reto: ' + error.message);
    }
}

// Formulario de participacion
document.getElementById('participation-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!selectedClassId) {
        alert('Selecciona una clase primero');
        return;
    }

    const description = document.getElementById('description').value;
    const points = parseInt(document.getElementById('points').value);
    const successEl = document.getElementById('participation-success');

    try {
        await apiCall('/participation', {
            method: 'POST',
            body: JSON.stringify({ description, points, class_id: selectedClassId })
        });

        successEl.classList.remove('hidden');
        setTimeout(() => successEl.classList.add('hidden'), 3000);

        document.getElementById('description').value = '';
        document.getElementById('points').value = '1';

        const totalEl = document.getElementById('total-participation');
        const current = parseInt(totalEl.textContent) || 0;
        totalEl.textContent = current + points;

    } catch (error) {
        alert('Error al enviar participacion: ' + error.message);
    }
});

// Helpers
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-MX', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
    });
}

// Inicializacion
async function init() {
    try {
        const config = await fetch('/api/config').then(r => r.json());
        googleClientId = config.google_client_id;
    } catch (error) {
        console.error('Error al obtener configuracion:', error);
    }

    // Check for teacher preview mode
    if (sessionStorage.getItem('teacherPreviewMode') === 'true' && authToken) {
        previewMode = true;
        previewStudentId = parseInt(sessionStorage.getItem('previewStudentId'));
        selectedClassId = parseInt(sessionStorage.getItem('previewClassId'));
        const previewClassName = sessionStorage.getItem('previewClassName') || 'Clase';

        try {
            // Fetch impersonated student info (X-Impersonate header is added by apiCall)
            currentStudent = await apiCall('/students/me');

            // Build a fake enrolledClasses entry so the class selector works
            enrolledClasses = [{
                class_id: selectedClassId,
                class_name: previewClassName,
                class_code: '',
                joined_at: new Date().toISOString(),
            }];

            showDashboard();
            loadDashboardData();
        } catch (error) {
            console.error('Error en modo preview:', error);
            exitPreviewMode();
        }
        return;
    }

    if (authToken) {
        try {
            currentStudent = await apiCall('/students/me');
            await checkEnrollment();
        } catch (error) {
            logout();
        }
    } else {
        showLogin();
        if (typeof google !== 'undefined') {
            initGoogleSignIn();
        } else {
            window.addEventListener('load', () => {
                setTimeout(initGoogleSignIn, 100);
            });
        }
    }

    document.getElementById('total-participation').textContent = '0';
}

init();
