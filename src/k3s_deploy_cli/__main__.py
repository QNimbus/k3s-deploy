#!/usr/bin/env python3
"""
Main module entry point for running k3s-deploy as a module.

This allows the package to be executed with: python -m k3s_deploy_cli
"""

from .main import main

if __name__ == "__main__":
    main()
