
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_FILE = PROJECT_ROOT / "data" / "raw" / "jira_issues.json"
PROCESSED_FILE = (
    PROJECT_ROOT / "data" / "processed" / "jira_issues_processed.json"
)


def extract_text(description):
    """Extract readable text from Jira's Atlassian Document Format."""

    if not description:
        return ""

    if isinstance(description, str):
        return description

    texts = []

    def traverse(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                texts.append(node.get("text", ""))

            for value in node.values():
                if isinstance(value, (dict, list)):
                    traverse(value)

        elif isinstance(node, list):
            for item in node:
                traverse(item)

    traverse(description)
    return " ".join(texts)


def process_issue(issue):
    fields = issue.get("fields", {})

    # Extract parent Epic
    parent = fields.get("parent", {})

    # Extract linked Jira issues
    linked_issues = []

    for link in fields.get("issuelinks", []):
        link_type = link.get("type", {})

        for side in ["inwardIssue", "outwardIssue"]:
            linked_issue = link.get(side)

            if linked_issue:
                relationship = (
                    link_type.get("inward")
                    if side == "inwardIssue"
                    else link_type.get("outward")
                )

                linked_issues.append({
                    "issue_key": linked_issue.get("key"),
                    "summary": linked_issue.get("fields", {}).get("summary"),
                    "relationship": relationship
                })

    return {
        "issue_key": issue.get("key"),
        "summary": fields.get("summary", ""),
        "issue_type": fields.get("issuetype", {}).get("name"),
        "description": extract_text(fields.get("description")),
        "priority": fields.get("priority", {}).get("name"),
        "status": fields.get("status", {}).get("name"),
        "parent_epic": parent.get("key"),
        "linked_issues": linked_issues
    }


def main():
    with open(RAW_FILE, "r", encoding="utf-8") as file:
        raw_issues = json.load(file)

    processed_issues = [
        process_issue(issue) for issue in raw_issues
    ]

    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(PROCESSED_FILE, "w", encoding="utf-8") as file:
        json.dump(processed_issues, file, indent=4, ensure_ascii=False)

    print(f"Processed {len(processed_issues)} Jira issues.")

    for issue in processed_issues:
        print(issue["issue_key"], "-", issue["summary"])

    print(f"\nSaved to: {PROCESSED_FILE}")


if __name__ == "__main__":
    main()
