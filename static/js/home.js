// ==================== State ====================
let authToken = localStorage.getItem('authToken');
let currentUser = null;
let googleClientId = null;
let previewMode = false;
let previewStudentId = null;

// Forum state
let forumClasses = [];
let selectedForumClassId = null;
let posts = [];
let currentPage = 1;
let hasMorePosts = false;
let openPostId = null;
let currentModalPost = null;
let activeReplyToId = null;

// Dashboard state
let enrolledClasses = [];   // student enrolled classes
let teachingClasses = [];   // teacher's classes
let gradesByClassId = {};   // { class_id: gradeCalcResponse }
let assignmentsByClassId = {}; // { class_id: [...assignments] }

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
        document.getElementById('dashboard-title').textContent = '📊 Mis Clases';
        document.getElementById('dashboard-subtitle').textContent = 'Haz clic en una clase para ver el dashboard completo';
    } else {
        document.getElementById('dashboard-title').textContent = '📊 Mi Progreso';
        document.getElementById('dashboard-subtitle').textContent = 'Resumen de todas tus clases';
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
}

// ==================== Show / Hide ====================

function showLogin() {
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('app-section').classList.add('hidden');
    // Fetch config for Google Client ID
    fetch('/api/config').then(r => r.json()).then(cfg => {
        googleClientId = cfg.google_client_id;
        if (window.google) initGoogleSignIn();
        else window.addEventListener('load', () => setTimeout(initGoogleSignIn, 100));
    }).catch(() => {});
}

function showApp() {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('app-section').classList.remove('hidden');
}

function scrollToForum() {
    document.getElementById('forum-section').scrollIntoView({ behavior: 'smooth' });
}

function scrollToDashboard() {
    document.getElementById('dashboard-anchor').scrollIntoView({ behavior: 'smooth' });
}

// ==================== Forum: load classes + posts ====================

async function loadForumSection() {
    try {
        forumClasses = await apiCall('/forum/classes');
    } catch (e) { forumClasses = []; }

    const sel = document.getElementById('nav-class-selector');
    if (!forumClasses.length) {
        sel.innerHTML = '<option>Sin clases</option>';
        document.getElementById('posts-container').innerHTML = '';
        document.getElementById('forum-no-class').classList.remove('hidden');
        document.getElementById('composer-wrapper').classList.add('hidden');
        return;
    }

    sel.innerHTML = forumClasses.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

    // Restore last selected forum class
    const saved = localStorage.getItem('forumClassId');
    if (saved && forumClasses.find(c => c.id === parseInt(saved))) {
        sel.value = saved;
    }
    selectedForumClassId = parseInt(sel.value);
    await loadPosts(true);
}

async function onForumClassChange() {
    const sel = document.getElementById('nav-class-selector');
    selectedForumClassId = parseInt(sel.value);
    localStorage.setItem('forumClassId', selectedForumClassId);
    await loadPosts(true);
}

async function loadPosts(reset = false) {
    if (reset) { currentPage = 1; posts = []; }
    const container = document.getElementById('posts-container');
    if (reset) container.innerHTML = '<p class="text-center text-gray-400 text-sm py-6">Cargando...</p>';

    try {
        const data = await apiCall(`/forum/posts?class_id=${selectedForumClassId}&page=${currentPage}&limit=10`);
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

    const authorLabel = isTeacherPost
        ? `<span class="font-medium text-secondary text-sm">👨‍🏫 ${escHtml(post.author_name)}</span><span class="text-secondary text-xs font-medium ml-1">• Profesor</span>`
        : `<span class="font-medium text-gray-800 text-sm">${escHtml(post.author_name)}</span><span class="px-2 py-0.5 bg-primary-10 text-secondary text-xs rounded-full ml-1">${escHtml(post.class_name)}</span>`;

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
    if (!content) { alert('El contenido no puede estar vacío.'); return; }
    try {
        const post = await apiCall('/forum/posts', {
            method: 'POST',
            body: JSON.stringify({ class_id: selectedForumClassId, title: title || null, content }),
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
    renderUpcomingAssignments();
}

function renderStudentClassCard(cls, grade) {
    const hasGrade = grade && grade.final_grade !== undefined;

    const finalGrade = hasGrade ? grade.final_grade.toFixed(1) : '--';
    const gradeColor = hasGrade ? (grade.final_grade >= 70 ? 'text-green-600' : grade.final_grade >= 60 ? 'text-yellow-600' : 'text-red-600') : 'text-gray-500';

    const partPts = hasGrade ? grade.participation_points : '--';
    const forumPts = hasGrade && grade.forum_points > 0 ? `+${grade.forum_points.toFixed(2)}` : '0';
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
        <div class="px-5 py-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div class="flex items-center gap-2">
                <span class="text-lg">⭐</span>
                <div>
                    <p class="text-xs text-gray-400">Participación</p>
                    <p class="font-semibold text-gray-700 text-sm">${partPts} pts</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-lg">🏆</span>
                <div>
                    <p class="text-xs text-gray-400">Puntos Foro</p>
                    <p class="font-semibold text-amber-500 text-sm">${forumPts} pts</p>
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
                    <p class="font-semibold ${absences > 0 ? 'text-red-500' : 'text-green-600'} text-sm">${absences} ${absences > 0 ? `(-${absences} pts)` : ''}</p>
                </div>
            </div>
        </div>
    </div>`;
}

function renderUpcomingAssignments() {
    const now = new Date();
    const upcoming = [];

    enrolledClasses.forEach(cls => {
        const assignments = assignmentsByClassId[cls.class_id] || [];
        assignments.forEach(a => {
            if (!a.due_date) return;
            const due = new Date(a.due_date);
            if (due < now) return; // already past
            if (a.submission && a.submission.grade !== null) return; // already graded
            upcoming.push({ ...a, class_name: cls.class_name, due });
        });
    });

    if (!upcoming.length) return;
    upcoming.sort((a, b) => a.due - b.due);

    const section = document.getElementById('upcoming-section');
    const list = document.getElementById('upcoming-list');
    section.classList.remove('hidden');

    list.innerHTML = upcoming.slice(0, 5).map(a => {
        const daysLeft = Math.ceil((a.due - now) / (1000 * 60 * 60 * 24));
        const urgency = daysLeft <= 2 ? 'text-red-600 bg-red-50 border-red-100' : daysLeft <= 5 ? 'text-amber-600 bg-amber-50 border-amber-100' : 'text-gray-600 bg-gray-50 border-gray-100';
        return `
        <div class="flex items-center justify-between px-4 py-3 rounded-lg border ${urgency}">
            <div>
                <span class="font-medium text-sm">${escHtml(a.title)}</span>
                <span class="text-xs opacity-70 ml-2">${escHtml(a.class_name)}</span>
            </div>
            <span class="text-xs font-medium">${daysLeft === 1 ? 'Mañana' : `${daysLeft} días`} 📅</span>
        </div>`;
    }).join('');
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
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePostModal(); });

// Enter submits join form
document.getElementById('join-class-code').addEventListener('keydown', e => { if (e.key === 'Enter') submitJoinClass(); });

// ==================== Boot ====================
init();
