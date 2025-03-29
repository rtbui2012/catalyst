"""
Example demonstrating the package installer tool.

This example shows how to use the PackageInstallerTool to:
1. Check if packages are installed
2. Install missing packages
3. Update existing packages
"""

import sys
import os

# Add the parent directory to the path to import the core module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.tools import PackageInstallerTool, ToolRegistry

def main():
    # Create a tool registry and register the package installer tool
    registry = ToolRegistry()
    package_installer = PackageInstallerTool()
    registry.register_tool(package_installer)
    
    print("Catalyst Package Installer Example")
    print("=================================\n")
    
    # Example 1: Check and install a common package
    print("Example 1: Installing a single package")
    result = registry.execute_tool("package_installer", packages=["numpy"])
    if result.success:
        if result.data["installed"]:
            print(f"✅ Successfully installed: {', '.join(result.data['installed'])}")
        if result.data["already_installed"]:
            print(f"ℹ️ Already installed: {', '.join(result.data['already_installed'])}")
    else:
        print(f"❌ Error: {result.error}")
    print()
    
    # Example 2: Install multiple packages at once
    print("Example 2: Installing multiple packages")
    result = registry.execute_tool("package_installer", packages=["matplotlib", "pandas", "seaborn"])
    if result.success:
        if result.data["installed"]:
            print(f"✅ Successfully installed: {', '.join(result.data['installed'])}")
        if result.data["already_installed"]:
            print(f"ℹ️ Already installed: {', '.join(result.data['already_installed'])}")
    else:
        print(f"❌ Error: {result.error}")
    print()
    
    # Example 3: Upgrade existing packages
    print("Example 3: Upgrading existing packages")
    result = registry.execute_tool("package_installer", packages=["numpy"], upgrade=True)
    if result.success:
        if result.data["installed"]:
            print(f"✅ Successfully upgraded: {', '.join(result.data['installed'])}")
        else:
            print("ℹ️ No packages needed upgrading")
    else:
        print(f"❌ Error: {result.error}")
    print()
    
    # Example 4: Install a package with a specific version
    print("Example 4: Installing a specific version")
    result = registry.execute_tool("package_installer", packages=["requests==2.25.1"])
    if result.success:
        if result.data["installed"]:
            print(f"✅ Successfully installed: {', '.join(result.data['installed'])}")
        if result.data["already_installed"]:
            print(f"ℹ️ Already installed: {', '.join(result.data['already_installed'])}")
    else:
        print(f"❌ Error: {result.error}")

if __name__ == "__main__":
    main()