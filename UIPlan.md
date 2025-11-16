# NLWeb UI Implementation Plan

## Overview
A browser-based chat interface that connects to the NLWeb HTTP endpoint, displays streaming results, and saves conversations to localStorage.

## Core Responsibilities
1. Send queries to NLWeb endpoint via HTTP/SSE
2. Display streaming responses in real-time
3. Store conversation history in localStorage
4. Provide a clean, responsive chat interface

## Key UI Pattern
- **Initial state**: Input box centered in the middle of the empty conversation area
- **After first query**: Messages appear in the main area, input moves to bottom for follow-up queries
- **Conversation persistence**: All conversations saved in localStorage and can be revisited

## Response Structure from NLWeb

### SSE Stream Format
```
data: {"_meta": {"version": "0.5"}}
data: {"content": [array of content items]}
data: {"content": [more content items]}
...
```

### Content Types
```javascript
// Text type
{
    "type": "text",
    "text": "Description text"
}

// Resource type
{
    "type": "resource",
    "resource": {
        "data": {
            "@type": "Item",
            "url": "https://example.com",
            "name": "Title",
            "site": "example.com",
            "description": "Description",
            "@context": "https://schema.org",
            "@graph": [/* Schema.org data */]
        }
    }
}
```

## Implementation Steps

## Step 1: HTML Structure (`index.html`)

### Layout with Sidebar and Two-Stage Input Flow
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NLWeb Chat</title>
    <link rel="stylesheet" href="nlweb-chat.css">
</head>
<body>
    <!-- Floating trigger button -->
    <button id="nlweb-trigger" class="nlweb-trigger">
        💬
    </button>

    <!-- Main chat application -->
    <div id="nlweb-app" class="nlweb-app hidden">

        <!-- Sidebar toggle (visible on mobile) -->
        <button id="sidebar-toggle" class="sidebar-toggle">
            ☰
        </button>

        <!-- Sidebar for conversation history -->
        <aside id="nlweb-sidebar" class="nlweb-sidebar">
            <div class="sidebar-header">
                <h3>Conversations</h3>
                <button id="new-chat-btn" class="new-chat-btn">+</button>
            </div>
            <div id="conversations-list" class="conversations-list">
                <!-- Conversation items will be added dynamically -->
            </div>
        </aside>

        <!-- Main chat container -->
        <div id="nlweb-container" class="nlweb-container">
            <!-- Header -->
            <div class="nlweb-header">
                <h3>NLWeb Search</h3>
                <button id="nlweb-close">×</button>
            </div>

            <!-- Chat area -->
            <div class="chat-area">
                <!-- Initial center input (shown when no messages) -->
                <div id="nlweb-initial-input" class="nlweb-initial-input">
                    <div class="initial-input-wrapper">
                        <h2>What would you like to know?</h2>
                        <input type="text"
                               id="nlweb-site-initial"
                               class="site-input"
                               placeholder="Site filter (optional)">
                        <textarea id="nlweb-query-initial"
                                  class="query-input-large"
                                  placeholder="Ask a question..."
                                  rows="3"></textarea>
                        <button id="nlweb-submit-initial" class="submit-button">
                            Send
                        </button>
                    </div>
                </div>

                <!-- Messages area (initially hidden) -->
                <div id="nlweb-messages" class="nlweb-messages hidden">
                    <!-- Messages will be added here dynamically -->
                </div>
            </div>

            <!-- Follow-up input area (shown after first query) -->
            <div id="nlweb-followup-input" class="nlweb-followup-input hidden">
                <div class="followup-input-wrapper">
                    <input type="text"
                           id="nlweb-site-followup"
                           placeholder="Site filter (optional)">
                    <textarea id="nlweb-query-followup"
                              placeholder="Ask a follow-up question..."
                              rows="2"></textarea>
                    <button id="nlweb-submit-followup">Send</button>
                </div>
            </div>
        </div>

        <!-- Overlay for mobile sidebar -->
        <div id="sidebar-overlay" class="sidebar-overlay"></div>
    </div>

    <script src="nlweb-chat.js"></script>
</body>
</html>
```

## Step 2: JavaScript Implementation (`nlweb-chat.js`)

### 2.1 Main Class Structure
```javascript
class NLWebChat {
    constructor() {
        this.baseUrl = 'https://nlw.azurewebsites.net';
        this.currentStream = null;
        this.conversations = {};
        this.currentConversation = null;
        this.init();
    }

    init() {
        this.bindElements();
        this.attachEventListeners();
        this.loadConversations();
    }
}
```

### 2.2 Event Handling
```javascript
bindElements() {
    this.elements = {
        // Main app elements
        app: document.getElementById('nlweb-app'),
        trigger: document.getElementById('nlweb-trigger'),
        container: document.getElementById('nlweb-container'),
        closeBtn: document.getElementById('nlweb-close'),
        messagesDiv: document.getElementById('nlweb-messages'),

        // Sidebar elements
        sidebar: document.getElementById('nlweb-sidebar'),
        sidebarToggle: document.getElementById('sidebar-toggle'),
        sidebarOverlay: document.getElementById('sidebar-overlay'),
        conversationsList: document.getElementById('conversations-list'),
        newChatBtn: document.getElementById('new-chat-btn'),

        // Initial center input elements
        initialInput: document.getElementById('nlweb-initial-input'),
        queryInputInitial: document.getElementById('nlweb-query-initial'),
        siteInputInitial: document.getElementById('nlweb-site-initial'),
        submitBtnInitial: document.getElementById('nlweb-submit-initial'),

        // Follow-up input elements
        followupInput: document.getElementById('nlweb-followup-input'),
        queryInputFollowup: document.getElementById('nlweb-query-followup'),
        siteInputFollowup: document.getElementById('nlweb-site-followup'),
        submitBtnFollowup: document.getElementById('nlweb-submit-followup')
    };
}

attachEventListeners() {
    // Main controls
    this.elements.trigger.onclick = () => this.open();
    this.elements.closeBtn.onclick = () => this.close();

    // Sidebar controls
    this.elements.sidebarToggle.onclick = () => this.toggleSidebar();
    this.elements.sidebarOverlay.onclick = () => this.closeSidebar();
    this.elements.newChatBtn.onclick = () => this.startNewChat();

    // Initial input handlers
    this.elements.submitBtnInitial.onclick = () => this.sendInitialQuery();
    this.elements.queryInputInitial.onkeypress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendInitialQuery();
        }
    };

    // Follow-up input handlers
    this.elements.submitBtnFollowup.onclick = () => this.sendFollowupQuery();
    this.elements.queryInputFollowup.onkeypress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendFollowupQuery();
        }
    };
}

// Sidebar methods
toggleSidebar() {
    this.elements.sidebar.classList.toggle('active');
    this.elements.sidebarOverlay.classList.toggle('active');
}

closeSidebar() {
    this.elements.sidebar.classList.remove('active');
    this.elements.sidebarOverlay.classList.remove('active');
}

startNewChat() {
    // Clear current conversation
    this.currentConversation = null;
    this.elements.messagesDiv.innerHTML = '';

    // Reset to initial state
    this.elements.initialInput.classList.remove('hidden');
    this.elements.messagesDiv.classList.add('hidden');
    this.elements.followupInput.classList.add('hidden');

    // Focus on initial input
    this.elements.queryInputInitial.focus();

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
        this.closeSidebar();
    }
}
```

### 2.3 Query Handling with UI Transitions
```javascript
sendInitialQuery() {
    const query = this.elements.queryInputInitial.value.trim();
    const site = this.elements.siteInputInitial.value.trim() || 'all';

    if (!query) return;

    // Transition UI from initial to conversation view
    this.transitionToConversationView();

    // Clear input
    this.elements.queryInputInitial.value = '';

    // Send the query
    this.sendQuery(query, site);
}

sendFollowupQuery() {
    const query = this.elements.queryInputFollowup.value.trim();
    const site = this.elements.siteInputFollowup.value.trim() || 'all';

    if (!query) return;

    // Clear input
    this.elements.queryInputFollowup.value = '';

    // Send the query
    this.sendQuery(query, site);
}

transitionToConversationView() {
    // Hide initial center input
    this.elements.initialInput.classList.add('hidden');

    // Show messages area
    this.elements.messagesDiv.classList.remove('hidden');

    // Show follow-up input at bottom
    this.elements.followupInput.classList.remove('hidden');
}

async sendQuery(query, site) {
    // Initialize conversation if needed
    if (!this.currentConversation) {
        this.currentConversation = {
            id: Date.now().toString(),
            messages: []
        };
    }

    // Add user message to UI
    this.addMessage('user', query, { site });

    // Create assistant message container
    const assistantDiv = this.addMessage('assistant', '', {});

    // Start streaming
    this.streamFromNLWeb(query, site, assistantDiv);
}

streamFromNLWeb(query, site, messageDiv) {
    // Close any existing stream
    if (this.currentStream) {
        this.currentStream.close();
    }

    // Build request URL
    const params = new URLSearchParams({
        query: query,
        site: site,
        num_results: 50,
        streaming: 'true'
    });

    const url = `${this.baseUrl}/ask?${params}`;

    // Create EventSource for SSE
    this.currentStream = new EventSource(url);

    // Container for accumulating content
    const contentDiv = messageDiv.querySelector('.message-content');
    let allContent = [];

    // Handle incoming messages
    this.currentStream.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            // Handle metadata
            if (data._meta) {
                console.log('Stream meta:', data._meta);
            }

            // Handle content
            if (data.content) {
                allContent.push(...data.content);

                // Render each content item
                data.content.forEach(item => {
                    const element = this.renderContentItem(item);
                    contentDiv.appendChild(element);
                });

                // Auto-scroll
                this.scrollToBottom();
            }
        } catch (err) {
            console.error('Parse error:', err);
        }
    };

    // Handle stream completion/error
    this.currentStream.onerror = () => {
        this.currentStream.close();
        this.currentStream = null;

        // Save complete message to conversation
        this.updateMessage(messageDiv.dataset.msgId, allContent);
        this.saveConversations();
    };
}
```

### 2.4 Content Rendering
```javascript
renderContentItem(item) {
    if (item.type === 'text') {
        const p = document.createElement('p');
        p.className = 'result-text';
        p.textContent = item.text;
        return p;
    }

    if (item.type === 'resource') {
        return this.renderResourceCard(item.resource);
    }

    return document.createElement('div');
}

renderResourceCard(resource) {
    const data = resource.data;
    const card = document.createElement('div');
    card.className = 'result-card';

    // Extract title from schema.org data
    const title = this.extractTitle(data);
    const image = this.extractImage(data);

    // Build card HTML
    let cardHTML = '';

    // Add image if available
    if (image) {
        cardHTML += `<img src="${image}" alt="${title}" class="result-image">`;
    }

    // Add content
    cardHTML += `
        <div class="result-content">
            <h4 class="result-title">
                <a href="${data.url}" target="_blank" rel="noopener">
                    ${title}
                </a>
            </h4>
            <p class="result-description">${data.description || ''}</p>
            <span class="result-site">${data.site}</span>
        </div>
    `;

    card.innerHTML = cardHTML;
    return card;
}

extractTitle(data) {
    // Check @graph for structured data
    if (data['@graph'] && Array.isArray(data['@graph'])) {
        for (const item of data['@graph']) {
            // Recipe title
            if (item['@type'] === 'Recipe' && item.name) {
                return item.name;
            }
            // Article headline
            if (item['@type'] === 'Article' && item.headline) {
                return item.headline;
            }
            // Page name
            if (item['@type'] === 'WebPage' && item.name) {
                return item.name;
            }
        }
    }

    // Fallback to direct properties
    return data.name || 'Unknown';
}

extractImage(data) {
    if (data['@graph'] && Array.isArray(data['@graph'])) {
        for (const item of data['@graph']) {
            // Look for ImageObject
            if (item['@type'] === 'ImageObject' && item.url) {
                return item.url;
            }
            // Thumbnail URL
            if (item.thumbnailUrl) {
                return item.thumbnailUrl;
            }
        }
    }
    return null;
}
```

### 2.5 Message Management
```javascript
addMessage(role, content, metadata) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message message-${role}`;
    msgDiv.dataset.msgId = Date.now().toString();

    if (role === 'user') {
        msgDiv.innerHTML = `
            <div class="message-header">You</div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;

        // Add to conversation history
        this.currentConversation.messages.push({
            id: msgDiv.dataset.msgId,
            role: 'user',
            content: content,
            metadata: metadata,
            timestamp: new Date().toISOString()
        });
    } else {
        msgDiv.innerHTML = `
            <div class="message-header">NLWeb</div>
            <div class="message-content"></div>
        `;

        // Add placeholder to conversation
        this.currentConversation.messages.push({
            id: msgDiv.dataset.msgId,
            role: 'assistant',
            content: [], // Will be filled by streaming
            timestamp: new Date().toISOString()
        });
    }

    this.elements.messagesDiv.appendChild(msgDiv);
    this.scrollToBottom();
    return msgDiv;
}

updateMessage(msgId, content) {
    // Update in conversation history
    const msg = this.currentConversation.messages.find(m => m.id === msgId);
    if (msg) {
        msg.content = content;
    }
}

escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

scrollToBottom() {
    this.elements.messagesDiv.scrollTop = this.elements.messagesDiv.scrollHeight;
}
```

### 2.6 localStorage and Conversation List Management
```javascript
saveConversations() {
    if (this.currentConversation) {
        // Generate title if not set
        if (!this.currentConversation.title) {
            const firstMessage = this.currentConversation.messages[0];
            if (firstMessage) {
                this.currentConversation.title = firstMessage.content.substring(0, 30) + '...';
            }
        }

        // Add to conversations object
        this.conversations[this.currentConversation.id] = this.currentConversation;

        // Save to localStorage
        localStorage.setItem('nlweb_conversations', JSON.stringify(this.conversations));
        localStorage.setItem('nlweb_current', this.currentConversation.id);

        // Update sidebar
        this.updateConversationsList();
    }
}

loadConversations() {
    // Load all conversations
    const saved = localStorage.getItem('nlweb_conversations');
    if (saved) {
        this.conversations = JSON.parse(saved);
    }

    // Update sidebar list
    this.updateConversationsList();

    // Load current conversation
    const currentId = localStorage.getItem('nlweb_current');
    if (currentId && this.conversations[currentId]) {
        this.loadConversation(currentId);
    }
}

updateConversationsList() {
    // Clear list
    this.elements.conversationsList.innerHTML = '';

    // Sort conversations by most recent
    const sortedConversations = Object.values(this.conversations)
        .sort((a, b) => {
            const timeA = a.messages[a.messages.length - 1]?.timestamp || a.id;
            const timeB = b.messages[b.messages.length - 1]?.timestamp || b.id;
            return timeB.localeCompare(timeA);
        });

    // Add each conversation to sidebar
    sortedConversations.forEach(conv => {
        const item = document.createElement('div');
        item.className = 'conversation-item';
        if (conv.id === this.currentConversation?.id) {
            item.classList.add('active');
        }

        item.innerHTML = `
            <div class="conversation-title">${conv.title || 'New conversation'}</div>
            <div class="conversation-time">${this.formatDate(conv.id)}</div>
        `;

        item.onclick = () => this.loadConversation(conv.id);

        this.elements.conversationsList.appendChild(item);
    });
}

loadConversation(conversationId) {
    // Save current conversation first
    if (this.currentConversation) {
        this.saveConversations();
    }

    // Load selected conversation
    this.currentConversation = this.conversations[conversationId];

    // Transition to conversation view
    this.transitionToConversationView();

    // Display the conversation
    this.displayConversation();

    // Update sidebar active state
    this.updateConversationsList();

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
        this.closeSidebar();
    }
}

formatDate(timestamp) {
    const date = new Date(parseInt(timestamp));
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
}

displayConversation() {
    // Clear messages div
    this.elements.messagesDiv.innerHTML = '';

    // Display all messages
    this.currentConversation.messages.forEach(msg => {
        if (msg.role === 'user') {
            // Recreate user message
            const msgDiv = document.createElement('div');
            msgDiv.className = 'message message-user';
            msgDiv.innerHTML = `
                <div class="message-header">You</div>
                <div class="message-content">${this.escapeHtml(msg.content)}</div>
            `;
            this.elements.messagesDiv.appendChild(msgDiv);
        } else {
            // Recreate assistant message
            const msgDiv = document.createElement('div');
            msgDiv.className = 'message message-assistant';
            msgDiv.innerHTML = `
                <div class="message-header">NLWeb</div>
                <div class="message-content"></div>
            `;

            // Render saved content
            const contentDiv = msgDiv.querySelector('.message-content');
            if (Array.isArray(msg.content)) {
                msg.content.forEach(item => {
                    const element = this.renderContentItem(item);
                    contentDiv.appendChild(element);
                });
            }

            this.elements.messagesDiv.appendChild(msgDiv);
        }
    });
}
```

### 2.7 UI Controls
```javascript
open() {
    this.elements.container.classList.remove('hidden');
    this.elements.queryInput.focus();
}

close() {
    this.elements.container.classList.add('hidden');

    // Stop any active stream
    if (this.currentStream) {
        this.currentStream.close();
        this.currentStream = null;
    }
}

clearConversation() {
    this.currentConversation = null;
    this.elements.messagesDiv.innerHTML = '';
    this.saveConversations();
}
```

## Step 3: CSS Styling (`nlweb-chat.css`)

### 3.1 Base Layout with Sidebar
```css
* {
    box-sizing: border-box;
}

/* Trigger button */
.nlweb-trigger {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: #007bff;
    color: white;
    border: none;
    cursor: pointer;
    font-size: 24px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 1000;
    transition: transform 0.2s;
}

.nlweb-trigger:hover {
    transform: scale(1.1);
}

/* Main app container */
.nlweb-app {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    background: #f5f5f5;
    z-index: 999;
}

.nlweb-app.hidden {
    display: none;
}

/* Sidebar */
.nlweb-sidebar {
    width: 260px;
    background: white;
    border-right: 1px solid #e0e0e0;
    display: flex;
    flex-direction: column;
    transition: transform 0.3s;
}

.sidebar-header {
    padding: 15px;
    border-bottom: 1px solid #e0e0e0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.sidebar-header h3 {
    margin: 0;
    font-size: 16px;
}

.new-chat-btn {
    width: 30px;
    height: 30px;
    border: none;
    background: #007bff;
    color: white;
    border-radius: 50%;
    cursor: pointer;
    font-size: 20px;
}

.conversations-list {
    flex: 1;
    overflow-y: auto;
}

.conversation-item {
    padding: 12px 15px;
    cursor: pointer;
    border-bottom: 1px solid #f0f0f0;
    transition: background 0.2s;
}

.conversation-item:hover {
    background: #f8f9fa;
}

.conversation-item.active {
    background: #e3f2fd;
}

.conversation-title {
    font-size: 14px;
    color: #333;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.conversation-time {
    font-size: 11px;
    color: #999;
    margin-top: 4px;
}

/* Main chat container */
.nlweb-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: white;
}

/* Sidebar toggle (hidden on desktop) */
.sidebar-toggle {
    display: none;
    position: fixed;
    top: 15px;
    left: 15px;
    z-index: 1001;
    width: 40px;
    height: 40px;
    border: none;
    background: white;
    border-radius: 50%;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    cursor: pointer;
    font-size: 20px;
}

/* Overlay for mobile */
.sidebar-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
    z-index: 998;
}
```

### 3.2 Header
```css
.nlweb-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 20px;
    border-bottom: 1px solid #e0e0e0;
    background: #f8f9fa;
    border-radius: 12px 12px 0 0;
}

.nlweb-header h3 {
    margin: 0;
    font-size: 18px;
    color: #333;
}

.nlweb-header button {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #666;
    padding: 0;
    width: 30px;
    height: 30px;
}
```

### 3.3 Messages Area
```css
.nlweb-messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 15px;
}

/* Message bubbles */
.message {
    max-width: 85%;
    animation: slideIn 0.3s ease;
}

.message-user {
    align-self: flex-end;
    background: #007bff;
    color: white;
    padding: 10px 15px;
    border-radius: 18px 18px 4px 18px;
}

.message-assistant {
    align-self: flex-start;
    background: #f1f3f4;
    padding: 10px 15px;
    border-radius: 18px 18px 18px 4px;
    max-width: 100%;
}

.message-header {
    font-size: 11px;
    font-weight: 600;
    margin-bottom: 5px;
    opacity: 0.7;
    text-transform: uppercase;
}

.message-content {
    font-size: 14px;
    line-height: 1.5;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
```

### 3.4 Result Cards
```css
.result-card {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    transition: box-shadow 0.2s;
}

.result-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.result-image {
    width: 100%;
    height: 120px;
    object-fit: cover;
    border-radius: 6px;
    margin-bottom: 10px;
}

.result-title {
    margin: 0 0 8px 0;
    font-size: 15px;
    line-height: 1.3;
}

.result-title a {
    color: #1a73e8;
    text-decoration: none;
}

.result-title a:hover {
    text-decoration: underline;
}

.result-description {
    margin: 8px 0;
    font-size: 13px;
    color: #555;
    line-height: 1.4;
}

.result-site {
    font-size: 11px;
    color: #999;
    display: inline-block;
    margin-top: 5px;
}

.result-text {
    margin: 8px 0;
    font-size: 14px;
    line-height: 1.5;
    color: #333;
}
```

### 3.5 Input Area
```css
.nlweb-input {
    padding: 15px;
    border-top: 1px solid #e0e0e0;
    background: #f8f9fa;
    border-radius: 0 0 12px 12px;
}

.nlweb-input input {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 6px;
    margin-bottom: 10px;
    font-size: 14px;
}

.nlweb-input textarea {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 6px;
    resize: none;
    font-size: 14px;
    font-family: inherit;
    margin-bottom: 10px;
}

.nlweb-input button {
    width: 100%;
    padding: 10px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: background 0.2s;
}

.nlweb-input button:hover {
    background: #0056b3;
}

.nlweb-input button:disabled {
    background: #ccc;
    cursor: not-allowed;
}
```

### 3.6 Mobile Responsive Design
```css
/* Tablet and Mobile (768px and below) */
@media (max-width: 768px) {
    /* Hide sidebar by default on mobile */
    .nlweb-sidebar {
        position: fixed;
        top: 0;
        left: 0;
        bottom: 0;
        transform: translateX(-100%);
        z-index: 1000;
    }

    /* Show sidebar when active */
    .nlweb-sidebar.active {
        transform: translateX(0);
    }

    /* Show sidebar toggle button */
    .sidebar-toggle {
        display: block;
    }

    /* Show overlay when sidebar is open */
    .sidebar-overlay.active {
        display: block;
    }

    /* Make main container take full width */
    .nlweb-container {
        width: 100%;
    }

    /* Adjust header for mobile */
    .nlweb-header {
        padding-left: 60px; /* Space for hamburger menu */
    }
}

/* Small mobile devices (480px and below) */
@media (max-width: 480px) {
    /* Full screen chat on small devices */
    .nlweb-app {
        border-radius: 0;
    }

    .nlweb-trigger {
        bottom: 10px;
        right: 10px;
        width: 50px;
        height: 50px;
    }

    /* Smaller sidebar on very small screens */
    .nlweb-sidebar {
        width: 220px;
    }

    /* Adjust input areas for small screens */
    .initial-input-wrapper {
        padding: 20px;
    }

    .query-input-large {
        font-size: 16px; /* Prevents zoom on iOS */
    }

    .followup-input-wrapper textarea {
        font-size: 16px; /* Prevents zoom on iOS */
    }

    /* Smaller text and padding */
    .result-card {
        padding: 10px;
    }

    .result-title {
        font-size: 14px;
    }

    .result-description {
        font-size: 12px;
    }
}
```

## Mobile Behavior Summary

### Desktop (>768px)
- Sidebar always visible on the left (260px wide)
- Main chat takes remaining space
- No hamburger menu needed

### Tablet/Mobile (≤768px)
- Sidebar hidden by default (slides in from left)
- Hamburger menu button appears (top-left)
- Tap hamburger to open sidebar
- Tap overlay or select conversation to close sidebar
- Full-width chat interface

### Key Mobile Interactions
1. **Opening sidebar**: Tap hamburger menu
2. **Closing sidebar**:
   - Tap overlay
   - Select a conversation
   - Start new chat
3. **Auto-close**: Sidebar closes automatically when user interacts with chat
4. **Smooth transitions**: CSS transform for slide animation

## Testing Checklist

### Functionality
- [ ] Chat opens when trigger clicked
- [ ] Chat closes when X clicked
- [ ] Query sends when button clicked
- [ ] Query sends when Enter pressed
- [ ] Site filter is included in request
- [ ] Empty queries are prevented

### SSE Streaming
- [ ] Connection establishes to NLWeb endpoint
- [ ] Messages stream in real-time
- [ ] Stream closes properly on completion
- [ ] Stream closes when chat closed

### Content Rendering
- [ ] Text items display correctly
- [ ] Resource cards render with title and link
- [ ] Schema.org data extracted properly
- [ ] Images display when available
- [ ] Links open in new tab

### localStorage
- [ ] Conversations save after each message
- [ ] Previous conversation loads on open
- [ ] Content persists across page refreshes
- [ ] Storage handles large conversations

### UI/UX
- [ ] Auto-scroll works during streaming
- [ ] Messages animate in smoothly
- [ ] Initial input centered when no messages
- [ ] Input moves to bottom after first query
- [ ] Loading states are clear

### Mobile Specific
- [ ] Sidebar hidden by default on mobile
- [ ] Hamburger menu visible and functional
- [ ] Sidebar slides in smoothly
- [ ] Overlay appears when sidebar open
- [ ] Tap overlay closes sidebar
- [ ] Selecting conversation closes sidebar
- [ ] Full-width layout on mobile
- [ ] No horizontal scrolling
- [ ] Input doesn't zoom on iOS (font-size: 16px)

## Deployment

### Files Required
```
nlweb-ui/
├── index.html
├── nlweb-chat.js
└── nlweb-chat.css
```

### Integration Options

1. **Standalone**: Open index.html directly
2. **Embedded**: Include script in any page
3. **Widget**: Add trigger button to existing site

### Configuration
Can be made configurable:
```javascript
const chat = new NLWebChat({
    baseUrl: 'https://custom-nlweb.com',
    defaultSite: 'mysite.com',
    maxResults: 100
});
```

## Summary

This UI implementation:
- **Sends** HTTP requests to NLWeb endpoint
- **Receives** SSE streaming responses
- **Displays** results progressively as they arrive
- **Stores** complete conversations in localStorage
- **Provides** a clean, responsive chat interface

No server-side logic, no model management, no MCP protocol - just a simple frontend that talks to the NLWeb HTTP API and displays results.