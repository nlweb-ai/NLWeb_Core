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


async def health_handler(request):
    """Simple health check endpoint."""
    return web.json_response({"status": "ok"})


async def ask_handler(request):
    """
    Handle /ask requests (both GET and POST).

    Routes to either HTTP SSE (streaming=true, default) or
    HTTP JSON (streaming=false) interface based on parameters.

    Expected parameters:
    - query: The natural language query (required)
    - site: Site to search (optional, defaults to "all")
    - num_results: Number of results to return (optional, defaults to 50)
    - db: Database endpoint to use (optional)
    - streaming: Whether to use SSE streaming (optional, defaults to true)

    Returns:
    - If streaming=false: JSON response with the complete NLWeb answer
    - Otherwise: Server-Sent Events stream
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

    # Check streaming parameter (default: true)
    streaming = get_param(query_params, "streaming", bool, True)

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


def create_app():
    """Create and configure the aiohttp application."""
    app = web.Application()

    # Add HTTP routes
    app.router.add_get('/ask', ask_handler)
    app.router.add_post('/ask', ask_handler)
    app.router.add_get('/health', health_handler)

    # Add MCP routes
    app.router.add_post('/mcp', mcp_handler)  # MCP StreamableHTTP (JSON-RPC over HTTP)
    app.router.add_get('/mcp-sse', mcp_sse_handler)  # MCP over SSE (streaming)
    app.router.add_post('/mcp-sse', mcp_sse_handler)  # MCP over SSE (streaming)

    # Add A2A routes
    app.router.add_post('/a2a', a2a_handler)  # A2A StreamableHTTP (JSON-RPC over HTTP)
    app.router.add_get('/a2a-sse', a2a_sse_handler)  # A2A over SSE (streaming)
    app.router.add_post('/a2a-sse', a2a_sse_handler)  # A2A over SSE (streaming)

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
