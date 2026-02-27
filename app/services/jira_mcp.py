import asyncio
import json
import os
from typing import TypedDict, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings


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


async def _call(tool: str, args: dict) -> str:
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            return result.content[0].text if result.content else ""


def _parse_jira_response(raw_response: str) -> JiraIssue:
    """Parse JSON response from MCP Atlassian into structured JiraIssue object."""
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError as e:
        print(f"[Jira] Failed to parse MCP response as JSON: {e}")
        print(f"[Jira] Raw response: {raw_response[:500]}")
        return {}

    # Extract top-level fields
    issue: JiraIssue = {
        "issue_key": data.get("key", ""),
        "summary": data.get("fields", {}).get("summary", ""),
        "description": data.get("fields", {}).get("description", ""),
        "status": data.get("fields", {}).get("status", {}).get("name", ""),
        "assignee": data.get("fields", {}).get("assignee", {}).get("displayName", ""),
        "priority": data.get("fields", {}).get("priority", {}).get("name", ""),
        "created": data.get("fields", {}).get("created", ""),
        "updated": data.get("fields", {}).get("updated", ""),
    }

    # Parse comments
    comments: list[JiraComment] = []
    for comment_data in data.get("fields", {}).get("comment", {}).get("comments", []):
        comments.append({
            "author": comment_data.get("author", {}).get("displayName", "Unknown"),
            "body": comment_data.get("body", ""),
            "created": comment_data.get("created", ""),
        })

    if comments:
        issue["comments"] = comments

    return issue


def get_issue(issue_key: str, comment_limit: int = 10) -> JiraIssue:
    """Fetch issue details from Jira and return structured data with comments."""
    raw_response = asyncio.run(_call("get_issue", {
        "issue_key": issue_key,
        "comment_limit": comment_limit
    }))
    return _parse_jira_response(raw_response)


def add_comment(issue_key: str, comment: str) -> None:
    """Add comment to Jira issue."""
    asyncio.run(_call("add_comment", {"issue_key": issue_key, "comment": comment}))