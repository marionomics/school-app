// Estado
let authToken = localStorage.getItem('authToken');
let currentTeacher = null;
let googleClientId = null;
let classes = [];

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

// UI Functions
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

// Data Loading
async function loadInitialData() {
    await loadClasses();
    await loadGlobalStats();
}

// Classes
async function loadClasses() {
    try {
        classes = await apiCall('/classes/teaching');
        renderClasses();
    } catch (error) {
        console.error('Error al cargar clases:', error);
        document.getElementById('classes-list').innerHTML =
            '<p class="text-center text-red-500 py-4">Error al cargar clases</p>';
    }
}

async function loadGlobalStats() {
    // Update class count
    document.getElementById('stat-total-classes').textContent = classes.length;

    // Calculate total students
    const totalStudents = classes.reduce((sum, c) => sum + (c.student_count || 0), 0);
    document.getElementById('stat-total-students').textContent = totalStudents;

    // Load pending participation count across all classes
    let pendingCount = 0;
    let totalGrades = 0;
    let gradeCount = 0;

    for (const c of classes) {
        try {
            const dashboard = await apiCall(`/admin/classes/${c.id}/dashboard`);
            pendingCount += dashboard.stats.pending_participation || 0;
            if (dashboard.stats.average_grade > 0) {
                totalGrades += dashboard.stats.average_grade;
                gradeCount++;
            }
        } catch (error) {
            console.error(`Error loading stats for class ${c.id}:`, error);
        }
    }

    document.getElementById('stat-pending-participation').textContent = pendingCount;
    document.getElementById('stat-overall-average').textContent =
        gradeCount > 0 ? (totalGrades / gradeCount).toFixed(1) : '--';
}

function renderClasses() {
    const container = document.getElementById('classes-list');

    if (classes.length === 0) {
        container.innerHTML = `
            <div class="text-center py-12">
                <svg class="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
                </svg>
                <p class="text-gray-500 mb-4">No tienes clases creadas aun</p>
                <button onclick="openCreateClassModal()"
                        class="bg-primary hover:bg-indigo-700 text-white font-medium py-2 px-6 rounded-lg transition">
                    Crear tu primera clase
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = classes.map(c => `
        <div class="border border-gray-200 rounded-xl p-5 hover:shadow-lg hover:border-primary/30 transition cursor-pointer group"
             onclick="openClassDashboard(${c.id})">
            <div class="flex flex-col sm:flex-row justify-between gap-4">
                <div class="flex-1">
                    <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-semibold text-gray-800 group-hover:text-primary transition">${c.name}</h3>
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            ${c.student_count || 0} estudiante${c.student_count !== 1 ? 's' : ''}
                        </span>
                    </div>
                    <div class="flex items-center gap-3">
                        <code class="bg-gray-100 px-3 py-1 rounded-lg text-sm font-mono text-gray-700">${c.code}</code>
                        <button onclick="event.stopPropagation(); copyCode('${c.code}')"
                                class="text-gray-400 hover:text-primary transition" title="Copiar codigo">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="flex items-center gap-3">
                    <div class="text-right hidden sm:block">
                        <p class="text-xs text-gray-400">Clic para abrir</p>
                        <p class="text-sm font-medium text-primary">Dashboard →</p>
                    </div>
                    <button onclick="event.stopPropagation(); deleteClass(${c.id})"
                            class="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition"
                            title="Eliminar clase">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                        </svg>
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

function openClassDashboard(classId) {
    window.location.href = `/admin/class/${classId}`;
}

async function deleteClass(classId) {
    const classToDelete = classes.find(c => c.id === classId);
    if (!confirm(`¿Estas seguro de eliminar la clase "${classToDelete?.name}"? Esta accion no se puede deshacer.`)) {
        return;
    }

    try {
        await apiCall(`/classes/teaching/${classId}`, { method: 'DELETE' });
        await loadClasses();
        await loadGlobalStats();
    } catch (error) {
        alert('Error al eliminar clase: ' + error.message);
    }
}

// Create Class Modal
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
        await loadGlobalStats();
    } catch (error) {
        alert('Error al crear clase: ' + error.message);
    }
});

// Initialization
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
