# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
HTTP SSE interface - Streaming HTTP responses via Server-Sent Events.

Handles both GET and POST requests, streams results as they arrive
using the SSE (Server-Sent Events) protocol.
"""

import json
from typing import Dict, Any
from aiohttp import web
from .base import BaseInterface


class HTTPSSEInterface(BaseInterface):
    """
    HTTP interface that streams responses via Server-Sent Events (streaming=true).

    Supports both GET and POST methods:
    - GET: Parameters from query string
    - POST: Parameters from JSON body (takes precedence) or query string

    Streams each result immediately as it's generated.
    """

    async def parse_request(self, request: web.Request) -> Dict[str, Any]:
        """
        Parse HTTP request and extract query parameters.

        Args:
            request: aiohttp Request object

        Returns:
            Dict of query parameters

        Raises:
            ValueError: If 'query' parameter is missing
        """
        # Get query parameters from URL
        query_params = dict(request.query)

        # For POST requests, merge JSON body params (body takes precedence)
        if request.method == 'POST':
            try:
                body = await request.json()
                # Merge body params into query_params, with body taking precedence
                query_params = {**query_params, **body}
            except Exception:
                # If body parsing fails, just use query params
                pass

        # Validate required parameters
        if 'query' not in query_params:
            raise ValueError("Missing required parameter: query")

        return query_params

    async def send_response(self, response: web.StreamResponse, data: Dict[str, Any]) -> None:
        """
        Send data as Server-Sent Event.

        Args:
            response: aiohttp StreamResponse object
            data: Data from NLWeb handler (dict with _meta or content)
        """
        # Format as SSE: data: {json}\n\n
        event_data = f"data: {json.dumps(data)}\n\n"
        await response.write(event_data.encode('utf-8'))

    async def finalize_response(self, response: web.StreamResponse) -> None:
        """
        Close the SSE stream.

        Args:
            response: aiohttp StreamResponse object
        """
        await response.write_eof()

    async def handle_request(self, request: web.Request, handler_class) -> web.StreamResponse:
        """
        Handle HTTP request and stream SSE responses.

        Args:
            request: aiohttp Request object
            handler_class: NLWeb handler class to instantiate

        Returns:
            aiohttp StreamResponse
        """
        import sys
        try:
            # Parse request
            query_params = await self.parse_request(request)
            print(f"[DEBUG] Parsed query_params: {query_params}", file=sys.stderr)

            # Create SSE response
            response = web.StreamResponse(
                status=200,
                reason='OK',
                headers={
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                }
            )
            await response.prepare(request)

            # Create streaming output method
            output_method = self.create_output_method(response)

            # Create and run handler
            print(f"[DEBUG] Creating handler with class: {handler_class}", file=sys.stderr)
            handler = handler_class(query_params, output_method)
            print(f"[DEBUG] Running query...", file=sys.stderr)
            await handler.runQuery()
            print(f"[DEBUG] Query completed successfully", file=sys.stderr)

            # Finalize stream
            await self.finalize_response(response)

            return response

        except ValueError as e:
            print(f"[ERROR] ValueError: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            # For errors, return a single SSE event with error
            response = web.StreamResponse(
                status=200,  # SSE uses 200 even for errors
                reason='OK',
                headers={
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                }
            )
            await response.prepare(request)

            error_data = {
                "_meta": {
                    "nlweb/streaming_status": "error",
                    "error": str(e)
                }
            }
            event_data = f"data: {json.dumps(error_data)}\n\n"
            await response.write(event_data.encode('utf-8'))
            await response.write_eof()

            return response

        except Exception as e:
            print(f"[ERROR] Unexpected exception: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            # For unexpected errors
            response = web.StreamResponse(
                status=200,
                reason='OK',
                headers={
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                }
            )
            await response.prepare(request)

            error_data = {
                "_meta": {
                    "nlweb/streaming_status": "error",
                    "error": str(e)
                }
            }
            event_data = f"data: {json.dumps(error_data)}\n\n"
            await response.write(event_data.encode('utf-8'))
            await response.write_eof()

            return response
