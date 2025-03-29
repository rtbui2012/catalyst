"""
Dynamic Python code execution tool example.

This example demonstrates how to use the DynamicCodeExecutionTool
in an agent-based workflow to dynamically generate and execute Python code.
"""

import os
import sys
import json
from typing import Dict, Any, List
from agentic.core.agent import Agent
from agentic.core.config import AgentConfig
from agentic.core.tools import ToolRegistry, DynamicCodeExecutionTool

# Configure the agent
config = AgentConfig(
    model_name="gpt-4",
    temperature=0.2,
    max_tokens=2000,
    verbose=True
)

# Create a tool registry
tool_registry = ToolRegistry()

# Register the dynamic code execution tool
code_execution_tool = DynamicCodeExecutionTool()
tool_registry.register_tool(code_execution_tool)

# Create an agent with the configured tools
agent = Agent(config, tool_registry)

# Example task for the agent to perform
task = """
Complete the following task step by step:
1. Retrieve current weather data for Seattle using the OpenWeatherMap API
2. Create a summary report of the weather forecast
3. Save the report to a file named 'seattle_weather_report.txt'
"""

# Example conversation with the agent about the task
response = agent.chat(task)
print(f"Agent response:\n{response}")

# Example of how this would work in a real scenario:
# The agent would:
# 1. Generate Python code for OpenWeatherMap API request
# 2. Execute that code using the DynamicCodeExecutionTool
# 3. Process the results to create the summary
# 4. Generate code to save the report to a file
# 5. Execute that code using the DynamicCodeExecutionTool again

# Example of what the generated code might look like:
example_code = """
import requests
import json
from datetime import datetime

# OpenWeatherMap API key would typically be passed as a variable in the real scenario
API_KEY = "YOUR_API_KEY"  # In a real system, this would come from environment variables or secrets
CITY = "Seattle"

# Make API request
url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric"
response = requests.get(url)
data = response.json()

# Process the data
if response.status_code == 200:
    weather_info = {
        "city": CITY,
        "temperature": data["main"]["temp"],
        "description": data["weather"][0]["description"],
        "humidity": data["main"]["humidity"],
        "wind_speed": data["wind"]["speed"],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Create a formatted report
    report = f'''Weather Report for {weather_info["city"]}
Time: {weather_info["time"]}
Temperature: {weather_info["temperature"]}°C
Conditions: {weather_info["description"]}
Humidity: {weather_info["humidity"]}%
Wind Speed: {weather_info["wind_speed"]} m/s
'''
    
    print(report)
    return weather_info
else:
    print(f"Error: Could not retrieve weather data. Status code: {response.status_code}")
    return None
"""

# To demonstrate what the tool execution might look like
print("\nExample code execution:")
print("Note: This would normally be executed by the agent dynamically")
result = code_execution_tool.execute(code=example_code.replace("YOUR_API_KEY", "DUMMY_KEY"))

if result.success:
    print("\nExecution result:")
    print(f"Output: {result.data['stdout']}")
    if result.data.get('stderr'):
        print(f"Errors/Warnings: {result.data['stderr']}")
    print(f"Return value: {result.data.get('return_value')}")
else:
    print(f"Execution failed: {result.error}")

# Example of saving report to file
save_file_code = """
report = \"\"\"Weather Report for Seattle
Time: 2025-03-28 12:00:00
Temperature: 12.5°C
Conditions: scattered clouds
Humidity: 65%
Wind Speed: 3.6 m/s
\"\"\"

with open('seattle_weather_report.txt', 'w') as f:
    f.write(report)

print("Weather report saved to seattle_weather_report.txt")
"""

print("\nExample file saving code execution:")
result = code_execution_tool.execute(code=save_file_code)

if result.success:
    print(f"Output: {result.data['stdout']}")
else:
    print(f"Execution failed: {result.error}")

# Check if the file was created
if os.path.exists('seattle_weather_report.txt'):
    print("\nCreated file contents:")
    with open('seattle_weather_report.txt', 'r') as f:
        print(f.read())