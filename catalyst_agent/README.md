# Catalyst Agent

An AI agent toolkit with multiple capabilities for advanced AI interactions.

## Overview

Catalyst Agent is a flexible and powerful framework for building AI agents with various capabilities including:

- Dynamic code execution
- Web search
- Web content fetching
- Image generation
- Package management
- Memory management
- Planning and reasoning

## Installation

You can install the package via pip:

```bash
pip install catalyst-agent
```

Or install from source:

```bash
git clone https://github.com/catalyst-team/catalyst-agent.git
cd catalyst-agent
pip install -e .
```

## Quick Start

```python
from catalyst_agent.agent import AgentCore, AgentConfig
from catalyst_agent.tools.code_execution import DynamicCodeExecutionTool

# Initialize the agent with a configuration
config = AgentConfig()
agent = AgentCore(config)

# Register the code execution tool
code_execution_tool = DynamicCodeExecutionTool()
agent.register_tool(code_execution_tool)

# Process a message
response = agent.process_message("Calculate the first 10 Fibonacci numbers")
print(response)
```

## Available Tools

- **DynamicCodeExecutionTool**: Execute Python code dynamically
- **WebSearchTool**: Search the web for information
- **WebFetchTool**: Retrieve and process web page content
- **ImageGenerationTool**: Generate images using DALL-E
- **PackageInstallerTool**: Install Python packages

## Examples

Check out the examples directory for detailed examples of how to use each tool and functionality:

- Basic code execution
- Advanced code execution with visualization
- Image generation
- Web search and content retrieval
- Package installation

## Configuration

You can configure the agent through the `AgentConfig` class:

```python
config = AgentConfig(
    planning_enabled=True,
    verbose=True,
    short_term_memory_capacity=15,
    long_term_memory_enabled=True,
    available_tools=["execute_python", "web_search", "image_generation"]
)
```

## Requirements

- Python 3.8+
- Dependencies listed in requirements.txt

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.