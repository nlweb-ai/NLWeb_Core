# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
NLWeb Network Server - HTTP/MCP/A2A server using pluggable interface adapters.

This server provides multiple protocol endpoints:
- /ask: HTTP endpoint (GET/POST) with streaming (SSE) or non-streaming (JSON) responses
- /mcp: MCP protocol endpoint (JSON-RPC 2.0)
- /mcp-sse: MCP protocol with Server-Sent Events streaming
- /a2a: A2A protocol endpoint (JSON-RPC 2.0)
- /a2a-sse: A2A protocol with Server-Sent Events streaming
- /health: Health check endpoint

Each endpoint uses an interface adapter to handle protocol-specific
formatting while routing to the appropriate NLWeb handler.
"""

from aiohttp import web
from nlweb_core.config import CONFIG
from nlweb_core.NLWebVectorDBRankingHandler import NLWebVectorDBRankingHandler
from nlweb_core.utils import get_param
from nlweb_network.interfaces import (
    HTTPJSONInterface,
    HTTPSSEInterface,
    MCPStreamableInterface,
    MCPSSEInterface,
    A2AStreamableInterface,
    A2ASSEInterface
)
import pathlib


async def health_handler(request):
    """Simple health check endpoint."""
    return web.json_response({"status": "ok"})


async def config_handler(request):
    """Expose client configuration."""
    from nlweb_core.config import CONFIG
    return web.json_response({
        "test_user": CONFIG.test_user
    })


async def ask_handler(request):
    """
    Handle /ask requests (both GET and POST).

    Routes to either HTTP SSE (streaming=true, default) or
    HTTP JSON (streaming=false) interface based on prefer.streaming parameter.

    Expected v0.54 format:
    {
        "query": {"text": "...", ...},
        "context": {...},
        "prefer": {"streaming": true/false, ...},
        "meta": {...}
    }

    Returns:
    - If prefer.streaming=false: JSON response with the complete NLWeb answer
    - Otherwise (default): Server-Sent Events stream
    """
    # Get query parameters to check streaming preference
    query_params = dict(request.query)

    # For POST requests, check JSON body too
    if request.method == 'POST':
        try:
            body = await request.json()
            query_params = {**query_params, **body}
        except Exception:
            pass

    # Extract streaming from prefer section (default: true)
    prefer = query_params.get('prefer', {})
    streaming = prefer.get('streaming', True) if isinstance(prefer, dict) else True

    # Route to appropriate interface
    if streaming:
        interface = HTTPSSEInterface()
    else:
        interface = HTTPJSONInterface()

    return await interface.handle_request(request, NLWebVectorDBRankingHandler)


async def mcp_handler(request):
    """
    Handle MCP protocol requests (JSON-RPC 2.0 over HTTP).

    This is the standard MCP StreamableHTTP transport.
    Handles initialize, tools/list, and tools/call methods.

    Returns:
    - JSON-RPC 2.0 formatted responses
    """
    interface = MCPStreamableInterface()
    return await interface.handle_request(request, NLWebVectorDBRankingHandler)


async def mcp_sse_handler(request):
    """
    Handle MCP protocol requests with Server-Sent Events streaming.

    Similar to /mcp but streams results via SSE for tools/call.
    Supports both GET and POST requests.

    Returns:
    - JSON-RPC 2.0 formatted responses via SSE
    """
    interface = MCPSSEInterface()
    return await interface.handle_request(request, NLWebVectorDBRankingHandler)


async def a2a_handler(request):
    """
    Handle A2A protocol requests (JSON-RPC 2.0 over HTTP).

    This is the standard A2A StreamableHTTP transport.
    Handles agent/card and message/send methods.

    Returns:
    - JSON-RPC 2.0 formatted responses
    """
    interface = A2AStreamableInterface()
    return await interface.handle_request(request, NLWebVectorDBRankingHandler)


async def a2a_sse_handler(request):
    """
    Handle A2A protocol requests with Server-Sent Events streaming.

    Similar to /a2a but streams results via SSE for message/stream.
    Supports both GET and POST requests.

    Returns:
    - JSON-RPC 2.0 formatted responses via SSE
    """
    interface = A2ASSEInterface()
    return await interface.handle_request(request, NLWebVectorDBRankingHandler)


async def await_handler(request):
    """
    Handle /await requests for promise checking.

    Expected POST body (v0.54 format):
    {
        "promise_token": "promise_xyz789",
        "action": "checkin",  // or "cancel"
        "meta": {...}
    }

    Returns:
    - JSON response with promise status or final answer
    """
    try:
        body = await request.json()

        # Validate required fields
        if 'promise_token' not in body:
            return web.json_response({
                '_meta': {'response_type': 'Failure', 'version': '0.54'},
                'error': {'code': 'MISSING_FIELD', 'message': 'Missing required field: promise_token'}
            }, status=400)

        if 'action' not in body or body['action'] not in ['checkin', 'cancel']:
            return web.json_response({
                '_meta': {'response_type': 'Failure', 'version': '0.54'},
                'error': {'code': 'INVALID_ACTION', 'message': 'Action must be "checkin" or "cancel"'}
            }, status=400)

        # TODO: Implement promise tracking/checking logic
        # For now, return a placeholder Promise response
        return web.json_response({
            '_meta': {'response_type': 'Promise', 'version': '0.54'},
            'promise': {'token': body['promise_token'], 'estimated_time': 60}
        })

    except Exception as e:
        return web.json_response({
            '_meta': {'response_type': 'Failure', 'version': '0.54'},
            'error': {'code': 'INTERNAL_ERROR', 'message': str(e)}
        }, status=500)


async def init_app(app):
    """Initialize conversation storage on startup."""
    from nlweb_core.config import CONFIG

    # Initialize conversation storage on startup if enabled
    if hasattr(CONFIG, 'conversation_storage') and CONFIG.conversation_storage.enabled:
        try:
            from nlweb_core.conversation.storage import ConversationStorageClient
            storage = ConversationStorageClient(CONFIG.conversation_storage)
            # Initialize pool and schema on startup to avoid first-request latency
            await storage.backend.initialize()
            app['conversation_storage'] = storage
            # Also set in CONFIG so handlers can access it
            CONFIG.conversation_storage_client = storage
            print("Conversation storage initialized on startup")
        except Exception as e:
            print(f"Failed to initialize conversation storage: {e}")
            import traceback
            traceback.print_exc()


async def cleanup_app(app):
    """Cleanup conversation storage on shutdown."""
    if 'conversation_storage' in app:
        try:
            await app['conversation_storage'].backend.close()
            print("Conversation storage closed")
        except Exception as e:
            print(f"Error closing conversation storage: {e}")


def create_app():
    """Create and configure the aiohttp application."""
    app = web.Application()

    # Add startup and cleanup hooks
    app.on_startup.append(init_app)
    app.on_cleanup.append(cleanup_app)

    # Add HTTP routes
    app.router.add_get('/ask', ask_handler)
    app.router.add_post('/ask', ask_handler)
    app.router.add_post('/await', await_handler)
    app.router.add_get('/health', health_handler)
    app.router.add_get('/config', config_handler)

    # Add MCP routes
    app.router.add_post('/mcp', mcp_handler)  # MCP StreamableHTTP (JSON-RPC over HTTP)
    app.router.add_get('/mcp-sse', mcp_sse_handler)  # MCP over SSE (streaming)
    app.router.add_post('/mcp-sse', mcp_sse_handler)  # MCP over SSE (streaming)

    # Add A2A routes
    app.router.add_post('/a2a', a2a_handler)  # A2A StreamableHTTP (JSON-RPC over HTTP)
    app.router.add_get('/a2a-sse', a2a_sse_handler)  # A2A over SSE (streaming)
    app.router.add_post('/a2a-sse', a2a_sse_handler)  # A2A over SSE (streaming)

    # Serve static files (UI)
    static_dir = pathlib.Path(__file__).parent / 'static'
    if static_dir.exists():
        app.router.add_static('/static', static_dir, name='static')
        # Serve index.html at root
        app.router.add_get('/', lambda request: web.FileResponse(static_dir / 'index.html'))
    else:
        print(f"Warning: Static directory not found at {static_dir}")

    # Enable CORS if configured
    if CONFIG.server.enable_cors:
        try:
            from aiohttp_cors import setup as cors_setup, ResourceOptions

            cors = cors_setup(app, defaults={
                "*": ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*"
                )
            })

            # Configure CORS for all routes
            for route in list(app.router.routes()):
                cors.add(route)
        except ImportError:
            print("Warning: aiohttp-cors not installed. CORS will not be enabled.")
            print("Install with: pip install aiohttp-cors")

    return app


def main():
    """Main entry point to run the server."""
    app = create_app()

    # Get host and port from config
    host = CONFIG.server.host
    port = CONFIG.port

    # Run the server
    web.run_app(app, host=host, port=port)


if __name__ == '__main__':
    main()
