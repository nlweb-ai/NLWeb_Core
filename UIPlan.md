# NLWeb Universal Host Implementation Guide

## Project Goal
Build NLWeb as a universal host that can run ChatGPT Apps (and any MCP-compatible apps) with any AI model (OpenAI, Anthropic, Llama, etc.), making these apps portable and model-agnostic.

## Background Context

### What are ChatGPT Apps?
ChatGPT Apps (like Zillow, Canva, Spotify) are interactive experiences that run inside ChatGPT using:
- **Model Context Protocol (MCP)**: The communication protocol
- **Apps SDK**: UI rendering framework 
- **Tool invocation**: Apps expose tools that the model can call

### The Problem
Currently, these apps are locked to ChatGPT. They can't run with other AI models or in other environments.

### The Solution: NLWeb as Universal Host
NLWeb will act as a bridge/host that:
1. Accepts connections from ChatGPT Apps (via MCP protocol)
2. Translates between different AI models
3. Manages conversation context explicitly
4. Enables any app to work with any model

## Technical Architecture

### Core Components Needed

```
┌─────────────────────────────────────────────┐
│           Web Browser / Client               │
├─────────────────────────────────────────────┤
│         NLWeb Universal Host                 │
│  ┌─────────────────────────────────────────┐    │
│  │   MCP Server Implementation         │    │
│  │   - Implements MCP protocol         │    │
│  │   - Exposes tools/list, tools/call  │    │
│  │   - Handles UI rendering metadata   │    │
│  └─────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │   Model Adapter Layer               │    │
│  │   - OpenAI API                      │    │
│  │   - Anthropic API                   │    │
│  │   - Local Llama                     │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │   NLWeb Protocol Handler            │    │
│  │   - Ask endpoint                    │    │
│  │   - Context management              │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

## Implementation Requirements

### 1. MCP Server Implementation

Create an MCP server that ChatGPT Apps can connect to:

```javascript
// File: src/mcp-server.js

class NLWebMCPServer {
  constructor() {
    this.apps = new Map(); // Registry of connected apps
    this.sessions = new Map(); // Active sessions
  }

  // MCP Protocol Methods
  async initialize(params) {
    // Handle MCP initialization handshake
    return {
      protocolVersion: "2024-11-05",
      serverInfo: {
        name: "nlweb-universal-host",
        version: "1.0.0"
      },
      capabilities: {
        tools: {},
        resources: {}
      }
    };
  }

  async listTools() {
    // Return tools from all connected apps
    const tools = [];
    for (const app of this.apps.values()) {
      tools.push(...app.tools);
    }
    return { tools };
  }

  async callTool(params) {
    const { name, arguments: args } = params;
    
    // Find which app provides this tool
    const app = this.findAppForTool(name);
    
    // Convert to NLWeb Ask format with context
    const nlwebRequest = {
      query: this.synthesizeQuery(name, args),
      prev: this.getConversationHistory(params.sessionId),
      context: this.extractContext(params),
      mode: "tool_invocation",
      site: app.id
    };
    
    // Forward to app and get response
    const response = await app.handleAsk(nlwebRequest);
    
    // Format response for MCP
    return {
      content: response.content,
      structuredContent: response.data,
      _meta: response.metadata
    };
  }
}
```

### 2. Model Adapter Layer

Support multiple AI models:

```javascript
// File: src/model-adapter.js

class ModelAdapter {
  constructor(config) {
    this.provider = config.provider; // 'openai', 'anthropic', 'local'
    this.apiKey = config.apiKey;
  }

  async processQuery(query, context) {
    switch(this.provider) {
      case 'openai':
        return this.processOpenAI(query, context);
      case 'anthropic':
        return this.processAnthropic(query, context);
      case 'local':
        return this.processLocal(query, context);
    }
  }

  async processOpenAI(query, context) {
    // Call OpenAI API with context
    const messages = [
      ...this.formatContext(context),
      { role: 'user', content: query }
    ];
    
    const response = await openai.chat.completions.create({
      model: 'gpt-4',
      messages,
      tools: this.formatToolsForOpenAI()
    });
    
    return this.extractToolCalls(response);
  }

  async processAnthropic(query, context) {
    // Call Anthropic API
    const response = await anthropic.messages.create({
      model: 'claude-3-opus-20240229',
      messages: this.formatContextForClaude(context, query),
      tools: this.formatToolsForClaude()
    });
    
    return this.extractToolCalls(response);
  }
}
```

### 3. NLWeb Protocol Handler

Implement NLWeb's Ask/Who protocol:

```javascript
// File: src/nlweb-protocol.js

class NLWebProtocol {
  async handleAsk(params) {
    const {
      query,
      prev = [],
      context = "",
      mode = "summary",
      site = null,
      streaming = false,
      conversation_id = null,
      constr = {},
      response_format = "nlweb"
    } = params;

    // Build full context
    const fullContext = {
      previous: prev,
      additional: context,
      constraints: constr
    };

    // Route to appropriate model
    const modelResponse = await this.modelAdapter.processQuery(
      query, 
      fullContext
    );

    // If model wants to call tools, execute them
    if (modelResponse.toolCalls) {
      const toolResults = await this.executeTools(modelResponse.toolCalls);
      return this.formatResponse(toolResults, response_format);
    }

    return this.formatResponse(modelResponse, response_format);
  }

  async handleWho(params) {
    // Return list of available agents/apps
    const agents = [];
    for (const app of this.apps.values()) {
      agents.push({
        id: app.id,
        name: app.name,
        description: app.description,
        capabilities: app.tools.map(t => t.name)
      });
    }
    return { agents };
  }
}
```

### 4. Transport Layer Support

Support multiple transport protocols:

```javascript
// File: src/transports/index.js

class TransportManager {
  constructor(nlwebHost) {
    this.host = nlwebHost;
    this.transports = new Map();
  }

  async initialize() {
    // HTTP/REST endpoint
    this.addTransport('http', new HTTPTransport(this.host));
    
    // WebSocket for streaming
    this.addTransport('websocket', new WebSocketTransport(this.host));
    
    // MCP over stdio (for local apps)
    this.addTransport('stdio', new StdioTransport(this.host));
    
    // MCP over HTTP (SSE)
    this.addTransport('mcp-sse', new MCPSSETransport(this.host));
  }
}

// File: src/transports/mcp-sse.js
class MCPSSETransport {
  constructor(host) {
    this.host = host;
  }

  async start(port = 8080) {
    const app = express();
    
    // MCP endpoint
    app.post('/mcp', async (req, res) => {
      const { method, params, id } = req.body;
      
      try {
        let result;
        switch(method) {
          case 'initialize':
            result = await this.host.mcp.initialize(params);
            break;
          case 'tools/list':
            result = await this.host.mcp.listTools();
            break;
          case 'tools/call':
            result = await this.host.mcp.callTool(params);
            break;
        }
        
        res.json({
          jsonrpc: '2.0',
          id,
          result
        });
      } catch (error) {
        res.json({
          jsonrpc: '2.0',
          id,
          error: {
            code: -32603,
            message: error.message
          }
        });
      }
    });
    
    app.listen(port);
  }
}
```

### 5. App Registry and Management

Manage connected apps:

```javascript
// File: src/app-registry.js

class AppRegistry {
  constructor() {
    this.apps = new Map();
    this.routes = new Map(); // tool name -> app mapping
  }

  async registerApp(config) {
    const app = {
      id: config.id,
      name: config.name,
      endpoint: config.endpoint,
      tools: [],
      resources: []
    };

    // If it's an MCP app, discover its tools
    if (config.type === 'mcp') {
      const tools = await this.discoverMCPTools(config.endpoint);
      app.tools = tools;
      
      // Register tool routes
      for (const tool of tools) {
        this.routes.set(tool.name, app.id);
      }
    }

    this.apps.set(app.id, app);
    return app;
  }

  async discoverMCPTools(endpoint) {
    // Connect to MCP server and get tools
    const response = await fetch(`${endpoint}/mcp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'tools/list',
        id: 1
      })
    });
    
    const data = await response.json();
    return data.result.tools;
  }
}
```

### 6. UI Widget Support (for Apps SDK)

Handle UI rendering metadata:

```javascript
// File: src/ui-handler.js

class UIHandler {
  async processToolResponse(response) {
    // Check for UI metadata
    if (response._meta && response._meta['openai/outputTemplate']) {
      const template = response._meta['openai/outputTemplate'];
      
      // Fetch the UI resource
      const uiResource = await this.fetchUIResource(template);
      
      // Return enhanced response with UI
      return {
        ...response,
        ui: {
          type: 'iframe',
          content: uiResource.html,
          scripts: uiResource.scripts,
          data: response.structuredContent
        }
      };
    }
    
    return response;
  }

  async fetchUIResource(templateUri) {
    // Fetch HTML/JS for rendering
    // This would get the widget from the app server
    const response = await fetch(templateUri);
    return await response.text();
  }
}
```

### 7. Main Application

Tie everything together:

```javascript
// File: src/index.js

class NLWebUniversalHost {
  constructor(config) {
    this.config = config;
    
    // Initialize components
    this.mcp = new NLWebMCPServer();
    this.modelAdapter = new ModelAdapter(config.model);
    this.protocol = new NLWebProtocol();
    this.registry = new AppRegistry();
    this.ui = new UIHandler();
    this.transport = new TransportManager(this);
    
    // Wire up dependencies
    this.protocol.modelAdapter = this.modelAdapter;
    this.protocol.apps = this.registry.apps;
    this.mcp.apps = this.registry.apps;
  }

  async start() {
    // Initialize transports
    await this.transport.initialize();
    
    // Start MCP server on port 8080
    await this.transport.get('mcp-sse').start(8080);
    
    console.log('NLWeb Universal Host started');
    console.log('MCP endpoint: http://localhost:8080/mcp');
    console.log('NLWeb endpoint: http://localhost:8080/nlweb');
  }

  async connectToApp(config) {
    // Register a ChatGPT app
    const app = await this.registry.registerApp({
      id: config.id,
      name: config.name,
      type: 'mcp',
      endpoint: config.endpoint
    });
    
    console.log(`Connected to app: ${app.name}`);
    console.log(`Available tools: ${app.tools.map(t => t.name).join(', ')}`);
  }
}

// Usage
const host = new NLWebUniversalHost({
  model: {
    provider: 'anthropic',
    apiKey: process.env.ANTHROPIC_API_KEY
  }
});

await host.start();

// Connect to a ChatGPT app (e.g., Pizzaz demo)
await host.connectToApp({
  id: 'pizzaz',
  name: 'Pizzaz Pizza App',
  endpoint: 'http://localhost:8000'
});
```

## Testing Instructions

1. **Test with OpenAI's Pizzaz demo app**:
   - Clone: `git clone https://github.com/openai/openai-apps-sdk-examples`
   - Start Pizzaz server: `cd pizzaz_server_node && npm start`
   - Connect NLWeb to it
   - Test tool invocation through different models

2. **Test with MCPJam Inspector**:
   - Use MCPJam Inspector to connect to NLWeb's MCP endpoint
   - Verify tools are listed correctly
   - Test tool invocation

3. **Test cross-model compatibility**:
   - Configure NLWeb to use OpenAI
   - Invoke a tool
   - Switch to Anthropic
   - Invoke the same tool
   - Verify both work

## Success Criteria

1. ✅ ChatGPT Apps can connect to NLWeb via MCP protocol
2. ✅ Tool discovery (`tools/list`) returns all available tools
3. ✅ Tool invocation (`tools/call`) executes correctly
4. ✅ Context is properly managed across conversations
5. ✅ Works with OpenAI, Anthropic, and local models
6. ✅ UI widgets render correctly (iframe with data injection)
7. ✅ NLWeb Ask protocol works alongside MCP

## Additional Notes

- Start with MCP protocol support first
- Context management is key - NLWeb adds explicit context that MCP lacks
- The UI rendering (Apps SDK) can be phase 2
- Consider using existing MCP libraries where possible
- Test with real ChatGPT Apps to ensure compatibility

## Resources

- MCP Specification: https://modelcontextprotocol.io
- OpenAI Apps SDK Examples: https://github.com/openai/openai-apps-sdk-examples
- MCPJam Inspector (for testing): https://github.com/MCPJam/inspector
- NLWeb Protocol Spec: [Include the full spec provided earlier]

## Package.json

```json
{
  "name": "nlweb-universal-host",
  "version": "1.0.0",
  "description": "Universal host for ChatGPT Apps using NLWeb protocol",
  "main": "src/index.js",
  "type": "module",
  "scripts": {
    "start": "node src/index.js",
    "dev": "nodemon src/index.js",
    "test": "jest"
  },
  "dependencies": {
    "express": "^4.18.0",
    "ws": "^8.0.0",
    "openai": "^4.0.0",
    "@anthropic-ai/sdk": "^0.20.0",
    "node-fetch": "^3.0.0",
    "dotenv": "^16.0.0",
    "cors": "^2.8.5"
  },
  "devDependencies": {
    "nodemon": "^3.0.0",
    "jest": "^29.0.0"
  }
}
```

