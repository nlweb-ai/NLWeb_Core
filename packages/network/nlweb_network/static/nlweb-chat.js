// Copyright (c) 2025 Microsoft Corporation.
// Licensed under the MIT License

/**
 * NLWeb Chat UI - A browser-based chat interface for NLWeb
 * Connects to NLWeb HTTP endpoint, displays streaming results, and saves conversations
 */

class NLWebChat {
    constructor(config = {}) {
        this.baseUrl = this.loadServerUrl() || config.baseUrl || 'https://nlw.azurewebsites.net';
        this.defaultSite = config.defaultSite || 'imdb.com';
        this.maxResults = config.maxResults || 50;
        this.currentStream = null;
        this.conversations = {};
        this.currentConversation = null;
        this.conversationHistory = []; // Track previous queries for v0.54 context
        this.init();
    }

    async init() {
        console.log('Initializing NLWeb Chat...');
        this.bindElements();
        this.attachEventListeners();
        await this.loadConfig();
        this.loadConversations();
        this.updateServerUrlDisplay();
        this.updateUI();
    }

    async loadConfig() {
        try {
            const response = await fetch(`${this.baseUrl}/config`);
            if (response.ok) {
                const config = await response.json();
                window.TEST_USER = config.test_user;
                console.log('Loaded test user:', window.TEST_USER);
            }
        } catch (error) {
            console.warn('Failed to load config:', error);
            window.TEST_USER = 'anonymous';
        }
    }

    bindElements() {
        this.elements = {
            // Server config elements
            serverUrlInput: document.getElementById('server-url-input'),
            serverUrlStatus: document.getElementById('server-url-status'),

            // Sidebar elements
            sidebar: document.getElementById('sidebar'),
            sidebarToggle: document.getElementById('sidebar-toggle'),
            mobileMenuToggle: document.getElementById('mobile-menu-toggle'),
            conversationsList: document.getElementById('conversations-list'),
            newChatBtn: document.getElementById('new-chat-btn'),

            // Messages area
            chatMessages: document.getElementById('chat-messages'),
            messagesContainer: document.getElementById('messages-container'),
            centeredInputContainer: document.querySelector('.centered-input-container'),

            // Centered input (initial)
            centeredInput: document.getElementById('centered-chat-input'),
            centeredSendBtn: document.getElementById('centered-send-button'),
            centeredProfileBtn: document.getElementById('centered-profile-button'),
            siteInput: document.getElementById('site-input'),

            // Follow-up input (bottom)
            chatInputContainer: document.querySelector('.chat-input-container'),
            chatInput: document.getElementById('chat-input'),
            sendButton: document.getElementById('send-button'),
            profileButton: document.getElementById('profile-button')
        };
    }

    attachEventListeners() {
        // Server URL configuration - auto-save on blur and Enter
        this.elements.serverUrlInput.onblur = () => this.saveServerUrl();
        this.elements.serverUrlInput.onkeypress = (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.saveServerUrl();
                this.elements.serverUrlInput.blur();
            }
        };

        // Sidebar controls
        this.elements.sidebarToggle.onclick = () => this.toggleSidebar();
        this.elements.mobileMenuToggle.onclick = () => this.toggleSidebar();
        this.elements.newChatBtn.onclick = () => this.startNewChat();

        // Centered input handlers
        this.elements.centeredSendBtn.onclick = () => this.sendQuery();
        this.elements.centeredProfileBtn.onclick = () => this.sendProfileQuery();
        this.elements.centeredInput.onkeypress = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendQuery();
            }
        };

        // Follow-up input handlers
        this.elements.sendButton.onclick = () => this.sendFollowupQuery();
        this.elements.profileButton.onclick = () => this.sendFollowupProfileQuery();
        this.elements.chatInput.onkeypress = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendFollowupQuery();
            }
        };

        // Auto-resize textarea
        this.elements.centeredInput.oninput = () => this.autoResizeTextarea(this.elements.centeredInput);
        this.elements.chatInput.oninput = () => this.autoResizeTextarea(this.elements.chatInput);
    }

    // ============ UI Control Methods ============

    loadServerUrl() {
        try {
            const stored = localStorage.getItem('nlweb_server_url');
            return stored || null;
        } catch (err) {
            console.error('Error loading server URL:', err);
            return null;
        }
    }

    saveServerUrl() {
        try {
            let url = this.elements.serverUrlInput.value.trim();
            
            if (!url) {
                this.showServerUrlStatus('Please enter a server URL', true);
                return;
            }

            // Normalize the URL - add https:// if no protocol specified
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                url = 'https://' + url;
            }

            // Validate URL format
            try {
                new URL(url);
            } catch (e) {
                this.showServerUrlStatus('Invalid URL format', true);
                return;
            }

            // Remove trailing slash
            url = url.replace(/\/$/, '');

            // Save to localStorage and update
            localStorage.setItem('nlweb_server_url', url);
            this.baseUrl = url;
            this.elements.serverUrlInput.value = url;
            
            this.showServerUrlStatus('✓ Saved');
            console.log('Server URL updated to:', url);
        } catch (err) {
            console.error('Error saving server URL:', err);
            this.showServerUrlStatus('Error saving URL', true);
        }
    }

    updateServerUrlDisplay() {
        if (this.elements.serverUrlInput) {
            this.elements.serverUrlInput.value = this.baseUrl;
        }
    }

    showServerUrlStatus(message, isError = false) {
        this.elements.serverUrlStatus.textContent = message;
        this.elements.serverUrlStatus.className = 'server-url-status' + (isError ? ' error' : '');
        
        // Clear status after 3 seconds
        setTimeout(() => {
            this.elements.serverUrlStatus.textContent = '';
        }, 3000);
    }

    toggleSidebar() {
        // For mobile, use 'active' class; for desktop, use 'collapsed' class
        if (window.innerWidth <= 768) {
            this.elements.sidebar.classList.toggle('active');
        } else {
            this.elements.sidebar.classList.toggle('collapsed');
            this.elements.sidebarToggle.classList.toggle('collapsed');
        }
    }

    startNewChat() {
        // Save current conversation if exists
        if (this.currentConversation) {
            this.saveConversations();
        }

        // Create new conversation
        this.currentConversation = {
            id: Date.now(),
            title: 'New chat',
            site: this.defaultSite,
            messages: [],
            createdAt: Date.now(),
            updatedAt: Date.now()
        };

        // Reset conversation history for v0.54 context
        this.conversationHistory = [];

        // Update UI
        this.updateUI();
        this.elements.centeredInput.focus();

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            this.toggleSidebar();
        }
    }

    updateUI() {
        // Show/hide input areas
        const hasMessages = this.currentConversation && this.currentConversation.messages.length > 0;
        this.elements.centeredInputContainer.style.display = hasMessages ? 'none' : 'flex';
        this.elements.chatInputContainer.style.display = hasMessages ? 'block' : 'none';

        // Set site input default
        if (this.elements.siteInput) {
            this.elements.siteInput.value = this.defaultSite;
        }

        // Render messages if any
        if (hasMessages) {
            this.renderMessages();
        } else {
            // Clear messages container except the centered input
            const messages = this.elements.messagesContainer.querySelectorAll('.message');
            messages.forEach(msg => msg.remove());
        }

        // Update conversations list
        this.renderConversationsList();
    }

    // ============ Query Sending Methods ============

    async sendQuery() {
        const query = this.elements.centeredInput.value.trim();
        const site = this.elements.siteInput.value.trim() || this.defaultSite;

        if (!query) return;

        // Create conversation if none exists
        if (!this.currentConversation) {
            this.currentConversation = {
                id: Date.now(),
                title: query.substring(0, 50),
                site: site,
                messages: [],
                createdAt: Date.now(),
                updatedAt: Date.now()
            };
        }

        // Add user message
        const userMessage = {
            id: Date.now(),
            role: 'user',
            content: query,
            metadata: { site: site }
        };
        this.currentConversation.messages.push(userMessage);
        this.currentConversation.updatedAt = Date.now();

        // Clear input
        this.elements.centeredInput.value = '';

        // Update UI to show messages
        this.updateUI();

        // Send to NLWeb
        await this.streamQuery(query, site);
    }

    async sendProfileQuery() {
        const query = this.elements.centeredInput.value.trim();
        const site = this.elements.siteInput.value.trim() || this.defaultSite;

        if (!query) return;

        // Send profile request without updating conversation
        await this.streamProfileQuery(query, site);
    }

    async sendFollowupQuery() {
        const query = this.elements.chatInput.value.trim();
        if (!query || !this.currentConversation) return;

        const site = this.currentConversation.site || this.defaultSite;

        // Add user message
        const userMessage = {
            id: Date.now(),
            role: 'user',
            content: query,
            metadata: { site: site }
        };
        this.currentConversation.messages.push(userMessage);
        this.currentConversation.updatedAt = Date.now();

        // Clear input
        this.elements.chatInput.value = '';

        // Render the new user message
        this.renderMessages();

        // Send to NLWeb
        await this.streamQuery(query, site);
    }

    async sendFollowupProfileQuery() {
        const query = this.elements.chatInput.value.trim();
        if (!query) return;

        const site = this.currentConversation ? (this.currentConversation.site || this.defaultSite) : this.defaultSite;

        // Send profile request without updating conversation
        await this.streamProfileQuery(query, site);
    }

    async streamQuery(query, site) {
        // Create assistant message placeholder
        const assistantMessage = {
            id: Date.now(),
            role: 'assistant',
            content: [],
            metadata: {}
        };
        this.currentConversation.messages.push(assistantMessage);

        // Add to conversation history for v0.54 context
        this.conversationHistory.push(query);

        // Render with loading indicator
        this.renderMessages();

        try {
            // Check if summarize checkbox is checked
            const summarizeCheckbox = document.getElementById('summarize-checkbox');
            const shouldSummarize = summarizeCheckbox && summarizeCheckbox.checked;
            const mode = shouldSummarize ? 'list,summarize' : 'list';

            // Build v0.54 request
            const v054Request = {
                query: {
                    text: query,
                    site: site,
                    num_results: this.maxResults
                },
                prefer: {
                    streaming: true,
                    response_format: 'conv_search',
                    mode: mode
                },
                meta: {
                    api_version: '0.54',
                    user: {
                        id: window.TEST_USER || 'anonymous'
                    },
                    remember: true
                }
            };

            // Add conversation context if available
            if (this.conversationHistory.length > 1) {
                v054Request.context = {
                    '@type': 'ConversationalContext',
                    prev: this.conversationHistory.slice(-6, -1) // Last 5 queries (excluding current)
                };
            }

            // Send POST request to get streaming response
            const response = await fetch(`${this.baseUrl}/ask`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                },
                body: JSON.stringify(v054Request)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Handle streaming response
            await this.handleStreamingResponse(response, assistantMessage);

        } catch (error) {
            console.error('Error starting stream:', error);
            assistantMessage.content.push({
                name: 'Error',
                description: `Sorry, there was an error connecting to the server: ${error.message}`
            });
            this.renderMessages();
            this.saveConversations();
        }
    }

    async handleStreamingResponse(response, assistantMessage) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        try {
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.trim() || !line.startsWith('data: ')) continue;

                    try {
                        const dataStr = line.slice(6); // Remove 'data: ' prefix
                        const data = JSON.parse(dataStr);

                        // Handle v0.54 response types
                        if (data._meta) {

                            // Check for failure response
                            if (data._meta.response_type === 'Failure' && data.error) {
                                assistantMessage.content = [{
                                    name: 'Error',
                                    description: `Error (${data.error.code}): ${data.error.message}`
                                }];
                                this.renderMessages();
                                this.saveConversations();
                                return;
                            }
                        }

                        // Handle v0.54 results array (conv_search format)
                        if (data.results && Array.isArray(data.results)) {
                            // Add new results
                            data.results.forEach((result) => {
                                // Check if result already exists (by URL or name)
                                const exists = assistantMessage.content.some(item =>
                                    (item.url && item.url === result.url) ||
                                    (item.name && item.name === result.name)
                                );

                                if (!exists) {
                                    assistantMessage.content.push(result);
                                }
                            });

                            // Sort by score
                            this.sortResultsByScore(assistantMessage.content);
                            this.renderMessages();
                        }

                        // Handle v0.54 structuredData array (chatgpt_app format)
                        if (data.structuredData && Array.isArray(data.structuredData)) {
                            // Add new results
                            data.structuredData.forEach((result) => {
                                // Check if result already exists (by URL or name)
                                const exists = assistantMessage.content.some(item =>
                                    (item.url && item.url === result.url) ||
                                    (item.name && item.name === result.name)
                                );

                                if (!exists) {
                                    assistantMessage.content.push(result);
                                }
                            });

                            // Sort by score
                            this.sortResultsByScore(assistantMessage.content);
                            this.renderMessages();
                        }

                        // Handle legacy content array
                        if (data.content && Array.isArray(data.content)) {
                            // Extract resource items from content array
                            data.content.forEach((item) => {
                                if (item.type === 'resource' && item.resource && item.resource.data) {
                                    const result = item.resource.data;

                                    // Check if result already exists
                                    const exists = assistantMessage.content.some(existing =>
                                        (existing.url && existing.url === result.url) ||
                                        (existing.name && existing.name === result.name)
                                    );

                                    if (!exists) {
                                        assistantMessage.content.push(result);
                                    }
                                }
                            });

                            // Sort by score
                            this.sortResultsByScore(assistantMessage.content);
                            this.renderMessages();
                        }

                        // Handle elicitation
                        if (data.elicitation) {
                            let elicitationText = data.elicitation.text + '\n\n';
                            data.elicitation.questions.forEach(q => {
                                elicitationText += `**${q.text}**\n`;
                                if (q.options) {
                                    elicitationText += q.options.map(opt => `- ${opt}`).join('\n') + '\n';
                                }
                                elicitationText += '\n';
                            });

                            assistantMessage.content = [{
                                name: 'Question',
                                description: elicitationText
                            }];
                            this.renderMessages();
                            this.saveConversations();
                        }

                        // Handle promise
                        if (data.promise) {
                            const estimatedTime = data.promise.estimated_time
                                ? ` (estimated ${data.promise.estimated_time}s)`
                                : '';
                            assistantMessage.content = [{
                                name: 'Task Started',
                                description: `Task started${estimatedTime}. Token: ${data.promise.token}`
                            }];
                            this.renderMessages();
                            this.saveConversations();
                        }

                    } catch (err) {
                        console.error('Error parsing SSE line:', err, 'Line:', line);
                    }
                }
            }

            // Stream complete
            console.log('Stream complete');
            this.saveConversations();

        } catch (error) {
            console.error('Error reading stream:', error);
            if (assistantMessage.content.length === 0) {
                assistantMessage.content.push({
                    name: 'Error',
                    description: 'Sorry, there was an error processing your request.'
                });
                this.renderMessages();
            }
            this.saveConversations();
        }
    }

    async streamProfileQuery(query, site) {
        try {
            // Check if summarize checkbox is checked
            const summarizeCheckbox = document.getElementById('summarize-checkbox');
            const shouldSummarize = summarizeCheckbox && summarizeCheckbox.checked;
            const mode = shouldSummarize ? 'list,summarize' : 'list';

            // Build v0.54 request - same as streamQuery
            const v054Request = {
                query: {
                    text: query,
                    site: site,
                    num_results: this.maxResults
                },
                prefer: {
                    streaming: false,
                    response_format: 'conv_search',
                    mode: mode
                },
                meta: {
                    api_version: '0.54'
                }
            };

            // Add conversation context if available
            if (this.conversationHistory.length > 0) {
                v054Request.context = {
                    '@type': 'ConversationalContext',
                    prev: this.conversationHistory.slice(-5) // Last 5 queries
                };
            }

            // Open new window for profile results
            const profileWindow = window.open('', '_blank');
            if (!profileWindow) {
                alert('Please allow pop-ups to view profiling results');
                return;
            }

            // Send POST request with X-Profile-Request header
            const response = await fetch(`${this.baseUrl}/ask`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream',
                    'X-Profile-Request': 'true'
                },
                body: JSON.stringify(v054Request)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Read the entire response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullResponse = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                fullResponse += decoder.decode(value, { stream: true });
            }

            // Write the complete response to the profile window
            profileWindow.document.write(fullResponse);
            console.log('Profile stream complete');

        } catch (error) {
            console.error('Error during profile request:', error);
            alert(`Profile request failed: ${error.message}`);
        }
    }

    // ============ Rendering Methods ============

    renderMessages() {
        if (!this.currentConversation) return;

        // Clear existing messages (but keep centered input if visible)
        const messages = this.elements.messagesContainer.querySelectorAll('.message');
        messages.forEach(msg => msg.remove());

        // Render all messages before the centered input container
        const insertPoint = this.elements.centeredInputContainer;
        
        this.currentConversation.messages.forEach(msg => {
            const msgDiv = this.createMessageElement(msg);
            this.elements.messagesContainer.insertBefore(msgDiv, insertPoint);
        });

        // Scroll to show user's prompt and first result
        this.scrollToFirstResult();
    }

    createMessageElement(msg) {
        const msgDiv = document.createElement('div');
        
        if (msg.role === 'user') {
            msgDiv.className = 'message user-message message-appear';
            msgDiv.dataset.timestamp = new Date(msg.id).toISOString();
            msgDiv.innerHTML = `
                <div class="message-sender"></div>
                <div class="message-text">${this.escapeHtml(msg.content)}</div>
            `;
        } else {
            msgDiv.className = 'message assistant-message';
            
            const messageText = document.createElement('div');
            messageText.className = 'message-text';

            if (Array.isArray(msg.content) && msg.content.length > 0) {
                const searchResults = document.createElement('div');
                searchResults.className = 'search-results';
                
                msg.content.forEach(item => {
                    const itemElement = this.renderResourceItem(item);
                    searchResults.appendChild(itemElement);
                });
                
                messageText.appendChild(searchResults);
            } else {
                // Loading indicator
                const loading = document.createElement('div');
                loading.className = 'loading-indicator';
                messageText.appendChild(loading);
            }

            msgDiv.appendChild(messageText);
        }

        return msgDiv;
    }

    renderResourceItem(data) {
        const container = document.createElement('div');
        container.className = 'item-container';
        
        const content = document.createElement('div');
        content.className = 'item-content';
        
        // Title row with link
        const titleRow = document.createElement('div');
        titleRow.className = 'item-title-row';
        const titleLink = document.createElement('a');
        titleLink.href = data.url || data.grounding || '#';
        titleLink.className = 'item-title-link';
        titleLink.textContent = data.name || data.title || data.description?.substring(0, 50) + '...' || 'Result';
        titleLink.target = '_blank';
        titleRow.appendChild(titleLink);
        content.appendChild(titleRow);
        
        // Site link
        if (data.site) {
            const siteLink = document.createElement('a');
            siteLink.href = `/ask?site=${data.site}`;
            siteLink.className = 'item-site-link';
            siteLink.textContent = data.site;
            content.appendChild(siteLink);
        }
        
        // Description
        if (data.description) {
            const description = document.createElement('div');
            description.className = 'item-description';
            description.textContent = data.description;
            content.appendChild(description);
        }
        
        container.appendChild(content);
        
        // Image
        if (data.image) {
            const imgWrapper = document.createElement('div');
            const img = document.createElement('img');
            img.src = data.image;
            img.alt = 'Item image';
            img.className = 'item-image';
            imgWrapper.appendChild(img);
            container.appendChild(imgWrapper);
        }
        
        return container;
    }

    // ============ Conversation Management ============

    loadConversations() {
        try {
            const stored = localStorage.getItem('nlweb_conversations');
            if (stored) {
                this.conversations = JSON.parse(stored);
                console.log('Loaded conversations:', Object.keys(this.conversations).length);
            }
        } catch (err) {
            console.error('Error loading conversations:', err);
        }
    }

    saveConversations() {
        try {
            if (this.currentConversation) {
                this.conversations[this.currentConversation.id] = this.currentConversation;
            }
            localStorage.setItem('nlweb_conversations', JSON.stringify(this.conversations));
            this.renderConversationsList();
        } catch (err) {
            console.error('Error saving conversations:', err);
        }
    }

    renderConversationsList() {
        this.elements.conversationsList.innerHTML = '';

        // Group conversations by site
        const conversationsBySite = {};
        Object.values(this.conversations).forEach(conv => {
            const site = conv.site || 'all';
            if (!conversationsBySite[site]) {
                conversationsBySite[site] = [];
            }
            conversationsBySite[site].push(conv);
        });

        // Sort sites alphabetically
        const sortedSites = Object.keys(conversationsBySite).sort();

        sortedSites.forEach(site => {
            const siteGroup = document.createElement('div');
            siteGroup.className = 'site-group';

            // Site group header
            const siteHeader = document.createElement('div');
            siteHeader.className = 'site-group-header';
            const siteName = document.createElement('span');
            siteName.textContent = site;
            siteHeader.appendChild(siteName);
            
            // Chevron icon
            const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            chevron.classList.add('chevron');
            chevron.setAttribute('viewBox', '0 0 24 24');
            chevron.setAttribute('fill', 'none');
            chevron.setAttribute('stroke', 'currentColor');
            chevron.setAttribute('stroke-width', '2');
            const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
            polyline.setAttribute('points', '6 9 12 15 18 9');
            chevron.appendChild(polyline);
            siteHeader.appendChild(chevron);
            
            // Toggle collapse on click
            siteHeader.onclick = () => {
                siteGroup.classList.toggle('collapsed');
            };
            
            siteGroup.appendChild(siteHeader);

            // Site conversations container
            const siteConversations = document.createElement('div');
            siteConversations.className = 'site-conversations';

            // Sort by most recent, remove duplicates by title
            const uniqueTitles = new Set();
            const conversations = conversationsBySite[site]
                .sort((a, b) => b.updatedAt - a.updatedAt)
                .filter(conv => {
                    if (uniqueTitles.has(conv.title)) {
                        return false;
                    }
                    uniqueTitles.add(conv.title);
                    return true;
                });

            conversations.forEach(conv => {
                const item = document.createElement('div');
                item.className = 'conversation-item';
                if (this.currentConversation && this.currentConversation.id === conv.id) {
                    item.classList.add('active');
                }
                item.dataset.conversationId = conv.id;

                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'conversation-delete';
                deleteBtn.textContent = '×';
                deleteBtn.title = 'Delete conversation';
                deleteBtn.onclick = (e) => {
                    e.stopPropagation();
                    this.deleteConversation(conv.id);
                };

                const content = document.createElement('div');
                content.className = 'conversation-content';
                
                const title = document.createElement('span');
                title.className = 'conversation-title';
                title.textContent = conv.title;
                
                content.appendChild(title);
                item.appendChild(deleteBtn);
                item.appendChild(content);

                item.onclick = () => this.loadConversation(conv.id);

                siteConversations.appendChild(item);
            });

            siteGroup.appendChild(siteConversations);
            this.elements.conversationsList.appendChild(siteGroup);
        });
    }

    loadConversation(id) {
        this.currentConversation = this.conversations[id];
        if (this.currentConversation) {
            // Rebuild conversation history from messages for v0.54 context
            this.conversationHistory = this.currentConversation.messages
                .filter(msg => msg.role === 'user')
                .map(msg => msg.query);

            this.updateUI();

            // Close sidebar on mobile
            if (window.innerWidth <= 768) {
                this.toggleSidebar();
            }
        }
    }

    deleteConversation(id) {
        delete this.conversations[id];
        localStorage.setItem('nlweb_conversations', JSON.stringify(this.conversations));

        if (this.currentConversation && this.currentConversation.id === id) {
            this.currentConversation = null;
            this.updateUI();
        }

        this.renderConversationsList();
    }

    // ============ Utility Methods ============

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    sortResultsByScore(results) {
        // Sort results by score in descending order
        results.sort((a, b) => {
            const scoreA = a.score || 0;
            const scoreB = b.score || 0;
            return scoreB - scoreA;
        });
    }

    scrollToFirstResult() {
        // Find the last user message
        const userMessages = this.elements.messagesContainer.querySelectorAll('.user-message');
        if (userMessages.length === 0) {
            this.scrollToBottom();
            return;
        }

        const lastUserMessage = userMessages[userMessages.length - 1];
        
        // Scroll to show the user message at the top of the viewport
        lastUserMessage.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = textarea.scrollHeight + 'px';
    }
}

// Initialize on page load
console.log('NLWeb Chat script loaded');
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing NLWeb Chat');
    window.nlwebChat = new NLWebChat();
    console.log('NLWeb Chat initialized');
});
