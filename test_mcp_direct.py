#!/usr/bin/env python3
"""
Test MCP Atlassian connection directly.
This helps diagnose if the MCP server is running and responding correctly.
"""

import asyncio
import json
import logging
from app.config import settings
from app.services.jira_mcp import _server_params, _call, _parse_jira_response

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def test_mcp_connection():
    """Test if MCP Atlassian server is reachable and working."""
    logger.info("=" * 60)
    logger.info("Testing MCP Atlassian Connection")
    logger.info("=" * 60)
    
    # Check settings
    logger.info(f"\nConfiguration:")
    logger.info(f"  JIRA_URL: {settings.jira_url}")
    logger.info(f"  JIRA_TOKEN: {'***' if settings.jira_token else 'NOT SET'}")
    
    server_params = _server_params()
    logger.info(f"  Command: {server_params.command}")
    logger.info(f"  Args: {server_params.args}")
    logger.info(f"  Env vars: {list(server_params.env.keys()) if server_params.env else 'None'}")
    
    logger.info("\nAttempting to call MCP get_issue tool...")
    
    try:
        # Try to call get_issue
        result = await _call("get_issue", {
            "issue_key": "TEST-1",
            "comment_limit": 5
        })
        
        logger.info(f"\n✓ MCP call succeeded!")
        logger.info(f"Response length: {len(result)} chars")
        logger.info(f"Response preview:\n{result[:500]}")
        
        # Try to parse
        try:
            parsed = _parse_jira_response(result)
            logger.info(f"\n✓ Response parsed successfully!")
            logger.info(f"  issue_key: {parsed.get('issue_key')}")
            logger.info(f"  summary: {parsed.get('summary')[:50] if parsed.get('summary') else 'N/A'}")
            logger.info(f"  description: {parsed.get('description')[:50] if parsed.get('description') else 'N/A'}")
            logger.info(f"  comments: {len(parsed.get('comments', []))} items")
            
            return True
        except Exception as parse_error:
            logger.error(f"✗ Failed to parse response: {parse_error}")
            return False
            
    except Exception as e:
        logger.error(f"✗ MCP call failed: {e}")
        
        # Provide diagnostic advice
        error_str = str(e)
        if "Unknown tool" in error_str:
            logger.error("\n⚠️ DIAGNOSTIC:")
            logger.error("   MCP server is running but doesn't recognize 'get_issue' tool")
            logger.error("   This might mean mcp-atlassian package isn't installed or is incompatible")
            logger.error("\n   Try:")
            logger.error("   1. Stop current MCP server")
            logger.error("   2. Run: uvx --force-reinstall mcp-atlassian")
            logger.error("   3. Restart MCP server")
            
        elif "Connection refused" in error_str or "No such file" in error_str:
            logger.error("\n⚠️ DIAGNOSTIC:")
            logger.error("   MCP server is NOT running")
            logger.error("\n   To start it, open a new terminal and run:")
            logger.error("   1. & C:\\ai-agent-support\\myvenv\\Scripts\\Activate.ps1")
            logger.error("   2. uvx mcp-atlassian")
        else:
            logger.error(f"\n⚠️ Unknown error. Full traceback:")
            import traceback
            traceback.print_exc()
        
        return False


if __name__ == "__main__":
    result = asyncio.run(test_mcp_connection())
    
    logger.info("\n" + "=" * 60)
    if result:
        logger.info("SUCCESS: MCP is working correctly!")
    else:
        logger.info("FAILURE: MCP connection has issues (see above)")
    logger.info("=" * 60)
