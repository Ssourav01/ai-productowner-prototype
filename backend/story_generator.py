
import json
import re

from llm_service import generate_response


def generate_story_proposals(
    requirements: list[dict],
    jira_issues: list[dict],
    change_analysis: dict,
    missing_stories: list[dict]
) -> dict:

    """
    Generate proposed updates to existing Jira issues
    and candidate new stories.

    This function does not modify Jira.
    All proposals require Product Owner review.
    """

    # ---------------------------------------------------------
    # 1. Validate input
    # ---------------------------------------------------------

    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Requirements must be a non-empty list.")

    if not isinstance(jira_issues, list):
        raise ValueError("Jira issues must be a list.")

    if not isinstance(change_analysis, dict):
        raise ValueError("Change analysis must be a dictionary.")

    if not isinstance(missing_stories, list):
        raise ValueError("Missing stories must be a list.")

    valid_issue_map = {
        issue.get("issue_key"): issue
        for issue in jira_issues
        if issue.get("issue_key")
    }

    valid_issue_keys = set(valid_issue_map.keys())

    valid_requirement_ids = {
        requirement.get("requirement_id")
        for requirement in requirements
        if requirement.get("requirement_id")
    }

    candidate_titles = {
        story.get("title")
        for story in missing_stories
        if story.get("title")
    }

    # ---------------------------------------------------------
    # 2. Identify affected Jira issues
    # ---------------------------------------------------------

    direct_impacts = change_analysis.get("direct_impacts", [])
    indirect_impacts = change_analysis.get("indirect_impacts", [])

    def extract_issue_keys(impacts):

        keys = set()

        for item in impacts:

            if isinstance(item, str):
                keys.add(item)

            elif isinstance(item, dict):
                issue_key = item.get("issue_key")

                if issue_key:
                    keys.add(issue_key)

        return keys

    direct_issue_keys = extract_issue_keys(direct_impacts)
    indirect_issue_keys = extract_issue_keys(indirect_impacts)

    affected_issue_keys = direct_issue_keys | indirect_issue_keys

    unknown_affected_keys = affected_issue_keys - valid_issue_keys

    if unknown_affected_keys:
        raise ValueError(
            f"Impact analysis contains unknown Jira issues: "
            f"{unknown_affected_keys}"
        )

    # ---------------------------------------------------------
    # 3. Prepare prompt
    # ---------------------------------------------------------

    prompt = f"""
You are an experienced Product Owner and Agile Business Analyst.

Generate proposed Jira changes based on the updated requirements
and the impact analysis.

UPDATED REQUIREMENTS:
{json.dumps(requirements, indent=2)}

ALL EXISTING JIRA ISSUES:
{json.dumps(jira_issues, indent=2)}

IMPACT ANALYSIS:
{json.dumps(change_analysis, indent=2)}

CANDIDATE MISSING STORIES:
{json.dumps(missing_stories, indent=2)}

YOUR TASKS:

A. EXISTING JIRA ISSUE UPDATES

Review the directly and indirectly affected issues.

For each affected issue:

1. Check whether an actual change to its summary or description
   is necessary.

2. Do not propose an update merely because an issue was classified
   as affected.

3. Preserve existing functionality, business rules and acceptance
   criteria that are not affected by the change.

4. Do not remove existing information simply to make the
   description shorter.

5. Incorporate the changed requirements without contradicting
   existing valid requirements.

6. Keep the existing issue's purpose and issue type intact.
   Do not convert an Epic into a Story or vice versa.

7. Do not propose technical implementation details that are
   unsupported by the supplied information.

8. Explain precisely what changed and why.

B. NEW JIRA STORIES

Use the supplied candidate missing stories.

For each candidate:

1. Generate a clear, actionable user story.
2. Include relevant acceptance criteria in the proposed description.
3. Preserve the candidate's intended functionality.
4. Do not duplicate existing Jira functionality.
5. Do not invent additional functionality.
6. Link the proposal to its exact source candidate title.

C. GENERAL RULES

- Use only existing Jira issue keys supplied in the input.
- Use only requirement IDs supplied in the input.
- Never invent Jira issue keys.
- Do not propose updates for unaffected issues.
- Do not create new stories unrelated to the supplied candidates.
- Do not create duplicate proposals.
- Do not automatically approve any proposal.
- Do not assume that a dependency automatically needs a new story.
- If no changes are justified, return empty lists.

RETURN ONLY VALID JSON:

{{
    "updated_stories": [
        {{
            "issue_key": "Existing Jira issue key",
            "proposed_summary": "Updated summary",
            "proposed_description": "Complete proposed description preserving unaffected content",
            "reason": "Why this update is necessary",
            "related_requirements": ["REQ-001"],
            "review_status": "REQUIRES_PRODUCT_OWNER_REVIEW"
        }}
    ],
    "new_stories": [
        {{
            "source_candidate_title": "Exact title from candidate missing stories",
            "proposed_summary": "New story summary",
            "proposed_description": "User story with acceptance criteria",
            "reason": "Why this story is needed",
            "related_requirements": ["REQ-001"],
            "review_status": "REQUIRES_PRODUCT_OWNER_REVIEW"
        }}
    ]
}}
"""

    # ---------------------------------------------------------
    # 4. Generate proposals using the local AI model
    # ---------------------------------------------------------

    response_text = generate_response(prompt)

    cleaned_response = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        response_text.strip(),
        flags=re.IGNORECASE
    )

    # ---------------------------------------------------------
    # 5. Parse AI response
    # ---------------------------------------------------------

    try:
        result = json.loads(cleaned_response)

    except json.JSONDecodeError as error:
        raise ValueError(
            "The AI returned invalid JSON for story generation."
        ) from error

    if not isinstance(result, dict):
        raise ValueError("Unexpected AI response format.")

    updated_stories = result.get("updated_stories")
    new_stories = result.get("new_stories")

    if not isinstance(updated_stories, list):
        raise ValueError("Invalid updated_stories list.")

    if not isinstance(new_stories, list):
        raise ValueError("Invalid new_stories list.")

    # ---------------------------------------------------------
    # 6. Validate existing issue update proposals
    # ---------------------------------------------------------

    seen_updated_keys = set()

    for story in updated_stories:

        if not isinstance(story, dict):
            raise ValueError("Invalid existing story proposal.")

        issue_key = story.get("issue_key")

        if issue_key not in valid_issue_keys:
            raise ValueError("AI returned an unknown Jira issue.")

        if issue_key not in affected_issue_keys:
            raise ValueError(
                f"AI proposed updating unaffected issue: {issue_key}"
            )

        if issue_key in seen_updated_keys:
            raise ValueError(
                f"Duplicate update proposal for {issue_key}."
            )

        seen_updated_keys.add(issue_key)

        for field in ["proposed_summary", "proposed_description", "reason"]:

            if not isinstance(story.get(field), str) or not story[field].strip():
                raise ValueError(
                    f"Updated story has an invalid '{field}' field."
                )

        related_requirements = story.get("related_requirements")

        if not isinstance(related_requirements, list):
            raise ValueError("Invalid related_requirements format.")

        if not set(related_requirements).issubset(valid_requirement_ids):
            raise ValueError(
                "Updated story references an unknown requirement."
            )

        if story.get("review_status") != "REQUIRES_PRODUCT_OWNER_REVIEW":
           raise ValueError(
           f"Invalid existing story review status for "
           f"{story.get('issue_key')}. "
           f"Received: {story.get('review_status')!r}"
        )
        
    # ---------------------------------------------------------
    # 7. Validate new story proposals
    # ---------------------------------------------------------

    seen_candidate_titles = set()

    for story in new_stories:

        if not isinstance(story, dict):
            raise ValueError("Invalid new story proposal.")

        source_title = story.get("source_candidate_title")

        if source_title not in candidate_titles:
            raise ValueError(
                "New story does not reference a valid missing story candidate."
            )

        if source_title in seen_candidate_titles:
            raise ValueError(
                "Duplicate proposal for the same missing story candidate."
            )

        seen_candidate_titles.add(source_title)

        for field in ["proposed_summary", "proposed_description", "reason"]:

            if not isinstance(story.get(field), str) or not story[field].strip():
                raise ValueError(
                    f"New story has an invalid '{field}' field."
                )

        related_requirements = story.get("related_requirements")

        if not isinstance(related_requirements, list):
            raise ValueError("Invalid related_requirements format.")

        if not set(related_requirements).issubset(valid_requirement_ids):
            raise ValueError(
                "New story references an unknown requirement."
            )

        if story.get("review_status") != "REQUIRES_PRODUCT_OWNER_REVIEW":
            raise ValueError("Invalid new story review status.")

    # ---------------------------------------------------------
    # 8. Return validated proposals
    # ---------------------------------------------------------

    return {
        "updated_stories": updated_stories,
        "new_stories": new_stories
    }
