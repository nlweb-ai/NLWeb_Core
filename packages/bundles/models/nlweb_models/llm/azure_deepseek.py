# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
DeepSeek on Azure wrapper  

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.

"""

import json
from openai import AsyncAzureOpenAI
import os
from nlweb_core.config import CONFIG
import asyncio
import threading
import re
from typing import Dict, Any, Optional

from nlweb_core.llm import LLMProvider


class DeepSeekAzureProvider(LLMProvider):
    """Implementation of LLMProvider for DeepSeek on Azure."""
    
    # Global client with thread-safe initialization
    _client_lock = threading.Lock()
    _client = None

    @classmethod
    def get_azure_endpoint(cls) -> str:
        """Get DeepSeek Azure endpoint from config"""
        provider_config = CONFIG.llm_endpoints.get("deepseek_azure")
        if provider_config and provider_config.endpoint:
            endpoint = provider_config.endpoint
            if endpoint:
                endpoint = endpoint.strip('"')
                return endpoint
        return None

    @classmethod
    def get_api_key(cls) -> str:
        """Get DeepSeek Azure API key from config"""
        provider_config = CONFIG.llm_endpoints.get("deepseek_azure")
        if provider_config and provider_config.api_key:
            api_key = provider_config.api_key
            if api_key:
                api_key = api_key.strip('"')
                return api_key
        return None

    @classmethod
    def get_api_version(cls) -> str:
        """Get DeepSeek Azure API version from config"""
        provider_config = CONFIG.llm_endpoints.get("deepseek_azure")
        if provider_config and provider_config.api_version:
            return provider_config.api_version
        return None

    @classmethod
    def get_client(cls) -> AsyncAzureOpenAI:
        """Get or create DeepSeek Azure client"""
        with cls._client_lock:
            if cls._client is None:
                endpoint = cls.get_azure_endpoint()
                api_key = cls.get_api_key()
                api_version = cls.get_api_version()
                
                if not all([endpoint, api_key, api_version]):
                    error_msg = "Missing required DeepSeek Azure configuration"
                    raise ValueError(error_msg)
                    
                try:
                    cls._client = AsyncAzureOpenAI(
                        azure_endpoint=endpoint,
                        api_key=api_key,
                        api_version=api_version,
                        timeout=30.0
                    )
                except Exception as e:
                    return None
        
        return cls._client

    @classmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """Clean and parse DeepSeek response"""
        response_text = content.strip()
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        if start_idx == -1 or end_idx == 0:
            error_msg = "No valid JSON object found in response"
            return {}
        
        json_str = response_text[start_idx:end_idx]
        
        try:
            result = json.loads(json_str)
            return result
        except json.JSONDecodeError as e:
            return {}

    async def get_completion(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 8.0,
        **kwargs
    ) -> Dict[str, Any]:
        """Get completion from DeepSeek on Azure"""
        if model is None:
            # Get model from config if not provided
            provider_config = CONFIG.llm_endpoints.get("deepseek_azure")
            model = provider_config.models.high if provider_config else "deepseek-coder-33b"
        
        
        client = self.get_client()
        system_prompt = f"""You are an expert AI assistant that always provides responses in valid JSON format.
Your response must exactly match the following JSON schema: {json.dumps(schema)}
Only output the JSON object itself, with no markdown formatting, no explanations, and no additional text."""
        
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"}  # Force JSON response
                ),
                timeout=timeout
            )
            
            content = response.choices[0].message.content
            
            result = self.clean_response(content)
            return result
            
        except asyncio.TimeoutError:
            return {}
        except Exception as e:
            raise


# Create a singleton instance
provider = DeepSeekAzureProvider()

# For backwards compatibility
get_deepseek_completion = provider.get_completion