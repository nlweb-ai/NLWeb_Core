# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
This file contains the abstract ranking handler class.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from nlweb_core.baseNLWeb import NLWebHandler
from nlweb_core.ranking import Ranking
import asyncio


class NLWebRankingHandler(NLWebHandler):
    """
    Abstract handler that performs retrieval and ranking.

    The retriever class should be initialized with the handler and have a do() method.
    """

    def __init__(self, query_params, output_method, retriever_class):
        """
        Initialize the ranking handler.

        Args:
            query_params: Query parameters dict
            output_method: Method to send output
            retriever_class: A class that will be initialized with the handler and has a do() method
        """
        super().__init__(query_params, output_method)
        self.retriever_class = retriever_class
        self.retrieved_items = []

        # Initialize connection and pre-check events for ranking
        self.connection_alive_event = asyncio.Event()
        self.connection_alive_event.set()  # Initially set as alive
        self.pre_checks_done_event = asyncio.Event()
        self.pre_checks_done_event.set()  # Set immediately since we don't do pre-checks in this simple handler

    async def runQueryBody(self):
        """
        Execute the query body by retrieving and ranking items.
        """
        # Initialize and run the retriever
        retriever = self.retriever_class(self)
        self.retrieved_items = await retriever.do()

        # Rank the retrieved items
        ranking = Ranking(self, self.retrieved_items)
        await ranking.do()

   