"""Compatibility entry point for the REST-backed FastMCP server."""

from mcp_tools.server import mcp


if __name__ == "__main__":
    mcp.run()
