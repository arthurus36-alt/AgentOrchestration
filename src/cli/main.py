"""CLI entry point for the agent orchestrator."""

import argparse
import sys

from src.common.config import Config
from src.common.logging import configure_logging


def cli(args=None):
    parser = argparse.ArgumentParser(description="Agent Orchestrator CLI")
    parser.add_argument("--config", "-c", help="Path to config file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    # Fix for #6: Added choices validation for --output-mode
    parser.add_argument("--output-mode", "-o", choices=["json", "text", "yaml", "table"], default="text", help="Format of the output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    init_parser = subparsers.add_parser("init", help="Initialize a new project")
    init_parser.add_argument("name", help="Project name")

    deploy_parser = subparsers.add_parser("deploy", help="Deploy an agent")
    deploy_parser.add_argument("manifest", help="Path to agent manifest file")

    status_parser = subparsers.add_parser("status", help="Show agent status")
    status_parser.add_argument("--watch", "-w", action="store_true", help="Watch mode")

    logs_parser = subparsers.add_parser("logs", help="View agent logs")
    logs_parser.add_argument("agent_id", help="Agent ID")
    logs_parser.add_argument("--tail", "-t", type=int, default=50, help="Number of lines")

    parsed_args = parser.parse_args(args)

    if parsed_args.verbose:
        configure_logging("DEBUG")
    else:
        configure_logging("INFO")

    if parsed_args.command == "init":
        print(f"Initializing project: {parsed_args.name}")
    elif parsed_args.command == "deploy":
        print(f"Deploying agent from manifest: {parsed_args.manifest}")
    elif parsed_args.command == "status":
        print(f"Checking agent status... (Output mode: {parsed_args.output_mode})")
    elif parsed_args.command == "logs":
        print(f"Fetching logs for agent: {parsed_args.agent_id} (Output mode: {parsed_args.output_mode})")
    else:
        parser.print_help()
        if args is None:
            sys.exit(1)

    return parsed_args


if __name__ == "__main__":
    cli()
