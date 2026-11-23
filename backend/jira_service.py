
import requests
from requests.auth import HTTPBasicAuth

from config import (
    JIRA_BASE_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN,
    JIRA_PROJECT_KEY
)


JIRA_SEARCH_URL = (
    f"{JIRA_BASE_URL.rstrip('/')}/rest/api/3/search/jql"
)


def get_jira_auth():
    """Create Jira authentication."""

    return HTTPBasicAuth(
        JIRA_EMAIL,
        JIRA_API_TOKEN
    )


def extract_adf_text(description):
    """
    Convert Jira Atlassian Document Format (ADF)
    into readable plain text.
    """

    if not isinstance(description, dict):
        return ""

    extracted_text = []

    def traverse(node):

        if isinstance(node, dict):

            if node.get("type") == "text":
                extracted_text.append(node.get("text", ""))

            for child in node.get("content", []):
                traverse(child)

        elif isinstance(node, list):

            for item in node:
                traverse(item)

    traverse(description)

    return " ".join(extracted_text).strip()


def fetch_all_jira_issues():
    """
    Fetch all issues belonging to the configured Jira project.

    Uses pagination so that larger projects can be retrieved.
    """

    all_issues = []
    next_page_token = None

    headers = {
        "Accept": "application/json"
    }

    fields = [
        "summary",
        "description",
        "issuetype",
        "status",
        "priority",
        "issuelinks",
        "parent",
        "labels",
        "created",
        "updated"
    ]

    while True:

        payload = {
            "jql": f'project = "{JIRA_PROJECT_KEY}" ORDER BY key ASC',
            "maxResults": 100,
            "fields": fields
        }

        if next_page_token:
            payload["nextPageToken"] = next_page_token

        response = requests.post(
            JIRA_SEARCH_URL,
            json=payload,
            headers=headers,
            auth=get_jira_auth(),
            timeout=60
        )

        response.raise_for_status()

        result = response.json()

        issues = result.get("issues", [])
        all_issues.extend(issues)

        next_page_token = result.get("nextPageToken")

        if not next_page_token:
            break

    return all_issues


def process_jira_issues(raw_issues):
    """
    Convert Jira API responses into a consistent
    format for the AI analysis modules.
    """

    processed_issues = []

    for issue in raw_issues:

        fields = issue.get("fields", {})

        parent = fields.get("parent")

        parent_key = (
            parent.get("key")
            if isinstance(parent, dict)
            else None
        )

        linked_issues = []

        for link in fields.get("issuelinks", []):

            linked_issue = (
                link.get("outwardIssue")
                or link.get("inwardIssue")
            )

            if linked_issue:
                linked_issues.append(linked_issue.get("key"))

        processed_issues.append({

            "issue_key": issue.get("key"),

            "summary": fields.get("summary", ""),

            "issue_type": (
                fields.get("issuetype", {}).get("name", "")
            ),

            "description": extract_adf_text(
                fields.get("description")
            ),

            "priority": (
                fields.get("priority", {}).get("name")
                if fields.get("priority")
                else None
            ),

            "status": (
                fields.get("status", {}).get("name")
                if fields.get("status")
                else None
            ),

            "parent_epic": parent_key,

            "linked_issues": linked_issues,

            "labels": fields.get("labels", []),

            "created": fields.get("created"),

            "updated": fields.get("updated")

        })

    return processed_issues


def get_project_issues():
    """
    Main function used by the analysis pipeline.

    Fetches and processes Jira issues in one operation.
    """

    raw_issues = fetch_all_jira_issues()

    processed_issues = process_jira_issues(raw_issues)

    return processed_issues


if __name__ == "__main__":

    try:

        issues = get_project_issues()

        print("Jira issues retrieved successfully!")

        print("Total issues:", len(issues))

        for issue in issues:
            print(
                issue["issue_key"],
                "-",
                issue["summary"]
            )

    except requests.exceptions.RequestException as error:

        print("Jira API error:", error)
