"""
Base agent class for PropPulse Agentic RAG pipeline
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the PropPulse Agentic RAG pipeline.
    
    All agents must implement the process method which takes input data,
    performs agent-specific processing, and returns output data.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent with optional configuration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data and return output data.
        
        Args:
            input_data: Input data dictionary
            
        Returns:
            Dict[str, Any]: Output data dictionary
        """
        pass
    
    def validate_input(self, input_data: Dict[str, Any], required_keys: List[str]) -> bool:
        """
        Validate that input data contains all required keys.
        
        Args:
            input_data: Input data dictionary
            required_keys: List of required keys
            
        Returns:
            bool: True if input data is valid, False otherwise
        """
        return all(key in input_data for key in required_keys)
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key, with an optional default.
        
        Args:
            key: Configuration key
            default: Default value if key is not found
            
        Returns:
            Any: Configuration value
        """
        return self.config.get(key, default)
