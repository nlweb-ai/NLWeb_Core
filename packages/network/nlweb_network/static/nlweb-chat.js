// Copyright (c) 2025 Microsoft Corporation.
// Licensed under the MIT License

/**
 * NLWeb Chat UI - A browser-based chat interface for NLWeb
 * Connects to NLWeb HTTP endpoint, displays streaming results, and saves conversations
 */

class NLWebChat {
    constructor(config = {}) {
        // Use config baseUrl if provided, otherwise detect from window.location
        // For production deployment, auto-detect the current host
        this.baseUrl = config.baseUrl || window.location.origin;
        this.defaultSite = config.defaultSite || 'imdb.com';
        this.maxResults = config.maxResults || 10;
        this.currentStream = null;
        this.conversations = {};
        this.currentConversation = null;
        this.init();
    }

    init() {
        this.bindElements();
        this.attachEventListeners();
        this.loadConversations();
        this.updateUI();
    }

    bindElements() {
        this.elements = {
            // Container
            appContainer: document.querySelector('.app-container'),
            
            // Sidebar elements
            sidebar: document.getElementById('sidebar'),
            sidebarToggle: document.getElementById('sidebar-toggle'),
            mobileMenuToggle: document.getElementById('mobile-menu-toggle'),
            conversationsList: document.getElementById('conversations-list'),
            newChatBtn: document.getElementById('new-chat-btn'),

            // Header elements
            chatTitle: document.querySelector('.chat-title'),
            chatSiteInfo: document.getElementById('chat-site-info'),

            // Messages area
            chatMessages: document.getElementById('chat-messages'),
            messagesContainer: document.getElementById('messages-container'),
            centeredInputContainer: document.querySelector('.centered-input-container'),

            // Centered input (initial)
            centeredInput: document.getElementById('centered-chat-input'),
            centeredSendBtn: document.getElementById('centered-send-button'),
            siteInput: document.getElementById('site-input'),

            // Follow-up input (bottom)
            chatInputContainer: document.querySelector('.chat-input-container'),
            chatInput: document.getElementById('chat-input'),
            sendButton: document.getElementById('send-button')
        };
    }

    attachEventListeners() {
        // Sidebar controls
        this.elements.sidebarToggle.onclick = () => this.toggleSidebar();
        this.elements.mobileMenuToggle.onclick = () => this.toggleSidebar();
        this.elements.newChatBtn.onclick = () => this.startNewChat();

        // Centered input handlers
        this.elements.centeredSendBtn.onclick = () => this.sendQuery();
        this.elements.centeredInput.onkeypress = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendQuery();
            }
        };

        // Follow-up input handlers
        this.elements.sendButton.onclick = () => this.sendFollowupQuery();
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

    toggleSidebar() {
        this.elements.sidebar.classList.toggle('collapsed');
        this.elements.appContainer.classList.toggle('sidebar-collapsed');
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

        // Update UI
        this.updateUI();
        this.elements.centeredInput.focus();

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            this.toggleSidebar();
        }
    }

    updateUI() {
        // Update header (only if elements exist)
        if (this.elements.chatTitle && this.currentConversation) {
            this.elements.chatTitle.textContent = this.currentConversation.title;
        }
        if (this.elements.chatSiteInfo) {
            const site = this.currentConversation?.site || 'all';
            this.elements.chatSiteInfo.textContent = `Asking ${site}`;
        }

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

    async streamQuery(query, site) {
        // Create assistant message placeholder
        const assistantMessage = {
            id: Date.now(),
            role: 'assistant',
            content: [],
            metadata: {}
        };
        this.currentConversation.messages.push(assistantMessage);

        // Render with loading indicator
        this.renderMessages();

        try {
            // Build URL
            const url = new URL(`${this.baseUrl}/ask`);
            url.searchParams.set('query', query);
            url.searchParams.set('site', site);
            url.searchParams.set('max_results', this.maxResults);
            url.searchParams.set('mode', 'list');
            
            // Add previous queries from conversation (exclude the current assistant message placeholder)
            const previousQueries = this.currentConversation.messages
                .slice(0, -1) // Exclude the assistant message placeholder we just added
                .filter(msg => msg.role === 'user')
                .map(msg => msg.content);
            
            if (previousQueries.length > 1) {
                // Join all previous queries except the current one with commas
                url.searchParams.set('prev', previousQueries.slice(0, -1).join(','));
            }

            // Create EventSource for SSE
            this.currentStream = new EventSource(url.toString());

            this.currentStream.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('Received SSE event:', data);

                    // Handle _meta message
                    if (data._meta) {
                        console.log('Metadata:', data._meta);
                        return;
                    }

                    // Handle content array (NLWeb format)
                    if (data.content && Array.isArray(data.content)) {
                        console.log('Processing content array:', data.content);
                        data.content.forEach((item, idx) => {
                            console.log(`Content item ${idx}:`, item);
                            
                            // Only add resource items (skip text items)
                            if (item.type === 'resource' && item.resource && item.resource.data) {
                                console.log('Resource data:', item.resource.data);
                                console.log('Score in data:', item.resource.data.score);
                                assistantMessage.content.push(item.resource.data);
                            }
                        });
                        // Sort by score (descending) before rendering
                        this.sortResultsByScore(assistantMessage.content);
                        this.renderMessages();
                        return;
                    }

                    // Handle text content
                    if (data.type === 'text' || data.text) {
                        assistantMessage.content.push({
                            type: 'text',
                            content: data.content || data.text
                        });
                        this.renderMessages();
                    } 
                    // Handle item/result
                    else if (data.type === 'item' || data.type === 'result' || data.title) {
                        assistantMessage.content.push({
                            type: 'item',
                            title: data.title,
                            snippet: data.snippet || data.description,
                            link: data.link || data.url
                        });
                        this.renderMessages();
                    } 
                    // Handle done/complete
                    else if (data.type === 'done' || data.type === 'complete') {
                        console.log('Stream complete');
                        this.currentStream.close();
                        this.currentStream = null;
                        this.saveConversations();
                    }
                } catch (err) {
                    console.error('Error parsing SSE data:', err, 'Raw data:', event.data);
                }
            };

            this.currentStream.onerror = (error) => {
                console.log('SSE connection closed or error:', error);
                
                if (this.currentStream) {
                    this.currentStream.close();
                    this.currentStream = null;
                }

                // Only show error if we have no content yet
                if (assistantMessage.content.length === 0) {
                    assistantMessage.content.push({
                        name: 'Error',
                        description: 'Sorry, there was an error processing your request.'
                    });
                    this.renderMessages();
                }
                
                this.saveConversations();
            };

        } catch (error) {
            console.error('Error starting stream:', error);
            assistantMessage.content.push({
                type: 'text',
                content: 'Sorry, there was an error connecting to the server.'
            });
            this.renderMessages();
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
        
        // Title row with link and score
        const titleRow = document.createElement('div');
        titleRow.className = 'item-title-row';
        const titleLink = document.createElement('a');
        titleLink.href = data.url || data.grounding || '#';
        titleLink.className = 'item-title-link';
        titleLink.textContent = data.name || data.title || data.description?.substring(0, 50) + '...' || 'Result';
        titleLink.target = '_blank';
        titleRow.appendChild(titleLink);
        
        // Add score badge if available
        if (data.score !== undefined && data.score !== null) {
            const scoreBadge = document.createElement('span');
            scoreBadge.className = 'item-score-badge';
            scoreBadge.textContent = `Score: ${data.score}`;
            titleRow.appendChild(scoreBadge);
        }
        
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
document.addEventListener('DOMContentLoaded', () => {
    window.nlwebChat = new NLWebChat();
});
