"""
Package management tools for the Agentic Core.

This module provides tools for handling package dependencies,
including installing missing modules on-demand.
"""

import subprocess
import sys
import importlib
import pkg_resources
from typing import List, Dict, Any, Optional

from .base import Tool, ToolResult


class PackageInstallerTool(Tool):
    """Tool for installing Python packages using pip."""
    
    def __init__(self):
        """Initialize the package installer tool."""
        super().__init__(
            name="package_installer",
            description="Install Python packages using pip. Can check if packages are installed and install missing ones."
        )
    
    def execute(self, packages: List[str], upgrade: bool = False) -> ToolResult:
        """
        Install packages using pip.
        
        Args:
            packages: List of package names to install
            upgrade: Whether to upgrade the packages if already installed
            
        Returns:
            ToolResult with information about installed packages
        """
        if not packages:
            return ToolResult.error_result("No packages specified")
        
        # Check which packages need to be installed
        packages_to_install = []
        already_installed = []
        
        for package in packages:
            # Split package name from version if present
            if "==" in package:
                package_name = package.split("==")[0]
            elif ">=" in package:
                package_name = package.split(">=")[0]
            elif "<=" in package:
                package_name = package.split("<=")[0]
            else:
                package_name = package
                
            # Check if package is already installed
            try:
                if not upgrade:
                    importlib.import_module(package_name)
                    already_installed.append(package)
                    continue
            except ImportError:
                # Some packages have different import names than their PyPI names
                try:
                    pkg_resources.get_distribution(package_name)
                    if not upgrade:
                        already_installed.append(package)
                        continue
                except pkg_resources.DistributionNotFound:
                    pass
            
            packages_to_install.append(package)
        
        if not packages_to_install:
            return ToolResult.success_result({
                "message": "All packages are already installed",
                "installed": [],
                "already_installed": already_installed
            })
        
        # Install packages using pip
        try:
            cmd = [sys.executable, "-m", "pip", "install"]
            if upgrade:
                cmd.append("--upgrade")
            cmd.extend(packages_to_install)
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            return ToolResult.success_result({
                "message": "Packages installed successfully",
                "installed": packages_to_install,
                "already_installed": already_installed,
                "output": process.stdout
            })
        except subprocess.CalledProcessError as e:
            return ToolResult.error_result(
                f"Error installing packages: {e}\nOutput: {e.stdout}\nError: {e.stderr}"
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """Get a schema describing the tool's parameters."""
        return {
            "parameters": {
                "packages": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of package names to install",
                    "required": True
                },
                "upgrade": {
                    "type": "boolean",
                    "description": "Whether to upgrade the packages if already installed",
                    "required": False,
                    "default": False
                }
            },
            "returns": {
                "type": "object",
                "description": "Information about the installed packages"
            }
        }


def check_module_installed(module_name: str) -> bool:
    """
    Check if a Python module is installed.
    
    Args:
        module_name: Name of the module to check
        
    Returns:
        True if the module is installed, False otherwise
    """
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        # Some packages have different import names than their PyPI names
        try:
            pkg_resources.get_distribution(module_name)
            return True
        except pkg_resources.DistributionNotFound:
            return False