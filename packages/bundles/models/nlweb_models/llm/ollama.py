# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.

"""

import json
from ollama import AsyncClient
import os
from nlweb_core.config import CONFIG
import asyncio
import threading
import re
from typing import Dict, Any, Optional

from nlweb_core.llm import LLMProvider



class OllamaProvider(LLMProvider):
    """Implementation of LLMProvider for Ollama."""

    # Global client with thread-safe initialization
    _client_lock = threading.Lock()
    _client = None

    @classmethod
    def get_ollama_endpoint(cls) -> str:
        """Get Ollama endpoint from config"""
        provider_config = CONFIG.llm_endpoints.get("ollama")
        if provider_config and provider_config.endpoint:
            endpoint = provider_config.endpoint
            if endpoint:
                endpoint = endpoint.strip('"')
                return endpoint
        error_msg = "Ollama endpoint not found in config"
        raise ValueError(error_msg)

    @classmethod
    def get_client(cls) -> AsyncClient:
        """Get or create Ollama client"""
        with cls._client_lock:
            if cls._client is None:
                endpoint = cls.get_ollama_endpoint()

                if not all([endpoint]):
                    error_msg = "Missing required Ollama configuration"
                    raise ValueError(error_msg)

                try:
                    cls._client = AsyncClient(host=endpoint)
                except Exception as e:
                    raise RuntimeError("Failed to initialize Ollama client") from e

        return cls._client

    @classmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """Clean and parse Ollama response"""
        response_text = content.strip()
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}") + 1
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
        timeout: float = 60.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get completion from Ollama"""
        if model is None:
            # Get model from config if not provided
            provider_config = CONFIG.llm_endpoints.get("ollama")
            model = provider_config.models.high if provider_config else "llama3"


        client = self.get_client()
        system_prompt = f"""You are a helpful assistant that provides responses in JSON format.
Your response must be valid JSON that matches this schema: {json.dumps(schema)}
Only output the JSON object, no additional text or explanation."""

        try:
            response = await asyncio.wait_for(
                client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    model=model,
                    options={
                        "temperature": temperature,
                    },
                    format="json",  # Force JSON response
                ),
                timeout=timeout,
            )
            content = response.message.content


            result = self.clean_response(content)
            return result

        except asyncio.TimeoutError:
            return {}
        except Exception as e:
            raise


# Create a singleton instance
provider = OllamaProvider()

# For backwards compatibility
get_ollama_completion = provider.get_completion
