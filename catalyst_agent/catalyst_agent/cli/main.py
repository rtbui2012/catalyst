"""
Main CLI entry point for the Catalyst Agent.

This module provides the main command-line interface functionality
for interacting with the Catalyst Agent.
"""

import argparse
import logging
import os
import sys
from typing import List, Optional

from catalyst_agent import AgentCore, AgentConfig


def main(args: Optional[List[str]] = None) -> int:
    """ Main entry point for the CLI. """
    parser = argparse.ArgumentParser(description="Catalyst Agent CLI")
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Interactive mode parser
    interactive_parser = subparsers.add_parser("interactive", help="Start an interactive session")
    interactive_parser.add_argument("--model", default="gpt-4o", help="Model to use")
    interactive_parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    # Single query parser
    query_parser = subparsers.add_parser("query", help="Process a single query")
    query_parser.add_argument("text", help="Query text to process")
    query_parser.add_argument("--model", default="gpt-4o", help="Model to use")
    query_parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    # Parse arguments
    parsed_args = parser.parse_args(args)
    
    if not parsed_args.command:
        parser.print_help()
        return 1
    
    # Configure the agent
    config = AgentConfig(
        model_name=parsed_args.model,
        verbose=parsed_args.verbose
    )
    
    # Initialize the agent
    try:
        agent = AgentCore(config)
    except Exception as e:
        print(f"Error initializing agent: {e}")
        return 1
    
    # Execute the requested command
    if parsed_args.command == "interactive":
        return run_interactive_mode(agent)
    elif parsed_args.command == "query":
        return process_single_query(agent, parsed_args.text)
    
    return 0


def run_interactive_mode(agent: AgentCore) -> int:
    """
    Run the agent in interactive mode.
    
    Args:
        agent: Initialized agent instance
        
    Returns:
        Exit code
    """
    print("Catalyst Agent Interactive Mode")
    print("Type 'exit' or 'quit' to end the session")
    print()
    
    while True:
        try:
            # Get user input
            user_input = input("You: ")
            
            # Check for exit command
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
            
            # Process the message
            response = agent.process_message(user_input)
            
            # Display the response
            print(f"Agent: {response}")
            print()
            
        except KeyboardInterrupt:
            print("\nSession terminated by user")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    return 0


def process_single_query(agent: AgentCore, query: str) -> int:
    """
    Process a single query and print the response.
    
    Args:
        agent: Initialized agent instance
        query: Query text to process
        
    Returns:
        Exit code
    """
    try:
        # Process the query
        response = agent.process_message(query)
        
        # Print the response
        print(response)
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())