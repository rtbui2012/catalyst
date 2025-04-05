import os
import logging
from typing import List, Dict, Any, Optional
import tiktoken
from openai import AzureOpenAI

from .config import AgentConfig
from .llm_base import BaseLLM

class AzureOpenAILLM(BaseLLM):
    """Concrete implementation for Azure OpenAI."""

    def __init__(self, config: AgentConfig, logger: logging.Logger):
        """Initialize the Azure OpenAI client."""
        super().__init__(config, logger)
        self._initialize_client()
        self._initialize_tokenizer()

    def _initialize_client(self):
        """Initialize the Azure OpenAI client with configuration settings."""
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        # TODO: Add 'api_version' to AgentConfig schema if not already present
        api_version = getattr(self.config, 'api_version', None) or os.getenv("OPENAI_API_VERSION", "2024-02-15-preview")
        self._deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", self.config.model_name)

        if not api_key:
            self.logger.error("Azure OpenAI API key not found in environment variables")
            raise ValueError("Azure OpenAI API key is required")

        if not endpoint:
            self.logger.error("Azure OpenAI endpoint not found in environment variables")
            raise ValueError("Azure OpenAI endpoint is required")

        try:
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint
            )
            self.logger.info(f"Initialized Azure OpenAI client with endpoint: {endpoint} for deployment: {self._deployment_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            raise

    def _initialize_tokenizer(self):
        """Initialize the tokenizer for token counting."""
        try:
            # Use the base model name for tokenizer compatibility if available
            base_model_name = getattr(self.config, 'base_model_name', self.config.model_name)
            self._tokenizer = tiktoken.encoding_for_model(base_model_name)
            self.logger.info(f"Initialized tokenizer for base model: {base_model_name}")
        except Exception as e:
            self.logger.warning(f"Failed to initialize tokenizer for {self.config.model_name} (base: {base_model_name}): {e}. Token estimation might be inaccurate.")
            self._tokenizer = None

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Generate a chat completion using Azure OpenAI."""
        self.logger.debug(f"Sending completion request to Azure deployment: {self._deployment_name}")
        try:
            response = self.client.chat.completions.create(
                model=self._deployment_name, # Use deployment name here
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format
            )
            # Return the response object directly or convert to dict if needed by consumers
            # For now, returning the Pydantic model response
            return response.model_dump() # Convert to dict for consistent return type
        except Exception as e:
            self.logger.error(f"Azure OpenAI chat completion failed: {e}")
            raise # Re-raise the exception to be handled by the caller

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens using the initialized tokenizer."""
        if self._tokenizer:
            try:
                return len(self._tokenizer.encode(text))
            except Exception as e:
                self.logger.warning(f"Tokenizer encoding failed: {e}. Falling back to approximation.")
                # Fallback estimation (rough approximation)
                return len(text) // 4
        else:
            # Fallback estimation if tokenizer failed to initialize
            return len(text) // 4

    @property
    def model_name(self) -> str:
        """Return the deployment name used by this Azure LLM instance."""
        return self._deployment_name