#!/bin/bash
# Script to run the Steve MCP server

# Set environment variable to indicate we're running for Claude Desktop
export CLAUDE_DESKTOP_MCP=1

# Load environment variables from .env file
if [ -f "/Users/alvin/Projects/steve-mcp/.env" ]; then
    source "/Users/alvin/Projects/steve-mcp/.env"
fi

# Use the Poetry virtual environment Python
# This ensures all dependencies are available
cd /Users/alvin/Projects/steve-mcp
/Users/alvin/Projects/steve-mcp/.venv/bin/python server.py
