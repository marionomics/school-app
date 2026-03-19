// Estado
let authToken = localStorage.getItem('authToken');
let currentStudent = null;
let googleClientId = null;
let enrolledClasses = [];
let selectedClassId = localStorage.getItem('selectedClassId') ? parseInt(localStorage.getItem('selectedClassId')) : null;
let previewMode = false;
let previewStudentId = null;
let fileUploadsEnabled = false;

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

function apiUpload(endpoint, formData, onProgress) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_BASE}${endpoint}`);

        if (authToken) {
            xhr.setRequestHeader('Authorization', `Bearer ${authToken}`);
        }
        if (previewMode && previewStudentId) {
            xhr.setRequestHeader('X-Impersonate', previewStudentId.toString());
        }

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable && onProgress) {
                onProgress(Math.round((e.loaded / e.total) * 100));
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                resolve(JSON.parse(xhr.responseText));
            } else {
                const err = JSON.parse(xhr.responseText || '{}');
                reject(new Error(err.detail || `Error: ${xhr.status}`));
            }
        });

        xhr.addEventListener('error', () => reject(new Error('Error de red')));
        xhr.send(formData);
    });
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function viewSubmissionFile(submissionId) {
    try {
        const data = await apiCall(`/students/submissions/${submissionId}/file`);
        window.open(data.download_url, '_blank');
    } catch (error) {
        alert('Error al abrir archivo: ' + error.message);
    }
}

async function uploadAssignmentFile(assignmentId) {
    const fileInput = document.getElementById(`file-input-${assignmentId}`);
    const file = fileInput?.files[0];
    if (!file) {
        alert('Selecciona un archivo primero');
        return;
    }

    const progressBar = document.getElementById(`upload-progress-${assignmentId}`);
    const progressFill = document.getElementById(`upload-progress-fill-${assignmentId}`);
    const uploadBtn = document.getElementById(`upload-btn-${assignmentId}`);

    progressBar.classList.remove('hidden');
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Subiendo...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        await apiUpload(`/students/me/assignments/${assignmentId}/upload`, formData, (pct) => {
            progressFill.style.width = pct + '%';
        });
        loadAssignments();
    } catch (error) {
        alert('Error al subir archivo: ' + error.message);
    } finally {
        progressBar.classList.add('hidden');
        progressFill.style.width = '0%';
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Subir';
    }
}

function handleFileSelect(assignmentId, input) {
    const infoEl = document.getElementById(`file-info-${assignmentId}`);
    const uploadBtn = document.getElementById(`upload-btn-${assignmentId}`);
    if (input.files.length > 0) {
        const file = input.files[0];
        infoEl.textContent = `${file.name} (${formatFileSize(file.size)})`;
        infoEl.classList.remove('hidden');
        uploadBtn.classList.remove('hidden');
    } else {
        infoEl.classList.add('hidden');
        uploadBtn.classList.add('hidden');
    }
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
        const forumLink = document.getElementById('nav-forum-link');
        if (forumLink) forumLink.classList.remove('hidden');
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
                    class="px-3 py-1 text-sm bg-primary text-white rounded hover:bg-secondary">
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
        loadForumPoints(),
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
        <div class="flex justify-between items-center p-3 bg-primary-5 rounded-lg mt-3">
            <div>
                <span class="font-medium text-secondary">Participacion</span>
                <span class="text-xs text-primary ml-2">(${calc.participation_points} pts aprobados)</span>
            </div>
            <span class="font-medium text-secondary">+${calc.participation_contribution.toFixed(1)} pts</span>
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

    // Forum points
    if (calc.forum_points > 0) {
        html += `
            <div class="flex justify-between items-center p-3 bg-amber-50 rounded-lg mt-3 border border-amber-100">
                <div>
                    <span class="font-medium text-amber-800">🏆 Puntos de Foro</span>
                    <span class="text-xs text-amber-600 ml-2">(likes y publicaciones en el foro)</span>
                </div>
                <span class="font-medium text-amber-700">+${calc.forum_points.toFixed(2)} pts</span>
            </div>
        `;
    }

    // Absence penalty
    if (calc.absence_count > 0) {
        html += `
            <div class="flex justify-between items-center p-3 bg-red-50 rounded-lg mt-3">
                <div>
                    <span class="font-medium text-red-800">Faltas injustificadas</span>
                    <span class="text-xs text-red-600 ml-2">(${calc.absence_count} falta(s) × -1 punto)</span>
                </div>
                <span class="font-medium text-red-800">-${calc.absence_penalty.toFixed(1)} pts</span>
            </div>
        `;
    }

    // Total
    const gradingMode = calc.grading_mode || 'points';
    const finalLabel = gradingMode === 'points' ? 'Calificacion Final (sin límite)' : 'Calificacion Final';
    const maxBase = calc.max_base_grade != null ? calc.max_base_grade : null;
    const baseNote = gradingMode === 'points' && maxBase != null
        ? `<span class="text-xs font-normal text-gray-500 ml-1">(base: ${maxBase.toFixed(0)} pts)</span>`
        : '';
    html += `
        <div class="flex justify-between items-center p-3 bg-primary-10 rounded-lg mt-4 border-t-2 border-primary">
            <span class="font-bold text-gray-800">${finalLabel}${baseNote}</span>
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

async function loadForumPoints() {
    try {
        const result = await apiCall(`/forum/points/summary?class_id=${selectedClassId}`);
        document.getElementById('forum-points-stat').textContent = '+' + result.total.toFixed(2);
    } catch (e) {
        document.getElementById('forum-points-stat').textContent = '0';
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
            <tr><td colspan="4" class="px-6 py-4 text-center text-gray-500">Sin registros de asistencia</td></tr>
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

        // Justification column
        let justificationHtml = '-';
        const canJustify = (record.status === 'absent' || record.status === 'late') && record.justification_status !== 'approved';

        if (record.justification_status === 'approved') {
            justificationHtml = '<span class="text-xs px-2 py-0.5 rounded bg-green-100 text-green-700">Aprobada</span>';
        } else if (record.justification_status === 'pending') {
            justificationHtml = `
                <span class="text-xs px-2 py-0.5 rounded bg-yellow-100 text-yellow-700">En revision</span>
                ${record.has_justification_file ? `<button onclick="viewJustificationFile(${record.id})" class="text-xs text-primary hover:underline ml-1">Ver archivo</button>` : ''}
            `;
        } else if (record.justification_status === 'rejected') {
            justificationHtml = `
                <span class="text-xs px-2 py-0.5 rounded bg-red-100 text-red-700">Rechazada</span>
                ${!previewMode ? `<button onclick="showJustificationUpload(${record.id})" class="text-xs text-primary hover:underline ml-1">Re-enviar</button>` : ''}
            `;
        } else if (canJustify && !previewMode) {
            justificationHtml = `
                <button onclick="showJustificationUpload(${record.id})" class="text-xs px-2 py-1 bg-primary-10 text-secondary rounded hover:bg-primary-20 transition">
                    Justificar
                </button>
            `;
        }

        return `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 text-gray-700">${formatDate(record.date)}</td>
                <td class="px-6 py-4">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}">
                        ${statusName}
                    </span>
                </td>
                <td class="px-6 py-4 text-gray-500 text-sm">${record.notes || '-'}</td>
                <td class="px-6 py-4">
                    ${justificationHtml}
                    <div id="justify-upload-${record.id}" class="hidden mt-2"></div>
                </td>
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

            const hasSubmission = !!a.submission;
            const isGraded = a.submission?.grade !== null && a.submission?.grade !== undefined;

            // Submission details block (when submitted)
            let submissionDetailsHtml = '';
            if (hasSubmission) {
                const submittedDate = new Date(a.submission.submitted_at).toLocaleString('es-MX', {
                    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
                });

                const fileInfoLine = a.submission.has_file
                    ? `<div class="flex items-center gap-1">
                            <span class="font-medium">Archivo:</span>
                            <button onclick="viewSubmissionFile(${a.submission.id})"
                                    class="text-primary hover:text-secondary underline">
                                ${a.submission.file_name || 'archivo'} (${formatFileSize(a.submission.file_size || 0)})
                            </button>
                       </div>`
                    : '';

                const driveLine = a.submission.drive_url
                    ? `<div class="flex items-center gap-1">
                            <span class="font-medium">Enlace:</span>
                            <a href="${a.submission.drive_url}" target="_blank" rel="noopener noreferrer"
                               class="text-primary hover:text-secondary underline">Google Drive</a>
                       </div>`
                    : '';

                const canDelete = !isGraded && !previewMode;

                submissionDetailsHtml = `
                    <div class="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm">
                        <div class="flex justify-between items-start gap-3">
                            <div class="space-y-1 text-gray-600">
                                ${fileInfoLine}
                                ${driveLine}
                                <div>Entregado: ${submittedDate}</div>
                                ${a.submission.is_late ? `<div>${penaltyHtml}</div>` : ''}
                            </div>
                            ${canDelete ? `
                            <button onclick="deleteSubmission(${a.submission.id})"
                                    class="shrink-0 text-xs px-3 py-1.5 bg-red-100 text-red-700 rounded hover:bg-red-200 transition">
                                Eliminar Entrega
                            </button>
                            ` : ''}
                        </div>
                    </div>
                `;
            }

            // Feedback display
            const feedbackHtml = a.submission?.feedback ? `
                <div class="mt-2 p-2 bg-blue-50 rounded text-sm text-blue-800">
                    <span class="font-medium">Retroalimentacion:</span> ${a.submission.feedback}
                </div>
            ` : '';

            // Submit form (only when no submission)
            const canSubmit = !hasSubmission && !previewMode;
            const submitHtml = canSubmit ? `
                <div class="mt-3 pt-3 border-t border-gray-100">
                    <div class="flex gap-2">
                        <input type="url" id="submit-url-${a.id}" placeholder="https://drive.google.com/..."
                               class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none" />
                        <button onclick="submitAssignment(${a.id})"
                                class="self-end px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-secondary transition">
                            Enviar
                        </button>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">Comparte tu archivo de Google Drive y pega el enlace aqui</p>
                    ${fileUploadsEnabled ? `
                    <div class="mt-3 pt-3 border-t border-gray-100">
                        <div class="flex items-center gap-2">
                            <label class="flex-1 flex items-center gap-2 px-3 py-2 border border-gray-300 border-dashed rounded-lg text-sm text-gray-500 cursor-pointer hover:bg-gray-50">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                                <span>Subir archivo</span>
                                <input type="file" id="file-input-${a.id}" class="hidden"
                                       accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip,.rar,.7z,.png,.jpg,.jpeg,.gif,.webp,.svg"
                                       onchange="handleFileSelect(${a.id}, this)" />
                            </label>
                            <button id="upload-btn-${a.id}" onclick="uploadAssignmentFile(${a.id})"
                                    class="hidden px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-secondary transition">
                                Subir
                            </button>
                        </div>
                        <p id="file-info-${a.id}" class="text-xs text-gray-500 mt-1 hidden"></p>
                        <div id="upload-progress-${a.id}" class="hidden mt-2 w-full bg-gray-200 rounded-full h-2">
                            <div id="upload-progress-fill-${a.id}" class="bg-primary h-2 rounded-full transition-all" style="width: 0%"></div>
                        </div>
                        <p class="text-xs text-gray-400 mt-1">PDF, DOCX, ZIP, imagenes. Max 10 MB</p>
                    </div>
                    ` : ''}
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
                    ${submissionDetailsHtml}
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

async function deleteSubmission(submissionId) {
    if (!confirm('¿Estas seguro que quieres eliminar tu entrega?\n\nNo podras recuperar el archivo. Tendras que volver a subirlo.')) {
        return;
    }

    try {
        await apiCall(`/students/submissions/${submissionId}`, { method: 'DELETE' });
        loadAssignments();
    } catch (error) {
        alert('Error al eliminar entrega: ' + error.message);
    }
}

// Justification functions
function showJustificationUpload(attendanceId) {
    const container = document.getElementById(`justify-upload-${attendanceId}`);
    if (!container) return;

    if (!container.classList.contains('hidden')) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    container.innerHTML = `
        <div class="flex items-center gap-2">
            <label class="flex-1 flex items-center gap-2 px-3 py-2 border border-gray-300 border-dashed rounded-lg text-xs text-gray-500 cursor-pointer hover:bg-gray-50">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                <span>Subir justificante (PDF, imagen)</span>
                <input type="file" id="justify-file-${attendanceId}" class="hidden"
                       accept=".pdf,.png,.jpg,.jpeg,.gif,.webp"
                       onchange="handleJustificationFileSelect(${attendanceId}, this)" />
            </label>
        </div>
        <p id="justify-file-info-${attendanceId}" class="text-xs text-gray-500 mt-1 hidden"></p>
        <button id="justify-upload-btn-${attendanceId}" onclick="uploadJustification(${attendanceId})"
                class="hidden mt-1 px-3 py-1 text-xs bg-primary text-white rounded hover:bg-secondary transition">
            Enviar justificante
        </button>
        <div id="justify-progress-${attendanceId}" class="hidden mt-1 w-full bg-gray-200 rounded-full h-1.5">
            <div id="justify-progress-fill-${attendanceId}" class="bg-primary h-1.5 rounded-full transition-all" style="width: 0%"></div>
        </div>
    `;
}

function handleJustificationFileSelect(attendanceId, input) {
    const infoEl = document.getElementById(`justify-file-info-${attendanceId}`);
    const btn = document.getElementById(`justify-upload-btn-${attendanceId}`);
    if (input.files.length > 0) {
        const file = input.files[0];
        infoEl.textContent = `${file.name} (${formatFileSize(file.size)})`;
        infoEl.classList.remove('hidden');
        btn.classList.remove('hidden');
    } else {
        infoEl.classList.add('hidden');
        btn.classList.add('hidden');
    }
}

async function uploadJustification(attendanceId) {
    const fileInput = document.getElementById(`justify-file-${attendanceId}`);
    const file = fileInput?.files[0];
    if (!file) {
        alert('Selecciona un archivo primero');
        return;
    }

    const progressBar = document.getElementById(`justify-progress-${attendanceId}`);
    const progressFill = document.getElementById(`justify-progress-fill-${attendanceId}`);
    const btn = document.getElementById(`justify-upload-btn-${attendanceId}`);

    progressBar.classList.remove('hidden');
    btn.disabled = true;
    btn.textContent = 'Enviando...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        await apiUpload(`/students/me/attendance/${attendanceId}/justify`, formData, (pct) => {
            progressFill.style.width = pct + '%';
        });
        // Reload attendance table
        loadAttendance();
    } catch (error) {
        alert('Error al enviar justificante: ' + error.message);
    } finally {
        progressBar.classList.add('hidden');
        progressFill.style.width = '0%';
        btn.disabled = false;
        btn.textContent = 'Enviar justificante';
    }
}

async function viewJustificationFile(attendanceId) {
    try {
        const data = await apiCall(`/students/attendance/${attendanceId}/justification-file`);
        window.open(data.download_url, '_blank');
    } catch (error) {
        alert('Error al abrir archivo: ' + error.message);
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
        fileUploadsEnabled = config.file_uploads_enabled || false;
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
    document.getElementById('forum-points-stat').textContent = '0';
}

init();
