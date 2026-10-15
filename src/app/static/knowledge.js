const elements = {
    rows: document.getElementById('knowledgeRows'),
    empty: document.getElementById('emptyState'),
    loading: document.getElementById('loadingState'),
    pagination: document.getElementById('pagination'),
    resultTitle: document.getElementById('resultTitle'),
    resultCount: document.getElementById('resultCount'),
    pageStatus: document.getElementById('pageStatus'),
    searchForm: document.getElementById('searchForm'),
    keyword: document.getElementById('keywordInput'),
    reset: document.getElementById('resetButton'),
    refresh: document.getElementById('refreshButton'),
    pageSize: document.getElementById('pageSizeSelect'),
    create: document.getElementById('createButton'),
    dialog: document.getElementById('editorDialog'),
    form: document.getElementById('editorForm'),
    documentId: document.getElementById('documentId'),
    editorTitle: document.getElementById('editorTitle'),
    source: document.getElementById('sourceInput'),
    content: document.getElementById('contentInput'),
    contentCount: document.getElementById('contentCount'),
    editorStatus: document.getElementById('editorStatus'),
    save: document.getElementById('saveButton'),
    close: document.getElementById('closeEditorButton'),
    cancel: document.getElementById('cancelEditorButton')
};

const state = { page: 0, size: 10, keyword: '', totalPages: 0, items: [] };

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
}

async function responseError(response, fallback) {
    try {
        const body = await response.json();
        return new Error(body.message || body.detail || fallback);
    } catch (_) {
        return new Error(fallback);
    }
}

function setPageStatus(message = '', type = '') {
    elements.pageStatus.className = `page-status ${type}`.trim();
    elements.pageStatus.textContent = message;
}

function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
    }).format(date);
}

function documentDate(document) {
    return document.metadata?.updatedAt || document.metadata?.createdAt;
}

async function loadDocuments() {
    elements.loading.classList.remove('hidden');
    elements.empty.classList.add('hidden');
    setPageStatus();
    const params = new URLSearchParams({
        page: String(state.page),
        size: String(state.size),
        keyword: state.keyword
    });
    try {
        const response = await fetch(`/api/knowledge/documents?${params}`);
        if (!response.ok) throw await responseError(response, '知识库读取失败');
        const data = await response.json();
        state.items = data.items || [];
        state.totalPages = data.totalPages || 0;
        if (state.page > 0 && !state.items.length && data.totalElements > 0) {
            state.page -= 1;
            return loadDocuments();
        }
        renderDocuments();
        renderPagination();
        elements.resultTitle.textContent = state.keyword ? `“${state.keyword}”的结果` : '全部知识';
        elements.resultCount.textContent = `共 ${data.totalElements || 0} 条`;
    } catch (error) {
        state.items = [];
        elements.rows.innerHTML = '';
        elements.resultCount.textContent = '读取失败';
        setPageStatus(error.message, 'error');
    } finally {
        elements.loading.classList.add('hidden');
    }
}

function renderDocuments() {
    elements.rows.innerHTML = state.items.map(document => {
        const source = document.metadata?.source;
        return `
            <tr>
                <td>
                    <div class="content-cell">
                        <span class="content-preview">${escapeHtml(document.content)}</span>
                        <span class="document-id" title="${escapeHtml(document.id)}">${escapeHtml(document.id)}</span>
                    </div>
                </td>
                <td>${source
                    ? `<span class="source-badge" title="${escapeHtml(source)}">${escapeHtml(source)}</span>`
                    : '<span class="muted-value">未设置</span>'}</td>
                <td><span class="date-value">${escapeHtml(formatDate(documentDate(document)))}</span></td>
                <td>
                    <div class="row-actions">
                        <button class="row-action" type="button" data-action="edit" data-id="${escapeHtml(document.id)}">编辑</button>
                        <button class="row-action danger" type="button" data-action="delete" data-id="${escapeHtml(document.id)}">删除</button>
                    </div>
                </td>
            </tr>`;
    }).join('');
    elements.empty.classList.toggle('hidden', state.items.length > 0);
}

function pageNumbers() {
    const pages = new Set([0, state.totalPages - 1]);
    for (let page = state.page - 2; page <= state.page + 2; page += 1) {
        if (page >= 0 && page < state.totalPages) pages.add(page);
    }
    return [...pages].filter(page => page >= 0).sort((a, b) => a - b);
}

function renderPagination() {
    if (state.totalPages <= 1) {
        elements.pagination.innerHTML = '';
        return;
    }
    const pages = pageNumbers();
    let previous = -2;
    const buttons = pages.map(page => {
        const gap = page - previous > 1 ? '<span class="page-ellipsis">…</span>' : '';
        previous = page;
        return `${gap}<button class="page-button ${page === state.page ? 'active' : ''}"
            type="button" data-page="${page}" aria-label="第 ${page + 1} 页">${page + 1}</button>`;
    }).join('');
    elements.pagination.innerHTML = `
        <button class="page-button" type="button" data-page="${state.page - 1}" ${state.page === 0 ? 'disabled' : ''}>上一页</button>
        ${buttons}
        <button class="page-button" type="button" data-page="${state.page + 1}" ${state.page + 1 >= state.totalPages ? 'disabled' : ''}>下一页</button>`;
}

function openCreate() {
    elements.form.reset();
    elements.documentId.value = '';
    elements.editorTitle.textContent = '新增知识';
    elements.editorStatus.textContent = '';
    updateContentCount();
    elements.dialog.showModal();
    elements.content.focus();
}

function openEdit(document) {
    elements.documentId.value = document.id;
    elements.source.value = document.metadata?.source || '';
    elements.content.value = document.content || '';
    elements.editorTitle.textContent = '编辑知识';
    elements.editorStatus.textContent = '';
    updateContentCount();
    elements.dialog.showModal();
    elements.content.focus();
}

function closeEditor() {
    if (!elements.save.disabled) elements.dialog.close();
}

async function deleteDocument(document) {
    const preview = (document.content || '').replaceAll(/\s+/g, ' ').slice(0, 60);
    if (!window.confirm(`确定删除这条知识吗？\n\n${preview}${document.content?.length > 60 ? '…' : ''}`)) return;
    try {
        const response = await fetch(`/api/knowledge/documents/${encodeURIComponent(document.id)}`, { method: 'DELETE' });
        if (!response.ok) throw await responseError(response, '删除失败');
        await loadDocuments();
        setPageStatus('知识已删除。', 'success');
    } catch (error) {
        setPageStatus(error.message, 'error');
    }
}

elements.searchForm.addEventListener('submit', event => {
    event.preventDefault();
    state.keyword = elements.keyword.value.trim();
    state.page = 0;
    loadDocuments();
});

elements.reset.addEventListener('click', () => {
    elements.keyword.value = '';
    state.keyword = '';
    state.page = 0;
    loadDocuments();
});

elements.refresh.addEventListener('click', loadDocuments);
elements.create.addEventListener('click', openCreate);
elements.close.addEventListener('click', closeEditor);
elements.cancel.addEventListener('click', closeEditor);

elements.pageSize.addEventListener('change', () => {
    state.size = Number(elements.pageSize.value);
    state.page = 0;
    loadDocuments();
});

elements.pagination.addEventListener('click', event => {
    const button = event.target.closest('[data-page]');
    if (!button || button.disabled) return;
    state.page = Number(button.dataset.page);
    loadDocuments();
});

elements.rows.addEventListener('click', event => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const document = state.items.find(item => item.id === button.dataset.id);
    if (!document) return;
    if (button.dataset.action === 'edit') openEdit(document);
    if (button.dataset.action === 'delete') deleteDocument(document);
});

elements.form.addEventListener('submit', async event => {
    event.preventDefault();
    const id = elements.documentId.value;
    const content = elements.content.value.trim();
    if (!content) return;
    elements.save.disabled = true;
    elements.editorStatus.className = 'dialog-status working';
    elements.editorStatus.textContent = id ? '正在更新内容并重新生成向量…' : '正在生成向量并保存…';
    try {
        const source = elements.source.value.trim();
        const metadata = id ? { source: source || null } : (source ? { source } : {});
        const response = await fetch(id
                ? `/api/knowledge/documents/${encodeURIComponent(id)}`
                : '/api/knowledge/documents', {
            method: id ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, metadata })
        });
        if (!response.ok) throw await responseError(response, id ? '更新失败' : '新增失败');
        elements.dialog.close();
        state.page = 0;
        await loadDocuments();
        setPageStatus(id ? '知识已更新并重新生成向量。' : '知识已添加到向量库。', 'success');
    } catch (error) {
        elements.editorStatus.className = 'dialog-status error';
        elements.editorStatus.textContent = error.message;
    } finally {
        elements.save.disabled = false;
    }
});

function updateContentCount() {
    elements.contentCount.textContent = `${elements.content.value.length} / 20000`;
}

elements.content.addEventListener('input', updateContentCount);
loadDocuments();
