"""
Example usage of the Agentic Core.

This script demonstrates how to use the AgentCore to process messages
and shows the basic functionality of the framework with Azure OpenAI integration.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add the parent directory to sys.path to allow importing the agentic module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import AgentCore, AgentConfig
from core.tools import Tool, ToolResult


# Load environment variables for Azure OpenAI
def load_environment():
    """Load environment variables from .env file."""
    # Try to load from .env file
    env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"Loaded environment variables from {env_file}")


# Example tool implementation
class CalculatorTool(Tool):
    """A simple calculator tool for demonstration purposes."""
    
    def __init__(self):
        """Initialize the calculator tool."""
        super().__init__(
            name="calculator",
            description="Performs basic arithmetic operations (add, subtract, multiply, divide)"
        )
    
    def execute(self, operation: str, a: float, b: float) -> ToolResult:
        """
        Execute the calculator operation.
        
        Args:
            operation: The operation to perform (add, subtract, multiply, divide)
            a: First number
            b: Second number
            
        Returns:
            Result of the calculation
        """
        try:
            if operation == "add":
                result = a + b
            elif operation == "subtract":
                result = a - b
            elif operation == "multiply":
                result = a * b
            elif operation == "divide":
                if b == 0:
                    return ToolResult.error_result("Division by zero is not allowed")
                result = a / b
            else:
                return ToolResult.error_result(f"Unknown operation: {operation}")
            
            return ToolResult.success_result(result)
        except Exception as e:
            return ToolResult.error_result(f"Error in calculator: {str(e)}")
    
    def get_schema(self) -> dict:
        """Get the schema for the calculator tool."""
        return {
            "parameters": {
                "operation": {
                    "type": "string", 
                    "description": "The operation to perform (add, subtract, multiply, divide)",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "required": True
                },
                "a": {
                    "type": "number",
                    "description": "First number (NOT operand1, use 'a' instead)",
                    "required": True
                },
                "b": {
                    "type": "number",
                    "description": "Second number (NOT operand2, use 'b' instead)",
                    "required": True
                }
            },
            "returns": {
                "type": "number",
                "description": "Result of the calculation"
            },
            "example": {
                "operation": "add",
                "a": 2,
                "b": 3
            }
        }


def main():
    """Run an example conversation with the AgentCore."""
    # Load environment variables for Azure OpenAI
    load_environment()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create agent configuration
    config = AgentConfig(
        model_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
        api_type="azure",
        verbose=True,
        planning_enabled=True,
        long_term_memory_enabled=True
    )
    
    # Create agent core
    agent = AgentCore(config)
    
    # Register example tool
    calculator_tool = CalculatorTool()
    agent.register_tool(calculator_tool)
    
    print("\n=== Agentic Core Example with Azure OpenAI ===\n")
    print("This example demonstrates a simple conversation with the AgentCore")
    print("powered by Azure OpenAI. The agent has a calculator tool.")
    print("Type 'exit' to end the conversation.\n")
    
    # Simulate a conversation
    while True:
        # Get user input
        user_message = input("You: ")
        
        if user_message.lower() in ('exit', 'quit', 'bye'):
            print("\nExiting conversation. Goodbye!")
            break
        
        # Process the message
        try:
            response = agent.process_message(user_message)
            
            # Display the response
            print(f"Agent: {response}\n")
            
            # Check if the agent can accomplish a task (for demonstration)
            if user_message.startswith("Can you"):
                assessment = agent.can_accomplish(user_message)
                print(f"Task assessment: {assessment['can_accomplish']}")
                print(f"Reason: {assessment['reason']}\n")
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            print("Please make sure your Azure OpenAI credentials are correct and the service is available.")


if __name__ == "__main__":
    main()