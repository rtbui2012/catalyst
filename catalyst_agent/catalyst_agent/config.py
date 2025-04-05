"""
Configuration for the Agentic Core.

This module defines configuration settings for the agentic AI system,
including default parameters, model settings, and operational modes.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class AgentConfig:
    """Configuration settings for the Agentic Core."""
    
    # Model configuration
    model_name: str = "gpt-4o"
    api_type: str = "azure"  # Deprecated? Provider logic now uses llm_provider
    llm_provider: str = "azure" # "azure" or "gemini"
    temperature: float = 0.7
    max_tokens: int = 1000
    # Agent behavior configuration
    planning_enabled: bool = True
    self_improvement_enabled: bool = False
    verbose: bool = False
    
    # Memory configuration
    short_term_memory_capacity: int = 10  # Number of recent interactions to keep
    long_term_memory_enabled: bool = True
    
    # Tool configuration
    available_tools: List[str] = field(default_factory=list)
    tool_discovery_enabled: bool = True
    
    # Blob storage configuration
    blob_storage_path: Optional[str] = "./"  # Path to blob storage for tools output

    # Additional custom parameters
    custom_parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format."""
        return {
            "model_name": self.model_name,
            "api_type": self.api_type, # Keep for potential backward compatibility?
            "llm_provider": self.llm_provider,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "planning_enabled": self.planning_enabled,
            "self_improvement_enabled": self.self_improvement_enabled,
            "verbose": self.verbose,
            "short_term_memory_capacity": self.short_term_memory_capacity,
            "long_term_memory_enabled": self.long_term_memory_enabled,
            "available_tools": self.available_tools,
            "tool_discovery_enabled": self.tool_discovery_enabled,
            "custom_parameters": self.custom_parameters,
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'AgentConfig':
        """Create configuration from dictionary."""
        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})