// Estado
let authToken = localStorage.getItem('authToken');
let currentStudent = null;
let googleClientId = null;

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
        throw new Error(`Error de API: ${response.status}`);
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
        showDashboard();
        loadDashboardData();
    } catch (error) {
        console.error('Error de autenticación:', error);
        errorEl.textContent = 'Error de autenticación. Por favor intenta de nuevo.';
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
        console.error('Error al cerrar sesión:', error);
    }

    authToken = null;
    currentStudent = null;
    localStorage.removeItem('authToken');
    showLogin();

    if (googleClientId) {
        initGoogleSignIn();
    }
}

// Funciones de UI
function showLogin() {
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('dashboard-section').classList.add('hidden');
}

function showDashboard() {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('dashboard-section').classList.remove('hidden');

    if (currentStudent) {
        document.getElementById('student-name').textContent = currentStudent.name;
    }
}

// Carga de datos
async function loadDashboardData() {
    await Promise.all([
        loadGrades(),
        loadAttendance()
    ]);
}

async function loadGrades() {
    try {
        const grades = await apiCall('/students/me/grades');
        renderGrades(grades);
        calculateAverageGrade(grades);
    } catch (error) {
        console.error('Error al cargar calificaciones:', error);
        document.getElementById('grades-table').innerHTML = `
            <tr><td colspan="3" class="px-6 py-4 text-center text-gray-500">Error al cargar calificaciones</td></tr>
        `;
    }
}

async function loadAttendance() {
    try {
        const attendance = await apiCall('/students/me/attendance');
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
            <tr><td colspan="3" class="px-6 py-4 text-center text-gray-500">Sin calificaciones aún</td></tr>
        `;
        return;
    }

    const categoryNames = {
        homework: 'Tarea',
        quiz: 'Quiz',
        exam: 'Examen',
        project: 'Proyecto'
    };

    tbody.innerHTML = grades.map(grade => {
        const percentage = ((grade.score / grade.max_score) * 100).toFixed(1);
        const colorClass = percentage >= 70 ? 'text-green-600' : percentage >= 50 ? 'text-yellow-600' : 'text-red-600';
        const categoryName = categoryNames[grade.category] || grade.category;

        return `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        ${categoryName}
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

// Cálculos
function calculateAverageGrade(grades) {
    const avgEl = document.getElementById('avg-grade');

    if (grades.length === 0) {
        avgEl.textContent = 'N/A';
        return;
    }

    const totalPercentage = grades.reduce((sum, grade) => {
        return sum + (grade.score / grade.max_score) * 100;
    }, 0);

    const average = (totalPercentage / grades.length).toFixed(1);
    avgEl.textContent = `${average}%`;
}

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

// Formulario de participación
document.getElementById('participation-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const description = document.getElementById('description').value;
    const points = parseInt(document.getElementById('points').value);
    const successEl = document.getElementById('participation-success');

    try {
        await apiCall('/participation', {
            method: 'POST',
            body: JSON.stringify({ description, points })
        });

        successEl.classList.remove('hidden');
        setTimeout(() => successEl.classList.add('hidden'), 3000);

        document.getElementById('description').value = '';
        document.getElementById('points').value = '1';

        const totalEl = document.getElementById('total-participation');
        const current = parseInt(totalEl.textContent) || 0;
        totalEl.textContent = current + points;

    } catch (error) {
        alert('Error al enviar participación. Por favor intenta de nuevo.');
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

// Inicialización
async function init() {
    try {
        const config = await fetch('/api/config').then(r => r.json());
        googleClientId = config.google_client_id;
    } catch (error) {
        console.error('Error al obtener configuración:', error);
    }

    if (authToken) {
        try {
            currentStudent = await apiCall('/students/me');
            showDashboard();
            loadDashboardData();
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
