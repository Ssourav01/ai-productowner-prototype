
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


# Locate the project root and load environment variables
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

# Jira REST API configuration
SEARCH_URL = f"{JIRA_BASE_URL}/rest/api/3/search/jql"

FIELDS = [
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


def validate_configuration():
    """Check whether all required Jira credentials are available."""

    required = {
        "JIRA_BASE_URL": JIRA_BASE_URL,
        "JIRA_EMAIL": JIRA_EMAIL,
        "JIRA_API_TOKEN": JIRA_API_TOKEN,
        "JIRA_PROJECT_KEY": JIRA_PROJECT_KEY
    }

    missing = [key for key, value in required.items() if not value]

    if missing:
        raise ValueError(
            f"Missing environment variables: {', '.join(missing)}"
        )


def fetch_jira_issues():
    """Fetch all issues belonging to the configured Jira project."""

    validate_configuration()

    all_issues = []
    next_page_token = None

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    while True:
        payload = {
            "jql": f"project = {JIRA_PROJECT_KEY} ORDER BY key ASC",
            "maxResults": 100,
            "fields": FIELDS
        }

        if next_page_token:
            payload["nextPageToken"] = next_page_token

        response = requests.post(
            SEARCH_URL,
            headers=headers,
            auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            json=payload,
            timeout=30
        )

        if not response.ok:
            raise RuntimeError(
                f"Jira API error {response.status_code}: "
                f"{response.text[:1000]}"
            )

        data = response.json()

        issues = data.get("issues", [])
        all_issues.extend(issues)

        next_page_token = data.get("nextPageToken")

        print(f"Retrieved {len(all_issues)} issues so far.")

        if not next_page_token:
            break

    return all_issues


def save_issues(issues):
    """Save retrieved Jira issues as a JSON file."""

    output_dir = PROJECT_ROOT / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "jira_issues.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(issues, file, indent=4, ensure_ascii=False)

    print(f"\nSaved {len(issues)} Jira issues.")
    print(f"File location: {output_file}")


if __name__ == "__main__":
    try:
        print("Connecting to Jira...")

        issues = fetch_jira_issues()

        print("\nJira connection successful!")
        print(f"Total issues retrieved: {len(issues)}")

        for issue in issues:
            print(
                issue["key"],
                "-",
                issue["fields"]["summary"]
            )

        save_issues(issues)

    except Exception as error:
        print(f"\nError: {error}")
