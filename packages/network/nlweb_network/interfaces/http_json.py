# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
HTTP JSON interface - Non-streaming HTTP responses.

Handles both GET and POST requests, collects all results,
and returns a single JSON response.
"""

import json
from typing import Dict, Any
from aiohttp import web
from .base import BaseInterface


class HTTPJSONInterface(BaseInterface):
    """
    HTTP interface that returns complete JSON responses (streaming=false).

    Supports both GET and POST methods:
    - GET: Parameters from query string
    - POST: Parameters from JSON body (takes precedence) or query string
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

    async def send_response(self, response: web.Response, data: Dict[str, Any]) -> None:
        """
        Collect response data (not sent immediately in non-streaming mode).

        Args:
            response: Not used in non-streaming mode
            data: Data from NLWeb handler
        """
        # Data is collected via create_collector_output_method
        # This method is not used in non-streaming mode
        pass

    async def finalize_response(self, response: web.Response) -> None:
        """
        Not used in non-streaming mode (response created and returned directly).

        Args:
            response: Not used
        """
        pass

    def build_json_response(self, responses: list) -> Dict[str, Any]:
        """
        Build final JSON response from collected outputs.

        Args:
            responses: List of response dicts from handler

        Returns:
            Complete JSON response dict
        """
        # Separate _meta and content items
        meta = {}
        content = []

        for response in responses:
            if '_meta' in response:
                # Merge meta information (first one wins for duplicates)
                for key, value in response['_meta'].items():
                    if key not in meta:
                        meta[key] = value
            if 'content' in response:
                # Collect all content items
                content.extend(response['content'])

        # Build final response
        result = {}
        if meta:
            result['_meta'] = meta
        if content:
            result['content'] = content

        return result

    async def handle_request(self, request: web.Request, handler_class) -> web.Response:
        """
        Handle complete HTTP request and return JSON response.

        Args:
            request: aiohttp Request object
            handler_class: NLWeb handler class to instantiate

        Returns:
            aiohttp JSON response
        """
        try:
            # Parse request
            query_params = await self.parse_request(request)

            # Create collector output method
            output_method = self.create_collector_output_method()

            # Create and run handler
            handler = handler_class(query_params, output_method)
            await handler.runQuery()

            # Build and return JSON response
            responses = self.get_collected_responses()
            result = self.build_json_response(responses)

            return web.json_response(result)

        except ValueError as e:
            return web.json_response(
                {"error": str(e), "_meta": {}},
                status=400
            )
        except Exception as e:
            return web.json_response(
                {"error": str(e), "_meta": {}},
                status=500
            )
