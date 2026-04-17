// IDP Agent — Frontend Logic v4 (Annotations + Download Report)

document.addEventListener('DOMContentLoaded', () => {
    initAnimations();
    initUpload();
    initChat();
    checkBackend();
    setInterval(checkBackend, 30000);
});

// ── Backend Health ──────────────────────────────────────────────────────────
async function checkBackend() {
    const dot   = document.getElementById('backend-status');
    const label = document.getElementById('status-label');
    try {
        const res  = await fetch('/health');
        const data = await res.json();
        dot.className   = 'online-dot online';
        label.innerText = data.document_loaded
            ? `Online · ${data.filename}`
            : 'Backend Online';
    } catch {
        dot.className   = 'online-dot offline';
        label.innerText = 'Backend Offline';
    }
}

// ── Animations ──────────────────────────────────────────────────────────────
function initAnimations() {
    if (typeof gsap === 'undefined') return;
    gsap.timeline()
        .from('.hero-title',    { opacity: 0, y: 30, duration: 1,   ease: 'power4.out' })
        .from('.hero-subtitle', { opacity: 0, y: 20, duration: 0.8, ease: 'power3.out' }, '-=0.5')
        .from('.app-grid',      { opacity: 0, y: 40, duration: 1,   ease: 'power4.out' }, '-=0.5');

    const container = document.getElementById('particles-container');
    if (!container) return;
    for (let i = 0; i < 20; i++) {
        const p = document.createElement('div');
        p.style.cssText = `position:absolute;border-radius:50%;
            width:${Math.random() * 4 + 2}px;height:${Math.random() * 4 + 2}px;
            background:rgba(34,211,238,0.2);
            left:${Math.random() * 100}%;top:${Math.random() * 100}%`;
        container.appendChild(p);
        gsap.to(p, {
            x: (Math.random() - 0.5) * 200, y: (Math.random() - 0.5) * 200,
            duration: Math.random() * 10 + 10, repeat: -1, yoyo: true, ease: 'sine.inOut'
        });
    }
}

// ── Upload (Click + Drag-and-Drop) ──────────────────────────────────────────
function initUpload() {
    const zone     = document.getElementById('upload-zone');
    const input    = document.getElementById('file-input');
    const reset    = document.getElementById('reset-btn');

    zone.onclick = () => input.click();

    ['dragenter', 'dragover'].forEach(e => zone.addEventListener(e, ev => {
        ev.preventDefault(); zone.classList.add('drag-over');
    }));
    ['dragleave', 'drop'].forEach(e => zone.addEventListener(e, ev => {
        ev.preventDefault(); zone.classList.remove('drag-over');
    }));
    zone.addEventListener('drop', e => {
        const f = e.dataTransfer.files[0];
        if (f) processFile(f);
    });
    input.onchange = e => { if (e.target.files[0]) processFile(e.target.files[0]); };
    reset.onclick  = resetUpload;
}

async function processFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        addMessage('system', '❌ Only PDF files are supported. Please upload a .pdf file.');
        return;
    }

    document.getElementById('doc-name').innerText = file.name;
    document.getElementById('doc-size').innerText = (file.size / 1024 / 1024).toFixed(2) + ' MB';

    const progress = document.getElementById('upload-progress');
    const fill     = progress.querySelector('.progress-fill');
    const label    = document.getElementById('progress-label');

    document.getElementById('upload-zone').classList.add('hidden');
    progress.classList.remove('hidden');
    label.innerText = 'Indexing document with semantic embeddings...';
    if (typeof gsap !== 'undefined') gsap.to(fill, { width: '85%', duration: 3, ease: 'power2.inOut' });

    try {
        const formData = new FormData();
        formData.append('file', file);
        const res  = await fetch('/upload', { method: 'POST', body: formData });
        const data = await res.json();

        if (res.ok) {
            if (typeof gsap !== 'undefined') gsap.to(fill, { width: '100%', duration: 0.3 });
            showDocumentInfo();
            enableChat();
            showAnnotationsPanel();
            document.getElementById('download-btn').classList.remove('hidden');
            addMessage('system', `✅ **${file.name}** ready!\n\n📊 *${data.chunks_indexed} knowledge chunks indexed.* You can now:\n- 💬 Ask questions about the document\n- 📝 Add personal annotations (left panel)\n- ⬇️ Download a PDF report anytime`);
            checkBackend();
        } else {
            addMessage('system', '❌ Upload failed: ' + (data.detail || 'Unknown error'));
            resetUpload();
        }
    } catch {
        addMessage('system', '❌ Could not reach the backend. Make sure the server is healthy.');
        resetUpload();
    } finally {
        setTimeout(() => {
            progress.classList.add('hidden');
            if (typeof gsap !== 'undefined') gsap.set(fill, { width: '0%' });
        }, 600);
    }
}

function showDocumentInfo() {
    const info = document.getElementById('document-info');
    info.classList.remove('hidden');
    if (typeof gsap !== 'undefined') gsap.from(info, { scale: 0.9, opacity: 0, duration: 0.5, ease: 'back.out(1.7)' });
}

function resetUpload() {
    document.getElementById('file-input').value   = '';
    document.getElementById('document-info').classList.add('hidden');
    document.getElementById('upload-zone').classList.remove('hidden');
    document.getElementById('annotations-panel').classList.add('hidden');
    document.getElementById('download-btn').classList.add('hidden');
    document.getElementById('annotations-list').innerHTML = '';
    document.getElementById('ann-count').innerText = '0';
    disableChat();
    checkBackend();
}

// ── Annotations ─────────────────────────────────────────────────────────────
function showAnnotationsPanel() {
    const panel = document.getElementById('annotations-panel');
    panel.classList.remove('hidden');
    if (typeof gsap !== 'undefined') gsap.from(panel, { opacity: 0, y: 10, duration: 0.5, ease: 'power2.out' });
}

async function addAnnotation() {
    const input = document.getElementById('annotation-input');
    const text  = input.value.trim();
    if (!text) return;

    const btn = document.getElementById('add-annotation-btn');
    btn.disabled  = true;
    btn.innerText = 'Saving...';

    try {
        const res  = await fetch('/annotations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const data = await res.json();

        if (res.ok) {
            input.value = '';
            renderAnnotations();
            addMessage('system', `📝 Annotation saved! I'll include this context when answering your questions.`);
        } else {
            addMessage('system', '❌ ' + (data.detail || 'Could not save annotation'));
        }
    } catch {
        addMessage('system', '❌ Failed to save annotation. Check connection.');
    } finally {
        btn.disabled  = false;
        btn.innerText = '+ Add Note';
    }
}

// Shortcut: Ctrl+Enter in annotation textarea
document.addEventListener('DOMContentLoaded', () => {
    const annInput = document.getElementById('annotation-input');
    if (annInput) {
        annInput.addEventListener('keydown', e => {
            if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); addAnnotation(); }
        });
    }
});

async function renderAnnotations() {
    const res  = await fetch('/annotations');
    const data = await res.json();
    const list = document.getElementById('annotations-list');
    const count = document.getElementById('ann-count');

    count.innerText = data.annotations.length;
    list.innerHTML  = '';

    data.annotations.forEach((ann, i) => {
        const item = document.createElement('div');
        item.className = 'annotation-item';
        item.innerHTML = `
            <div class="ann-meta">${ann.timestamp}</div>
            <div class="ann-text">${escapeHtml(ann.text)}</div>
            <button class="ann-delete-btn" onclick="deleteAnnotation(${i})" title="Delete">✕</button>
        `;
        list.appendChild(item);
        if (typeof gsap !== 'undefined') gsap.from(item, { opacity: 0, x: -10, duration: 0.3 });
    });
}

async function deleteAnnotation(index) {
    const res = await fetch(`/annotations/${index}`, { method: 'DELETE' });
    if (res.ok) renderAnnotations();
}

// ── Download Report ──────────────────────────────────────────────────────────
async function downloadReport() {
    const btn = document.getElementById('download-btn');
    btn.innerHTML = '<span>⏳</span> Generating...';
    btn.disabled  = true;

    try {
        const res = await fetch('/download-report');
        if (!res.ok) {
            const err = await res.json();
            addMessage('system', '❌ Could not generate report: ' + (err.detail || 'Unknown error'));
            return;
        }

        // Trigger file download
        const blob     = await res.blob();
        const url      = URL.createObjectURL(blob);
        const a        = document.createElement('a');
        const filename = res.headers.get('content-disposition')
            ?.match(/filename="(.+)"/)?.[1] || 'IDP_Report.pdf';
        a.href         = url;
        a.download     = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        addMessage('system', `✅ **Report downloaded!** Your PDF report includes all annotations and Q&A history.`);
    } catch {
        addMessage('system', '❌ Download failed. Check your connection.');
    } finally {
        btn.innerHTML = '<span>⬇</span> Download Report';
        btn.disabled  = false;
    }
}

// ── Chat ─────────────────────────────────────────────────────────────────────
function initChat() {
    const input = document.getElementById('chat-input');
    const send  = document.getElementById('send-btn');
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    send.onclick = sendMessage;
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const query = input.value.trim();
    if (!query || input.disabled) return;

    addMessage('user', query);
    input.value = '';
    setAgentBusy(true);

    try {
        const res  = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        const data = await res.json();

        if (data.response) {
            addMessage('system', data.response);
        } else if (data.error) {
            addMessage('system', '⚠️ ' + data.error);
        }
    } catch {
        addMessage('system', '⛔ Lost connection to the AI brain. Please refresh.');
    } finally {
        setAgentBusy(false);
    }
}

// ── Message Rendering ────────────────────────────────────────────────────────
function renderMarkdown(text) {
    return text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;font-family:monospace;font-size:0.85em">$1</code>')
        .replace(/^[-•]\s(.+)/gm, '<li>$1</li>')
        .replace(/^\d+\.\s(.+)/gm, '<li>$1</li>')
        .replace(/<li>/g, '<li style="margin-left:16px;list-style:disc">')
        .replace(/\n/g, '<br>');
}

function addMessage(type, text) {
    const chat = document.getElementById('chat-messages');
    const msg  = document.createElement('div');
    msg.className = `message ${type}`;
    msg.innerHTML = `<div class="avatar">${type === 'user' ? '👤' : '🤖'}</div><div class="text"></div>`;
    const target = msg.querySelector('.text');
    chat.appendChild(msg);

    if (type === 'system') {
        target.innerHTML     = renderMarkdown(text);
        target.style.opacity = '0';
        if (typeof gsap !== 'undefined') gsap.to(target, { opacity: 1, duration: 0.5 });
        else target.style.opacity = '1';
    } else {
        target.innerText = text;
    }

    if (typeof gsap !== 'undefined') gsap.from(msg, { opacity: 0, x: type === 'user' ? 20 : -20, duration: 0.4, ease: 'power2.out' });
    chat.scrollTop = chat.scrollHeight;
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function enableChat()  { document.getElementById('chat-input').disabled = false; document.getElementById('send-btn').disabled = false; }
function disableChat() { document.getElementById('chat-input').disabled = true;  document.getElementById('send-btn').disabled = true;  }

function setAgentBusy(busy) {
    const ind   = document.getElementById('agent-indicator');
    const label = document.getElementById('agent-label');
    const send  = document.getElementById('send-btn');
    const input = document.getElementById('chat-input');
    if (busy) {
        ind.className   = 'agent-busy';
        label.innerText = 'Agent Thinking...';
        send.disabled   = true;
        input.disabled  = true;
    } else {
        ind.className   = 'agent-ready';
        label.innerText = 'Agent Ready';
        send.disabled   = false;
        input.disabled  = false;
        input.focus();
    }
}

function escapeHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
