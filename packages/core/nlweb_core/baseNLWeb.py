# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the base abstract class for all handlers.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""


from abc import ABC, abstractmethod
import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from nlweb_core.query_analysis.query_analysis import DefaultQueryAnalysisHandler, QueryAnalysisHandler, query_analysis_tree
from nlweb_core.utils import get_param as _get_param
from nlweb_core.protocol.models import Query, Context, Prefer, Meta, AskRequest
from nlweb_core.config import CONFIG
from nlweb_core.request_context import set_request_id, get_request_id

logger = logging.getLogger(__name__)

class NLWebHandler(ABC):

    def __init__(self, query_params, output_method):

        # Generate and set request ID for this handler instance
        self.request_id = set_request_id()
        # Sanitize query text for logging to prevent log injection
        query_text = query_params.get('query', {}).get('text', 'N/A')[:50]
        sanitized_query = query_text.replace('\n', '\\n').replace('\r', '\\r')
        logger.info(f"Initializing handler for query: {sanitized_query}")

        self.output_method = output_method
        self.query_params_raw = query_params  # Store raw params for conversation storage

        # Parse v0.54 request structure into protocol objects
        # Query object (required)
        query_dict = query_params.get('query', {})
        if not isinstance(query_dict, dict) or 'text' not in query_dict:
            raise ValueError("Invalid request: 'query' must be an object with 'text' field")
        self.query = Query(**query_dict)

        # Context object (optional)
        context_dict = query_params.get('context', {})
        self.context = Context(**context_dict) if context_dict else Context()

        # Prefer object (optional)
        prefer_dict = query_params.get('prefer', {})
        self.prefer = Prefer(**prefer_dict) if prefer_dict else Prefer()

        # Meta object (optional)
        meta_dict = query_params.get('meta', {})
        self.meta = Meta(**meta_dict) if meta_dict else Meta()

        # Extract mode from prefer.mode (comma-separated list like "list", "list,summarize", etc.)
        mode_str = self.prefer.mode or 'list'
        self.modes = [m.strip() for m in mode_str.split(',')]

        # Conversation tracking
        self.conversation_id = self._get_or_create_conversation_id()
        self.user_id = self._get_user_id()
        self.conversation_storage = None
        self._init_conversation_storage()

        self.return_value = None
        self._meta = {
            'version': '0.54',
            'response_type': 'Answer',
            'request_id': self.request_id  # Include request ID in response metadata
        }
    
    async def runQuery(self):
        # Send metadata first
        await self.send_meta()
        await self.prepare()
        await self.runQueryBody()
        await self.postResults()
        return self.return_value

    async def prepare(self):
        await self.decontextualizeQuery()
        query_analysis_handler = QueryAnalysisHandler(self)
        await query_analysis_handler.do()

    @abstractmethod
    async def runQueryBody(self):
        pass

    async def decontextualizeQuery(self):
        """
        Decontextualize the query using conversation context.
        Sets self.query.decontextualized_query with the processed query.
        """
        # Get context information from protocol objects
        prev_queries = self.context.prev or []
        context_text = self.context.text
        site = getattr(self.query, 'site', 'all') or 'all'

        # Build temporary params dict for query analysis handlers
        # (query analysis code still uses query_params dict structure)
        self.query_params = {
            "request.rawQuery": self.query.text,
            "request.site": site
        }

        if len(prev_queries) == 0 and context_text is None:
            # No context - use original query
            self.query.decontextualized_query = self.query.text
        elif len(prev_queries) > 0 and context_text is None:
            # Decontextualize using previous queries
            self.query_params["request.previousQueries"] = ", ".join(prev_queries)

            result = await DefaultQueryAnalysisHandler(self, prompt_ref="PrevQueryDecontextualizer", root_node=query_analysis_tree).do()

            if result and "decontextualized_query" in result:
                self.query.decontextualized_query = result["decontextualized_query"]
            else:
                self.query.decontextualized_query = self.query.text
        else:
            # Decontextualize using both prev queries and context text
            self.query_params["request.previousQueries"] = ", ".join(prev_queries) if prev_queries else ""
            self.query_params["request.context"] = context_text

            result = await DefaultQueryAnalysisHandler(self, prompt_ref="FullContextDecontextualizer", root_node=query_analysis_tree).do()
            if result and "decontextualized_query" in result:
                self.query.decontextualized_query = result["decontextualized_query"]
            else:
                self.query.decontextualized_query = self.query.text


    def set_meta_attribute(self, key, value):
        """Set a metadata attribute in the _meta object."""
        self._meta[key] = value

    async def send_meta(self):
        """Send the metadata object via the output method."""
        if self.output_method:
            await self.output_method({"_meta": self._meta})

    def _extract_text_from_dict(self, data):
        """Extract text fields from a dict or list of dicts."""
        text_parts = []

        def extract_from_item(item):
            if isinstance(item, dict):
                # Common text fields to extract
                for field in ['text', 'description', 'name', 'title', 'summary']:
                    if field in item and item[field]:
                        text_parts.append(str(item[field]))
            elif isinstance(item, str):
                text_parts.append(item)

        if isinstance(data, list):
            for item in data:
                extract_from_item(item)
        else:
            extract_from_item(data)

        return " ".join(text_parts)

    async def send_results(self, results: list):
        """
        Send v0.54 compliant results array.

        Args:
            results: List of result objects (dicts with @type, name, etc.)
        """
        if self.output_method:
            await self.output_method({"results": results})

    async def send_elicitation(self, text: str, questions: list):
        """
        Send an elicitation response.

        Args:
            text: Introductory text for the elicitation
            questions: List of question dicts with id, text, type, options
        """
        self._meta['response_type'] = 'Elicitation'
        await self.send_meta()
        if self.output_method:
            await self.output_method({
                "elicitation": {
                    "text": text,
                    "questions": questions
                }
            })

    async def send_promise(self, token: str, estimated_time: int = None):
        """
        Send a promise response.

        Args:
            token: Promise token for checking status
            estimated_time: Estimated time to completion in seconds (optional)
        """
        self._meta['response_type'] = 'Promise'
        await self.send_meta()
        if self.output_method:
            promise = {"token": token}
            if estimated_time is not None:
                promise["estimated_time"] = estimated_time
            await self.output_method({"promise": promise})

    async def send_failure(self, code: str, message: str):
        """
        Send a failure response.

        Args:
            code: Error code (e.g., NO_RESULTS, INTERNAL_ERROR)
            message: Error message
        """
        self._meta['response_type'] = 'Failure'
        await self.send_meta()
        if self.output_method:
            await self.output_method({
                "error": {
                    "code": code,
                    "message": message
                }
            })

    def get_param(self, param_name, param_type=str, default_value=None):
        """Get a parameter from query_params with type conversion."""
        return _get_param(self.query_params, param_name, param_type, default_value)
    
    async def postResults(self):
        """Hook for any post-processing after main query body."""
        pass

    # ============ Conversation Storage Methods ============

    def _get_or_create_conversation_id(self) -> str:
        """Get conversation_id from meta.session_context or create new one."""
        if (self.meta and
            self.meta.session_context and
            self.meta.session_context.conversation_id):
            return self.meta.session_context.conversation_id
        return str(uuid.uuid4())

    def _get_user_id(self) -> Optional[str]:
        """Extract user_id from meta.user if available."""
        if self.meta and hasattr(self.meta, 'user') and self.meta.user:
            # meta.user is expected to be an object with user identifier
            if isinstance(self.meta.user, dict):
                return self.meta.user.get('id') or self.meta.user.get('user_id')
            elif hasattr(self.meta.user, 'id'):
                return self.meta.user.id
        return None

    def _init_conversation_storage(self):
        """Initialize conversation storage if enabled."""
        # Get storage client from CONFIG (initialized when config was loaded)
        if hasattr(CONFIG, 'conversation_storage_client'):
            self.conversation_storage = CONFIG.conversation_storage_client
        else:
            self.conversation_storage = None

    async def save_conversation_turn(self):
        """Save the complete conversation turn (user request + assistant response)."""
        if not self.conversation_storage:
            return

        # Only save if meta.remember is explicitly set to True
        if not (self.meta and hasattr(self.meta, 'remember') and self.meta.remember):
            return

        # Don't save if no user_id (anonymous conversations)
        if not self.user_id:
            return

        try:
            from nlweb_core.conversation.models import ConversationMessage
            from nlweb_core.protocol.models import ResultObject

            # Build AskRequest from raw params
            request = AskRequest(**self.query_params_raw)

            # Get results if available
            results = None
            if hasattr(self, 'final_ranked_answers') and self.final_ranked_answers:
                # Convert result dicts to ResultObject models
                results = [ResultObject(**r) if isinstance(r, dict) else r for r in self.final_ranked_answers]

            message = ConversationMessage(
                message_id=str(uuid.uuid4()),
                conversation_id=self.conversation_id,
                timestamp=datetime.now(timezone.utc),
                request=request,
                results=results,
                metadata={
                    "user_id": self.user_id,
                    "site": getattr(self.query, 'site', None),
                    "response_format": self.prefer.response_format
                }
            )

            await self.conversation_storage.store_message(message)
        except Exception as e:
            # Don't fail the query if storage fails
            logger.error(f"Failed to save conversation turn: {e}", exc_info=True)