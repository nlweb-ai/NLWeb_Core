# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the base abstract class for all handlers.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""


from abc import ABC, abstractmethod
import asyncio
from nlweb_core.query_analysis.query_analysis import DefaultQueryAnalysisHandler, QueryAnalysisHandler
from nlweb_core.utils import get_param as _get_param

class NLWebHandler(ABC):

    def __init__(self, query_params, output_method):

        self.output_method = output_method
        self.query_params = query_params
        self.query = self.get_param("query", str, "")
        self.query_params["raw_query"] = self.query
        self.return_value = None
        self._meta = {}
    
    async def runQuery(self):
        # Send metadata first
        self.set_meta_attribute("version", "0.5")
        await self.send_meta()

        await self.prepare()
        await self.runQueryBody()
        return self.return_value

    async def prepare(self):
        await self.decontextualizeQuery()
        query_analysis_handler = QueryAnalysisHandler(self)
        await query_analysis_handler.do()

    @abstractmethod
    async def runQueryBody(self):
        pass

    async def decontextualizeQuery(self):
        prev_queries = self.get_param("prev", list, [])
        context = self.get_param("context", str, None)

        if (len(prev_queries) == 0 and context is None):
            self.query_params["decontextualized_query"] = self.query
        elif (len(prev_queries) > 0 and context is None):
            DefaultQueryAnalysisHandler(self.nlweb_handler, prompt_ref="PrevQueryDecontextualizer").do()
            self.query_params["query"] = self.query_params["decontextualized_query"]
        else:
            DefaultQueryAnalysisHandler(self.nlweb_handler, prompt_ref="FullContextDecontextualizer").do()
            self.query_params["query"] = self.query_params["decontextualized_query"]
    
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

    async def send_answer(self, data):
        """
        Send an answer by constructing a content object.

        Args:
            data: A dict or list of dicts representing the resource data
        """
        # Extract text from the data
        text = self._extract_text_from_dict(data)

        # Construct the content array
        content = []

        # Add text item if we extracted any text
        if text:
            content.append({
                "type": "text",
                "text": text
            })

        # Add resource item
        content.append({
            "type": "resource",
            "resource": {
                "data": data
            }
        })

        # Send via output method
        if self.output_method:
            await self.output_method({"content": content})

    def get_param(self, param_name, param_type=str, default_value=None):
        """Get a parameter from query_params with type conversion."""
        return _get_param(self.query_params, param_name, param_type, default_value)
