from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

# Assuming AgentConfig is used for configuration across LLMs,
# otherwise, a more generic config type might be needed.
from .config import AgentConfig

class BaseLLM(ABC):
    """Abstract base class for Language Model implementations."""

    @abstractmethod
    def __init__(self, config: AgentConfig, logger: logging.Logger):
        """Initialize the LLM client."""
        self.config = config
        self.logger = logger

    @abstractmethod
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a chat completion response.

        Args:
            messages: A list of message dictionaries (e.g., [{"role": "user", "content": "Hello"}]).
            temperature: The sampling temperature.
            max_tokens: The maximum number of tokens to generate.
            response_format: Optional format specification (e.g., {"type": "json_object"}).

        Returns:
            A dictionary representing the completion response structure,
            typically including 'choices' with 'message' and 'content'.
            Example (OpenAI-like):
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Response text"
                        },
                        # ... other choice info
                    }
                ],
                # ... other response metadata
            }

        Raises:
            Exception: If the API call fails.
        """
        pass

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a given text.

        Args:
            text: The text to estimate tokens for.

        Returns:
            The estimated number of tokens.
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the specific model name/identifier being used by this LLM instance."""
        pass