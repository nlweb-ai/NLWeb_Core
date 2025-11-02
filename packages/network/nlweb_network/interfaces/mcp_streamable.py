# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
MCP StreamableHTTP interface - Model Context Protocol over HTTP.

Implements MCP protocol using JSON-RPC 2.0 over standard HTTP.
This is the recommended MCP transport for HTTP-based communication.
"""

import json
from typing import Dict, Any
from aiohttp import web
from .base import BaseInterface


class MCPStreamableInterface(BaseInterface):
    """
    MCP interface using StreamableHTTP transport (JSON-RPC 2.0 over HTTP).

    Handles MCP protocol methods:
    - initialize: Protocol handshake
    - tools/list: List available tools
    - tools/call: Execute tool calls (routes to NLWeb handlers)

    MCP calls default to non-streaming mode.
    """

    MCP_VERSION = "2024-11-05"
    SERVER_NAME = "nlweb-mcp-server"
    SERVER_VERSION = "0.5.0"

    async def parse_request(self, request: web.Request) -> Dict[str, Any]:
        """
        Parse MCP JSON-RPC 2.0 request.

        Args:
            request: aiohttp Request object with JSON-RPC body

        Returns:
            Dict containing 'method', 'params', 'id', and extracted 'query_params'

        Raises:
            ValueError: If request is invalid or malformed
        """
        try:
            body = await request.json()
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body")

        # MCP uses JSON-RPC 2.0 format
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        if not method:
            raise ValueError("Missing 'method' in JSON-RPC request")

        return {
            "method": method,
            "params": params,
            "id": request_id,
            "query_params": params.get("arguments", {}) if method == "tools/call" else {}
        }

    async def send_response(self, response: web.Response, data: Dict[str, Any]) -> None:
        """
        Not used for MCP StreamableHTTP (uses single JSON-RPC response).

        Args:
            response: Not used
            data: Not used
        """
        pass

    async def finalize_response(self, response: web.Response) -> None:
        """
        Not used for MCP StreamableHTTP.

        Args:
            response: Not used
        """
        pass

    def build_initialize_response(self, request_id: Any) -> Dict[str, Any]:
        """
        Build MCP initialize response.

        Args:
            request_id: JSON-RPC request ID

        Returns:
            JSON-RPC 2.0 response dict
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": self.MCP_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": self.SERVER_NAME,
                    "version": self.SERVER_VERSION
                }
            }
        }

    def build_tools_list_response(self, request_id: Any) -> Dict[str, Any]:
        """
        Build MCP tools/list response.

        Args:
            request_id: JSON-RPC request ID

        Returns:
            JSON-RPC 2.0 response dict with available tools
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "ask",
                        "description": "Search and answer natural language queries using NLWeb's vector database and LLM ranking",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Natural language query"
                                },
                                "site": {
                                    "type": "string",
                                    "description": "Target site identifier"
                                },
                                "num_results": {
                                    "type": "integer",
                                    "description": "Number of results to return"
                                },
                                "streaming": {
                                    "type": "boolean",
                                    "description": "Enable streaming response",
                                    "default": False
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
            }
        }

    def build_tool_call_response(self, request_id: Any, nlweb_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build MCP tools/call response from NLWeb result.

        Args:
            request_id: JSON-RPC request ID
            nlweb_result: Result from NLWeb handler

        Returns:
            JSON-RPC 2.0 response dict
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(nlweb_result, indent=2)
                    }
                ]
            }
        }

    def build_error_response(self, request_id: Any, code: int, message: str) -> Dict[str, Any]:
        """
        Build JSON-RPC 2.0 error response.

        Args:
            request_id: JSON-RPC request ID
            code: Error code (JSON-RPC standard codes)
            message: Error message

        Returns:
            JSON-RPC 2.0 error response dict
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }

    async def handle_request(self, request: web.Request, handler_class) -> web.Response:
        """
        Handle MCP JSON-RPC 2.0 request.

        Args:
            request: aiohttp Request object
            handler_class: NLWeb handler class to instantiate (for tools/call)

        Returns:
            aiohttp JSON response with JSON-RPC 2.0 format
        """
        request_id = None

        try:
            # Parse MCP request
            parsed = await self.parse_request(request)
            method = parsed["method"]
            params = parsed["params"]
            request_id = parsed["id"]

            # Handle initialize
            if method == "initialize":
                response = self.build_initialize_response(request_id)
                return web.json_response(response)

            # Handle tools/list
            elif method == "tools/list":
                response = self.build_tools_list_response(request_id)
                return web.json_response(response)

            # Handle tools/call
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                if tool_name != "ask":
                    response = self.build_error_response(
                        request_id,
                        -32602,
                        f"Unknown tool: {tool_name}"
                    )
                    return web.json_response(response)

                # MCP calls default to non-streaming
                if "streaming" not in arguments:
                    arguments["streaming"] = False

                query_params = arguments

                if 'query' not in query_params:
                    response = self.build_error_response(
                        request_id,
                        -32602,
                        "Missing required parameter: query"
                    )
                    return web.json_response(response)

                # Create collector output method
                output_method = self.create_collector_output_method()

                # Create and run handler
                handler = handler_class(query_params, output_method)
                await handler.runQuery()

                # Build NLWeb result from collected responses
                from .http_json import HTTPJSONInterface
                http_interface = HTTPJSONInterface()
                nlweb_result = http_interface.build_json_response(self.get_collected_responses())

                # Wrap in MCP response
                response = self.build_tool_call_response(request_id, nlweb_result)
                return web.json_response(response)

            else:
                response = self.build_error_response(
                    request_id,
                    -32601,
                    f"Method not found: {method}"
                )
                return web.json_response(response)

        except ValueError as e:
            response = self.build_error_response(
                request_id,
                -32700 if "JSON" in str(e) else -32602,
                str(e)
            )
            return web.json_response(response, status=400)

        except Exception as e:
            response = self.build_error_response(
                request_id,
                -32603,
                f"Internal error: {str(e)}"
            )
            return web.json_response(response, status=500)
