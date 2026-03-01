import asyncio
import json
import logging
import os
from typing import TypedDict, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings

logger = logging.getLogger(__name__)


class JiraComment(TypedDict, total=False):
    author: str
    body: str
    created: str


class JiraIssue(TypedDict, total=False):
    issue_key: str
    summary: str
    description: str
    status: str
    assignee: str
    priority: str
    created: str
    updated: str
    comments: list[JiraComment]


def _server_params() -> StdioServerParameters:
    env = {**os.environ, "JIRA_URL": settings.jira_url}
    if settings.jira_token:
        env["JIRA_PERSONAL_TOKEN"] = settings.jira_token
    return StdioServerParameters(command="uvx", args=["mcp-atlassian"], env=env)


class MCPError(Exception):
    """Raised when MCP tool call returns an error."""
    pass


async def _call(tool: str, args: dict) -> str:
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            text = result.content[0].text if result.content else ""
            if result.isError:
                raise MCPError(text)
            return text


async def _list_tools() -> list[str]:
    """List available tools from MCP Atlassian server (for diagnostics)."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [t.name for t in tools.tools]


def list_tools() -> list[str]:
    """List available MCP tools (useful for debugging tool name mismatches)."""
    return asyncio.run(_list_tools())


def _parse_jira_response(raw_response: str) -> JiraIssue:
    """Parse response from MCP Atlassian into structured JiraIssue object.

    Handles both:
    - Raw Jira API JSON (nested under 'fields')
    - Simplified mcp-atlassian format (flat dict with top-level keys)
    - Plain text / markdown responses
    """
    if not raw_response or not raw_response.strip():
        logger.warning("[Jira] Empty response from MCP")
        return {}

    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError:
        # Response is not JSON — likely markdown or plain text from mcp-atlassian
        logger.info("[Jira] Response is not JSON, treating as text content")
        return {
            "issue_key": "",
            "summary": "",
            "description": raw_response.strip(),
        }

    if not isinstance(data, dict):
        logger.warning(f"[Jira] Unexpected response type: {type(data)}")
        return {}

    # Detect format: raw Jira API has 'fields' nesting, mcp-atlassian has flat keys
    if "fields" in data:
        # Raw Jira API format
        fields = data.get("fields", {})
        issue: JiraIssue = {
            "issue_key": data.get("key", ""),
            "summary": fields.get("summary", ""),
            "description": fields.get("description", ""),
            "status": fields.get("status", {}).get("name", "") if isinstance(fields.get("status"), dict) else str(fields.get("status", "")),
            "assignee": fields.get("assignee", {}).get("displayName", "") if isinstance(fields.get("assignee"), dict) else str(fields.get("assignee", "")),
            "priority": fields.get("priority", {}).get("name", "") if isinstance(fields.get("priority"), dict) else str(fields.get("priority", "")),
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
        }
        comments: list[JiraComment] = []
        for comment_data in fields.get("comment", {}).get("comments", []):
            comments.append({
                "author": comment_data.get("author", {}).get("displayName", "Unknown") if isinstance(comment_data.get("author"), dict) else str(comment_data.get("author", "Unknown")),
                "body": comment_data.get("body", ""),
                "created": comment_data.get("created", ""),
            })
        if comments:
            issue["comments"] = comments
    else:
        # Simplified mcp-atlassian format (flat dict)
        issue: JiraIssue = {
            "issue_key": data.get("key", "") or data.get("issue_key", ""),
            "summary": data.get("summary", ""),
            "description": data.get("description", ""),
            "status": data.get("status", "") if isinstance(data.get("status"), str) else str(data.get("status", "")),
            "assignee": data.get("assignee", "") if isinstance(data.get("assignee"), str) else str(data.get("assignee", "")),
            "priority": data.get("priority", "") if isinstance(data.get("priority"), str) else str(data.get("priority", "")),
            "created": data.get("created", ""),
            "updated": data.get("updated", ""),
        }
        # Comments may be a flat list in simplified format
        comments: list[JiraComment] = []
        raw_comments = data.get("comments", [])
        if isinstance(raw_comments, list):
            for c in raw_comments:
                if isinstance(c, dict):
                    comments.append({
                        "author": c.get("author", "Unknown") if isinstance(c.get("author"), str) else str(c.get("author", "Unknown")),
                        "body": c.get("body", "") or c.get("text", ""),
                        "created": c.get("created", ""),
                    })
        if comments:
            issue["comments"] = comments

    logger.debug(f"[Jira] Parsed issue: key={issue.get('issue_key')}, summary={issue.get('summary', '')[:50]}")
    return issue


def get_issue(issue_key: str, comment_limit: int = 10) -> JiraIssue:
    """Fetch issue details from Jira and return structured data with comments."""
    raw_response = asyncio.run(_call("jira_get_issue", {
        "issue_key": issue_key,
        "comment_limit": comment_limit
    }))
    return _parse_jira_response(raw_response)


def add_comment(issue_key: str, comment: str) -> str:
    """Add comment to Jira issue. Returns MCP response text."""
    result = asyncio.run(_call("jira_add_comment", {"issue_key": issue_key, "comment": comment}))
    if result:
        logger.info(f"[Jira] add_comment response: {result[:200]}")
    else:
        logger.warning(f"[Jira] add_comment returned empty response for {issue_key}")
    return result