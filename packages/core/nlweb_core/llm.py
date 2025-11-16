# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
LLM provider interface and orchestration.

This module provides:
1. LLMProvider abstract base class that all LLM providers must implement
2. Orchestration functions for loading providers and routing requests

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.

"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from nlweb_core.config import CONFIG
import asyncio


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    This class defines the interface that all LLM providers must implement
    to ensure consistent behavior across different implementations.
    """

    @abstractmethod
    async def get_completion(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 30.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a completion request to the LLM provider and return the parsed response.

        Args:
            prompt: The text prompt to send to the LLM
            schema: JSON schema that the response should conform to
            model: The specific model to use (if None, use default from config)
            temperature: Controls randomness of the output (0-1)
            max_tokens: Maximum tokens in the generated response
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific arguments

        Returns:
            Parsed JSON response from the LLM

        Raises:
            TimeoutError: If the request times out
            ValueError: If the response cannot be parsed or request fails
        """
        pass

    @classmethod
    @abstractmethod
    def get_client(cls):
        """
        Get or initialize the client for this provider.
        Returns a client instance ready to make API calls.

        Returns:
            A client instance configured for the provider
        """
        pass

    @classmethod
    @abstractmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """
        Clean and parse the raw response content into a structured dict.

        Args:
            content: Raw response content from the LLM

        Returns:
            Parsed JSON as a Python dictionary

        Raises:
            ValueError: If the content doesn't contain valid JSON
        """
        pass

# Cache for loaded providers
_loaded_providers = {}

def init():
    """Initialize LLM providers based on configuration."""
    # Get all configured LLM endpoints
    for endpoint_name, endpoint_config in CONFIG.llm_endpoints.items():
        llm_type = endpoint_config.llm_type
        if llm_type and endpoint_name == CONFIG.preferred_llm_endpoint:
            try:
                # Use _get_provider which will load and cache the provider
                _get_provider(llm_type, endpoint_config)
            except Exception as e:
                pass


def _get_provider(llm_type: str, provider_config=None):
    """
    Lazily load and return the provider for the given LLM type.

    Args:
        llm_type: The type of LLM provider to load
        provider_config: Optional provider config with import_path and class_name

    Returns:
        The provider instance

    Raises:
        ValueError: If the LLM type is unknown
    """
    # Return cached provider if already loaded
    if llm_type in _loaded_providers:
        return _loaded_providers[llm_type]

    # Use config-driven dynamic import if available
    if provider_config and provider_config.import_path and provider_config.class_name:
        try:
            import_path = provider_config.import_path
            class_name = provider_config.class_name
            module = __import__(import_path, fromlist=[class_name])
            provider_class = getattr(module, class_name)
            # Instantiate if it's a class, or use directly if it's already an instance
            provider = provider_class() if callable(provider_class) else provider_class
            _loaded_providers[llm_type] = provider
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Failed to load provider for {llm_type}: {e}")
    else:
        raise ValueError(f"No import_path and class_name configured for LLM type: {llm_type}")

    return _loaded_providers[llm_type]

async def ask_llm(
    prompt: str,
    schema: Dict[str, Any],
    provider: Optional[str] = None,
    level: str = "low",
    timeout: int = 8,
    query_params: Optional[Dict[str, Any]] = None,
    max_length: int = 512
) -> Dict[str, Any]:
    """
    Route an LLM request to the specified endpoint, with dispatch based on llm_type.
    
    Args:
        prompt: The text prompt to send to the LLM
        schema: JSON schema that the response should conform to
        provider: The LLM endpoint to use (if None, use preferred endpoint from config)
        level: The model tier to use ('low' or 'high')
        timeout: Request timeout in seconds
        query_params: Optional query parameters for development mode provider override
        max_length: Maximum length of the response in tokens (default: 512)
        
    Returns:
        Parsed JSON response from the LLM
        
    Raises:
        ValueError: If the endpoint is unknown or response cannot be parsed
        TimeoutError: If the request times out
    """
    # Determine provider from parameter or config
    provider_name = provider or CONFIG.preferred_llm_endpoint

    if provider_name not in CONFIG.llm_endpoints:
        return {}

    # Get provider config using the helper method
    provider_config = CONFIG.get_llm_provider(provider_name)
    if not provider_config or not provider_config.models:
        return {}

    # Get llm_type for dispatch
    llm_type = provider_config.llm_type

    model_id = getattr(provider_config.models, level)

    # Initialize variables for exception handling
    llm_type_for_error = llm_type

    try:

        # Get the provider instance based on llm_type
        try:
            provider_instance = _get_provider(llm_type, provider_config)
        except ValueError as e:
            return {}

        # Simply call the provider's get_completion method without locking
        # Each provider should handle thread-safety internally
        result = await asyncio.wait_for(
            provider_instance.get_completion(prompt, schema, model=model_id, timeout=timeout, max_tokens=max_length),
            timeout=timeout
        )
        return result

    except asyncio.TimeoutError:
        return {}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {}


def get_available_providers() -> list:
    """
    Get a list of LLM providers that have their required API keys available.
    
    Returns:
        List of provider names that are available for use.
    """
    available_providers = []
    
    for provider_name, provider_config in CONFIG.llm_endpoints.items():
        # Check if provider config exists and has required fields
        if (provider_config and 
            hasattr(provider_config, 'api_key') and provider_config.api_key and 
            provider_config.api_key.strip() != "" and
            hasattr(provider_config, 'models') and provider_config.models and
            provider_config.models.high and provider_config.models.low):
            available_providers.append(provider_name)
    
    return available_providers
