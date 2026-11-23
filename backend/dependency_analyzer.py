
from collections import deque


def get_related_issue_keys(issue: dict) -> set[str]:
    """
    Extract Jira issue references from existing relationships.
    Supports linked issues and parent relationships.
    """

    related_keys = set()

    parent = issue.get("parent_epic")

    if isinstance(parent, str) and parent:
        related_keys.add(parent)

    elif isinstance(parent, dict):
        parent_key = parent.get("key") or parent.get("issue_key")
        if parent_key:
            related_keys.add(parent_key)

    linked_issues = issue.get("linked_issues", [])

    if isinstance(linked_issues, list):
        for link in linked_issues:

            if isinstance(link, str):
                related_keys.add(link)

            elif isinstance(link, dict):
                key = (
                    link.get("issue_key")
                    or link.get("key")
                    or link.get("outwardIssue", {}).get("key")
                    or link.get("inwardIssue", {}).get("key")
                )

                if key:
                    related_keys.add(key)

    return related_keys



def analyze_dependencies(
    change_analysis: dict,
    jira_issues: list[dict]
) -> dict:

    """
    Discover existing Jira relationships connected to affected issues.

    These relationships are candidates for further impact review.
    A Jira link alone does not prove that an issue is affected.
    """

    issues_by_key = {
        issue["issue_key"]: issue
        for issue in jira_issues
        if issue.get("issue_key")
    }

    adjacency = {
        key: get_related_issue_keys(issue)
        for key, issue in issues_by_key.items()
    }

    direct_keys = {
        item["issue_key"]
        for item in change_analysis.get("direct_impacts", [])
    }

    indirect_keys = {
        item["issue_key"]
        for item in change_analysis.get("indirect_impacts", [])
    }

    # Include all issues already classified as affected.
    affected_keys = direct_keys | indirect_keys

    # Explore relationships starting from affected issues.
    visited = set(affected_keys)
    queue = deque(affected_keys)

    relationship_candidates = []

    while queue:

        current_key = queue.popleft()

        for related_key in adjacency.get(current_key, set()):

            # Only consider issues retrieved from this Jira project.
            if related_key not in issues_by_key:
                continue

            if related_key in visited:
                continue

            visited.add(related_key)
            queue.append(related_key)

            relationship_candidates.append({
                "issue_key": related_key,
                "summary": issues_by_key[related_key].get(
                    "summary", ""
                ),
                "issue_type": issues_by_key[related_key].get(
                    "issue_type", ""
                ),
                "relationship_source": current_key,
                "relationship_type": "EXISTING_JIRA_LINK",
                "classification": "REQUIRES_REVIEW",
                "reason": (
                    f"This issue is connected to affected issue "
                    f"{current_key} through an existing Jira relationship. "
                    "The relationship does not establish actual impact. "
                    "Review its functionality before deciding whether "
                    "it requires an update."
                )
            })

    return {
        "direct_issue_keys": sorted(direct_keys),
        "indirect_issue_keys": sorted(indirect_keys),
        "relationship_candidates": relationship_candidates
    }
