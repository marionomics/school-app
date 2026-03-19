// ==================== State ====================
let authToken = localStorage.getItem('authToken');
let currentUser = null;
let allClasses = [];
let selectedClassId = null;
let posts = [];
let currentPage = 1;
let hasMorePosts = false;
let openPostId = null; // currently open in modal
let currentModalPost = null; // full post data for the open modal

const API_BASE = '/api';

// ==================== API ====================

async function apiCall(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });

    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Error desconocido' }));
        if (response.status === 401) {
            authToken = null;
            localStorage.removeItem('authToken');
            showLoginSection();
            return;
        }
        const msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
        throw new Error(msg);
    }
    return response.json();
}

function logout() {
    apiCall('/auth/logout', { method: 'POST' }).catch(() => {});
    localStorage.removeItem('authToken');
    window.location.href = '/';
}

// ==================== Init ====================

async function init() {
    if (!authToken) {
        showLoginSection();
        return;
    }
    try {
        currentUser = await apiCall('/students/me');
        document.getElementById('user-name').textContent = currentUser.name;
        setAvatarInitials('composer-avatar', currentUser.name);
        setAvatarInitials('modal-avatar', currentUser.name);

        // Load classes
        allClasses = await apiCall('/forum/classes');

        if (!allClasses.length) {
            showSection('forum-section');
            document.getElementById('class-selector').innerHTML = '<option>Sin clases</option>';
            document.getElementById('no-class-state').classList.remove('hidden');
            document.getElementById('composer-trigger').classList.add('hidden');
            return;
        }

        // Populate class selector
        const selector = document.getElementById('class-selector');
        selector.innerHTML = allClasses.map(c =>
            `<option value="${c.id}">${c.name}</option>`
        ).join('');

        // Check URL params for class_id
        const params = new URLSearchParams(window.location.search);
        const urlClassId = params.get('class_id');
        if (urlClassId && allClasses.find(c => c.id === parseInt(urlClassId))) {
            selector.value = urlClassId;
        }

        selectedClassId = parseInt(selector.value);
        showSection('forum-section');
        await loadPosts(true);
    } catch (e) {
        console.error('Init error:', e);
        showLoginSection();
    }
}

function showLoginSection() {
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('forum-section').classList.add('hidden');
}

function showSection(id) {
    document.getElementById('login-section').classList.add('hidden');
    document.getElementById('forum-section').classList.add('hidden');
    document.getElementById(id).classList.remove('hidden');
}

// ==================== Posts ====================

async function onClassChange() {
    const selector = document.getElementById('class-selector');
    selectedClassId = parseInt(selector.value);
    await loadPosts(true);
}

async function loadPosts(reset = false) {
    if (reset) {
        currentPage = 1;
        posts = [];
    }

    const container = document.getElementById('posts-container');
    if (reset) container.innerHTML = '<p class="text-center text-gray-400 text-sm py-6">Cargando...</p>';

    try {
        const data = await apiCall(`/forum/posts?class_id=${selectedClassId}&page=${currentPage}&limit=20`);
        if (reset) posts = data.posts;
        else posts = [...posts, ...data.posts];
        hasMorePosts = data.has_more;
        renderPosts(reset);
    } catch (e) {
        container.innerHTML = `<p class="text-center text-red-400 text-sm py-6">Error al cargar: ${e.message}</p>`;
    }
}

async function loadMorePosts() {
    currentPage += 1;
    await loadPosts(false);
}

function renderPosts(reset) {
    const container = document.getElementById('posts-container');
    const emptyState = document.getElementById('empty-state');
    const loadMoreContainer = document.getElementById('load-more-container');

    if (!posts.length) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        loadMoreContainer.classList.add('hidden');
        return;
    }

    emptyState.classList.add('hidden');

    if (reset) {
        container.innerHTML = posts.map(renderPostCard).join('');
    } else {
        container.insertAdjacentHTML('beforeend', posts.slice(posts.length - (currentPage > 1 ? 20 : 0)).map(renderPostCard).join(''));
    }

    loadMoreContainer.classList.toggle('hidden', !hasMorePosts);
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
        ? `<span class="font-medium text-secondary text-sm">👨‍🏫 ${escHtml(post.author_name)}</span><span class="text-secondary text-xs font-medium">• Profesor</span>`
        : `<span class="font-medium text-gray-800 text-sm">${escHtml(post.author_name)}</span><span class="px-2 py-0.5 bg-primary-10 text-secondary text-xs rounded-full">${escHtml(post.class_name)}</span>`;

    const pinnedBadge = post.pinned ? `<span class="text-amber-500 text-xs font-medium">📌 Fijado</span>` : '';
    const lockedBadge = post.locked ? `<span class="text-gray-400 text-xs">🔒 Bloqueado</span>` : '';

    const likeBtn = cantLike
        ? `<span class="flex items-center gap-1 text-xs text-gray-300 cursor-not-allowed select-none">
               ${heartIcon(false)} ${post.like_count}
           </span>`
        : `<button onclick="toggleLike(event, ${post.id})" data-post-id="${post.id}"
                   class="flex items-center gap-1 text-xs ${post.liked_by_me ? 'text-red-500' : 'text-gray-400 hover:text-red-400'} transition">
               ${heartIcon(post.liked_by_me)} <span id="like-count-${post.id}">${post.like_count}</span>
           </button>`;

    const teacherActions = currentUser.role === 'teacher'
        ? `<button onclick="event.stopPropagation(); togglePin(${post.id})"
                   class="text-sm ${post.pinned ? 'text-amber-500 hover:text-amber-700' : 'text-gray-300 hover:text-amber-500'} transition"
                   title="${post.pinned ? 'Desfijar' : 'Fijar'}">📌</button>
           <button onclick="event.stopPropagation(); toggleLock(${post.id})"
                   class="text-sm ${post.locked ? 'text-blue-400 hover:text-blue-600' : 'text-gray-300 hover:text-blue-400'} transition"
                   title="${post.locked ? 'Desbloquear' : 'Bloquear'}">🔒</button>`
        : '';

    const deleteBtn = canDelete
        ? `<button onclick="deletePost(event, ${post.id})"
                   class="text-gray-300 hover:text-red-400 transition" title="Eliminar">
               <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
               </svg>
           </button>` : '';

    return `
    <article onclick="openPost(${post.id})"
             class="bg-white rounded-xl shadow-sm border ${post.pinned ? 'border-amber-200' : 'border-gray-100'} p-4 cursor-pointer hover:border-gray-200 hover:shadow transition">
        <div class="flex items-start gap-3">
            <div class="avatar text-white text-xs shrink-0" style="background:${avatarColor}">${initials}</div>
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap mb-1">
                    ${authorLabel}
                    ${pinnedBadge}
                    ${lockedBadge}
                    <span class="text-gray-400 text-xs ml-auto">${timeStr}</span>
                </div>
                ${post.title ? `<p class="font-semibold text-gray-800 text-sm mb-1">${escHtml(post.title)}</p>` : ''}
                <p class="text-gray-600 text-sm line-clamp-3 whitespace-pre-wrap">${linkify(post.content)}</p>
                <div class="flex items-center gap-3 mt-3" onclick="event.stopPropagation()">
                    ${likeBtn}
                    <button onclick="openPost(${post.id})"
                            class="flex items-center gap-1 text-xs text-gray-400 hover:text-primary transition">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                        </svg>
                        ${post.comment_count}
                    </button>
                    ${post.points_earned > 0 ? `<span class="text-xs text-amber-500 font-medium">🏆 +${post.points_earned.toFixed(2)}</span>` : ''}
                    <span class="ml-auto flex items-center gap-2">
                        ${teacherActions}
                        ${deleteBtn}
                    </span>
                </div>
            </div>
        </div>
    </article>`;
}

// ==================== Composer ====================

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
            body: JSON.stringify({ class_id: selectedClassId, title: title || null, content }),
        });
        closeComposer();
        // Prepend to list
        posts.unshift(post);
        const container = document.getElementById('posts-container');
        const emptyState = document.getElementById('empty-state');
        emptyState.classList.add('hidden');
        container.insertAdjacentHTML('afterbegin', renderPostCard(post));
    } catch (e) {
        alert('Error al publicar: ' + e.message);
    }
}

// ==================== Likes ====================

async function toggleLike(event, postId) {
    event.stopPropagation();
    const btn = event.currentTarget;
    try {
        const result = await apiCall(`/forum/posts/${postId}/like`, { method: 'POST' });
        // Update local state
        const post = posts.find(p => p.id === postId);
        if (post) {
            post.like_count = result.like_count;
            post.liked_by_me = result.liked;
            if (result.post_points_earned !== undefined) post.points_earned = result.post_points_earned;
        }
        // Update UI
        const countEl = document.getElementById(`like-count-${postId}`);
        if (countEl) countEl.textContent = result.like_count;
        if (result.liked) {
            btn.classList.add('text-red-500');
            btn.classList.remove('text-gray-400', 'hover:text-red-400');
            btn.querySelector('svg path') && (btn.innerHTML = heartIcon(true) + ` <span id="like-count-${postId}">${result.like_count}</span>`);
            // Casino notification
            if (result.points_awarded > 0) _showLikeToast(result);
        } else {
            btn.classList.remove('text-red-500');
            btn.classList.add('text-gray-400', 'hover:text-red-400');
            btn.innerHTML = heartIcon(false) + ` <span id="like-count-${postId}">${result.like_count}</span>`;
        }
    } catch (e) {
        alert(e.message);
    }
}

function heartIcon(filled) {
    return filled
        ? `<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>`
        : `<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>`;
}

// ==================== Delete ====================

async function deletePost(event, postId) {
    event.stopPropagation();
    const post = posts.find(p => p.id === postId);
    const isTeacherDeletingOther = currentUser.role === 'teacher' && post && post.author_id !== currentUser.id;
    const confirmMsg = isTeacherDeletingOther
        ? `¿Eliminar publicación de ${post.author_name}?`
        : '¿Estás seguro de eliminar esta publicación?';
    if (!confirm(confirmMsg)) return;
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE' });
        posts = posts.filter(p => p.id !== postId);
        const card = document.querySelector(`article[onclick="openPost(${postId})"]`);
        if (card) card.remove();
        if (!posts.length) document.getElementById('empty-state').classList.remove('hidden');
    } catch (e) {
        alert('Error al eliminar: ' + e.message);
    }
}

// ==================== Post Modal ====================

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
    openPostId = null;
    currentModalPost = null;
    // Clear any nested reply state
    activeReplyToId = null;
    if (document.getElementById('nested-reply-form')) {
        document.getElementById('nested-reply-form').remove();
    }
    // Restore reply composer visibility
    const composer = document.getElementById('modal-reply-composer');
    if (composer) composer.style.display = '';
}

function renderModalPost(post) {
    currentModalPost = post;
    const isTeacherPost = post.author_role === 'teacher';
    const initials = nameInitials(post.author_name);
    const avatarColor = isTeacherPost ? '#9C4927' : stringToColor(post.author_name);
    const timeStr = timeAgo(post.created_at);
    const isOwn = post.author_id === currentUser.id;
    const cantLike = isOwn;

    document.getElementById('modal-class-badge').textContent = post.class_name;

    const likeBtn = cantLike
        ? `<span class="flex items-center gap-1 text-sm text-gray-300 cursor-not-allowed">${heartIcon(false)} ${post.like_count}</span>`
        : `<button onclick="toggleModalLike(${post.id}, ${post.liked_by_me})" id="modal-like-btn"
                   class="flex items-center gap-1 text-sm ${post.liked_by_me ? 'text-red-500' : 'text-gray-500 hover:text-red-400'} transition">
               ${heartIcon(post.liked_by_me)} <span id="modal-like-count">${post.like_count}</span>
           </button>`;

    const teacherActions = currentUser.role === 'teacher'
        ? `<button onclick="togglePin(${post.id})"
                   class="flex items-center gap-1 text-sm ${post.pinned ? 'text-amber-500 hover:text-amber-700' : 'text-gray-400 hover:text-amber-500'} transition">
               📌 ${post.pinned ? 'Desfijar' : 'Fijar'}
           </button>
           <button onclick="toggleLock(${post.id})"
                   class="flex items-center gap-1 text-sm ${post.locked ? 'text-blue-400 hover:text-blue-600' : 'text-gray-400 hover:text-blue-400'} transition">
               🔒 ${post.locked ? 'Desbloquear' : 'Bloquear'}
           </button>`
        : '';

    const canDelete = isOwn || currentUser.role === 'teacher';
    const deleteBtn = canDelete
        ? `<button onclick="deleteModalPost()"
                   class="flex items-center gap-1 text-sm text-gray-400 hover:text-red-400 transition ml-auto">
               <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
               </svg>
               Eliminar
           </button>`
        : '';

    document.getElementById('modal-post-body').innerHTML = `
        <div class="flex items-start gap-3 mb-4">
            <div class="avatar text-white text-xs shrink-0" style="background:${avatarColor}">${initials}</div>
            <div>
                <p class="font-medium text-gray-800 text-sm">${isTeacherPost ? '👨‍🏫 ' : ''}${escHtml(post.author_name)}${isTeacherPost ? ' <span class="text-secondary text-xs font-medium">• Profesor</span>' : ''}</p>
                <p class="text-gray-400 text-xs">${timeStr}</p>
            </div>
        </div>
        ${post.title ? `<h2 class="font-bold text-gray-900 text-lg mb-2">${escHtml(post.title)}</h2>` : ''}
        <p class="text-gray-700 text-sm whitespace-pre-wrap leading-relaxed">${linkify(post.content)}</p>
        <div class="flex items-center gap-3 mt-4 pt-3 border-t border-gray-100 flex-wrap">
            ${likeBtn}
            <span class="flex items-center gap-1 text-sm text-gray-400">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
                <span id="modal-comment-count">${post.comment_count}</span>
            </span>
            ${teacherActions}
            ${deleteBtn}
        </div>
        ${post.locked ? '<p class="text-sm text-gray-400 mt-3 text-center py-2 bg-gray-50 rounded-lg">🔒 Esta publicación está bloqueada. No se permiten nuevas respuestas.</p>' : ''}
    `;

    // Show/hide reply composer based on locked status
    const replyComposer = document.getElementById('modal-reply-composer');
    if (replyComposer) replyComposer.style.display = post.locked ? 'none' : '';

    renderModalReplies(post.replies || []);
}

async function toggleModalLike(postId, currentlyLiked) {
    try {
        const result = await apiCall(`/forum/posts/${postId}/like`, { method: 'POST' });
        const btn = document.getElementById('modal-like-btn');
        const countEl = document.getElementById('modal-like-count');
        if (countEl) countEl.textContent = result.like_count;
        if (btn) {
            btn.className = `flex items-center gap-1 text-sm ${result.liked ? 'text-red-500' : 'text-gray-500 hover:text-red-400'} transition`;
            btn.innerHTML = heartIcon(result.liked) + ` <span id="modal-like-count">${result.like_count}</span>`;
            btn.setAttribute('onclick', `toggleModalLike(${postId}, ${result.liked})`);
        }
        // Update feed card and local state
        const post = posts.find(p => p.id === postId);
        if (post) {
            post.like_count = result.like_count;
            post.liked_by_me = result.liked;
            if (result.post_points_earned !== undefined) post.points_earned = result.post_points_earned;
        }
        const feedCount = document.getElementById(`like-count-${postId}`);
        if (feedCount) feedCount.textContent = result.like_count;
        // Casino notification
        if (result.liked && result.points_awarded > 0) _showLikeToast(result);
    } catch (e) {
        alert(e.message);
    }
}

// ==================== Replies ====================

let activeReplyToId = null; // parent_reply_id for nested reply

function renderModalReplies(replies) {
    const container = document.getElementById('modal-replies');
    if (!replies.length) {
        container.innerHTML = '<p class="text-gray-400 text-sm text-center py-2">Sin respuestas aún.</p>';
        return;
    }
    container.innerHTML = `
        <h3 class="text-sm font-semibold text-gray-600 mb-3">Respuestas (${countAllReplies(replies)})</h3>
        ${replies.map(r => renderReply(r, false)).join('')}
    `;
}

function countAllReplies(replies) {
    return replies.reduce((sum, r) => sum + 1 + (r.children ? r.children.length : 0), 0);
}

function renderReply(reply, isNested) {
    const isTeacherReply = reply.author_role === 'teacher';
    const initials = nameInitials(reply.author_name);
    const avatarColor = isTeacherReply ? '#9C4927' : stringToColor(reply.author_name);
    const canDelete = reply.author_id === currentUser.id || currentUser.role === 'teacher';
    const showReplyBtn = !isNested; // only top-level replies get a "Reply" button

    const teacherBadge = isTeacherReply
        ? `<span class="text-secondary text-xs font-medium">👨‍🏫 Profesor</span>` : '';

    const deleteBtn = canDelete
        ? `<button onclick="deleteReply(${reply.id})" class="text-gray-300 hover:text-red-400 transition text-xs">Eliminar</button>`
        : '';

    const replyBtn = showReplyBtn
        ? `<button onclick="startNestedReply(${reply.id})" class="text-gray-400 hover:text-primary text-xs transition">Responder</button>`
        : '';

    const children = reply.children && reply.children.length
        ? `<div class="reply-indent mt-2 space-y-2">
               ${reply.children.map(c => renderReply(c, true)).join('')}
           </div>`
        : '';

    const nestedReplyPlaceholder = showReplyBtn
        ? `<div id="nested-reply-placeholder-${reply.id}"></div>` : '';

    return `
    <div class="mb-3" id="reply-${reply.id}">
        <div class="flex items-start gap-2">
            <div class="avatar text-white shrink-0" style="background:${avatarColor}; width:1.75rem; height:1.75rem; font-size:0.65rem">${initials}</div>
            <div class="flex-1 min-w-0">
                <div class="flex items-baseline gap-2 flex-wrap">
                    <span class="font-medium ${isTeacherReply ? 'text-secondary' : 'text-gray-800'} text-xs">${isTeacherReply ? '👨‍🏫 ' : ''}${escHtml(reply.author_name)}</span>
                    ${teacherBadge}
                    <span class="text-gray-400 text-xs">${timeAgo(reply.created_at)}</span>
                </div>
                <p class="text-gray-700 text-sm mt-0.5 whitespace-pre-wrap">${linkify(reply.content)}</p>
                <div class="flex items-center gap-3 mt-1">
                    ${replyBtn}
                    ${deleteBtn}
                </div>
                ${nestedReplyPlaceholder}
                ${children}
            </div>
        </div>
    </div>`;
}

function startNestedReply(parentReplyId) {
    // Remove any existing nested reply form
    const existing = document.getElementById('nested-reply-form');
    if (existing) existing.remove();
    activeReplyToId = parentReplyId;

    const placeholder = document.getElementById(`nested-reply-placeholder-${parentReplyId}`);
    if (!placeholder) return;

    placeholder.insertAdjacentHTML('afterend', `
        <div id="nested-reply-form" class="mt-2 pl-2">
            <textarea id="nested-reply-input" rows="2" placeholder="Escribe tu respuesta..."
                      class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none focus:ring-2 focus:ring-primary outline-none"></textarea>
            <div class="flex justify-end gap-2 mt-1">
                <button onclick="cancelNestedReply()" class="text-xs text-gray-500 hover:text-gray-700">Cancelar</button>
                <button onclick="submitNestedReply(${parentReplyId})"
                        class="px-3 py-1 text-xs bg-primary hover:bg-secondary text-white rounded-lg transition">
                    Responder
                </button>
            </div>
        </div>
    `);
    document.getElementById('nested-reply-input').focus();
}

function cancelNestedReply() {
    const form = document.getElementById('nested-reply-form');
    if (form) form.remove();
    activeReplyToId = null;
}

async function submitModalReply() {
    const input = document.getElementById('modal-reply-input');
    const content = input.value.trim();
    if (!content) return;
    await postReply(content, null);
    input.value = '';
}

async function submitNestedReply(parentReplyId) {
    const input = document.getElementById('nested-reply-input');
    const content = input.value.trim();
    if (!content) return;
    await postReply(content, parentReplyId);
    cancelNestedReply();
}

async function postReply(content, parentReplyId) {
    if (!openPostId) return;
    try {
        await apiCall(`/forum/posts/${openPostId}/replies`, {
            method: 'POST',
            body: JSON.stringify({ content, parent_reply_id: parentReplyId }),
        });
        // Refresh the post to get updated replies
        const post = await apiCall(`/forum/posts/${openPostId}`);
        renderModalReplies(post.replies || []);
        // Update comment count in modal and feed
        const modalCount = document.getElementById('modal-comment-count');
        if (modalCount) modalCount.textContent = post.comment_count;
        const feedPost = posts.find(p => p.id === openPostId);
        if (feedPost) feedPost.comment_count = post.comment_count;
        // Update feed card comment count display (re-render won't work easily, just update text)
        const feedCards = document.querySelectorAll(`article[onclick="openPost(${openPostId})"]`);
        feedCards.forEach(card => {
            const commentSpans = card.querySelectorAll('button');
            commentSpans.forEach(btn => {
                if (btn.onclick && btn.onclick.toString().includes('openPost')) {
                    btn.querySelector('svg') && btn.childNodes.forEach(n => {
                        if (n.nodeType === 3 && n.textContent.trim()) n.textContent = ` ${post.comment_count}`;
                    });
                }
            });
        });
    } catch (e) {
        alert('Error al responder: ' + e.message);
    }
}

async function deleteReply(replyId) {
    if (!confirm('¿Eliminar esta respuesta?')) return;
    try {
        await apiCall(`/forum/replies/${replyId}`, { method: 'DELETE' });
        // Refresh post
        const post = await apiCall(`/forum/posts/${openPostId}`);
        renderModalReplies(post.replies || []);
        const modalCount = document.getElementById('modal-comment-count');
        if (modalCount) modalCount.textContent = post.comment_count;
    } catch (e) {
        alert('Error al eliminar: ' + e.message);
    }
}

// ==================== Moderation ====================

async function togglePin(postId) {
    try {
        const result = await apiCall(`/forum/posts/${postId}/pin`, { method: 'PATCH' });
        const post = posts.find(p => p.id === postId);
        if (post) post.pinned = result.pinned;
        // If modal is open for this post, refresh it
        if (currentModalPost && currentModalPost.id === postId) {
            const freshPost = await apiCall(`/forum/posts/${postId}`);
            renderModalPost(freshPost);
            return;
        }
        // Update feed card
        if (post) _replaceCard(postId, post);
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function toggleLock(postId) {
    try {
        const result = await apiCall(`/forum/posts/${postId}/lock`, { method: 'PATCH' });
        const post = posts.find(p => p.id === postId);
        if (post) post.locked = result.locked;
        // If modal is open for this post, refresh it
        if (currentModalPost && currentModalPost.id === postId) {
            const freshPost = await apiCall(`/forum/posts/${postId}`);
            renderModalPost(freshPost);
            return;
        }
        // Update feed card
        if (post) _replaceCard(postId, post);
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

function _replaceCard(postId, post) {
    const card = document.querySelector(`article[onclick="openPost(${postId})"]`);
    if (card) {
        const temp = document.createElement('div');
        temp.innerHTML = renderPostCard(post);
        card.replaceWith(temp.firstElementChild);
    }
}

async function deleteModalPost() {
    if (!currentModalPost) return;
    const isTeacherDeletingOther = currentUser.role === 'teacher' && currentModalPost.author_id !== currentUser.id;
    const confirmMsg = isTeacherDeletingOther
        ? `¿Eliminar publicación de ${currentModalPost.author_name}?`
        : '¿Estás seguro de eliminar esta publicación?';
    if (!confirm(confirmMsg)) return;
    const postId = currentModalPost.id;
    try {
        await apiCall(`/forum/posts/${postId}`, { method: 'DELETE' });
        closePostModal();
        posts = posts.filter(p => p.id !== postId);
        const card = document.querySelector(`article[onclick="openPost(${postId})"]`);
        if (card) card.remove();
        if (!posts.length) document.getElementById('empty-state').classList.remove('hidden');
    } catch (e) {
        alert('Error al eliminar: ' + e.message);
    }
}

// ==================== Notifications ====================

function _showLikeToast(result) {
    const pts = result.points_awarded.toFixed(2);
    const name = result.author_name || 'el autor';
    let msg, bg;

    let duration = 3000;
    if (result.bonus_type === 'jackpot') {
        msg = `💰 ¡JACKPOT! Le diste +${pts} pts a ${name}`;
        bg = 'linear-gradient(135deg, #f59e0b, #d97706)';
        duration = 5000;
    } else if (result.bonus_type === 'double') {
        msg = `🎰 ¡DOBLE! Le diste +${pts} pts a ${name}`;
        bg = 'linear-gradient(135deg, #EA8251, #9C4927)';
        duration = 4000;
    } else if (result.bonus_type === 'mini') {
        msg = `✨ Le diste +${pts} pts a ${name}`;
        bg = '#059669';
    } else {
        msg = `Le diste +${pts} pts a ${name}`;
        bg = '#1F2020';
    }
    _showToast(msg, bg, duration);
}

function _showToast(msg, bg, duration = 3000) {
    const el = document.createElement('div');
    el.style.cssText = `
        position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%) translateY(1rem);
        z-index: 9999; padding: 0.75rem 1.25rem; border-radius: 0.75rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25); color: #fff; font-size: 0.875rem;
        font-weight: 600; white-space: nowrap; background: ${bg};
        opacity: 0; transition: opacity 0.3s ease, transform 0.3s ease;
        font-family: system-ui, sans-serif;
    `;
    el.textContent = msg;
    document.body.appendChild(el);
    requestAnimationFrame(() => {
        el.style.opacity = '1';
        el.style.transform = 'translateX(-50%) translateY(0)';
    });
    setTimeout(() => {
        el.style.opacity = '0';
        el.style.transform = 'translateX(-50%) translateY(1rem)';
        setTimeout(() => el.remove(), 350);
    }, duration);
}

// ==================== Utils ====================

function escHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function linkify(text) {
    const escaped = escHtml(text);
    return escaped.replace(
        /(https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)\]])/g,
        '<a href="$1" target="_blank" rel="noopener noreferrer" class="text-primary underline hover:text-secondary break-all">$1</a>'
    );
}

function nameInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    return parts.length === 1
        ? parts[0][0].toUpperCase()
        : (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function setAvatarInitials(id, name) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = nameInitials(name);
    el.style.background = stringToColor(name);
    el.style.color = 'white';
}

function stringToColor(str) {
    const colors = [
        '#EA8251', '#9C4927', '#2563EB', '#059669', '#7C3AED',
        '#DC2626', '#0891B2', '#D97706', '#4F46E5', '#BE185D',
    ];
    let hash = 0;
    for (let i = 0; i < (str || '').length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
}

function timeAgo(isoString) {
    const date = new Date(isoString + (isoString.endsWith('Z') ? '' : 'Z'));
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHr = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHr / 24);

    if (diffSec < 60) return 'justo ahora';
    if (diffMin < 60) return `hace ${diffMin}m`;
    if (diffHr < 24) return `hace ${diffHr}h`;
    if (diffDay < 7) return `hace ${diffDay}d`;
    return date.toLocaleDateString('es-MX', { day: 'numeric', month: 'short' });
}

// Close modal on backdrop click
document.getElementById('post-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closePostModal();
});

// Keyboard: Escape closes modal
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePostModal();
});

// ==================== Boot ====================
init();
