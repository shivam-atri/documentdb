#!/usr/bin/env python3
"""Claude entrypoint for provider-neutral MCP server."""
from mcp_server import mcp

if __name__ == "__main__":
    mcp.run()
