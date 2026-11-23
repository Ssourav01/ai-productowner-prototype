
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote

from config import (
    JIRA_BASE_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN,
    JIRA_PROJECT_KEY
)


JIRA_API_URL = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/3"


def get_jira_auth():
    """Create Jira authentication."""

    return HTTPBasicAuth(
        JIRA_EMAIL,
        JIRA_API_TOKEN
    )


def convert_to_adf(text: str) -> dict:
    """
    Convert plain text into Jira's Atlassian Document Format.
    """

    paragraphs = []

    for line in text.splitlines():

        paragraphs.append({
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": line
                }
            ] if line else []
        })

    return {
        "type": "doc",
        "version": 1,
        "content": paragraphs
    }


def update_existing_issue(approved_change: dict) -> dict:
    """
    Update an existing Jira issue after explicit approval.
    """

    issue_key = approved_change.get("issue_key")

    if not issue_key:
        raise ValueError("Existing Jira issue key is required.")

    fields = {}

    if approved_change.get("proposed_summary"):
        fields["summary"] = approved_change["proposed_summary"]

    if approved_change.get("proposed_description"):
        fields["description"] = convert_to_adf(
            approved_change["proposed_description"]
        )

    if not fields:
        raise ValueError("No approved fields were supplied.")

    encoded_key = quote(issue_key, safe="-")

    response = requests.put(
        f"{JIRA_API_URL}/issue/{encoded_key}",
        json={"fields": fields},
        auth=get_jira_auth(),
        headers={"Accept": "application/json"},
        timeout=30
    )

    response.raise_for_status()

    return {
        "issue_key": issue_key,
        "status": "updated"
    }


def create_new_issue(approved_story: dict) -> dict:
    """
    Create a new Jira issue after explicit approval.

    The Product Owner must provide the issue type.
    """

    summary = approved_story.get("proposed_summary")
    description = approved_story.get("proposed_description")
    issue_type = approved_story.get("issue_type")

    if not summary or not description or not issue_type:
        raise ValueError(
            "Summary, description and approved issue type are required."
        )

    payload = {
        "fields": {
            "project": {
                "key": JIRA_PROJECT_KEY
            },
            "summary": summary,
            "description": convert_to_adf(description),
            "issuetype": {
                "name": issue_type
            }
        }
    }

    response = requests.post(
        f"{JIRA_API_URL}/issue",
        json=payload,
        auth=get_jira_auth(),
        headers={"Accept": "application/json"},
        timeout=30
    )

    response.raise_for_status()

    created_issue = response.json()

    return {
        "issue_key": created_issue.get("key"),
        "status": "created"
    }


def apply_approved_changes(approval_request: dict) -> dict:
    """
    Apply only explicitly approved Jira changes.
    """

    if approval_request.get("approved") is not True:
        raise PermissionError(
            "Changes cannot be applied without explicit approval."
        )

    approved_changes = approval_request.get("approved_changes")

    if not isinstance(approved_changes, list) or not approved_changes:
        raise ValueError("No approved changes were supplied.")

    results = []

    for change in approved_changes:

        action = change.get("action")

        if action == "update":
            result = update_existing_issue(change)

        elif action == "create":
            result = create_new_issue(change)

        else:
            raise ValueError(
                f"Unsupported Jira operation: {action}"
            )

        results.append(result)

    return {
        "total_changes_applied": len(results),
        "results": results
    }
