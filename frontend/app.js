// ============================================
// CODEAGENT - Frontend Application
// ============================================

const API_BASE_URL = 'http://localhost:8005/api/v1';

// Application State
const state = {
    currentRepo: null,
    currentSession: null,
    repositories: [],
    sessions: [],
    isConnected: false
};

// ============================================
// API Client
// ============================================

const api = {
    async healthCheck() {
        try {
            const response = await fetch('http://localhost:8005/health');
            const data = await response.json();
            return data;
        } catch (error) {
            throw new Error('Health check failed');
        }
    },

    async listRepos() {
        const response = await fetch(`${API_BASE_URL}/repos`);
        const data = await response.json();
        return data;
    },

    async createRepo(repoData) {
        const response = await fetch(`${API_BASE_URL}/repos`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(repoData)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error?.message || 'Failed to create repository');
        }
        return await response.json();
    },

    async deleteRepo(repoId) {
        const response = await fetch(`${API_BASE_URL}/repos/${repoId}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error('Failed to delete repository');
        return await response.json();
    },

    async createSession(repoId) {
        const response = await fetch(`${API_BASE_URL}/repos/${repoId}/sessions`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error('Failed to create session');
        return await response.json();
    },

    async getSession(repoId, sessionId) {
        const response = await fetch(`${API_BASE_URL}/repos/${repoId}/sessions/${sessionId}`);
        if (!response.ok) throw new Error('Failed to get session');
        return await response.json();
    },

    async deleteSession(repoId, sessionId) {
        const response = await fetch(`${API_BASE_URL}/repos/${repoId}/sessions/${sessionId}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error('Failed to delete session');
        return await response.json();
    },

    async askQuestion(repoId, question, sessionId = null) {
        const response = await fetch(`${API_BASE_URL}/repos/${repoId}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question,
                session_id: sessionId
            })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error?.message || 'Failed to ask question');
        }
        return await response.json();
    }
};

// ============================================
// UI Controllers
// ============================================

const ui = {
    // Health Status
    updateHealthStatus(status) {
        const healthStatus = document.getElementById('healthStatus');
        const statusText = healthStatus.querySelector('.status-text');

        if (status.status === 'healthy') {
            healthStatus.classList.remove('disconnected');
            healthStatus.classList.add('connected');
            statusText.textContent = '已连接';
            state.isConnected = true;
        } else {
            healthStatus.classList.remove('connected');
            healthStatus.classList.add('disconnected');
            statusText.textContent = '连接异常';
            state.isConnected = false;
        }
    },

    // Repository List
    renderRepositories(repos) {
        const repoList = document.getElementById('repoList');

        if (repos.length === 0) {
            repoList.innerHTML = '<div class="empty-state">暂无项目</div>';
            return;
        }

        repoList.innerHTML = repos.map(repo => `
            <div class="repo-item ${state.currentRepo?.id === repo.id ? 'active' : ''}" data-repo-id="${repo.id}">
                <div class="repo-name">${repo.name}</div>
                <div class="repo-path">${repo.path}</div>
            </div>
        `).join('');

        // Add click handlers
        repoList.querySelectorAll('.repo-item').forEach(item => {
            item.addEventListener('click', () => {
                const repoId = item.dataset.repoId;
                this.selectRepository(repoId);
            });
        });
    },

    async selectRepository(repoId) {
        const repo = state.repositories.find(r => r.id === repoId);
        if (!repo) return;

        state.currentRepo = repo;
        state.currentSession = null; // Clear current session

        // Update UI
        document.getElementById('currentRepoName').textContent = repo.name;
        document.getElementById('currentRepoPath').textContent = repo.path;

        // Load existing sessions first
        await this.loadSessions(repoId);

        // Show welcome with "New Chat" option
        this.showWelcomeScreen(repo);

        // Update active state in list
        document.querySelectorAll('.repo-item').forEach(item => {
            item.classList.toggle('active', item.dataset.repoId === repoId);
        });
    },

    showWelcomeScreen(repo) {
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M12 2L2 7L12 12L22 7L12 2Z"/>
                        <path d="M2 17L12 22L22 17"/>
                        <path d="M2 12L12 17L22 12"/>
                    </svg>
                </div>
                <h3>${repo.name}</h3>
                <p>开始新的对话或从历史记录中选择</p>
                ${state.sessions.length > 0 ? `
                    <p style="margin-top: 16px; color: #888;">
                        共有 ${state.sessions.length} 条历史对话
                    </p>
                ` : ''}
            </div>
        `;
    },

    startNewChat() {
        if (!state.currentRepo) return;

        // Clear current session - will be created when first message is sent
        state.currentSession = null;
        this.showWelcomeScreen(state.currentRepo);

        // Update active state in session list (remove all active)
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.remove('active');
        });
    },

    // Session List
    async loadSessions(repoId) {
        try {
            const response = await fetch(`${API_BASE_URL}/repos/${repoId}/sessions`);
            const sessions = await response.json();
            state.sessions = sessions.sessions || [];
            this.renderSessions();
        } catch (error) {
            console.error('Failed to load sessions:', error);
        }
    },

    renderSessions() {
        const sessionList = document.getElementById('sessionList');

        if (state.sessions.length === 0) {
            sessionList.innerHTML = '<div class="empty-state">暂无对话</div>';
            return;
        }

        // Sort sessions by created_at desc (newest first)
        const sortedSessions = [...state.sessions].sort((a, b) =>
            new Date(b.created_at) - new Date(a.created_at)
        );

        sessionList.innerHTML = sortedSessions.map(session => {
            // Get first user message as title
            const firstUserMsg = session.messages?.find(m => m.role === 'user');
            const title = firstUserMsg ? this.truncateText(firstUserMsg.content, 30) : '新对话';
            const time = this.formatSessionTime(session.created_at);

            return `
                <div class="session-item ${state.currentSession?.session_id === session.session_id ? 'active' : ''}" data-session-id="${session.session_id}">
                    <div class="session-name">${this.escapeHtml(title)}</div>
                    <div class="session-meta">${time}</div>
                </div>
            `;
        }).join('');

        // Add click handlers
        sessionList.querySelectorAll('.session-item').forEach(item => {
            item.addEventListener('click', async () => {
                const sessionId = item.dataset.sessionId;
                await this.loadSession(sessionId);
            });
        });
    },

    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text || '';
        return text.substring(0, maxLength) + '...';
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    formatSessionTime(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;

        // Less than 1 hour
        if (diff < 3600000) {
            return Math.floor(diff / 60000) + '分钟前';
        }
        // Today
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        }
        // Yesterday
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.toDateString() === yesterday.toDateString()) {
            return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        }
        // Older
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    },

    async loadSession(sessionId) {
        if (!state.currentRepo) return;

        try {
            const session = await api.getSession(state.currentRepo.id, sessionId);

            // Ensure messages array exists
            if (!session.messages) {
                session.messages = [];
            }
            state.currentSession = session;

            // Render messages
            const chatMessages = document.getElementById('chatMessages');
            chatMessages.innerHTML = '';

            session.messages.forEach(msg => {
                this.addMessage(msg.role, msg.content, msg.sources || []);
            });

            // Update active state
            document.querySelectorAll('.session-item').forEach(item => {
                item.classList.toggle('active', item.dataset.sessionId === sessionId);
            });
        } catch (error) {
            console.error('Failed to load session:', error);
        }
    },

    // Chat Messages
    addMessage(role, content, sources = []) {
        const chatMessages = document.getElementById('chatMessages');

        // Remove welcome message if present
        const welcomeMessage = chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        const avatar = role === 'user' ? 'U' : 'AI';

        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-bubble">${this.formatContent(content)}</div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    },

    formatContent(content) {
        // Convert markdown-style code blocks to HTML
        return content
            .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    },

    addTypingIndicator() {
        const chatMessages = document.getElementById('chatMessages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant';
        typingDiv.id = 'typingIndicator';
        typingDiv.innerHTML = `
            <div class="message-avatar">AI</div>
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    },

    removeTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    },

    // Streaming progress indicator
    addStreamingIndicator() {
        const chatMessages = document.getElementById('chatMessages');
        const streamingDiv = document.createElement('div');
        streamingDiv.className = 'message assistant';
        streamingDiv.id = 'streamingIndicator';
        streamingDiv.innerHTML = `
            <div class="message-avatar">AI</div>
            <div class="message-content">
                <div class="streaming-progress">
                    <div class="progress-spinner"></div>
                    <span class="progress-text">开始分析...</span>
                </div>
            </div>
        `;
        chatMessages.appendChild(streamingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    },

    removeStreamingIndicator() {
        const streamingIndicator = document.getElementById('streamingIndicator');
        if (streamingIndicator) {
            streamingIndicator.remove();
        }
    },

    updateProgress(text) {
        const progressText = document.querySelector('#streamingIndicator .progress-text');
        if (progressText) {
            progressText.textContent = text;
        }
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    },

    // Modal
    showModal() {
        document.getElementById('addRepoModal').classList.add('active');
    },

    hideModal() {
        document.getElementById('addRepoModal').classList.remove('active');
        document.getElementById('addRepoForm').reset();
    }
};

// ============================================
// Event Handlers
// ============================================

function setupEventHandlers() {
    // Add repository button
    document.getElementById('addRepoBtn').addEventListener('click', () => {
        ui.showModal();
    });

    // Close modal buttons
    document.getElementById('closeModalBtn').addEventListener('click', () => {
        ui.hideModal();
    });

    document.getElementById('cancelBtn').addEventListener('click', () => {
        ui.hideModal();
    });

    // Close modal on overlay click
    document.getElementById('addRepoModal').addEventListener('click', (e) => {
        if (e.target.id === 'addRepoModal') {
            ui.hideModal();
        }
    });

    // Add repository form
    document.getElementById('addRepoForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(e.target);
        const name = formData.get('name');
        const path = formData.get('path');

        // 自动生成 ID（基于名称的时间戳）
        const timestamp = Date.now().toString(36);
        const id = name.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-') + '-' + timestamp;

        const repoData = { id, name, path };

        try {
            const repo = await api.createRepo(repoData);
            state.repositories.push(repo);
            ui.renderRepositories(state.repositories);
            ui.hideModal();

            // Auto-select the new repository
            ui.selectRepository(repo.id);
        } catch (error) {
            alert(error.message);
        }
    });

    // Chat input
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');

    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
        sendBtn.disabled = !chatInput.value.trim() || !state.currentRepo;
    });

    // Send message on Enter (Shift+Enter for new line)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (chatInput.value.trim() && state.currentRepo) {
                sendMessage();
            }
        }
    });

    // Send button
    sendBtn.addEventListener('click', () => {
        if (chatInput.value.trim() && state.currentRepo) {
            sendMessage();
        }
    });

    // New chat button
    document.getElementById('newChatBtn').addEventListener('click', async () => {
        if (state.currentRepo) {
            await ui.startNewChat();
        }
    });

    // Clear chat button - same as new chat
    document.getElementById('clearChatBtn').addEventListener('click', async () => {
        if (state.currentRepo) {
            await ui.startNewChat();
        }
    });
}

async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();

    if (!message || !state.currentRepo) return;

    // Add user message
    ui.addMessage('user', message);
    chatInput.value = '';
    chatInput.style.height = 'auto';
    document.getElementById('sendBtn').disabled = true;

    // Show progress indicator with streaming
    ui.addStreamingIndicator();

    try {
        // Use streaming API with explicit UTF-8 encoding
        const response = await fetch(`${API_BASE_URL}/repos/${state.currentRepo.id}/ask/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
            body: new TextEncoder().encode(JSON.stringify({
                question: message,
                session_id: state.currentSession?.session_id
            }))
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        handleStreamEvent(event);
                        if (event.type === 'complete') {
                            finalResult = event.result;
                        }
                    } catch (e) {
                        console.error('Failed to parse event:', line);
                    }
                }
            }
        }

        // Remove streaming indicator and show final result
        ui.removeStreamingIndicator();

        if (finalResult) {
            ui.addMessage('assistant', finalResult.answer, finalResult.sources);

            if (finalResult.session_id) {
                // Update current session with messages
                if (!state.currentSession) {
                    state.currentSession = {
                        session_id: finalResult.session_id,
                        repo_id: state.currentRepo.id,
                        messages: []
                    };
                }

                // Ensure messages array exists
                if (!state.currentSession.messages) {
                    state.currentSession.messages = [];
                }

                // Add messages to session if not already there
                const hasUserMsg = state.currentSession.messages.some(
                    m => m.role === 'user' && m.content === message
                );
                if (!hasUserMsg) {
                    state.currentSession.messages.push({
                        role: 'user',
                        content: message,
                        timestamp: Date.now() / 1000
                    });
                }

                const hasAssistantMsg = state.currentSession.messages.some(
                    m => m.role === 'assistant' && m.content === finalResult.answer
                );
                if (!hasAssistantMsg) {
                    state.currentSession.messages.push({
                        role: 'assistant',
                        content: finalResult.answer,
                        timestamp: Date.now() / 1000,
                        sources: finalResult.sources
                    });
                }

                await ui.loadSessions(state.currentRepo.id);
            }
        }

    } catch (error) {
        ui.removeStreamingIndicator();
        ui.addMessage('assistant', `错误: ${error.message}`);
    }
}

function handleStreamEvent(event) {
    switch (event.type) {
        case 'start':
            ui.updateProgress(`开始分析... (最多 ${event.max_iterations} 轮)`);
            break;
        case 'progress':
            ui.updateProgress(`思考中... (${event.iteration}/${event.max_iterations})`);
            break;
        case 'tool_call':
            ui.updateProgress(`调用工具: ${event.tool}`);
            break;
        case 'tool_result':
            const status = event.success ? '✓' : '✗';
            ui.updateProgress(`${status} ${event.tool} 完成`);
            break;
        case 'force_stop':
            ui.updateProgress(`整理答案中...`);
            break;
        case 'warning':
            ui.updateProgress(`⚠ ${event.message}`);
            break;
        case 'error':
            ui.updateProgress(`❌ 错误: ${event.message}`);
            break;
    }
}

// ============================================
// Initialization
// ============================================

async function init() {
    setupEventHandlers();

    // Initial health check
    try {
        const health = await api.healthCheck();
        ui.updateHealthStatus(health);
    } catch (error) {
        ui.updateHealthStatus({ status: 'unhealthy' });
    }

    // Load repositories
    try {
        const response = await api.listRepos();
        state.repositories = response.repos || [];
        ui.renderRepositories(state.repositories);
    } catch (error) {
        console.error('Failed to load repositories:', error);
    }

    // Periodic health checks
    setInterval(async () => {
        try {
            const health = await api.healthCheck();
            ui.updateHealthStatus(health);
        } catch (error) {
            ui.updateHealthStatus({ status: 'unhealthy' });
        }
    }, 30000);
}

// Start application when DOM is ready
document.addEventListener('DOMContentLoaded', init);
