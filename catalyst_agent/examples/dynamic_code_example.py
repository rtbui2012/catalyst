#!/usr/bin/env python3
"""
Example demonstrating the use of AgentCore with the DynamicCodeExecutionTool.

This example shows how to:
1. Configure and initialize the AgentCore
2. Register the DynamicCodeExecutionTool
3. Process messages that involve dynamic code execution
"""

import os
import sys
from pathlib import Path

# Add the parent directory to sys.path to make imports work
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

from catalyst_agent.agent import AgentCore
from catalyst_agent.config import AgentConfig
from catalyst_agent.tools.code_execution import DynamicCodeExecutionTool
from dotenv import load_dotenv

# Load environment variables for Azure OpenAI
def load_environment():
    """Load environment variables from .env file."""
    # Try to load from .env file
    env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../', '.env'))
    if os.path.exists("../../.env"):
        load_dotenv(env_file)
        print(f"Loaded environment variables from {env_file}")
    else:
        print(f"No .env file found, {env_file}")

def main():
    load_environment()
    # Create configuration for the agent
    config = AgentConfig(
        planning_enabled=True,
        verbose=True,
        short_term_memory_capacity=10,
        long_term_memory_enabled=True,
        available_tools=["execute_python"]
    )
    
    # Initialize the agent core
    agent = AgentCore(config)
    
    # Register the DynamicCodeExecutionTool
    code_execution_tool = DynamicCodeExecutionTool(
        max_execution_time=60,
        allowed_imports=None  # Allow all imports for this example
    )
    agent.register_tool(code_execution_tool)
    
    print("=== Agent initialized with DynamicCodeExecutionTool ===")
    
    # Example 1: Basic code execution
    message1 = "Can you calculate the first 10 Fibonacci numbers for me?"
    print(f"\nUser: {message1}")
    response1 = agent.process_message(message1)
    print(f"Agent: {response1}")
    
    # Example 2: Code with data manipulation
    message2 = """
    I have a list of temperatures in Celsius: [0, 15, 30, 35, 40]
    Can you convert them to Fahrenheit and also calculate the average temperature in both units?
    """
    print(f"\nUser: {message2}")
    response2 = agent.process_message(message2)
    print(f"Agent: {response2}")
    
    # Example 3: More complex analysis
    message3 = """
    I need help analyzing this dataset of product sales:
    [
        {"product": "Laptop", "price": 1200, "units_sold": 50},
        {"product": "Phone", "price": 800, "units_sold": 100},
        {"product": "Tablet", "price": 300, "units_sold": 30},
        {"product": "Headphones", "price": 150, "units_sold": 200},
        {"product": "Monitor", "price": 400, "units_sold": 60}
    ]
    
    Can you find the total revenue, the product with the highest revenue, and create a bar chart of the revenues?
    """
    print(f"\nUser: {message3}")
    response3 = agent.process_message(message3)
    print(f"Agent: {response3}")
    
    print("\n=== Example of checking task capability ===")
    # Check if the agent can accomplish a task
    task = "Can you create a scatter plot showing the correlation between price and units sold?"
    capability = agent.can_accomplish(task)
    print(f"\nTask: {task}")
    print(f"Can accomplish: {capability['can_accomplish']}")
    print(f"Reason: {capability['reason']}")


if __name__ == "__main__":
    main()