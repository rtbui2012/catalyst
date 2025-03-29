#!/usr/bin/env python3
"""
Advanced example of using AgentCore with the DynamicCodeExecutionTool.

This example demonstrates:
1. More detailed interaction with the DynamicCodeExecutionTool
2. Accessing and inspecting execution results
3. Visualizing plan creation and execution
4. Providing additional context/variables to the code execution
"""

import os
import sys
import json
import time
from pathlib import Path
from pprint import pprint
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to sys.path to make imports work
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

from catalyst_agent.agent import AgentCore
from catalyst_agent.config import AgentConfig
from catalyst_agent.tools.code_execution import DynamicCodeExecutionTool
from catalyst_agent.tools import Tool, ToolResult
from catalyst_agent.planning import Plan


class CodeExecutionDebugger:
    """Helper class to debug and visualize code execution process"""
    
    def __init__(self, agent):
        self.agent = agent
        self.last_plan = None
    
    def print_plan(self, plan):
        """Print the plan in a readable format"""
        print("\n=== PLAN ===")
        print(f"Goal: {plan.goal}")
        print(f"Status: {plan.status.name}")
        
        for i, step in enumerate(plan.steps):
            print(f"\nStep {i+1}: {step.description}")
            print(f"  Tool: {step.tool_name or 'None'}")
            if step.tool_args:
                print(f"  Args: {json.dumps(step.tool_args, indent=2)}")
            print(f"  Status: {step.status.name}")
            
            if step.result:
                print(f"  Result: {type(step.result).__name__}")
                if isinstance(step.result, dict) and "stdout" in step.result:
                    print("  --- Output ---")
                    print(step.result.get("stdout", ""))
                    if step.result.get("stderr"):
                        print("  --- Errors ---")
                        print(step.result.get("stderr", ""))
            
            if step.error:
                print(f"  Error: {step.error}")
        print("=== END PLAN ===\n")
    
    def intercept_plan(self):
        """Monkey patch the planning engine to intercept plans"""
        original_create_plan = self.agent.planning_engine.create_plan
        original_execute_plan = self.agent.planning_engine.execute_plan
        
        def create_plan_wrapper(*args, **kwargs):
            plan = original_create_plan(*args, **kwargs)
            self.last_plan = plan
            print("Plan created!")
            return plan
        
        def execute_plan_wrapper(plan, *args, **kwargs):
            result = original_execute_plan(plan, *args, **kwargs)
            self.print_plan(plan)
            return result
        
        self.agent.planning_engine.create_plan = create_plan_wrapper
        self.agent.planning_engine.execute_plan = execute_plan_wrapper


def provide_data_context():
    """Provide some sample data for code execution contexts"""
    return {
        "sample_data": {
            "temperatures": [22.5, 25.3, 18.9, 31.2, 27.8],
            "sales": [
                {"quarter": "Q1", "amount": 12500},
                {"quarter": "Q2", "amount": 15800},
                {"quarter": "Q3", "amount": 14200},
                {"quarter": "Q4", "amount": 19500}
            ],
            "metrics": {
                "user_count": 5420,
                "active_users": 3250,
                "conversion_rate": 0.068
            }
        }
    }


def main():
    # Create configuration for the agent
    config = AgentConfig(
        planning_enabled=True,
        verbose=True,
        short_term_memory_capacity=15,
        long_term_memory_enabled=True,
        available_tools=["execute_python"]
    )
    
    # Initialize the agent core
    print("Initializing agent...")
    agent = AgentCore(config)
    
    # Set up the debugger
    debugger = CodeExecutionDebugger(agent)
    debugger.intercept_plan()
    
    # Register the DynamicCodeExecutionTool
    code_execution_tool = DynamicCodeExecutionTool(
        max_execution_time=60,
        allowed_imports=None  # Allow all imports for this example
    )
    agent.register_tool(code_execution_tool)
    
    print("=== Agent initialized with DynamicCodeExecutionTool ===")
    
    # Example 1: Executing code with provided context variables
    data_context = provide_data_context()
    
    message1 = """
    I need to analyze the sales data and create a chart. Can you help me?
    """
    
    print(f"\nUser: {message1}")
    
    # First, let's directly use the tool to demonstrate how it works
    print("\n=== Direct tool execution (bypassing the agent) ===")
    code_to_run = """
import matplotlib.pyplot as plt
import json

# Access the sales data provided in the context
sales = variables['sample_data']['sales']

# Extract quarters and amounts
quarters = [item['quarter'] for item in sales]
amounts = [item['amount'] for item in sales]

# Calculate total and average
total_sales = sum(amounts)
avg_sales = total_sales / len(amounts)

# Create a bar chart
plt.figure(figsize=(8, 5))
bars = plt.bar(quarters, amounts, color='skyblue')
plt.axhline(y=avg_sales, color='red', linestyle='--', label=f'Average: ${avg_sales:.2f}')
plt.xlabel('Quarter')
plt.ylabel('Sales Amount ($)')
plt.title('Quarterly Sales Performance')
plt.legend()

# Save the chart to a file instead of displaying it
plt.savefig('sales_chart.png')
plt.close()

# Print analysis
print(f"Total sales: ${total_sales}")
print(f"Average quarterly sales: ${avg_sales:.2f}")
print(f"Best performing quarter: {quarters[amounts.index(max(amounts))]}")
print(f"Chart saved as 'sales_chart.png'")

# Return a summary
return {
    'total': total_sales,
    'average': avg_sales,
    'best_quarter': quarters[amounts.index(max(amounts))],
    'chart_saved': 'sales_chart.png'
}
"""
    
    # Execute the tool directly
    result = code_execution_tool.execute(code_to_run, variables=data_context)
    
    if result.success:
        print("Code execution successful!")
        print(f"stdout: {result.data.get('stdout', '')}")
        if result.data.get('stderr'):
            print(f"stderr: {result.data.get('stderr', '')}")
        print("Return value:", result.data.get('return_value'))
    else:
        print(f"Code execution failed: {result.error}")
    
    # Now let's use the agent to handle the same request
    print("\n=== Now using the agent to process the request ===")
    
    # We need to modify the tools to accept our context
    original_execute = code_execution_tool.execute
    
    def execute_with_context(code, variables=None):
        # Merge variables with our data context
        merged_vars = data_context.copy()
        if variables:
            merged_vars.update(variables)
        return original_execute(code, merged_vars)
    
    # Replace the execution method temporarily
    code_execution_tool.execute = execute_with_context
    
    # Process the message with the agent
    response = agent.process_message(message1)
    print(f"Agent: {response}")
    
    # Restore the original method
    code_execution_tool.execute = original_execute
    
    # Example 2: Working with external libraries and error handling
    message2 = """
    Can you analyze and visualize the metrics data showing user_count, active_users and 
    calculate the activation rate (active_users/user_count)? 
    Then create a pie chart showing the proportion of active vs inactive users.
    """
    
    print(f"\nUser: {message2}")
    
    # Temporarily replace execute again
    code_execution_tool.execute = execute_with_context
    
    # Process the message
    response2 = agent.process_message(message2)
    print(f"Agent: {response2}")
    
    # Restore original method
    code_execution_tool.execute = original_execute
    
    print("\n=== Example complete ===")


if __name__ == "__main__":
    main()