# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Simple aiohttp server for NLWeb /ask queries.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import json
import asyncio
from aiohttp import web
from nlweb_core.NLWebVectorDBRankingHandler import NLWebVectorDBRankingHandler
from nlweb_core.config import CONFIG
from nlweb_core.utils import get_param
from pydantic import ValidationError
from nlweb_core.protocol import AskRequest, AskResponse, ResponseMeta


async def ask_handler(request):
    """
    Handle /ask requests (both GET and POST).

    For GET requests:
    - All parameters come from query string

    For POST requests:
    - Parameters can come from JSON body or query string
    - JSON body takes precedence over query string

    Expected parameters:
    - query: The natural language query (required)
    - site: Site to search (optional, defaults to "all")
    - num_results: Number of results to return (optional, defaults to 10)
    - db: Database endpoint to use (optional)
    - streaming: Whether to use SSE streaming (optional, defaults to true)

    Returns:
    - If streaming=false: JSON response with the complete NLWeb answer
    - Otherwise: Server-Sent Events stream
    """
    try:
        # Get query parameters from URL
        query_params = dict(request.query)

        # For POST requests, merge JSON body params (body takes precedence)
        if request.method == 'POST':
            try:
                body = await request.json()
                # Merge body params into query_params, with body taking precedence
                query_params = {**query_params, **body}
            except Exception as e:
                # If body parsing fails, just use query params
                pass

        # Print the request
        print(f"\n=== Incoming Request ===")
        print(f"Method: {request.method}")
        print(f"Path: {request.path}")
        print(f"Query params: {query_params}")


        # Validate required parameters using protocol model 'AskRequest' fields
        ask_request_fields = {
            k: v for k, v in query_params.items()
            if k in ['query', 'prev', 'context', 'mode', 'site', 'streaming', 'response_format']
        }

        try:
            ask_request = AskRequest(**ask_request_fields)
            print(f" Request validate: {ask_request.model_dump()}")
        except ValidationError as e:
                print(f" Validation error: {e}")
                return web.json_response(
                    {
                        "error": "Invalid request parameters",
                        "details": e.errors(),
                        "_meta": {"version": "0.5"}
                    },
                    status=400
                )
        
        print(f"========================\n")      

        # Check streaming parameter
        streaming = get_param(query_params, "streaming", bool, True)

        if not streaming:
            # Non-streaming mode: collect all responses and return JSON
            return await handle_non_streaming(query_params, ask_request)
        else:
            # Streaming mode: use SSE
            return await handle_streaming(request, query_params, ask_request)

    except Exception as e:
        return web.json_response(
            {
                "error": str(e),
                "_meta": {}
            },
            status=500
        )


async def handle_non_streaming(query_params, ask_request: AskRequest):
    """
    Handle non-streaming request, return complete JSON response.
    
    Args:
        query_params: Full params dict (includes non-protocol fields like num_results, db)
        ask_request: Validated AskRequest model from protocol
    """
    responses = []

    async def output_method(data):
        """Callback to collect output from handler."""
        responses.append(data)

    # Create and run the handler
    handler = NLWebVectorDBRankingHandler(query_params, output_method)
    await handler.runQuery()

    # Build the response with _meta
    response = {
        "_meta": {"version": "0.5"}
    }

    # Combine all responses
    for resp in responses:
        if "_meta" in resp:
            response["_meta"].update(resp["_meta"])
        if "content" in resp:
            if "content" not in response:
                response["content"] = []
            response["content"].extend(resp["content"])

    # Ensure content exists
    if "content" not in response:
        response["content"] = []

    return web.json_response(response)


async def handle_streaming(request, query_params, ask_request: AskRequest):
    """
    Handle streaming request using Server-Sent Events.
    
    Args:
        request: aiohttp request object
        query_params: Full params dict (includes non-protocol fields)
        ask_request: Validated AskRequest model from protocol
    """
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'

    await response.prepare(request)

    async def output_method(data):
        """Callback to stream output via SSE."""
        try:
            # Format as SSE
            event_data = f"data: {json.dumps(data)}\n\n"
            await response.write(event_data.encode('utf-8'))
        except Exception as e:
            print(f"Error writing to stream: {e}")

    try:
        # Create and run the handler
        handler = NLWebVectorDBRankingHandler(query_params, output_method)
        await handler.runQuery()

        # Send completion event
        completion = {
            "_meta": {
                "version": "0.5",
                "nlweb/streaming_status": "finished"
            }
        }
        event_data = f"data: {json.dumps(completion)}\n\n"
        await response.write(event_data.encode('utf-8'))

    except Exception as e:
        # Send error event
        error_data = {
            "_meta": {
                "version": "0.5",
                "nlweb/streaming_status": "error",
                "error": str(e)
            }
        }
        event_data = f"data: {json.dumps(error_data)}\n\n"
        await response.write(event_data.encode('utf-8'))

    await response.write_eof()
    return response


async def health_handler(request):
    """Simple health check endpoint."""
    return web.json_response({"status": "ok"})


async def mcp_handler(request):
    """
    MCP protocol endpoint - handles JSON-RPC 2.0 requests for MCP.

    Supports StreamableHttp transport (recommended) via POST requests.
    """
    # Handle POST request for StreamableHttp/JSON-RPC
    try:
        body = await request.json()

        # MCP uses JSON-RPC 2.0 format
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        # Handle initialize request
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "nlweb-mcp-server",
                        "version": "0.5.0"
                    }
                }
            }
            return web.json_response(response)

        # Handle tools/list request
        elif method == "tools/list":
            #Generate schema from AskRequest protocol model
            ask_schema = AskRequest.model_json_schema()

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "ask",
                            "description": "Search and answer natural language queries using NLWeb's vector database and LLM ranking",
                            "inputSchema": ask_schema
                        }
                    ]
                }
            }
            return web.json_response(response)

        # Handle tools/call request
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name != "ask":
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Unknown tool: {tool_name}"
                    }
                })

            # MCP calls should default to non-streaming
            if "streaming" not in arguments:
                arguments["streaming"] = False

            # Route to the ask handler
            query_params = arguments

            try: 
                ask_request = AskRequest(**arguments)
            except ValidationError as e:    
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid parameters",
                        "data": e.errors()
                    }
                })

            # Execute the query
            result_response = await handle_non_streaming(arguments, ask_request)

            # Extract the JSON from the response
            result_json = json.loads(result_response.body)

            # Return MCP response
            mcp_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result_json, indent=2)
                        }
                    ]
                }
            }
            return web.json_response(mcp_response)

        else:
            return web.json_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            })

    except json.JSONDecodeError:
        return web.json_response({
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error"
            }
        }, status=400)
    except Exception as e:
        return web.json_response({
            "jsonrpc": "2.0",
            "id": request_id if 'request_id' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }, status=500)


def create_app():
    """Create and configure the aiohttp application."""
    app = web.Application()

    # Add routes - support both GET and POST for /ask
    app.router.add_get('/ask', ask_handler)
    app.router.add_post('/ask', ask_handler)
    app.router.add_get('/health', health_handler)

    # MCP endpoint (JSON-RPC 2.0) - support both POST and GET (for SSE)
    app.router.add_get('/mcp', mcp_handler)
    app.router.add_post('/mcp', mcp_handler)

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

    print(f"Starting NLWeb server on http://{host}:{port}")
    print(f" Using protocol validation from nlweb_core.protocol")
    print(f"\nEndpoints:")
    print(f"  - GET/POST /ask")
    print(f"    Protocol parameters (validated):")
    print(f"      - query=<your query> (required)")
    print(f"      - mode=list|summary (optional)")
    print(f"      - site=<site_name> (optional)")
    print(f"      - streaming=<true|false> (optional)")
    print(f"      - prev=<previous queries as array> (optional)")
    print(f"      - context=<additional context> (optional)")
    print(f"      - response_format=<format preferences> (optional)")
    print(f"    Additional parameters (passed through):")
    print(f"      - num_results=<number> (optional)")
    print(f"      - num_start=<starting index> (optional)")
    print(f"      - db=<endpoint_name> (optional)")
    print(f"  - GET /health")
    print(f"  - POST /mcp - MCP protocol endpoint (JSON-RPC 2.0)")
    print(f"\nExamples:")
    print(f"  GET  - http://{host}:{port}/ask?query=best+pizza+restaurants&mode=list")
    print(f"  POST - curl -X POST http://{host}:{port}/ask -H 'Content-Type: application/json' -d '{{\"query\": \"best pizza\", \"mode\": \"summary\"}}'")    
    print(f"\nMCP Inspector:")
    print(f"  npx @modelcontextprotocol/inspector http://{host}:{port}/mcp")

    # Run the server
    web.run_app(app, host=host, port=port)


if __name__ == '__main__':
    main()
