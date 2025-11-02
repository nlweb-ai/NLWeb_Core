# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Shopify MCP Client - Interface for Shopify MCP (Model Context Protocol) operations.
This client enables search via MCP endpoints provided by Shopify sites.
"""

import os
import json
import aiohttp
import asyncio
from typing import List, Dict, Optional, Any, Union

from nlweb_core.config import CONFIG
from nlweb_core.retriever import VectorDBClientInterface


# Cache for MCP call results
# Key: (site, query), Value: list of results
_mcp_results_cache = {}


class ShopifyMCPClient(VectorDBClientInterface):
    """
    Client for Shopify MCP operations, providing search functionality via MCP endpoints.
    Currently supports search_shop_catalog method with USD currency and 50 results by default.
    """
    
    def __init__(self, endpoint_name: Optional[str] = None):
        """
        Initialize the Shopify MCP client.
        
        Args:
            endpoint_name: Name of the endpoint configuration in config_retrieval.yaml
        """
        super().__init__()  # Initialize the base class with caching
        self.endpoint_name = endpoint_name
    
    async def can_handle_query(self, site: Union[str, List[str]], **kwargs) -> bool:
        """
        Check if this Shopify MCP client can handle a query for the given site(s).
        Returns True if the site contains 'shopify' in the domain or is in the cached sites list.
        """
        # Convert site to list for uniform handling
        sites_to_check = [site] if isinstance(site, str) else site
        
        # Check if any site contains 'shopify' in the domain
        for site_name in sites_to_check:
            if 'shopify' in site_name.lower():
                return True
        
        # Fall back to the default implementation
        return await super().can_handle_query(site, **kwargs)
    
    async def search(self, query: str, site: Union[str, List[str]],
                    num_results: int = 50, query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        """
        Search using the MCP search_shop_catalog method.
        
        Args:
            query: The search query string
            site: Site identifier or list of sites
            num_results: Maximum number of results to return
            **kwargs: Additional parameters (including optional 'handler')
            
        Returns:
            List of search results formatted as [url, schema_json, name, site]
        """
        # Handle site parameter
        if isinstance(site, list):
            site = site[0] if site else None
        
        print(f"[SHOPIFY_MCP] search() called with query='{query}', site='{site}', num_results={num_results}")
        
        if not site:
            return []
        
        # Check if we have pre-computed rewritten queries from the handler
        handler = kwargs.get('handler')
        
        # Wait for rewritten_queries to be available if handler exists
        if handler:
            max_wait = 10  # Maximum wait time in seconds
            wait_interval = 0.1  # Check every 100ms
            waited = 0
            
            while not hasattr(handler, 'rewritten_queries') and waited < max_wait:
                await asyncio.sleep(wait_interval)
                waited += wait_interval
            
            if waited >= max_wait:
                pass

        rewritten_queries = getattr(handler, 'rewritten_queries', None) if handler else None
        
        # Use rewritten queries if available and multiple queries exist
        if rewritten_queries and len(rewritten_queries) > 1:
            print(f"[SHOPIFY_MCP] Original query: '{query}'")
            print(f"[SHOPIFY_MCP] Using {len(rewritten_queries)} rewritten queries: {rewritten_queries}")

            # Calculate results per query to maintain total count
            results_per_query = max(1, num_results // len(rewritten_queries))
            remainder = num_results % len(rewritten_queries)
            
            # Execute searches for each rewritten query in parallel
            tasks = []
            for i, rewritten_query in enumerate(rewritten_queries):
                # Add remainder to first queries
                query_results = results_per_query + (1 if i < remainder else 0)
                # Create a task for each rewritten query
                task = asyncio.create_task(
                    self._search_single_query(rewritten_query, site, query_results)
                )
                tasks.append(task)
            
            # Execute all searches in parallel
            all_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results, filtering out errors
            combined_results = []
            for i, result in enumerate(all_results):
                if isinstance(result, Exception):
                    pass
                elif result:
                    combined_results.extend(result)
            
            # Limit to requested number of results
            return combined_results[:num_results]
        
        # No rewritten queries - use original query
        result = await self._search_single_query(query, site, num_results)
        return result
    
    async def _search_single_query(self, query: str, site: str, num_results: int) -> List[List[str]]:
        """
        Internal method to search with a single query.

        Args:
            query: The search query string
            site: Site identifier
            num_results: Maximum number of results to return

        Returns:
            List of search results formatted as [url, schema_json, name, site]
        """
        # Check cache first
        cache_key = (site, query)
        if cache_key in _mcp_results_cache:
            cached_results = _mcp_results_cache[cache_key]
            print(f"[SHOPIFY_MCP] Query '{query}' to {site}: {len(cached_results)} results (cached)")
            return cached_results[:num_results]


        # Construct the MCP endpoint URL based on the site
        endpoint = f"https://{site}/api/mcp"
        
        # Prepare the MCP request
        mcp_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "search_shop_catalog",
                "arguments": {
                    "query": query,
                    "context": f"User is searching for: {query}",
                    "limit": 50,
                    "country": "US",
                    "language": "EN"
                }
            },
            "id": 1
        }
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                
                async with session.post(
                    endpoint,
                    json=mcp_request,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status != 200:
                        return []
                    
                    # Check content type (but be lenient since some servers misconfigure this)
                    content_type = response.headers.get('Content-Type', '')
                    
                    # Try to parse as JSON regardless of content type
                    # Some Shopify MCP endpoints incorrectly return text/html for JSON responses
                    try:
                        result = await response.json(content_type=None)  # Force JSON parsing
                    except Exception as json_error:
                        # If JSON parsing fails, then it's really not JSON
                        text = await response.text()
                        print(f"Failed to parse response as JSON. Content-Type: {content_type}")
                        return []
                    
                    # Check for JSON-RPC error
                    if 'error' in result:
                        return []
                    
                    # Extract search results
                    # Handle different response formats
                    mcp_result = result.get('result', {})
                    
                    # Check if result is wrapped in content array (some MCP implementations do this)
                    if 'content' in mcp_result and isinstance(mcp_result['content'], list):
                        for content_item in mcp_result['content']:
                            if content_item.get('type') == 'text' and 'text' in content_item:
                                try:
                                    # Parse the text as JSON
                                    search_data = json.loads(content_item['text'])
                                    formatted = self._format_results(search_data, site)
                                    # Cache the results
                                    _mcp_results_cache[cache_key] = formatted
                                    # Print query and results on one line
                                    print(f"[SHOPIFY_MCP] Query '{query}' to {site}: {len(formatted)} results")
                                    return formatted
                                except json.JSONDecodeError:
                                    pass

                    # Otherwise try direct format
                    formatted = self._format_results(mcp_result, site)

                    # Cache the results
                    _mcp_results_cache[cache_key] = formatted

                    # Print query and results on one line
                    print(f"[SHOPIFY_MCP] Query '{query}' to {site}: {len(formatted)} results")

                    return formatted
                    
        except asyncio.TimeoutError:
            print(f"[SHOPIFY_MCP] Query '{query}' to {site}: 0 results (timeout)")
            return []
        except Exception as e:
            print(f"[SHOPIFY_MCP] Query '{query}' to {site}: 0 results (error: {str(e)})")
            return []
    
    def _format_results(self, mcp_result: Dict, site: str) -> List[List[str]]:
        """
        Format MCP search results into the expected format for NLWeb.
        
        Args:
            mcp_result: Raw result from MCP search_shop_catalog
            site: The site name/domain
            
        Returns:
            List of formatted search results as [url, schema_json, name, site]
        """
        formatted_results = []
        
        try:
            # Extract products from the MCP response
            products = mcp_result.get('products', [])
            
            for product in products:
                # Start with basic schema.org structure
                schema_object = {
                    '@context': 'https://schema.org',
                    '@type': 'Product'
                }
                
                # Copy all fields from the product, mapping field names as needed
                field_mappings = {
                    'title': 'name',
                    'product_id': 'productID',
                    'product_type': 'category',
                    'vendor': 'brand',
                    'price_range': 'offers',
                    'image_url': 'image',
                    'image_alt_text': 'imageAltText'
                }
                
                # Copy all fields from product to schema_object
                for key, value in product.items():
                    if value is not None and value != '':
                        # Use mapped name if available, otherwise use original key
                        schema_key = field_mappings.get(key, key)
                        
                        # Special handling for certain fields
                        if key == 'vendor' and value:
                            # Format vendor as Brand object
                            schema_object[schema_key] = {
                                '@type': 'Brand',
                                'name': value
                            }
                        elif key == 'price_range' and value:
                            # Format price_range as AggregateOffer
                            schema_object[schema_key] = {
                                '@type': 'AggregateOffer',
                                'priceCurrency': value.get('currency', 'USD'),
                                'lowPrice': float(value.get('min', '0')) if value.get('min') else 0,
                                'highPrice': float(value.get('max', '0')) if value.get('max') else 0
                            }
                        elif key == 'variants' and value and len(value) > 1:
                            # If multiple variants, create individual offers
                            offers_list = []
                            for variant in value:
                                offer = {'@type': 'Offer'}
                                # Copy all variant fields
                                for v_key, v_value in variant.items():
                                    if v_value is not None and v_value != '':
                                        offer[v_key] = v_value
                                offers_list.append(offer)
                            
                            # Override the price_range offer with individual offers
                            if offers_list:
                                schema_object['offers'] = offers_list
                        else:
                            # Copy field as-is
                            schema_object[schema_key] = value
                
                # Format as expected by NLWeb: [url, schema_json, name, site]
                formatted_result = [
                    product.get('url', ''),  # url
                    json.dumps(schema_object),  # schema_json
                    product.get('title', ''),  # name
                    site  # site
                ]
                
                formatted_results.append(formatted_result)
                
        except Exception as e:
            pass

        return formatted_results
    
    def _extract_price(self, product: Dict) -> str:
        """
        Extract price information from product data.
        
        Args:
            product: Product data from MCP
            
        Returns:
            Price string or empty string if not available
        """
        try:
            price_range = product.get('priceRange', {})
            min_price = price_range.get('minVariantPrice', {})
            if min_price:
                amount = min_price.get('amount', '')
                currency = min_price.get('currencyCode', 'USD')
                return f"{amount} {currency}"
        except:
            pass
        return ''
