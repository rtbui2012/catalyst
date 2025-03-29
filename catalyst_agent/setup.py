#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

# Get the long description from the README file
with open(os.path.join(os.path.dirname(__file__), "README.md"), encoding="utf-8") as f:
    long_description = f.read()

# Get package requirements
with open(os.path.join(os.path.dirname(__file__), 
                      "catalyst_agent/requirements.txt"), encoding="utf-8") as f:
    requirements = f.read().splitlines()

setup(
    name="catalyst-agent",
    version="0.1.0",
    description="Catalyst Agent - An AI agent toolkit with multiple capabilities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Catalyst Team",
    author_email="info@catalyst-ai.org",
    url="https://github.com/catalyst-team/catalyst-agent",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    keywords="ai, agent, llm, ai-agent, tools",
)