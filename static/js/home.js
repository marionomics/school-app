// ==================== State ====================
let authToken = localStorage.getItem('authToken');
let currentUser = null;
let googleClientId = null;
let previewMode = false;
let previewStudentId = null;

// Forum state
let forumClasses = [];
let posts = [];
let currentPage = 1;
let hasMorePosts = false;
let openPostId = null;
let currentModalPost = null;
let activeReplyToId = null;

// Participation tap state
let tapCount = 0;
let tapTimer = null;
let tapDescription = '';

// Justification modal state
let justModalClassId = null;
let justModalAbsences = {};  // { class_id: [attendance records] }

// Dashboard state
let enrolledClasses = [];   // student enrolled classes
let teachingClasses = [];   // teacher's classes
let gradesByClassId = {};   // { class_id: gradeCalcResponse }
let assignmentsByClassId = {}; // { class_id: [...assignments] }
let fileUploadsEnabled = false;

const API = '/api';

// ==================== API ====================

async function apiCall(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    if (previewMode && previewStudentId) headers['X-Impersonate'] = String(previewStudentId);

    const res = await fetch(`${API}${endpoint}`, { ...options, headers });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Error desconocido' }));
        if (res.status === 401) { authToken = null; localStorage.removeItem('authToken'); showLogin(); return; }
        const msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
        throw new Error(msg);
    }
    return res.json();
}

function apiUpload(endpoint, formData, onProgress) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API}${endpoint}`);
        if (authToken) xhr.setRequestHeader('Authorization', `Bearer ${authToken}`);
        if (previewMode && previewStudentId) xhr.setRequestHeader('X-Impersonate', String(previewStudentId));
        xhr.upload.addEventListener('progress', e => {
            if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
        });
        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
            else { const err = JSON.parse(xhr.responseText || '{}'); reject(new Error(err.detail || `Error: ${xhr.status}`)); }
        });
        xhr.addEventListener('error', () => reject(new Error('Error de red')));
        xhr.send(formData);
    });
}

function logout() {
    apiCall('/auth/logout', { method: 'POST' }).catch(() => {});
    authToken = null; currentUser = null; enrolledClasses = []; teachingClasses = [];
    forumClasses = []; posts = [];
    localStorage.removeItem('authToken');
    showLogin();
}

function exitPreviewMode() {
    sessionStorage.removeItem('teacherPreviewMode');
    sessionStorage.removeItem('previewClassId');
    sessionStorage.removeItem('previewStudentId');
    sessionStorage.removeItem('previewClassName');
    window.location.href = '/admin';
}

// ==================== Google Auth ====================

async function handleGoogleCredentialResponse(response) {
    const err = document.getElementById('login-error');
    err.classList.add('hidden');
    try {
        const result = await apiCall('/auth/google', {
            method: 'POST',
            body: JSON.stringify({ credential: response.credential }),
        });
        authToken = result.token;
        currentUser = result.student;
        localStorage.setItem('authToken', authToken);
        await boot();
    } catch (e) {
        err.textContent = 'Error de autenticacion. Por favor intenta de nuevo.';
        err.classList.remove('hidden');
    }
}

function initGoogleSignIn() {
    if (!googleClientId) return;
    google.accounts.id.initialize({ client_id: googleClientId, callback: handleGoogleCredentialResponse });
    google.accounts.id.renderButton(document.getElementById('google-signin-container'), {
        theme: 'outline', size: 'large', width: 280,
    });
}

// ==================== Init ====================

async function init() {
    // Always fetch config first (sets fileUploadsEnabled and googleClientId)
    try {
        const cfg = await fetch('/api/config').then(r => r.json());
        googleClientId = cfg.google_client_id;
        fileUploadsEnabled = cfg.file_uploads_enabled || false;
    } catch (e) { /* non-fatal */ }

    // Check preview mode
    const params = new URLSearchParams(window.location.search);
    if (params.get('preview') === 'true' && sessionStorage.getItem('teacherPreviewMode')) {
        previewMode = true;
        previewStudentId = parseInt(sessionStorage.getItem('previewStudentId'));
    }

    if (!authToken) { showLogin(); return; }

    try {
        currentUser = await apiCall('/students/me');
        await boot();
    } catch (e) {
        showLogin();
    }
}

async function boot() {
    if (!currentUser) { showLogin(); return; }

    showApp();

    if (previewMode) {
        document.getElementById('preview-banner').classList.remove('hidden');
        const cn = sessionStorage.getItem('previewClassName') || 'Clase';
        document.getElementById('preview-class-name').textContent = cn;
    }

    // Update nav
    document.getElementById('nav-user-name').textContent = currentUser.name;
    setAvatarInitials('composer-avatar', currentUser.name);
    setAvatarInitials('modal-avatar', currentUser.name);

    if (currentUser.role === 'teacher') {
        document.getElementById('nav-admin-link').classList.remove('hidden');
    }

    // Hide composer in preview mode
    if (previewMode) {
        document.getElementById('composer-wrapper').classList.add('hidden');
    }

    // Load forum + dashboard in parallel
    await Promise.all([
        loadForumSection(),
        loadDashboardSection(),
    ]);

    // After dashboard loads, show participation form for students
    if (currentUser.role === 'student' && !previewMode) {
        renderParticipationSection();
    }
}

// ==================== Show / Hide ====================

function showLogin() {
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('app-section').classList.add('hidden');
    if (window.google) initGoogleSignIn();
    else window.addEventListener('load', () => setTimeout(initGoogleSignIn, 100));
}

function showApp() {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('app-section').classList.remove('hidden');
}


// ==================== Forum: load classes + posts ====================

async function loadForumSection() {
    try {
        forumClasses = await apiCall('/forum/classes');
    } catch (e) { forumClasses = []; }

    if (!forumClasses.length) {
        document.getElementById('posts-container').innerHTML = '';
        document.getElementById('forum-no-class').classList.remove('hidden');
        document.getElementById('composer-wrapper').classList.add('hidden');
        return;
    }

    // Populate class selector inside the composer
    const composerSel = document.getElementById('composer-class-selector');
    if (composerSel) {
        composerSel.innerHTML = forumClasses.map(c => `<option value="${c.id}">${escHtml(c.name)}</option>`).join('');
    }

    await loadPosts(true);
}

async function loadPosts(reset = false) {
    if (reset) { currentPage = 1; posts = []; }
    const container = document.getElementById('posts-container');
    if (reset) container.innerHTML = '<p class="text-center text-gray-400 text-sm py-6">Cargando...</p>';

    try {
        const data = await apiCall(`/forum/posts?page=${currentPage}&limit=10`);
        posts = reset ? data.posts : [...posts, ...data.posts];
        hasMorePosts = data.has_more;
        renderPosts(reset);
    } catch (e) {
        container.innerHTML = `<p class="text-center text-red-400 text-sm py-6">${e.message}</p>`;
    }
}

async function loadMorePosts() {
    currentPage += 1;
    await loadPosts(false);
}

function renderPosts(reset) {
    const container = document.getElementById('posts-container');
    const empty = document.getElementById('forum-empty');
    const loadMore = document.getElementById('load-more-container');

    if (!posts.length) {
        container.innerHTML = '';
        empty.classList.remove('hidden');
        loadMore.classList.add('hidden');
        return;
    }
    empty.classList.add('hidden');
    if (reset) {
        container.innerHTML = posts.map(renderPostCard).join('');
    } else {
        const newPosts = posts.slice(posts.length - (hasMorePosts ? 10 : posts.length - (currentPage - 1) * 10));
        container.insertAdjacentHTML('beforeend', newPosts.map(renderPostCard).join(''));
    }
    loadMore.classList.toggle('hidden', !hasMorePosts);
}

function renderPostCard(post) {
    const isTeacherPost = post.author_role === 'teacher';
    const initials = nameInitials(post.author_name);
    const avatarColor = isTeacherPost ? '#9C4927' : stringToColor(post.author_name);
    const timeStr = timeAgo(post.created_at);
    const isOwn = post.author_id === currentUser.id;
    const canDelete = isOwn || currentUser.role === 'teacher';
    const cantLike = isOwn;

    const classBadge = `<span class="px-2 py-0.5 bg-primary-10 text-secondary text-xs rounded-full">${escHtml(post.class_name)}</span>`;
    const authorLabel = isTeacherPost
        ? `<span class="font-medium text-secondary text-sm">👨‍🏫 ${escHtml(post.author_name)}</span><span class="text-secondary text-xs font-medium">• Profesor</span>${classBadge}`
        : `<span class="font-medium text-gray-800 text-sm">${escHtml(post.author_name)}</span>${classBadge}`;

    const pinnedBadge = post.pinned ? `<span class="text-amber-500 text-xs font-medium">📌 Fijado</span>` : '';
    const lockedBadge = post.locked ? `<span class="text-gray-400 text-xs">🔒</span>` : '';

    const likeBtn = cantLike
        ? `<span class="flex items-center gap-1 text-xs text-gray-300 cursor-not-allowed select-none">${heartIcon(false)} ${post.like_count}</span>`
        : `<button onclick="toggleLike(event,${post.id})" class="flex items-center gap-1 text-xs ${post.liked_by_me ? 'text-red-500' : 'text-gray-400 hover:text-red-400'} transition">
               ${heartIcon(post.liked_by_me)} <span id="like-count-${post.id}">${post.like_count}</span>
           </button>`;

    const teacherBtns = currentUser.role === 'teacher'
        ? `<button onclick="event.stopPropagation();togglePin(${post.id})" class="text-sm ${post.pinned ? 'text-amber-500 hover:text-amber-700' : 'text-gray-300 hover:text-amber-500'} transition" title="${post.pinned ? 'Desfijar' : 'Fijar'}">📌</button>
           <button onclick="event.stopPropagation();toggleLock(${post.id})" class="text-sm ${post.locked ? 'text-blue-400 hover:text-blue-600' : 'text-gray-300 hover:text-blue-400'} transition" title="${post.locked ? 'Desbloquear' : 'Bloquear'}">🔒</button>`
        : '';

    const delBtn = canDelete
        ? `<button onclick="deletePost(event,${post.id})" class="text-gray-300 hover:text-red-400 transition" title="Eliminar">
               <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
           </button>` : '';

    return `
    <article onclick="openPost(${post.id})"
             class="bg-white rounded-xl shadow-sm border ${post.pinned ? 'border-amber-200' : 'border-gray-100'} p-4 cursor-pointer hover:border-gray-200 hover:shadow transition">
        <div class="flex items-start gap-3">
            <div class="avatar text-white text-xs shrink-0" style="background:${avatarColor}">${initials}</div>
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap mb-1">
                    ${authorLabel} ${pinnedBadge} ${lockedBadge}
                    <span class="text-gray-400 text-xs ml-auto">${timeStr}</span>
                </div>
                ${post.title ? `<p class="font-semibold text-gray-800 text-sm mb-1">${escHtml(post.title)}</p>` : ''}
                <p class="text-gray-600 text-sm line-clamp-3 whitespace-pre-wrap">${escHtml(post.content)}</p>
                <div class="flex items-center gap-3 mt-3" onclick="event.stopPropagation()">
                    ${likeBtn}
                    <button onclick="openPost(${post.id})" class="flex items-center gap-1 text-xs text-gray-400 hover:text-primary transition">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                        ${post.comment_count}
                    </button>
                    ${post.points_earned > 0 ? `<span class="text-xs text-amber-500 font-medium">🏆 +${post.points_earned.toFixed(2)}</span>` : ''}
                    <span class="ml-auto flex items-center gap-2">${teacherBtns}${delBtn}</span>
                </div>
            </div>
        </div>
    </article>`;
}

// ==================== Forum: Composer ====================

function openComposer() {
    document.getElementById('composer-trigger').classList.add('hidden');
    document.getElementById('composer-form').classList.remove('hidden');
    document.getElementById('post-content').focus();
}

function closeComposer() {
    document.getElementById('composer-trigger').classList.remove('hidden');
    document.getElementById('composer-form').classList.add('hidden');
    document.getElementById('post-title').value = '';
    document.getElementById('post-content').value = '';
}

async function submitPost() {
    const title = document.getElementById('post-title').value.trim();
    const content = document.getElementById('post-content').value.trim();
    const classId = parseInt(document.getElementById('composer-class-selector')?.value);
    if (!content) { alert('El contenido no puede estar vacío.'); return; }
    if (!classId) { alert('Selecciona una clase.'); return; }
    try {
        const post = await apiCall('/forum/posts', {
            method: 'POST',
            body: JSON.stringify({ class_id: classId, title: title || null, content }),
        });
        closeComposer();
        posts.unshift(post);
        document.getElementById('forum-empty').classList.add('hidden');
        document.getElementById('posts-container').insertAdjacentHTML('afterbegin', renderPostCard(post));
    } catch (e) {
        alert('Error al publicar: ' + e.message);
    }
}

// ==================== Forum: Likes ====================

async function toggleLike(event, postId) {
    event.stopPropagation();
    const btn = event.currentTarget;
    try {
        const result = await apiCall(`/forum/posts/${postId}/like`, { method: 'POST' });
        const post = posts.find(p => p.id === postId);
        if (post) { post.like_count = result.like_count; post.liked_by_me = result.liked; if (result.post_points_earned !== undefined) post.points_earned = result.post_points_earned; }
        const countEl = document.getElementById(`like-count-${postId}`);
        if (countEl) countEl.textContent = result.like_count;
        if (result.liked) {
            btn.className = `flex items-center gap-1 text-xs text-red-500 transition`;
            btn.innerHTML = heartIcon(true) + ` <span id="like-count-${postId}">${result.like_count}</span>`;
            if (result.points_awarded > 0) _showLikeToast(result);
        } else {
            btn.className = `flex items-center gap-1 text-xs text-gray-400 hover:text-red-400 transition`;
            btn.innerHTML = heartIcon(false) + ` <span id="like-count-${postId}">${result.like_count}</span>`;
        }
    } catch (e) { alert(e.message); }
}

async function toggleModalLike(postId) {
    try {
        const result = await apiCall(`/forum/posts/${postId}/like`, { method: 'POST' });
        const btn = document.getElementById('modal-like-btn');
        if (btn) {
            btn.className = `flex items-center gap-1 text-sm ${result.liked ? 'text-red-500' : 'text-gray-500 hover:text-red-400'} transition`;
            btn.innerHTML = heartIcon(result.liked) + ` <span id="modal-like-count">${result.like_count}</span>`;
            btn.setAttribute('onclick', `toggleModalLike(${postId})`);
        }
        const post = posts.find(p => p.id === postId);
        if (post) { post.like_count = result.like_count; post.liked_by_me = result.liked; if (result.post_points_earned !== undefined) post.points_earned = result.post_points_earned; }
        const feedCount = document.getElementById(`like-count-${postId}`);
        if (feedCount) feedCount.textContent = result.like_count;
        if (result.liked && result.points_awarded > 0) _showLikeToast(result);
    } catch (e) { alert(e.message); }
}

function heartIcon(filled) {
    return filled
        ? `<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>`
        : `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>`;
}

// ==================== Forum: Delete ====================

async function deletePost(event, postId) {
    event.stopPropagation();
    const post = posts.find(p => p.id === postId);
    const isTeacherDeleting = currentUser.role === 'teacher' && post && post.author_id !== currentUser.id;
    const msg = isTeacherDeleting ? `¿Eliminar publicación de ${post.author_name}?` : '¿Estás seguro de eliminar esta publicación?';
    if (!confirm(msg)) return;
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE' });
        posts = posts.filter(p => p.id !== postId);
        document.querySelector(`article[onclick="openPost(${postId})"]`)?.remove();
        if (!posts.length) document.getElementById('forum-empty').classList.remove('hidden');
    } catch (e) { alert('Error al eliminar: ' + e.message); }
}

async function deleteModalPost() {
    if (!currentModalPost) return;
    const isTeacherDeleting = currentUser.role === 'teacher' && currentModalPost.author_id !== currentUser.id;
    const msg = isTeacherDeleting ? `¿Eliminar publicación de ${currentModalPost.author_name}?` : '¿Estás seguro de eliminar esta publicación?';
    if (!confirm(msg)) return;
    const postId = currentModalPost.id;
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE' });
        closePostModal();
        posts = posts.filter(p => p.id !== postId);
        document.querySelector(`article[onclick="openPost(${postId})"]`)?.remove();
        if (!posts.length) document.getElementById('forum-empty').classList.remove('hidden');
    } catch (e) { alert('Error al eliminar: ' + e.message); }
}

// ==================== Forum: Moderation ====================

async function togglePin(postId) {
    try {
        const result = await apiCall(`/forum/posts/${postId}/pin`, { method: 'PATCH' });
        const post = posts.find(p => p.id === postId);
        if (post) post.pinned = result.pinned;
        if (currentModalPost && currentModalPost.id === postId) {
            const fresh = await apiCall(`/forum/posts/${postId}`);
            renderModalPost(fresh); return;
        }
        if (post) _replaceCard(postId, post);
    } catch (e) { alert('Error: ' + e.message); }
}

async function toggleLock(postId) {
    try {
        const result = await apiCall(`/forum/posts/${postId}/lock`, { method: 'PATCH' });
        const post = posts.find(p => p.id === postId);
        if (post) post.locked = result.locked;
        if (currentModalPost && currentModalPost.id === postId) {
            const fresh = await apiCall(`/forum/posts/${postId}`);
            renderModalPost(fresh); return;
        }
        if (post) _replaceCard(postId, post);
    } catch (e) { alert('Error: ' + e.message); }
}

function _replaceCard(postId, post) {
    const card = document.querySelector(`article[onclick="openPost(${postId})"]`);
    if (card) { const t = document.createElement('div'); t.innerHTML = renderPostCard(post); card.replaceWith(t.firstElementChild); }
}

// ==================== Forum: Post Modal ====================

async function openPost(postId) {
    openPostId = postId;
    document.getElementById('post-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    document.getElementById('modal-post-body').innerHTML = '<p class="text-center text-gray-400 text-sm py-6">Cargando...</p>';
    document.getElementById('modal-replies').innerHTML = '';
    try {
        const post = await apiCall(`/forum/posts/${postId}`);
        renderModalPost(post);
    } catch (e) {
        document.getElementById('modal-post-body').innerHTML = `<p class="text-red-400 text-sm text-center py-4">${e.message}</p>`;
    }
}

function closePostModal() {
    document.getElementById('post-modal').classList.add('hidden');
    document.body.style.overflow = '';
    document.getElementById('modal-reply-input').value = '';
    openPostId = null; currentModalPost = null; activeReplyToId = null;
    document.getElementById('nested-reply-form')?.remove();
    const rc = document.getElementById('modal-reply-composer');
    if (rc) rc.style.display = '';
}

function renderModalPost(post) {
    currentModalPost = post;
    const isTeacherPost = post.author_role === 'teacher';
    const avatarColor = isTeacherPost ? '#9C4927' : stringToColor(post.author_name);
    const initials = nameInitials(post.author_name);
    const timeStr = timeAgo(post.created_at);
    const isOwn = post.author_id === currentUser.id;

    document.getElementById('modal-class-badge').textContent = post.class_name;

    const likeBtn = isOwn
        ? `<span class="flex items-center gap-1 text-sm text-gray-300 cursor-not-allowed">${heartIcon(false)} ${post.like_count}</span>`
        : `<button id="modal-like-btn" onclick="toggleModalLike(${post.id})"
               class="flex items-center gap-1 text-sm ${post.liked_by_me ? 'text-red-500' : 'text-gray-500 hover:text-red-400'} transition">
               ${heartIcon(post.liked_by_me)} <span id="modal-like-count">${post.like_count}</span>
           </button>`;

    const teacherBtns = currentUser.role === 'teacher'
        ? `<button onclick="togglePin(${post.id})" class="flex items-center gap-1 text-sm ${post.pinned ? 'text-amber-500 hover:text-amber-700' : 'text-gray-400 hover:text-amber-500'} transition">📌 ${post.pinned ? 'Desfijar' : 'Fijar'}</button>
           <button onclick="toggleLock(${post.id})" class="flex items-center gap-1 text-sm ${post.locked ? 'text-blue-400 hover:text-blue-600' : 'text-gray-400 hover:text-blue-400'} transition">🔒 ${post.locked ? 'Desbloquear' : 'Bloquear'}</button>`
        : '';

    const delBtn = (isOwn || currentUser.role === 'teacher')
        ? `<button onclick="deleteModalPost()" class="flex items-center gap-1 text-sm text-gray-400 hover:text-red-400 transition ml-auto">
               <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
               Eliminar
           </button>` : '';

    document.getElementById('modal-post-body').innerHTML = `
        <div class="flex items-start gap-3 mb-4">
            <div class="avatar text-white text-xs shrink-0" style="background:${avatarColor}">${initials}</div>
            <div>
                <p class="font-medium text-gray-800 text-sm">${isTeacherPost ? '👨‍🏫 ' : ''}${escHtml(post.author_name)}${isTeacherPost ? ' <span class="text-secondary text-xs">• Profesor</span>' : ''}</p>
                <p class="text-gray-400 text-xs">${timeStr}</p>
            </div>
        </div>
        ${post.title ? `<h2 class="font-bold text-gray-900 text-lg mb-2">${escHtml(post.title)}</h2>` : ''}
        <p class="text-gray-700 text-sm whitespace-pre-wrap leading-relaxed">${escHtml(post.content)}</p>
        <div class="flex items-center gap-3 mt-4 pt-3 border-t border-gray-100 flex-wrap">
            ${likeBtn}
            <span class="flex items-center gap-1 text-sm text-gray-400">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                <span id="modal-comment-count">${post.comment_count}</span>
            </span>
            ${teacherBtns} ${delBtn}
        </div>
        ${post.locked ? '<p class="text-sm text-gray-400 mt-3 text-center py-2 bg-gray-50 rounded-lg">🔒 Esta publicación está bloqueada.</p>' : ''}
    `;

    const rc = document.getElementById('modal-reply-composer');
    if (rc) rc.style.display = post.locked ? 'none' : '';
    renderModalReplies(post.replies || []);
}

// ==================== Forum: Replies ====================

function renderModalReplies(replies) {
    const container = document.getElementById('modal-replies');
    if (!replies.length) { container.innerHTML = '<p class="text-gray-400 text-sm text-center py-2">Sin respuestas aún.</p>'; return; }
    const total = replies.reduce((s, r) => s + 1 + (r.children ? r.children.length : 0), 0);
    container.innerHTML = `<h3 class="text-sm font-semibold text-gray-600 mb-3">Respuestas (${total})</h3>${replies.map(r => renderReply(r, false)).join('')}`;
}

function renderReply(reply, isNested) {
    const isTeacher = reply.author_role === 'teacher';
    const avatarColor = isTeacher ? '#9C4927' : stringToColor(reply.author_name);
    const initials = nameInitials(reply.author_name);
    const canDelete = reply.author_id === currentUser.id || currentUser.role === 'teacher';
    const showReplyBtn = !isNested;

    const delBtn = canDelete ? `<button onclick="deleteReply(${reply.id})" class="text-gray-300 hover:text-red-400 text-xs">Eliminar</button>` : '';
    const replyBtn = showReplyBtn ? `<button onclick="startNestedReply(${reply.id})" class="text-gray-400 hover:text-primary text-xs">Responder</button>` : '';
    const teacherBadge = isTeacher ? `<span class="text-secondary text-xs font-medium">👨‍🏫 Profesor</span>` : '';

    const children = reply.children && reply.children.length
        ? `<div class="reply-indent mt-2 space-y-2">${reply.children.map(c => renderReply(c, true)).join('')}</div>` : '';

    return `
    <div class="mb-3" id="reply-${reply.id}">
        <div class="flex items-start gap-2">
            <div class="avatar text-white shrink-0" style="background:${avatarColor}; width:1.75rem; height:1.75rem; font-size:0.65rem">${initials}</div>
            <div class="flex-1 min-w-0">
                <div class="flex items-baseline gap-2 flex-wrap">
                    <span class="font-medium ${isTeacher ? 'text-secondary' : 'text-gray-800'} text-xs">${isTeacher ? '👨‍🏫 ' : ''}${escHtml(reply.author_name)}</span>
                    ${teacherBadge}
                    <span class="text-gray-400 text-xs">${timeAgo(reply.created_at)}</span>
                </div>
                <p class="text-gray-700 text-sm mt-0.5 whitespace-pre-wrap">${escHtml(reply.content)}</p>
                <div class="flex items-center gap-3 mt-1">${replyBtn} ${delBtn}</div>
                ${showReplyBtn ? `<div id="nested-reply-placeholder-${reply.id}"></div>` : ''}
                ${children}
            </div>
        </div>
    </div>`;
}

function startNestedReply(parentId) {
    document.getElementById('nested-reply-form')?.remove();
    activeReplyToId = parentId;
    const placeholder = document.getElementById(`nested-reply-placeholder-${parentId}`);
    if (!placeholder) return;
    placeholder.insertAdjacentHTML('afterend', `
        <div id="nested-reply-form" class="mt-2 pl-2">
            <textarea id="nested-reply-input" rows="2" placeholder="Escribe tu respuesta..."
                      class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none focus:ring-2 focus:ring-primary outline-none"></textarea>
            <div class="flex justify-end gap-2 mt-1">
                <button onclick="cancelNestedReply()" class="text-xs text-gray-500">Cancelar</button>
                <button onclick="submitNestedReply(${parentId})" class="px-3 py-1 text-xs bg-primary hover:bg-secondary text-white rounded-lg">Responder</button>
            </div>
        </div>`);
    document.getElementById('nested-reply-input').focus();
}

function cancelNestedReply() { document.getElementById('nested-reply-form')?.remove(); activeReplyToId = null; }

async function submitModalReply() {
    const input = document.getElementById('modal-reply-input');
    const content = input.value.trim();
    if (!content) return;
    await postReply(content, null);
    input.value = '';
}

async function submitNestedReply(parentId) {
    const input = document.getElementById('nested-reply-input');
    const content = input.value.trim();
    if (!content) return;
    await postReply(content, parentId);
    cancelNestedReply();
}

async function postReply(content, parentId) {
    if (!openPostId) return;
    try {
        await apiCall(`/forum/posts/${openPostId}/replies`, { method: 'POST', body: JSON.stringify({ content, parent_reply_id: parentId }) });
        const post = await apiCall(`/forum/posts/${openPostId}`);
        renderModalReplies(post.replies || []);
        const mc = document.getElementById('modal-comment-count'); if (mc) mc.textContent = post.comment_count;
        const fp = posts.find(p => p.id === openPostId); if (fp) fp.comment_count = post.comment_count;
    } catch (e) { alert('Error al responder: ' + e.message); }
}

async function deleteReply(replyId) {
    if (!confirm('¿Eliminar esta respuesta?')) return;
    try {
        await apiCall(`/forum/replies/${replyId}`, { method: 'DELETE' });
        const post = await apiCall(`/forum/posts/${openPostId}`);
        renderModalReplies(post.replies || []);
        const mc = document.getElementById('modal-comment-count'); if (mc) mc.textContent = post.comment_count;
    } catch (e) { alert('Error: ' + e.message); }
}

// ==================== Dashboard ====================

async function loadDashboardSection() {
    if (currentUser.role === 'teacher') {
        await loadTeacherDashboard();
    } else {
        await loadStudentDashboard();
    }
}

async function loadStudentDashboard() {
    try {
        enrolledClasses = await apiCall('/classes/enrolled');
    } catch (e) { enrolledClasses = []; }

    const container = document.getElementById('class-cards');

    if (!enrolledClasses.length) {
        container.innerHTML = `
            <div class="text-center py-10">
                <p class="text-gray-500 mb-4">No estás inscrito en ninguna clase aún.</p>
                <button onclick="openJoinModal()" class="px-6 py-2 bg-primary text-white rounded-lg hover:bg-secondary transition font-medium">
                    Inscribirse a una clase
                </button>
            </div>`;
        return;
    }

    container.innerHTML = '<p class="text-center text-gray-400 text-sm py-4">Cargando estadísticas...</p>';

    // Load grade data for all classes in parallel
    const [gradeResults, assignmentResults] = await Promise.all([
        Promise.all(enrolledClasses.map(c => apiCall(`/students/me/grade-calculation/${c.class_id}`).catch(() => null))),
        Promise.all(enrolledClasses.map(c => apiCall(`/students/me/assignments?class_id=${c.class_id}`).catch(() => []))),
    ]);

    enrolledClasses.forEach((c, i) => {
        gradesByClassId[c.class_id] = gradeResults[i];
        assignmentsByClassId[c.class_id] = assignmentResults[i] || [];
    });

    container.innerHTML = enrolledClasses.map(c => renderStudentClassCard(c, gradesByClassId[c.class_id])).join('');
    renderAssignmentsSection();

    // Show justification link if any class has unjustified absences with no pending review
    const anyAbsences = enrolledClasses.some(c => {
        const g = gradesByClassId[c.class_id];
        return g && g.absence_count > 0 && (g.pending_justification_count ?? 0) < g.absence_count;
    });
    const justLinkSec = document.getElementById('justification-link-section');
    if (justLinkSec && !previewMode) justLinkSec.classList.toggle('hidden', !anyAbsences);
}

function renderStudentClassCard(cls, grade) {
    const hasGrade = grade && grade.final_grade !== undefined;

    const finalGrade = hasGrade ? grade.final_grade.toFixed(1) : '--';
    const gradeColor = hasGrade ? (grade.final_grade >= 70 ? 'text-green-600' : grade.final_grade >= 60 ? 'text-yellow-600' : 'text-red-600') : 'text-gray-500';

    const classPts = hasGrade ? (grade.participation_points_class ?? grade.participation_points ?? 0) : 0;
    const pendingPts = hasGrade ? (grade.pending_participation_points ?? 0) : 0;
    const forumPtsRaw = hasGrade ? (grade.participation_points_forum ?? grade.forum_points ?? 0) : 0;
    const absences = hasGrade ? grade.absence_count : 0;
    const spTotal = hasGrade ? grade.special_points.reduce((s, sp) => s + (sp.opted_in && sp.awarded ? sp.points_value : 0), 0) : 0;

    return `
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-50 flex items-center justify-between">
            <div>
                <h3 class="font-bold text-gray-800">${escHtml(cls.class_name)}</h3>
                <span class="text-xs text-gray-400">${escHtml(cls.class_code)}</span>
            </div>
            <span class="${gradeColor} text-2xl font-bold">${finalGrade}</span>
        </div>
        <div class="px-5 py-4 grid grid-cols-3 gap-4">
            <div class="flex items-center gap-2">
                <span class="text-lg">⭐</span>
                <div>
                    <p class="text-xs text-gray-400">Participación</p>
                    <p class="font-semibold text-gray-700 text-sm">${hasGrade ? classPts : '--'} pts</p>
                    ${pendingPts > 0 ? `<p class="text-xs text-violet-500">+${pendingPts} pendiente</p>` : ''}
                    ${forumPtsRaw > 0 ? `<p class="text-xs text-amber-500">+${forumPtsRaw.toFixed(2)} foro</p>` : ''}
                </div>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-lg">✨</span>
                <div>
                    <p class="text-xs text-gray-400">Pts. Extra</p>
                    <p class="font-semibold text-gray-700 text-sm">${spTotal > 0 ? '+' + spTotal.toFixed(1) : '0'} pts</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-lg">${absences > 0 ? '⚠️' : '✅'}</span>
                <div>
                    <p class="text-xs text-gray-400">Faltas</p>
                    <p class="font-semibold ${absences > 0 ? 'text-red-500' : 'text-green-600'} text-sm">${absences}${absences > 0 ? ` (-${absences})` : ''}</p>
                    ${(() => { const pendingJust = hasGrade ? (grade.pending_justification_count ?? 0) : 0; return pendingJust > 0 ? `<p class="text-xs text-yellow-600">⏳ ${pendingJust} en revisión</p>` : absences > 0 ? `<button onclick="event.stopPropagation();openJustificationModal(${cls.class_id})" class="text-xs text-red-400 hover:text-red-600 font-medium transition">Justificar →</button>` : ''; })()}
                </div>
            </div>
        </div>
        <div class="px-5 pb-4">
            <button onclick="openGradeModal(${cls.class_id})"
                    class="w-full py-2 text-sm text-primary font-medium border border-primary-30 rounded-lg hover:bg-primary-5 transition">
                Ver Desglose Completo →
            </button>
        </div>
    </div>`;
}

// ==================== Grade Breakdown Modal ====================

async function openGradeModal(classId) {
    document.getElementById('grade-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    const cls = enrolledClasses.find(c => c.class_id === classId);
    if (cls) document.getElementById('grade-modal-title').textContent = cls.class_name;

    document.getElementById('grade-modal-body').innerHTML = '<p class="text-center text-gray-400 text-sm py-6">Cargando...</p>';

    try {
        const calc = await apiCall(`/students/me/grade-calculation/${classId}`);
        gradesByClassId[classId] = calc;
        document.getElementById('grade-modal-body').innerHTML = renderGradeModalContent(calc);
    } catch (e) {
        document.getElementById('grade-modal-body').innerHTML = `<p class="text-red-400 text-sm text-center py-4">${e.message}</p>`;
    }
}

function closeGradeModal() {
    document.getElementById('grade-modal').classList.add('hidden');
    document.body.style.overflow = '';
}

function renderGradeModalContent(calc) {
    if (!calc) return '<p class="text-gray-400 text-sm text-center">Sin datos</p>';

    const classPts = calc.participation_points_class ?? calc.participation_points ?? 0;
    const pendingPts = calc.pending_participation_points ?? 0;
    const forumPtsRaw = calc.participation_points_forum ?? 0;
    const forumContrib = calc.forum_points ?? 0;
    const partContrib = parseFloat(classPts).toFixed(1);

    const categoriesHtml = (calc.categories || []).map(cat => {
        const pct = cat.average !== null && cat.average !== undefined ? cat.average.toFixed(1) : '--';
        const contrib = cat.weighted_contribution !== null && cat.weighted_contribution !== undefined ? cat.weighted_contribution.toFixed(1) : '--';
        const gradedInfo = cat.graded_count > 0
            ? `${cat.graded_count} calificada${cat.graded_count > 1 ? 's' : ''}`
            : 'Sin calificar';
        return `
        <div class="flex justify-between items-center py-2.5 border-b border-gray-100 last:border-0">
            <div>
                <p class="text-sm font-medium text-gray-700">${escHtml(cat.name)}</p>
                <p class="text-xs text-gray-400">${Math.round(cat.weight * 100)}% del total · ${gradedInfo}</p>
            </div>
            <div class="text-right">
                <p class="text-sm font-semibold text-gray-700">${contrib} pts</p>
                <p class="text-xs text-gray-400">Prom: ${pct}%</p>
            </div>
        </div>`;
    }).join('');

    const spTotal = (calc.special_points || []).reduce((s, sp) => s + (sp.opted_in && sp.awarded ? sp.points_value : 0), 0);
    const gradeColor = calc.final_grade >= 70 ? 'text-green-600' : calc.final_grade >= 60 ? 'text-yellow-600' : 'text-red-600';

    const totalGraded = (calc.categories || []).reduce((s, c) => s + (c.graded_count || 0), 0);

    return `
    <div class="space-y-4">
        <!-- Categories -->
        <div>
            <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Categorías de Calificación</h4>
            <div class="bg-gray-50 rounded-lg px-4 py-1">
                ${categoriesHtml || '<p class="text-xs text-gray-400 py-2 text-center">Sin categorías configuradas</p>'}
            </div>
        </div>

        <!-- Participation breakdown -->
        <div>
            <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Participación</h4>
            <div class="bg-gray-50 rounded-lg px-4 py-3 space-y-2">
                <div class="flex justify-between text-sm">
                    <span class="text-gray-600">⭐ Participación aprobada</span>
                    <span class="font-medium text-gray-700">${classPts} pts = <span class="text-green-600">+${partContrib}</span></span>
                </div>
                ${pendingPts > 0 ? `
                <div class="flex justify-between text-sm">
                    <span class="text-gray-600">⏳ Pendiente de aprobación</span>
                    <span class="font-medium text-violet-500">+${pendingPts} (pendiente)</span>
                </div>` : ''}
                ${forumPtsRaw > 0 ? `
                <div class="flex justify-between text-sm">
                    <span class="text-gray-600">🏆 Puntos del foro</span>
                    <span class="font-medium text-amber-600">+${forumContrib.toFixed(2)}</span>
                </div>` : `
                <div class="flex justify-between text-sm">
                    <span class="text-gray-400">🏆 Foro (sin actividad aún)</span>
                    <span class="text-gray-400">0</span>
                </div>`}
            </div>
        </div>

        <!-- Extras / Penalties -->
        ${spTotal > 0 || calc.absence_count > 0 ? `
        <div>
            <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Extras y Penalizaciones</h4>
            <div class="bg-gray-50 rounded-lg px-4 py-3 space-y-2">
                ${spTotal > 0 ? `
                <div class="flex justify-between text-sm">
                    <span class="text-gray-600">✨ Puntos especiales</span>
                    <span class="font-medium text-green-600">+${spTotal.toFixed(1)}</span>
                </div>` : ''}
                ${calc.absence_count > 0 ? `
                <div class="flex justify-between text-sm">
                    <span class="text-gray-600">⚠️ Faltas injustificadas (${calc.absence_count})</span>
                    <span class="font-medium text-red-500">-${calc.absence_penalty.toFixed(0)}</span>
                </div>` : ''}
            </div>
        </div>` : ''}

        <!-- Final grade -->
        <div class="flex items-center justify-between px-4 py-3 bg-primary-5 rounded-xl border border-primary-30">
            <span class="font-semibold text-gray-700">Calificación Final</span>
            <span class="text-2xl font-bold ${gradeColor}">${calc.final_grade.toFixed(1)}</span>
        </div>

        ${totalGraded > 0 ? `<p class="text-xs text-gray-400 text-center">Calculada sobre ${totalGraded} tarea${totalGraded !== 1 ? 's' : ''} calificada${totalGraded !== 1 ? 's' : ''}</p>` : ''}
    </div>`;
}

// ==================== Participation Form (multi-tap) ====================

function renderParticipationSection() {
    if (!enrolledClasses.length) return;
    const section = document.getElementById('participation-section');
    if (!section) return;
    section.classList.remove('hidden');

    const sel = document.getElementById('participation-class-selector');
    if (sel) {
        sel.innerHTML = enrolledClasses.map(c =>
            `<option value="${c.class_id}">${escHtml(c.class_name)}</option>`
        ).join('');
    }

    const textarea = document.getElementById('participation-description');
    const btn = document.getElementById('participation-submit-btn');
    if (textarea && btn) {
        textarea.addEventListener('input', () => {
            tapDescription = textarea.value.trim();
            btn.disabled = tapDescription.length < 5;
            // Reset tap count whenever the text changes
            tapCount = 0;
            clearTimeout(tapTimer);
            _updateTapIndicator();
        });
        btn.addEventListener('click', _handleParticipationTap);
    }
}

function _handleParticipationTap() {
    tapDescription = document.getElementById('participation-description')?.value.trim() || '';
    if (tapDescription.length < 5) return;

    tapCount = Math.min(tapCount + 1, 3);
    clearTimeout(tapTimer);

    const pts = tapCount;
    if (tapCount === 1) {
        _showTapAnimation(`✨ +${pts} pts`, 'tap-normal');
    } else if (tapCount === 2) {
        _showTapAnimation(`🎉 ×2! +${pts} pts`, 'tap-double');
    } else {
        _showTapAnimation(`🎊 ×3! +${pts} pts`, 'tap-triple');
        _doSubmitParticipation(3);
        return;
    }

    _updateTapIndicator();
    tapTimer = setTimeout(() => _doSubmitParticipation(tapCount), 2000);
}

function _updateTapIndicator() {
    const indicator = document.getElementById('tap-indicator');
    const dots = document.getElementById('tap-dots');
    const preview = document.getElementById('tap-pts-preview');
    if (!indicator) return;
    if (tapCount === 0) { indicator.classList.add('hidden'); return; }
    indicator.classList.remove('hidden');
    dots.textContent = '●'.repeat(tapCount);
    preview.textContent = `+${tapCount} pts`;
}

function _showTapAnimation(text, cssClass) {
    const wrapper = document.getElementById('participation-btn-wrapper');
    if (!wrapper) return;
    const el = document.createElement('div');
    el.className = `tap-animation ${cssClass}`;
    el.textContent = text;
    el.style.cssText = `top:50%;left:50%;font-size:1.75rem;font-weight:800;z-index:10;animation:popBounce 0.55s ease-out forwards;`;
    wrapper.appendChild(el);
    setTimeout(() => el.remove(), 600);
}

async function _doSubmitParticipation(multiplier) {
    clearTimeout(tapTimer);
    tapCount = 0;
    _updateTapIndicator();

    const classId = parseInt(document.getElementById('participation-class-selector')?.value);
    const description = tapDescription;

    const btn = document.getElementById('participation-submit-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Enviando...'; }

    try {
        await apiCall('/participation', {
            method: 'POST',
            body: JSON.stringify({ class_id: classId, description, points: multiplier }),
        });

        // Reset form
        const textarea = document.getElementById('participation-description');
        if (textarea) textarea.value = '';
        tapDescription = '';
        if (btn) { btn.disabled = true; btn.textContent = 'ENVIAR'; }

        _showToast(`✅ Participación enviada (+${multiplier} pts pendiente)`, '#7C3AED', 4000);

        // Refresh cards to show pending count
        await _refreshGradeCards();
    } catch (e) {
        alert('Error al enviar: ' + e.message);
        if (btn) { btn.disabled = false; btn.textContent = 'ENVIAR'; }
    }
}

async function _refreshGradeCards() {
    if (!enrolledClasses.length) return;
    const results = await Promise.all(
        enrolledClasses.map(c => apiCall(`/students/me/grade-calculation/${c.class_id}`).catch(() => null))
    );
    enrolledClasses.forEach((c, i) => { gradesByClassId[c.class_id] = results[i]; });
    const container = document.getElementById('class-cards');
    if (container) {
        container.innerHTML = enrolledClasses.map(c =>
            renderStudentClassCard(c, gradesByClassId[c.class_id])
        ).join('');
    }
    // Update justification link visibility
    const anyAbsences = enrolledClasses.some(c => {
        const g = gradesByClassId[c.class_id];
        return g && g.absence_count > 0 && (g.pending_justification_count ?? 0) < g.absence_count;
    });
    const justLinkSec = document.getElementById('justification-link-section');
    if (justLinkSec && !previewMode) justLinkSec.classList.toggle('hidden', !anyAbsences);
}

// ==================== Justification Modal ====================

async function openJustificationModal(preClassId = null) {
    document.getElementById('justification-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    justModalClassId = preClassId || (enrolledClasses.length > 0 ? enrolledClasses[0].class_id : null);
    await _renderJustificationModal();
}

function closeJustificationModal() {
    document.getElementById('justification-modal').classList.add('hidden');
    document.body.style.overflow = '';
}

async function _renderJustificationModal() {
    const body = document.getElementById('justification-modal-body');
    if (!justModalClassId) {
        body.innerHTML = '<p class="text-gray-400 text-sm text-center">No estás inscrito en ninguna clase.</p>';
        return;
    }

    body.innerHTML = '<p class="text-center text-gray-400 text-sm py-4">Cargando...</p>';

    // Fetch absences for this class (cache)
    if (!justModalAbsences[justModalClassId]) {
        try {
            const records = await apiCall(`/students/me/attendance?class_id=${justModalClassId}`);
            justModalAbsences[justModalClassId] = records.filter(r => r.status === 'absent' || r.status === 'late');
        } catch (e) {
            body.innerHTML = `<p class="text-red-400 text-sm text-center">${e.message}</p>`;
            return;
        }
    }

    const absences = justModalAbsences[justModalClassId];

    const classSelectorHtml = enrolledClasses.length > 1 ? `
        <div class="mb-4">
            <label class="block text-xs font-medium text-gray-500 mb-1">Clase</label>
            <select id="just-class-selector" onchange="_onJustClassChange(parseInt(this.value))"
                    class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-400 outline-none bg-gray-50">
                ${enrolledClasses.map(c => `<option value="${c.class_id}" ${c.class_id === justModalClassId ? 'selected' : ''}>${escHtml(c.class_name)}</option>`).join('')}
            </select>
        </div>` : `<p class="text-sm font-semibold text-gray-700 mb-4">${escHtml((enrolledClasses[0] || {}).class_name || '')}</p>`;

    if (!absences.length) {
        body.innerHTML = classSelectorHtml + `
            <div class="text-center py-6">
                <div class="text-3xl mb-2">✅</div>
                <p class="text-gray-500 text-sm">No tienes faltas o retardos en esta clase.</p>
            </div>`;
        return;
    }

    const absenceOptions = absences.map(a => {
        const dateStr = new Date(a.date + 'T12:00:00').toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric', month: 'long' });
        const typeLabel = a.status === 'absent' ? 'Falta' : 'Retardo';
        const statusSuffix = a.justification_status === 'pending' ? ' · en revisión ⏳'
            : a.justification_status === 'rejected' ? ' · rechazada ❌'
            : a.justification_status === 'approved' ? ' · aprobada ✅' : '';
        return `<option value="${a.id}">${dateStr} — ${typeLabel}${statusSuffix}</option>`;
    }).join('');

    body.innerHTML = `
        ${classSelectorHtml}
        <div class="mb-3">
            <label class="block text-xs font-medium text-gray-500 mb-1">Fecha de la falta</label>
            <select id="just-absence-selector" onchange="_onJustAbsenceChange(parseInt(this.value))"
                    class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-400 outline-none bg-gray-50">
                ${absenceOptions}
            </select>
        </div>
        <div id="just-status-hint" class="mb-3 hidden"></div>
        <div class="mb-3">
            <label class="block text-xs font-medium text-gray-500 mb-1">Motivo de la justificación</label>
            <textarea id="just-text" rows="3" placeholder="Explica brevemente el motivo de tu falta..."
                      class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none focus:ring-2 focus:ring-red-400 outline-none"></textarea>
        </div>
        ${fileUploadsEnabled ? `
        <div class="mb-4">
            <label class="block text-xs font-medium text-gray-500 mb-1">Documento justificante (opcional)</label>
            <label class="flex items-center gap-2 px-3 py-2 border border-dashed border-gray-300 rounded-lg text-sm text-gray-500 cursor-pointer hover:bg-gray-50 transition">
                <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/></svg>
                <span id="just-file-label">PDF, JPG, PNG · Máx. 10 MB</span>
                <input type="file" id="just-file-input" class="hidden" accept=".pdf,.jpg,.jpeg,.png"
                       onchange="_onJustFileSelect(this)">
            </label>
        </div>` : ''}
        <p id="just-submit-error" class="text-red-500 text-sm mb-2 hidden"></p>
        <button onclick="submitJustification()" id="just-submit-btn"
                class="w-full py-2.5 text-sm bg-red-500 hover:bg-red-600 text-white font-semibold rounded-lg transition">
            Enviar justificación
        </button>`;

    // Show status hint for first absence
    const firstId = absences[0]?.id;
    if (firstId) _onJustAbsenceChange(firstId);
}

async function _onJustClassChange(classId) {
    justModalClassId = classId;
    await _renderJustificationModal();
}

function _onJustAbsenceChange(attId) {
    const hintEl = document.getElementById('just-status-hint');
    if (!hintEl) return;
    const absences = justModalAbsences[justModalClassId] || [];
    const att = absences.find(a => a.id === attId);
    if (!att) { hintEl.classList.add('hidden'); return; }

    if (att.justification_status === 'pending') {
        hintEl.innerHTML = `<div class="px-3 py-2 bg-yellow-50 border border-yellow-200 rounded-lg text-xs text-yellow-800">⏳ Ya enviaste una justificación — está pendiente de revisión. Puedes reemplazarla.</div>`;
        hintEl.classList.remove('hidden');
    } else if (att.justification_status === 'rejected') {
        hintEl.innerHTML = `<div class="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800">❌ Tu justificación anterior fue rechazada. Puedes enviar una nueva.</div>`;
        hintEl.classList.remove('hidden');
    } else if (att.justification_status === 'approved') {
        hintEl.innerHTML = `<div class="px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-xs text-green-800">✅ Esta falta ya está justificada y aprobada.</div>`;
        hintEl.classList.remove('hidden');
    } else {
        hintEl.classList.add('hidden');
    }
}

function _onJustFileSelect(input) {
    const label = document.getElementById('just-file-label');
    if (!label) return;
    label.textContent = input.files.length > 0
        ? `${input.files[0].name} (${formatFileSize(input.files[0].size)})`
        : 'PDF, JPG, PNG · Máx. 10 MB';
}

async function submitJustification() {
    const absenceIdStr = document.getElementById('just-absence-selector')?.value;
    const text = document.getElementById('just-text')?.value.trim();
    const fileInput = document.getElementById('just-file-input');
    const file = fileInput?.files[0];
    const errEl = document.getElementById('just-submit-error');
    const btn = document.getElementById('just-submit-btn');

    if (!absenceIdStr) return;
    if (!text && !file) {
        errEl.textContent = 'Escribe un motivo o adjunta un documento.';
        errEl.classList.remove('hidden');
        return;
    }
    errEl.classList.add('hidden');

    btn.disabled = true;
    btn.textContent = 'Enviando...';

    const formData = new FormData();
    if (text) formData.append('justification_text', text);
    if (file) formData.append('file', file);

    try {
        await apiUpload(`/students/me/attendance/${absenceIdStr}/justify`, formData);

        // Invalidate cached absences for this class so they reload fresh
        delete justModalAbsences[justModalClassId];

        closeJustificationModal();
        _showToast('✅ Justificación enviada — el profesor la revisará pronto', '#059669', 4000);

        // Refresh cards to update absence/pending counts (also updates justification link)
        await _refreshGradeCards();
    } catch (e) {
        errEl.textContent = 'Error: ' + e.message;
        errEl.classList.remove('hidden');
        btn.disabled = false;
        btn.textContent = 'Enviar justificación';
    }
}

function renderAssignmentsSection() {
    const section = document.getElementById('upcoming-section');
    const list = document.getElementById('upcoming-list');

    // Collect all assignments across all enrolled classes
    const hasAny = enrolledClasses.some(cls => (assignmentsByClassId[cls.class_id] || []).length > 0);
    if (!hasAny) return;

    section.classList.remove('hidden');

    list.innerHTML = enrolledClasses.map(cls => {
        const assignments = assignmentsByClassId[cls.class_id] || [];
        if (!assignments.length) return '';
        return `
        <div class="mb-5">
            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">${escHtml(cls.class_name)}</p>
            <div class="space-y-3">${assignments.map(a => renderAssignmentCard(a)).join('')}</div>
        </div>`;
    }).join('');
}

function renderAssignmentCard(a) {
    const now = new Date();
    const due = new Date(a.due_date + 'Z');
    const isPast = now > due;
    const diff = due - now;
    const hasSubmission = !!a.submission;
    const isGraded = a.submission?.grade !== null && a.submission?.grade !== undefined;

    // Status badge
    let statusBadge, statusColor;
    if (isGraded) {
        statusBadge = `Calificado: ${a.submission.grade}/${a.max_points}`;
        statusColor = 'bg-blue-100 text-blue-800';
    } else if (hasSubmission) {
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
    if (!hasSubmission && !isPast) {
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        countdown = days > 0 ? `${days}d ${hours}h restantes` : `${hours}h ${Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))}m restantes`;
    }

    // Penalty badge
    let penaltyHtml = '';
    if (hasSubmission && a.submission.is_late) {
        const pct = a.submission.penalty_pct ?? 100;
        const pc = pct === 90 ? 'bg-yellow-100 text-yellow-800' : pct === 50 ? 'bg-orange-100 text-orange-800' : 'bg-red-100 text-red-800';
        penaltyHtml = `<span class="text-xs px-2 py-0.5 rounded ${pc}">Penalización: ${100 - pct}%</span>`;
    }

    // Submission details
    let submissionHtml = '';
    if (hasSubmission) {
        const submittedAt = new Date(a.submission.submitted_at + 'Z').toLocaleString('es-MX', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
        const fileLine = a.submission.has_file
            ? `<span class="font-medium">Archivo:</span> <button onclick="viewSubmissionFile(${a.submission.id})" class="text-primary hover:text-secondary underline">${escHtml(a.submission.file_name || 'archivo')} (${formatFileSize(a.submission.file_size || 0)})</button>`
            : '';
        const driveLine = a.submission.drive_url
            ? `<span class="font-medium">Enlace:</span> <a href="${escHtml(a.submission.drive_url)}" target="_blank" class="text-primary hover:text-secondary underline">Google Drive</a>`
            : '';
        const deleteBtn = !isGraded && !previewMode
            ? `<button onclick="deleteSubmission(${a.submission.id})" class="shrink-0 text-xs px-3 py-1.5 bg-red-100 text-red-700 rounded hover:bg-red-200 transition">Eliminar entrega</button>`
            : '';
        submissionHtml = `
        <div class="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm">
            <div class="flex justify-between items-start gap-3">
                <div class="space-y-1 text-gray-600">
                    ${fileLine ? `<div>${fileLine}</div>` : ''}
                    ${driveLine ? `<div>${driveLine}</div>` : ''}
                    <div>Entregado: ${submittedAt}</div>
                    ${penaltyHtml ? `<div>${penaltyHtml}</div>` : ''}
                </div>
                ${deleteBtn}
            </div>
        </div>`;
    }

    // Feedback
    const feedbackHtml = a.submission?.feedback
        ? `<div class="mt-2 p-2 bg-blue-50 rounded text-sm text-blue-800"><span class="font-medium">Retroalimentación:</span> ${escHtml(a.submission.feedback)}</div>`
        : '';

    // Submit form
    const submitHtml = !hasSubmission && !previewMode ? `
    <div class="mt-3 pt-3 border-t border-gray-100">
        <div class="flex gap-2">
            <input type="url" id="submit-url-${a.id}" placeholder="https://drive.google.com/..."
                   class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none">
            <button onclick="submitAssignment(${a.id})"
                    class="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-secondary transition">
                Enviar
            </button>
        </div>
        <p class="text-xs text-gray-400 mt-1">Pega el enlace de Google Drive de tu tarea</p>
        ${fileUploadsEnabled ? `
        <div class="mt-3 pt-3 border-t border-gray-100">
            <div class="flex items-center gap-2">
                <label class="flex-1 flex items-center gap-2 px-3 py-2 border border-dashed border-gray-300 rounded-lg text-sm text-gray-500 cursor-pointer hover:bg-gray-50">
                    <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/></svg>
                    <span>O subir archivo directamente</span>
                    <input type="file" id="file-input-${a.id}" class="hidden"
                           accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip,.rar,.7z,.png,.jpg,.jpeg,.gif,.webp,.svg"
                           onchange="handleFileSelect(${a.id}, this)">
                </label>
                <button id="upload-btn-${a.id}" onclick="uploadAssignmentFile(${a.id})"
                        class="hidden px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-secondary transition">
                    Subir
                </button>
            </div>
            <p id="file-info-${a.id}" class="text-xs text-gray-500 mt-1 hidden"></p>
            <div id="upload-progress-${a.id}" class="hidden mt-2 w-full bg-gray-200 rounded-full h-2">
                <div id="upload-progress-fill-${a.id}" class="bg-primary h-2 rounded-full transition-all" style="width:0%"></div>
            </div>
            <p class="text-xs text-gray-400 mt-1">PDF, DOCX, ZIP, imágenes · Máx. 10 MB</p>
        </div>` : ''}
    </div>` : '';

    return `
    <div class="bg-white border border-gray-200 rounded-lg p-4">
        <div class="flex items-start justify-between gap-2 mb-1">
            <span class="font-medium text-gray-800 text-sm">${escHtml(a.title)}</span>
            <span class="shrink-0 text-xs px-2 py-0.5 rounded ${statusColor}">${statusBadge}</span>
        </div>
        ${a.description ? `<p class="text-gray-500 text-sm mb-1">${escHtml(a.description)}</p>` : ''}
        <div class="flex items-center gap-3 text-xs text-gray-400">
            <span>Límite: ${new Date(a.due_date + 'Z').toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
            ${countdown ? `<span class="text-amber-600 font-medium">${countdown}</span>` : ''}
        </div>
        ${feedbackHtml}
        ${submissionHtml}
        ${submitHtml}
    </div>`;
}

// ==================== Assignment Submission ====================

async function submitAssignment(assignmentId) {
    const input = document.getElementById(`submit-url-${assignmentId}`);
    const driveUrl = input?.value.trim();
    if (!driveUrl) { alert('Por favor ingresa un enlace de Google Drive'); return; }
    try {
        await apiCall(`/students/me/assignments/${assignmentId}/submit`, {
            method: 'POST', body: JSON.stringify({ drive_url: driveUrl }),
        });
        await refreshAssignments();
    } catch (e) { alert('Error al enviar: ' + e.message); }
}

async function deleteSubmission(submissionId) {
    if (!confirm('¿Eliminar tu entrega? Tendrás que volver a subirla.')) return;
    try {
        await apiCall(`/students/submissions/${submissionId}`, { method: 'DELETE' });
        await refreshAssignments();
    } catch (e) { alert('Error al eliminar: ' + e.message); }
}

async function uploadAssignmentFile(assignmentId) {
    const fileInput = document.getElementById(`file-input-${assignmentId}`);
    const file = fileInput?.files[0];
    if (!file) { alert('Selecciona un archivo primero'); return; }
    const progressBar = document.getElementById(`upload-progress-${assignmentId}`);
    const progressFill = document.getElementById(`upload-progress-fill-${assignmentId}`);
    const btn = document.getElementById(`upload-btn-${assignmentId}`);
    progressBar.classList.remove('hidden');
    btn.disabled = true; btn.textContent = 'Subiendo...';
    const formData = new FormData();
    formData.append('file', file);
    try {
        await apiUpload(`/students/me/assignments/${assignmentId}/upload`, formData, pct => {
            progressFill.style.width = pct + '%';
        });
        await refreshAssignments();
    } catch (e) { alert('Error al subir: ' + e.message); }
    finally { progressBar.classList.add('hidden'); progressFill.style.width = '0%'; btn.disabled = false; btn.textContent = 'Subir'; }
}

function handleFileSelect(assignmentId, input) {
    const infoEl = document.getElementById(`file-info-${assignmentId}`);
    const btn = document.getElementById(`upload-btn-${assignmentId}`);
    if (input.files.length > 0) {
        infoEl.textContent = `${input.files[0].name} (${formatFileSize(input.files[0].size)})`;
        infoEl.classList.remove('hidden'); btn.classList.remove('hidden');
    } else { infoEl.classList.add('hidden'); btn.classList.add('hidden'); }
}

async function viewSubmissionFile(submissionId) {
    try {
        const data = await apiCall(`/students/submissions/${submissionId}/file`);
        window.open(data.download_url, '_blank');
    } catch (e) { alert('Error al abrir archivo: ' + e.message); }
}

async function refreshAssignments() {
    // Reload assignment data for all enrolled classes and re-render
    const results = await Promise.all(
        enrolledClasses.map(c => apiCall(`/students/me/assignments?class_id=${c.class_id}`).catch(() => []))
    );
    enrolledClasses.forEach((c, i) => { assignmentsByClassId[c.class_id] = results[i] || []; });
    renderAssignmentsSection();
}

async function loadTeacherDashboard() {
    try {
        teachingClasses = await apiCall('/classes/teaching');
    } catch (e) { teachingClasses = []; }

    const container = document.getElementById('class-cards');

    if (!teachingClasses.length) {
        container.innerHTML = `
            <div class="text-center py-10">
                <p class="text-gray-500 mb-4">No has creado ninguna clase aún.</p>
                <a href="/admin" class="px-6 py-2 bg-primary text-white rounded-lg hover:bg-secondary transition font-medium">
                    Ir al Panel del Profesor
                </a>
            </div>`;
        return;
    }

    container.innerHTML = teachingClasses.map(cls => `
        <a href="/admin/class/${cls.id}"
           class="block bg-white rounded-xl border border-gray-100 shadow-sm hover:border-primary hover:shadow transition p-5">
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="font-bold text-gray-800">${escHtml(cls.name)}</h3>
                    <span class="text-xs text-gray-400 font-mono">${escHtml(cls.code)}</span>
                </div>
                <div class="text-right">
                    <p class="text-2xl font-bold text-gray-700">${cls.student_count}</p>
                    <p class="text-xs text-gray-400">estudiantes</p>
                </div>
            </div>
            <div class="mt-3 flex items-center gap-2 text-sm text-primary font-medium">
                Ver dashboard completo
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
            </div>
        </a>`).join('');
}

// ==================== Join Class Modal ====================

function openJoinModal() {
    document.getElementById('join-modal').classList.remove('hidden');
    document.getElementById('join-class-code').focus();
}

function closeJoinModal() {
    document.getElementById('join-modal').classList.add('hidden');
    document.getElementById('join-class-code').value = '';
    document.getElementById('join-error').classList.add('hidden');
}

async function submitJoinClass() {
    const code = document.getElementById('join-class-code').value.trim().toUpperCase();
    const errEl = document.getElementById('join-error');
    errEl.classList.add('hidden');
    if (!code) return;
    try {
        const result = await apiCall('/classes/join', { method: 'POST', body: JSON.stringify({ code }) });
        enrolledClasses.push(result);
        closeJoinModal();
        // Refresh forum classes and dashboard
        await Promise.all([loadForumSection(), loadStudentDashboard()]);
        renderParticipationSection();
    } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.remove('hidden');
    }
}

// ==================== Toast Notifications ====================

function _showLikeToast(result) {
    const pts = result.points_awarded.toFixed(2);
    const name = result.author_name || 'el autor';
    let msg, bg, duration = 3000;
    if (result.bonus_type === 'jackpot') {
        msg = `💰 ¡JACKPOT! Le diste +${pts} pts a ${name}`; bg = 'linear-gradient(135deg,#f59e0b,#d97706)'; duration = 5000;
    } else if (result.bonus_type === 'double') {
        msg = `🎰 ¡DOBLE! Le diste +${pts} pts a ${name}`; bg = 'linear-gradient(135deg,#EA8251,#9C4927)'; duration = 4000;
    } else if (result.bonus_type === 'mini') {
        msg = `✨ Le diste +${pts} pts a ${name}`; bg = '#059669';
    } else {
        msg = `Le diste +${pts} pts a ${name}`; bg = '#1F2020';
    }
    _showToast(msg, bg, duration);
}

function _showToast(msg, bg, duration = 3000) {
    const el = document.createElement('div');
    el.style.cssText = `position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%) translateY(1rem);z-index:9999;padding:.75rem 1.25rem;border-radius:.75rem;box-shadow:0 4px 20px rgba(0,0,0,.25);color:#fff;font-size:.875rem;font-weight:600;white-space:nowrap;background:${bg};opacity:0;transition:opacity .3s ease,transform .3s ease;font-family:system-ui,sans-serif;`;
    el.textContent = msg;
    document.body.appendChild(el);
    requestAnimationFrame(() => { el.style.opacity = '1'; el.style.transform = 'translateX(-50%) translateY(0)'; });
    setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(-50%) translateY(1rem)'; setTimeout(() => el.remove(), 350); }, duration);
}

// ==================== Utilities ====================

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function escHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function nameInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    return parts.length === 1 ? parts[0][0].toUpperCase() : (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function setAvatarInitials(id, name) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = nameInitials(name);
    el.style.background = stringToColor(name);
    el.style.color = 'white';
}

function stringToColor(str) {
    const colors = ['#EA8251','#9C4927','#2563EB','#059669','#7C3AED','#DC2626','#0891B2','#D97706','#4F46E5','#BE185D'];
    let hash = 0;
    for (let i = 0; i < (str || '').length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
}

function timeAgo(isoString) {
    const date = new Date(isoString + (isoString.endsWith('Z') ? '' : 'Z'));
    const diff = (new Date() - date) / 1000;
    if (diff < 60) return 'justo ahora';
    if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
    if (diff < 604800) return `hace ${Math.floor(diff / 86400)}d`;
    return date.toLocaleDateString('es-MX', { day: 'numeric', month: 'short' });
}

// ==================== Event Listeners ====================

document.getElementById('post-modal').addEventListener('click', e => { if (e.target === e.currentTarget) closePostModal(); });
document.getElementById('grade-modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeGradeModal(); });
document.getElementById('justification-modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeJustificationModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closePostModal(); closeGradeModal(); closeJustificationModal(); } });

// Enter submits join form
document.getElementById('join-class-code').addEventListener('keydown', e => { if (e.key === 'Enter') submitJoinClass(); });

// ==================== Boot ====================
init();
