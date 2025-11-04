# Implementation Plan: NLWeb Universal Host for ChatGPT Apps

## Repository Architecture

This project consists of **TWO separate repositories**:

### 1. NLWeb_Core (this repository)
**Location**: `https://github.com/nlweb-ai/NLWeb_Core`

**Purpose**: Python backend with MCP server
- Vector database integration (Azure AI Search, Qdrant, etc.)
- LLM ranking and retrieval (OpenAI, Anthropic, Azure, etc.)
- MCP/A2A/HTTP protocol servers
- Already complete and deployed to PyPI

**Status**: ✅ Complete - No changes needed for nlweb-ui project

### 2. nlweb-ui (NEW - to be created)
**Location**: `https://github.com/nlweb-ai/nlweb-ui` (to be created)

**Purpose**: React/TypeScript frontend
- Chat interface for user queries
- Widget renderer (default ChatGPT-style list + custom iframes)
- MCP client to call backends
- AgentFinder integration for query routing
- Calls NLWeb_Core via HTTP/MCP

**Status**: 🚧 To be built - This is the main implementation work

### How They Connect

```
┌──────────────────────────────────┐
│  nlweb-ui                        │
│  React app on port 5173 (dev)    │
│  or port 80/443 (production)     │
└───────────────┬──────────────────┘
                │
                │ HTTP/MCP calls
                │
┌───────────────▼──────────────────┐
│  NLWeb_Core                      │
│  Python server on port 8080      │
│  Serves MCP protocol             │
└──────────────────────────────────┘
```

### Development Setup

```bash
# Terminal 1: Start backend (NLWeb_Core)
cd ~/code/NLWeb_Core
python -m nlweb_network.server.main config.yaml
# → Runs on http://localhost:8080

# Terminal 2: Start frontend (nlweb-ui, separate repo)
cd ~/code/nlweb-ui
npm run dev
# → Runs on http://localhost:5173
# → Calls backend at http://localhost:8080
```

### Production Deployment

```
┌─────────────────────────┐
│  Static Web Host        │
│  (Vercel/Netlify/CDN)   │
│  Serves: nlweb-ui       │
│  URL: https://nlweb.ai  │
└────────────┬────────────┘
             │
             │ API calls
             │
┌────────────▼────────────┐
│  Backend Server         │
│  (Cloud VM/Container)   │
│  Runs: NLWeb_Core       │
│  URL: https://api.nlweb.ai:8080
└─────────────────────────┘
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Browser                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  NLWeb JavaScript UI Container (React/TypeScript)      │ │
│  │  - Chat interface for user queries                     │ │
│  │  - Calls AgentFinder to route queries to apps          │ │
│  │  - MCP client to call selected app                     │ │
│  │  - Widget renderer (iframe host)                       │ │
│  │  - Implements window.openai API bridge                 │ │
│  └────────────────────────────────────────────────────────┘ │
│           │                   │                   │          │
│    ┌──────▼────────┐   ┌─────▼──────┐   ┌───────▼────┐    │
│    │ Widget iframes│   │Widget iframe│   │Widget iframe│    │
│    │ (from app)    │   │ (from app) │   │(from app)   │    │
│    └───────────────┘   └────────────┘   └─────────────┘    │
└─────────────────────────────────────────────────────────────┘
          │                    │                    │
    ┌─────▼──────┐      ┌─────▼──────┐     ┌──────▼────────┐
    │AgentFinder │      │  NLWeb     │     │ ChatGPT Apps  │
    │  Service   │      │  Python    │     │ (MCP Servers) │
    │            │      │  Backend   │     │               │
    │ Input:     │      │            │     │ - Pizzaz      │
    │  query     │      │ Provides:  │     │ - Zillow      │
    │ Output:    │      │ - "ask"    │     │ - Canva       │
    │  app URL   │      │   tool     │     │ - etc.        │
    │            │      │ - fallback │     │               │
    └────────────┘      └────────────┘     └───────────────┘
```

## Key Concepts

### What Are ChatGPT Apps?
- Interactive applications that run via MCP (Model Context Protocol)
- Expose tools that AI models can call
- Return rich UI widgets alongside data responses
- Examples: Pizzaz (pizza ordering), Zillow (real estate), Canva (design)

### How NLWeb Acts as Universal Host
- **NLWeb IS the AI model** - provides natural language understanding and generation
- **All NLWeb Apps are also ChatGPT Apps** - they speak MCP
- **All ChatGPT Apps are called with the "ask" tool** - standard interface
- **AgentFinder routes queries** - determines which app to use for each query
- **Widgets render in browser** - interactive UI components from apps

### The Flow
1. User types query in NLWeb UI
2. UI calls AgentFinder: "Which app should handle this query?"
3. AgentFinder returns MCP app endpoint (or null for fallback)
4. UI calls that app's "ask" tool via MCP
5. App returns data + widget metadata (`_meta["openai/outputTemplate"]`)
6. UI fetches widget HTML/JS/CSS and renders in iframe
7. Widget interacts with user, can call tools via `window.openai` API

## What Needs to Be Built

### 1. JavaScript UI Container (NEW - Primary Work)
**Location**: New package/repo `nlweb-ui` (React + TypeScript)

This is the main deliverable - a web application that hosts ChatGPT Apps.

**Components:**

#### 1.1 Chat Interface (`src/components/Chat.tsx`)
- Message list showing conversation history
- Each message can contain:
  - Text from user
  - Text from assistant (NLWeb)
  - Widget components from apps
- Input box for user queries
- Send button / Enter to submit

**Details:**
- Use React state to manage messages array
- Each message has: `{ id, role: 'user'|'assistant', content, widgets?: [] }`
- Auto-scroll to latest message
- Show loading indicator while waiting for responses

#### 1.2 AgentFinder Integration (`src/services/agentFinder.ts`)
**Purpose**: Determine which MCP app should handle each query

**API Contract** (from https://github.com/nlweb-ai/AgentFinder):
```typescript
interface AgentFinderRequest {
  query: string;
  conversationHistory?: Message[];
}

interface AgentFinderResponse {
  appEndpoint: string | null;  // null means use NLWeb fallback
  appName?: string;
  confidence?: number;
}

async function routeQuery(query: string): Promise<AgentFinderResponse>
```

**Logic:**
1. Send user query to AgentFinder
2. If response.appEndpoint is not null → use that MCP app
3. If response.appEndpoint is null → use NLWeb Python backend's "ask" tool
4. Cache routing decisions to avoid repeated calls for similar queries

#### 1.3 MCP Client (`src/services/mcpClient.ts`)
**Purpose**: Communicate with MCP servers (ChatGPT Apps)

**Methods:**
```typescript
class MCPClient {
  // Connect and handshake with MCP server
  async initialize(endpoint: string): Promise<void>

  // Get list of available tools (for validation)
  async listTools(endpoint: string): Promise<Tool[]>

  // Call a tool on the MCP server
  async callTool(
    endpoint: string,
    toolName: string,
    arguments: Record<string, any>
  ): Promise<ToolCallResponse>
}

interface ToolCallResponse {
  content: ContentItem[];        // Text, images, etc.
  structuredContent?: object;    // JSON data
  isError: boolean;
  _meta?: {
    "openai/outputTemplate"?: string;  // Widget URL
    [key: string]: any;
  };
}

interface ContentItem {
  type: 'text' | 'image' | 'resource';
  text?: string;
  data?: string;  // base64
  uri?: string;
}
```

**Protocol Details:**
- Uses JSON-RPC 2.0 format
- POST to `{endpoint}/mcp` with:
  ```json
  {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "ask",
      "arguments": {
        "query": "user's question"
      }
    },
    "id": 1
  }
  ```
- Response contains `content` array and optional `_meta` object
- Look for `_meta["openai/outputTemplate"]` to know if widget should render

**Transport:**
- HTTP/POST for single request-response
- SSE (Server-Sent Events) for streaming responses
- Must work in browser (no stdio transport)

#### 1.4 Widget Renderer (`src/components/WidgetRenderer.tsx`)
**Purpose**: Display interactive UI widgets from ChatGPT Apps

**Process:**
1. Tool response includes `_meta["openai/outputTemplate"]` = `"ui://widget/story.html"`
2. Extract widget URI from metadata
3. Convert `ui://widget/story.html` → `{appEndpoint}/assets/widget/story.html`
4. Fetch HTML bundle from app server
5. Parse HTML to extract CSS and JavaScript
6. Create isolated iframe with sandbox
7. Load HTML/CSS/JS into iframe
8. Inject `structuredContent` data via postMessage

**Component Structure:**
```typescript
interface WidgetProps {
  widgetUri: string;          // e.g., "ui://widget/story.html"
  appEndpoint: string;        // e.g., "http://localhost:8000"
  data: object;               // structuredContent from tool response
  onToolCall: (name: string, args: any) => void;
  onFollowUp: (message: string) => void;
}

function WidgetRenderer({ widgetUri, appEndpoint, data, ... }: WidgetProps) {
  // 1. Fetch widget bundle
  // 2. Create iframe
  // 3. Setup postMessage bridge
  // 4. Inject data
  // 5. Handle widget callbacks
}
```

**Security:**
- Use iframe with `sandbox="allow-scripts allow-forms allow-same-origin"`
- Restrict to HTTPS in production
- Validate widget URIs
- CSP headers to prevent XSS

**Widget Loading:**
```typescript
async function loadWidget(widgetUri: string, appEndpoint: string): Promise<string> {
  // Convert ui://widget/story.html → http://localhost:8000/assets/widget/story.html
  const url = widgetUri.replace('ui://', `${appEndpoint}/assets/`);
  const response = await fetch(url);
  return await response.text();  // Returns HTML with embedded CSS/JS
}
```

#### 1.5 Widget Bridge API (`src/services/widgetBridge.ts`)
**Purpose**: Implement `window.openai` API that widgets can call

Widgets run in iframes and need to communicate with the host. Use postMessage for this.

**APIs to Implement:**

```typescript
// In host window (nlweb-ui)
class WidgetBridge {
  constructor(iframeElement: HTMLIFrameElement, widgetId: string) {
    // Setup postMessage listener
    window.addEventListener('message', this.handleMessage);
  }

  handleMessage(event: MessageEvent) {
    const { type, payload } = event.data;

    switch(type) {
      case 'setWidgetState':
        this.saveState(payload);
        break;
      case 'callTool':
        this.handleToolCall(payload.name, payload.arguments);
        break;
      case 'sendFollowUpMessage':
        this.handleFollowUp(payload.message);
        break;
      case 'requestDisplayMode':
        this.handleDisplayMode(payload.mode);
        break;
    }
  }

  // Send data to widget
  sendToWidget(type: string, payload: any) {
    this.iframe.contentWindow.postMessage({ type, payload }, '*');
  }
}
```

**APIs Widgets Can Call** (via window.openai):
```typescript
// Injected into iframe as window.openai
interface WindowOpenAI {
  // Persist widget-specific state (survives page reload)
  setWidgetState(state: object): Promise<void>

  // Get current widget state
  getWidgetState(): Promise<object>

  // Call a tool on the MCP server
  callTool(toolName: string, args: object): Promise<any>

  // Insert a follow-up message into conversation
  sendFollowUpMessage(text: string): Promise<void>

  // Change widget display (inline, picture-in-picture, fullscreen)
  requestDisplayMode(mode: 'inline' | 'pip' | 'fullscreen'): Promise<void>

  // React hook for global state (optional, advanced)
  useOpenAiGlobal(): object
}
```

**Implementation Pattern:**
```typescript
// Inject into iframe
const windowOpenAIScript = `
  window.openai = {
    async setWidgetState(state) {
      return new Promise((resolve) => {
        const msgId = Math.random();
        window.addEventListener('message', function handler(e) {
          if (e.data.type === 'stateSet' && e.data.id === msgId) {
            window.removeEventListener('message', handler);
            resolve();
          }
        });
        window.parent.postMessage({
          type: 'setWidgetState',
          id: msgId,
          payload: state
        }, '*');
      });
    },

    async callTool(name, args) {
      // Similar pattern
    },

    // ... other methods
  };
`;
```

#### 1.6 AI Model Integration (`src/services/nlwebClient.ts`)
**Purpose**: Call NLWeb Python backend for fallback queries

**When to Use:**
- AgentFinder returns null (no specific app matches)
- General knowledge queries
- Queries that need vector database search

**API:**
```typescript
class NLWebClient {
  constructor(backendUrl: string) {
    this.baseUrl = backendUrl;  // e.g., http://localhost:8080
  }

  // Call NLWeb's "ask" tool via MCP
  async ask(query: string, options?: {
    site?: string,
    num_results?: number,
    streaming?: boolean
  }): Promise<ToolCallResponse> {
    // POST to http://localhost:8080/mcp
    // Same format as calling external apps
    return this.mcpClient.callTool(
      this.baseUrl,
      'ask',
      { query, ...options }
    );
  }
}
```

**Note:** NLWeb Python backend already has MCP endpoint - just call it!

#### 1.7 Conversation Manager (`src/services/conversationManager.ts`)
**Purpose**: Track conversation history and state

**State to Maintain:**
```typescript
interface Conversation {
  id: string;
  messages: Message[];
  widgetStates: Map<string, object>;
  metadata: {
    startedAt: Date;
    lastActivity: Date;
  };
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  widgets?: WidgetInstance[];
  toolCalls?: ToolCall[];
  timestamp: Date;
}

interface WidgetInstance {
  id: string;
  widgetUri: string;
  appEndpoint: string;
  data: object;
  state: object;
}
```

**Methods:**
```typescript
class ConversationManager {
  // Create new conversation
  createConversation(): Conversation

  // Add message to conversation
  addMessage(conversationId: string, message: Message): void

  // Get conversation history
  getHistory(conversationId: string): Message[]

  // Save/load from localStorage
  persist(conversationId: string): void
  restore(conversationId: string): Conversation

  // Widget state management
  setWidgetState(conversationId: string, widgetId: string, state: object): void
  getWidgetState(conversationId: string, widgetId: string): object
}
```

**Persistence:**
- Use localStorage for client-side persistence
- Key format: `nlweb:conversation:{id}`
- Serialize to JSON
- Option to add server-side sync later

### 2. Python Backend Enhancements (MINIMAL - Almost Nothing)

**Current State:** NLWeb already provides everything needed!
- ✅ MCP server at `/mcp` endpoint
- ✅ Exposes "ask" tool
- ✅ Multiple AI model support (OpenAI, Anthropic, Azure, etc.)
- ✅ Vector database integration
- ✅ HTTP/SSE streaming support

**No Code Changes Needed!**

**Only Configuration:**
Just run NLWeb with normal config, make sure:
```yaml
server:
  host: localhost
  port: 8080
  enable_cors: true  # Important for browser access!
```

### 3. Testing & Examples

#### 3.1 Test Setup
**Prerequisites:**
1. Start Pizzaz demo app: `cd pizzaz_server_node && npm start` (port 8000)
2. Start NLWeb Python backend: `python -m nlweb_network.server.main config.yaml` (port 8080)
3. Start nlweb-ui: `npm run dev` (port 5173)
4. AgentFinder service running (or mock it for testing)

#### 3.2 Test Scenarios

**Test 1: ChatGPT App (Pizzaz)**
```
User: "I want a pizza with pepperoni and mushrooms"
Expected:
1. AgentFinder returns Pizzaz endpoint
2. MCP client calls Pizzaz "ask" tool
3. Pizzaz returns widget with pizza visualization
4. Widget renders in iframe
5. User can interact with widget (add/remove toppings)
6. Widget can call tools to update order
```

**Test 2: NLWeb Fallback**
```
User: "What are some good pasta recipes?"
Expected:
1. AgentFinder returns null (no specific app)
2. UI falls back to NLWeb backend
3. NLWeb "ask" tool searches vector DB
4. Returns recipe results (no widget, just text/resources)
5. Displays in chat as regular message
```

**Test 3: Widget Interaction**
```
User: "Order a large pizza"
(Pizzaz widget appears)
User clicks "Add extra cheese" in widget
Expected:
1. Widget calls window.openai.callTool('update_order', {size: 'large', extra: ['cheese']})
2. Bridge forwards to Pizzaz MCP server
3. Pizzaz returns updated order
4. Widget updates display
```

**Test 4: Follow-up Message**
```
User: "Show me houses in Seattle"
(Zillow widget appears with listings)
User clicks "Tell me more about this house" in widget
Expected:
1. Widget calls window.openai.sendFollowUpMessage("Tell me about 123 Main St")
2. New user message appears in chat
3. AgentFinder routes to Zillow again
4. New tool call with context
```

## File Structure

```
nlweb-ui/                               # NEW repository
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── public/
│   └── favicon.ico
└── src/
    ├── App.tsx                         # Main app component
    ├── main.tsx                        # Entry point
    ├── components/
    │   ├── Chat.tsx                    # Chat interface container
    │   ├── MessageList.tsx             # Display conversation
    │   ├── MessageItem.tsx             # Individual message
    │   ├── MessageInput.tsx            # User input box
    │   ├── WidgetRenderer.tsx          # Render widget iframes
    │   └── WidgetFrame.tsx             # Individual iframe wrapper
    ├── services/
    │   ├── agentFinder.ts              # AgentFinder API client
    │   ├── mcpClient.ts                # MCP protocol implementation
    │   ├── nlwebClient.ts              # NLWeb backend client
    │   ├── widgetBridge.ts             # window.openai API bridge
    │   └── conversationManager.ts      # History tracking
    ├── types/
    │   ├── mcp.ts                      # MCP protocol types
    │   ├── widget.ts                   # Widget-related types
    │   ├── conversation.ts             # Message types
    │   └── agentFinder.ts              # AgentFinder types
    ├── utils/
    │   ├── widgetLoader.ts             # Load widget HTML bundles
    │   ├── sandboxPolicy.ts            # Iframe security config
    │   └── storage.ts                  # localStorage helpers
    └── config.ts                       # App configuration

NLWeb_Core/                             # Existing repository
└── (no changes needed!)
```

## Implementation Steps

### Phase 1: Foundation (Week 1)

**Day 1-2: Project Setup**
- [ ] Create nlweb-ui repository
- [ ] Initialize React + TypeScript + Vite
- [ ] Install dependencies:
  - react, react-dom
  - typescript
  - axios (HTTP client)
  - uuid (for generating IDs)
- [ ] Set up basic folder structure
- [ ] Create config file with AgentFinder URL, NLWeb URL

**Day 3-5: Chat Interface**
- [ ] Build Chat.tsx container
- [ ] Build MessageList.tsx (display messages)
- [ ] Build MessageInput.tsx (user input)
- [ ] Add basic styling (Tailwind CSS or CSS modules)
- [ ] Test with mock data

**Day 6-7: MCP Client**
- [ ] Implement MCPClient class
- [ ] Support JSON-RPC 2.0 format
- [ ] Handle tools/call method
- [ ] Parse responses (content, structuredContent, _meta)
- [ ] Add error handling
- [ ] Test with NLWeb Python backend

### Phase 2: Widget System (Week 2)

**Day 1-2: Widget Loading**
- [ ] Implement widgetLoader.ts (fetch HTML from apps)
- [ ] Handle ui:// URI conversion
- [ ] Parse HTML/CSS/JS from bundle
- [ ] Add caching for loaded widgets

**Day 3-4: Widget Rendering**
- [ ] Build WidgetRenderer.tsx component
- [ ] Create iframes with sandbox
- [ ] Load widget HTML into iframe
- [ ] Add loading/error states
- [ ] Test with Pizzaz demo

**Day 5-7: Widget Bridge**
- [ ] Implement WidgetBridge class
- [ ] Set up postMessage communication
- [ ] Inject window.openai API into iframes
- [ ] Implement setWidgetState
- [ ] Implement callTool
- [ ] Implement sendFollowUpMessage
- [ ] Implement requestDisplayMode
- [ ] Test bidirectional communication

### Phase 3: Integration (Week 3)

**Day 1-2: AgentFinder Integration**
- [ ] Create agentFinder.ts client
- [ ] Call AgentFinder API with user query
- [ ] Handle routing response
- [ ] Implement fallback to NLWeb
- [ ] Add caching/optimization

**Day 3-4: Conversation Management**
- [ ] Implement ConversationManager
- [ ] Track message history
- [ ] Persist to localStorage
- [ ] Handle widget state storage
- [ ] Add restore on page load

**Day 5: NLWeb Backend Client**
- [ ] Create nlwebClient.ts
- [ ] Wrapper around MCPClient for NLWeb backend
- [ ] Handle fallback queries
- [ ] Test with vector database queries

**Day 6-7: End-to-End Testing**
- [ ] Test with Pizzaz app
- [ ] Test with NLWeb fallback
- [ ] Test widget interactions
- [ ] Test follow-up messages
- [ ] Test state persistence
- [ ] Fix bugs

### Phase 4: Polish (Week 4)

**Day 1-3: UI/UX Improvements**
- [ ] Add loading indicators
- [ ] Improve error messages
- [ ] Add retry logic
- [ ] Better widget layouts (inline, PiP, fullscreen)
- [ ] Responsive design for mobile
- [ ] Accessibility (ARIA labels, keyboard nav)

**Day 4-5: Documentation**
- [ ] README with setup instructions
- [ ] Architecture documentation
- [ ] API documentation for widget developers
- [ ] Deployment guide
- [ ] Troubleshooting guide

**Day 6-7: Deployment Prep**
- [ ] Add production build config
- [ ] Environment variable management
- [ ] Docker configuration (optional)
- [ ] CI/CD setup (optional)

## Key Technical Decisions

### 1. Framework: React
**Why React:**
- Large ecosystem and community
- Good TypeScript support
- Hooks for managing widget lifecycle
- Easy to integrate with postMessage bridge
- ChatGPT Apps SDK uses React patterns

### 2. Build Tool: Vite
**Why Vite:**
- Fast dev server with HMR
- Simple TypeScript configuration
- Good for modern React apps
- Smaller bundle sizes than webpack

### 3. Widget Isolation: iframes
**Why iframes:**
- Strong security isolation
- Standard approach (ChatGPT uses this)
- Works with postMessage API
- Can sandbox untrusted code
- Each app provides its own HTML/CSS/JS

**Sandbox Policy:**
```html
<iframe
  sandbox="allow-scripts allow-same-origin allow-forms"
  src="about:blank"
/>
```

### 4. State Management: React Context + localStorage
**Why this approach:**
- Simple for MVP
- No external state library needed initially
- localStorage provides persistence
- Can upgrade to Redux/Zustand later if needed

### 5. Styling: Tailwind CSS (or CSS Modules)
**Why Tailwind:**
- Rapid prototyping
- Consistent design system
- Small bundle size
- No naming conflicts

### 6. Transport: HTTP/SSE
**Why not WebSocket:**
- MCP spec recommends HTTP/SSE
- Simpler than WebSocket
- Works through proxies
- ChatGPT Apps already support it

## Success Criteria

### Must Have (MVP)
1. ✅ User can type query and see response
2. ✅ AgentFinder integration works
3. ✅ Can call external MCP apps (Pizzaz demo)
4. ✅ Widgets render from outputTemplate
5. ✅ Widget can call tools via window.openai.callTool()
6. ✅ Fallback to NLWeb backend works
7. ✅ Conversation history persists across page reload
8. ✅ Multiple widgets can exist in same conversation

### Nice to Have (Future)
- [ ] Widget picture-in-picture mode
- [ ] Widget fullscreen mode
- [ ] Multiple conversation threads
- [ ] Export conversation to file
- [ ] Voice input
- [ ] Dark mode
- [ ] Mobile-optimized layout
- [ ] Server-side conversation sync

## Dependencies

### npm packages (nlweb-ui)
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "axios": "^1.6.0",
    "uuid": "^9.0.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.2.0",
    "tailwindcss": "^3.4.0"
  }
}
```

### External Services
- **AgentFinder**: https://github.com/nlweb-ai/AgentFinder (provides query routing)
- **NLWeb Backend**: localhost:8080 (existing Python backend)
- **ChatGPT Apps**: e.g., Pizzaz on localhost:8000

### Python (no changes)
- NLWeb packages already installed and working

## Security Considerations

### 1. Widget Isolation
- Use iframe sandbox attribute
- Restrict to `allow-scripts allow-same-origin allow-forms`
- Validate widget URIs before loading
- CSP headers to prevent XSS

### 2. postMessage Security
- Validate message origin
- Check message structure before processing
- Don't trust data from iframes without validation

### 3. API Keys
- Never expose API keys in frontend
- All model calls go through NLWeb backend
- AgentFinder should not require authentication (or use API key in backend)

### 4. CORS
- NLWeb backend must enable CORS for browser access
- Configure allowed origins properly

### 5. User Data
- Don't store sensitive data in localStorage
- Encrypt conversation history if needed
- Add session expiry

## Example Code Snippets

### Main Flow Example
```typescript
// src/App.tsx
async function handleUserQuery(query: string) {
  // 1. Add user message to chat
  conversationManager.addMessage({
    role: 'user',
    content: query
  });

  // 2. Route query via AgentFinder
  const routing = await agentFinder.routeQuery(query);

  let response;
  if (routing.appEndpoint) {
    // 3a. Call external MCP app
    response = await mcpClient.callTool(
      routing.appEndpoint,
      'ask',
      { query }
    );
  } else {
    // 3b. Fallback to NLWeb
    response = await nlwebClient.ask(query);
  }

  // 4. Extract widget if present
  const widgetUri = response._meta?.['openai/outputTemplate'];

  // 5. Add assistant message with widget
  conversationManager.addMessage({
    role: 'assistant',
    content: response.content[0].text,
    widgets: widgetUri ? [{
      uri: widgetUri,
      endpoint: routing.appEndpoint,
      data: response.structuredContent
    }] : undefined
  });
}
```

### Widget Bridge Example
```typescript
// Widget calls this from inside iframe
window.openai.callTool('update_order', {
  size: 'large',
  toppings: ['pepperoni', 'mushrooms']
});

// Host receives via postMessage
bridge.handleMessage({
  type: 'callTool',
  payload: {
    name: 'update_order',
    arguments: { size: 'large', toppings: [...] }
  }
});

// Host forwards to MCP server
const response = await mcpClient.callTool(
  appEndpoint,
  'update_order',
  payload.arguments
);

// Host sends result back to widget
iframe.contentWindow.postMessage({
  type: 'toolResult',
  payload: response
}, '*');
```

## Open Questions

1. **AgentFinder API Contract**: Need exact API specification
   - What is the request format?
   - What is the response format?
   - How is confidence/scoring handled?

2. **Widget Resource URLs**: How do apps serve widgets?
   - Is there a standard `/assets/` path?
   - Or does each app define its own structure?
   - How are `ui://` URIs resolved?

3. **Authentication**: Do ChatGPT Apps require auth?
   - User authentication for accessing apps?
   - API keys for app-to-app communication?
   - How does NLWeb pass user context to apps?

4. **Multi-turn Conversations**: How is context maintained?
   - Does AgentFinder need conversation history?
   - Do apps receive conversation context?
   - How does NLWeb format context for apps?

## Next Steps

1. **Create nlweb-ui repository**
2. **Set up development environment**
3. **Start with Phase 1: Foundation**
4. **Test with Pizzaz demo app**
5. **Iterate based on testing**

## Resources

- **MCP Specification**: https://modelcontextprotocol.io
- **OpenAI Apps SDK Examples**: https://github.com/openai/openai-apps-sdk-examples
- **AgentFinder Service**: https://github.com/nlweb-ai/AgentFinder
- **NLWeb Documentation**: README.md in this repo
- **Apps SDK Custom UX Guide**: https://developers.openai.com/apps-sdk/build/custom-ux/
